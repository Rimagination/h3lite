#!/usr/bin/env python3
"""Native Windows progress monitor for a local MiniMax H3 / ComfyUI run.

The window is deliberately a monitor, not another workflow editor. It reads
the existing H3 Lite run manifest, ComfyUI HTTP state, and optional ComfyUI
WebSocket progress events. Closing it does not interrupt the generation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
import re
from pathlib import Path
import queue
import sys
import threading
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from h3_generate import history_record, resolve_output_paths


DEFAULT_BASE_URL = "http://127.0.0.1:8188"
DEFAULT_POLL_INTERVAL = 2.0
STALE_AUTO_DISCOVERY_SECONDS = 6 * 60 * 60
TERMINAL_STATES = {"success", "failed", "error", "verification_failed"}
ACTIVE_STATES = {"submitting", "queued", "running"}


def progress_fraction(value: Any, maximum: Any) -> float | None:
    """Convert a ComfyUI progress value into a safe 0..1 fraction."""
    try:
        current = float(value)
        limit = float(maximum)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(current) or not math.isfinite(limit) or limit <= 0:
        return None
    return max(0.0, min(1.0, current / limit))


def manifest_client_id(manifest: dict[str, Any]) -> str | None:
    """Return the ComfyUI websocket client id recorded by H3 Lite."""
    value = manifest.get("client_id")
    return str(value) if value else None


def format_seconds(seconds: Any) -> str:
    """Format elapsed/remaining seconds without pretending precision."""
    try:
        value = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        return "--:--"
    hours, remainder = divmod(value, 3600)
    minutes, seconds_value = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds_value:02d}"
    return f"{minutes:02d}:{seconds_value:02d}"


def stage_label(state: str, node: str | None = None) -> str:
    """Turn a low-level state/node name into a user-facing phase."""
    normalized_state = str(state or "").lower()
    normalized_node = str(node or "").lower()
    if normalized_state in {"success", "completed"}:
        return "已完成"
    if normalized_state in {"failed", "error", "verification_failed"}:
        return "生成失败"
    if normalized_state in {"offline", "waiting"}:
        return "等待 ComfyUI"
    if normalized_state in {"queued", "submitting"}:
        return "排队等待"
    if "savevideo" in normalized_node or ("video" in normalized_node and "save" in normalized_node):
        return "正在写入视频"
    if "vae" in normalized_node and ("decode" in normalized_node or "encode" in normalized_node):
        return "正在解码"
    if any(token in normalized_node for token in ("scheduler", "sampler", "ksampler", "diffusion", "noise")):
        return "正在采样"
    if normalized_node.isdigit():
        return "正在采样"
    if any(token in normalized_node for token in ("load", "clip", "text", "checkpoint", "vae")):
        return "正在加载模型"
    if normalized_state in {"running", "executing"}:
        return "正在运行"
    return "准备中"


def estimate_remaining(
    elapsed_seconds: Any,
    progress: float | None,
    expected_seconds: Any,
) -> int | None:
    """Estimate remaining time from live progress, then cached plan timing."""
    try:
        elapsed = max(0.0, float(elapsed_seconds))
    except (TypeError, ValueError):
        return None
    if progress is not None and progress > 0:
        if progress >= 1:
            return 0
        return max(0, int(round(elapsed * (1.0 - progress) / progress)))
    try:
        expected = float(expected_seconds)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(expected):
        return None
    return max(0, int(round(expected - elapsed)))


def apply_progress_event(snapshot: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Apply one ComfyUI WebSocket event to a small serializable snapshot."""
    result = dict(snapshot)
    if not isinstance(event, dict):
        return result
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    event_prompt = data.get("prompt_id")
    target_prompt = result.get("prompt_id")
    if event_prompt and target_prompt and str(event_prompt) != str(target_prompt):
        return result

    event_type = str(event.get("type") or "")
    if event_type == "progress":
        result["state"] = "running"
        result["progress"] = progress_fraction(data.get("value"), data.get("max"))
        result["step"] = data.get("value")
        result["total_steps"] = data.get("max")
        result["node"] = data.get("node")
        result["progress_source"] = "progress"
    elif event_type == "progress_state":
        nodes = data.get("nodes")
        if not isinstance(nodes, dict):
            return result

        node_items = [item for item in nodes.values() if isinstance(item, dict)]
        finished_nodes = sum(1 for item in node_items if str(item.get("state")) == "finished")
        running_nodes = [item for item in node_items if str(item.get("state")) == "running"]
        active = running_nodes[0] if running_nodes else None
        active_fraction = progress_fraction(active.get("value"), active.get("max")) if active else None
        total_nodes = len(node_items)

        if total_nodes:
            completed_units = finished_nodes + (active_fraction or 0.0)
            result["progress"] = max(0.0, min(1.0, completed_units / total_nodes))
            result["finished_nodes"] = finished_nodes
            result["total_nodes"] = total_nodes
        if active:
            result["step"] = active.get("value")
            result["total_steps"] = active.get("max")
            result["node"] = active.get("display_node_id") or active.get("node_id")
            result["state"] = "running"
        elif total_nodes and finished_nodes >= total_nodes:
            result["progress"] = 1.0
        result["progress_source"] = "progress_state"
    elif event_type == "execution_start":
        result["state"] = "running"
    elif event_type == "executing":
        result["state"] = "running"
        result["node"] = data.get("node")
        if data.get("node") is None:
            result["state"] = "success"
            result["progress"] = 1.0
    elif event_type == "execution_error":
        result["state"] = "failed"
        result["error"] = data.get("exception_message") or data.get("error") or "ComfyUI execution error"
    elif event_type == "execution_success":
        result["state"] = "success"
        result["progress"] = 1.0
    return result


def default_run_root(comfyui: Path) -> Path:
    return comfyui / "user" / "h3lite_runs"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _safe_http_json(base_url: str, path: str, timeout: float = 2.5) -> Any:
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _manifest_activity_time(path: Path, manifest: dict[str, Any]) -> float:
    timestamps = [path.stat().st_mtime]
    for key in ("last_checked_at_utc", "updated_at_utc", "queued_at_utc", "created_at_utc"):
        parsed = _parse_timestamp(manifest.get(key))
        if parsed:
            timestamps.append(parsed.timestamp())
    return max(timestamps)


def _find_manifest(
    run_root: Path,
    prompt_id: str | None = None,
    *,
    now: float | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    now = time.time() if now is None else now
    candidates: list[tuple[float, Path, dict[str, Any]]] = []
    for path in run_root.rglob("manifest.json") if run_root.is_dir() else []:
        manifest = _load_json(path)
        if not manifest:
            continue
        if prompt_id and str(manifest.get("prompt_id")) != str(prompt_id):
            continue
        modified = _manifest_activity_time(path, manifest)
        candidates.append((modified, path, manifest))
    if prompt_id:
        if not candidates:
            return None, {}
        _, path, manifest = max(candidates, key=lambda item: item[0])
        return path, manifest
    active = [
        item
        for item in candidates
        if str(item[2].get("state", "")) in ACTIVE_STATES
        and now - item[0] <= STALE_AUTO_DISCOVERY_SECONDS
    ]
    if active:
        _, path, manifest = max(active, key=lambda item: item[0])
        return path, manifest
    return None, {}


def _history_error(record: dict[str, Any] | None) -> str | None:
    if not isinstance(record, dict):
        return None
    status = record.get("status") if isinstance(record.get("status"), dict) else {}
    status_name = str(status.get("status_str") or "").lower()
    if status_name in {"error", "failed"}:
        return str(status.get("status_str"))
    for key in ("exception_message", "error"):
        if record.get(key):
            return str(record[key])
    messages = status.get("messages", [])
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, list) and len(message) > 1 and isinstance(message[1], dict):
                payload = message[1]
                if message[0] in {"execution_error", "execution_failed"}:
                    return str(payload.get("exception_message") or payload.get("error") or message[0])
    return None


def _queue_state(queue_payload: Any, prompt_id: str | None) -> tuple[str | None, int | None]:
    if not isinstance(queue_payload, dict):
        return None, None
    running = queue_payload.get("queue_running")
    pending = queue_payload.get("queue_pending")
    running = running if isinstance(running, list) else []
    pending = pending if isinstance(pending, list) else []
    if prompt_id:
        for item in running:
            if isinstance(item, list) and len(item) > 1 and str(item[1]) == str(prompt_id):
                return "running", len(running) + len(pending)
        for item in pending:
            if isinstance(item, list) and len(item) > 1 and str(item[1]) == str(prompt_id):
                return "queued", len(running) + len(pending)
    return None, len(running) + len(pending)


def _read_expected_seconds(run_root: Path) -> float | None:
    plan = _load_json(run_root / "_environment" / "plan.json")
    estimate = plan.get("estimate") if isinstance(plan.get("estimate"), dict) else {}
    for key in ("upper_seconds", "expected_seconds", "median_seconds"):
        try:
            value = float(estimate[key])
            if value > 0:
                return value
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _log_sampling_progress(comfyui: Path, expected_total: Any = None) -> tuple[int, int] | None:
    """Parse the latest sampling-step line from ComfyUI's text log.

    H3 custom samplers do not emit ComfyUI WebSocket ``progress`` events, so the
    monitor would otherwise sit on a static "waiting for progress" state. The
    tqdm-style ``N/M [elapsed<remaining, s/it]`` lines that ComfyUI writes to
    its log file are used as a fallback so the bar still reflects real sampling.
    """
    log_path = comfyui / "comfyui.log"
    if not log_path.is_file():
        alt = comfyui / "user" / "comfyui.log"
        log_path = alt if alt.is_file() else log_path
    if not log_path.is_file():
        return None
    try:
        with open(log_path, "rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 40000))
            tail = handle.read().decode("utf-8", "replace")
    except OSError:
        return None
    matches = re.findall(r"(\d+)/(\d+)\s+\[", tail)
    if not matches:
        return None
    try:
        expected_total = int(expected_total) if expected_total else None
    except (TypeError, ValueError):
        expected_total = None
    if expected_total:
        for current, total in reversed(matches):
            if int(total) == expected_total:
                return int(current), int(total)
    current, total = matches[-1]
    return int(current), int(total)


def _resource_snapshot(base_url: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        from h3_doctor import nvidia_gpus, system_memory

        gpus = nvidia_gpus()
        if gpus and isinstance(gpus[0], dict):
            gpu = gpus[0]
            result["gpu_name"] = gpu.get("name")
            result["vram_total_gb"] = gpu.get("vram_total_gb")
            result["vram_free_gb"] = gpu.get("vram_free_gb")
    except Exception as exc:  # resource display must never break monitoring
        result["gpu_error"] = str(exc)
    try:
        memory = system_memory()
        if isinstance(memory, dict):
            result.update(
                {
                    "ram_total_gb": memory.get("total_gb"),
                    "ram_available_gb": memory.get("available_gb"),
                    "pagefile_total_gb": memory.get("page_file_total_gb"),
                    "pagefile_available_gb": memory.get("page_file_available_gb"),
                }
            )
    except Exception as exc:
        result["memory_error"] = str(exc)
    try:
        stats = _safe_http_json(base_url, "/system_stats")
        result["comfyui_online"] = isinstance(stats, dict)
    except Exception:
        result["comfyui_online"] = False
    return result


def _output_paths(manifest: dict[str, Any], record: dict[str, Any] | None) -> list[str]:
    paths: list[Path] = []
    output_dir = Path(str(manifest["output_dir"])) if manifest.get("output_dir") else None
    if record and output_dir:
        try:
            paths.extend(resolve_output_paths(record, output_dir))
        except (OSError, TypeError, ValueError):
            pass
    value = manifest.get("outputs")
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("path"):
                paths.append(Path(str(item["path"])))
            elif isinstance(item, str):
                paths.append(Path(item))
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def build_snapshot(
    manifest: dict[str, Any],
    record: dict[str, Any] | None,
    queue_state: str | None,
    queue_remaining: int | None,
    live_progress: dict[str, Any],
    resources: dict[str, Any],
    expected_seconds: float | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Merge manifest, HTTP history, queue, WebSocket, and resource data."""
    now = now or datetime.now(timezone.utc)
    error = _history_error(record)
    status = record.get("status") if isinstance(record, dict) and isinstance(record.get("status"), dict) else {}
    completed = bool(status.get("completed") is True or (record and record.get("outputs")))
    if error:
        state = "failed"
    elif completed:
        state = "success"
    elif live_progress.get("state") in {"running", "success", "failed"}:
        state = str(live_progress["state"])
    elif queue_state:
        state = queue_state
    else:
        state = str(manifest.get("state") or "waiting")
        if state == "submitting":
            state = "queued"

    elapsed_basis = "timestamp"
    elapsed = None
    try:
        manifest_elapsed = float(manifest.get("elapsed_seconds"))
        if math.isfinite(manifest_elapsed) and manifest_elapsed >= 0:
            elapsed = manifest_elapsed
            elapsed_basis = "manifest"
    except (TypeError, ValueError):
        pass
    if elapsed is None:
        started = _parse_timestamp(manifest.get("queued_at_utc") or manifest.get("created_at_utc"))
        elapsed = max(0.0, (now - started).total_seconds()) if started else None
    progress = live_progress.get("progress")
    if state == "success":
        progress = 1.0
    progress_source = live_progress.get("progress_source")
    if elapsed is None:
        eta = None
    elif state == "success":
        eta = 0
    elif progress_source == "progress_state":
        # Node counts are structural, not time-weighted. A single H3 node can
        # dominate the runtime, so never turn 4/5 nodes into a 20% ETA.
        eta = estimate_remaining(elapsed, None, expected_seconds)
    else:
        eta = estimate_remaining(elapsed, progress, expected_seconds)
    node = live_progress.get("node")
    progress_basis = {
        "progress_state": "node_completion",
        "progress": "sampling_steps",
    }.get(str(progress_source))
    eta_basis = "live_progress" if progress_source == "progress" else "empirical"
    return {
        "state": state,
        "stage": stage_label(state, node),
        "progress": progress,
        "step": live_progress.get("step"),
        "total_steps": live_progress.get("total_steps"),
        "node": node,
        "progress_source": live_progress.get("progress_source"),
        "progress_basis": progress_basis,
        "eta_basis": eta_basis,
        "finished_nodes": live_progress.get("finished_nodes"),
        "total_nodes": live_progress.get("total_nodes"),
        "node_elapsed_seconds": live_progress.get("node_elapsed_seconds"),
        "prompt_id": manifest.get("prompt_id") or live_progress.get("prompt_id"),
        "elapsed_seconds": elapsed,
        "elapsed_basis": elapsed_basis,
        "eta_seconds": eta,
        "queue_remaining": queue_remaining,
        "error": error or live_progress.get("error"),
        "outputs": _output_paths(manifest, record) if state == "success" else [],
        "resources": resources,
        "manifest_path": manifest.get("manifest_path"),
        "prompt": manifest.get("prompt_path"),
    }


class MonitorBackend:
    def __init__(
        self,
        comfyui: Path,
        base_url: str = DEFAULT_BASE_URL,
        prompt_id: str | None = None,
        run_root: Path | None = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        use_websocket: bool = True,
    ) -> None:
        self.comfyui = comfyui
        self.base_url = base_url
        self.prompt_id = prompt_id
        self.run_root = run_root or default_run_root(comfyui)
        self.poll_interval = max(0.5, poll_interval)
        self.use_websocket = use_websocket
        self.stop_event = threading.Event()
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.progress: dict[str, Any] = {"prompt_id": prompt_id, "progress": None}
        self.client_id: str | None = None
        self.current_node: str | None = None
        self.node_started_at: float | None = None
        self.lock = threading.Lock()
        self.threads: list[threading.Thread] = []

    def start(self) -> None:
        poller = threading.Thread(target=self._poll_loop, name="h3-monitor-poll", daemon=True)
        self.threads.append(poller)
        poller.start()
        if self.use_websocket:
            websocket_thread = threading.Thread(target=self._websocket_loop, name="h3-monitor-ws", daemon=True)
            self.threads.append(websocket_thread)
            websocket_thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def _poll_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.events.put(self.read_snapshot())
            except Exception as exc:
                self.events.put(
                    {
                        "state": "offline",
                        "stage": "等待 ComfyUI",
                        "progress": None,
                        "error": str(exc),
                        "resources": {},
                    }
                )
            self.stop_event.wait(self.poll_interval)

    def read_snapshot(self) -> dict[str, Any]:
        manifest_path, manifest = _find_manifest(self.run_root, self.prompt_id)
        if manifest.get("prompt_id") and not self.prompt_id:
            self.prompt_id = str(manifest["prompt_id"])
        manifest_client = manifest_client_id(manifest)
        if manifest_client:
            with self.lock:
                self.client_id = manifest_client
        with self.lock:
            live_progress = dict(self.progress)
            live_progress["prompt_id"] = self.prompt_id
            if self.current_node and self.node_started_at is not None:
                live_progress["node_elapsed_seconds"] = max(0.0, time.monotonic() - self.node_started_at)
        # H3 samplers emit no WebSocket progress events; fall back to the log.
        if live_progress.get("progress") is None:
            log_prog = _log_sampling_progress(self.comfyui, manifest.get("steps"))
            if log_prog:
                current, total = log_prog
                live_progress["progress"] = max(0.0, min(1.0, current / total)) if total else None
                live_progress["step"] = current
                live_progress["total_steps"] = total
                live_progress["progress_source"] = "log"

        record = None
        queue_state = None
        queue_remaining = None
        connection_error = None
        if self.prompt_id:
            try:
                history = _safe_http_json(self.base_url, f"/history/{urllib.parse.quote(self.prompt_id)}")
                record = history_record(history, self.prompt_id)
            except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
                connection_error = str(exc)
            try:
                queue_payload = _safe_http_json(self.base_url, "/queue")
                queue_state, queue_remaining = _queue_state(queue_payload, self.prompt_id)
            except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
                connection_error = connection_error or str(exc)
        resources = _resource_snapshot(self.base_url)
        if not manifest:
            if connection_error:
                return {
                    "state": "offline",
                    "stage": "等待 ComfyUI",
                    "progress": None,
                    "error": connection_error,
                    "resources": resources,
                    "prompt_id": self.prompt_id,
                }
            return {
                "state": "waiting",
                "stage": "等待 H3 任务",
                "progress": None,
                "error": None,
                "resources": resources,
                "prompt_id": self.prompt_id,
            }
        snapshot = build_snapshot(
            manifest,
            record,
            queue_state,
            queue_remaining,
            live_progress,
            resources,
            _read_expected_seconds(self.run_root),
        )
        snapshot["manifest_path"] = str(manifest_path) if manifest_path else snapshot.get("manifest_path")
        return snapshot

    def _websocket_loop(self) -> None:
        try:
            import websocket  # type: ignore
        except ImportError:
            return
        websocket_url = self.base_url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + "/ws"
        while not self.stop_event.is_set():
            with self.lock:
                client_id = self.client_id
            if not client_id:
                self.stop_event.wait(0.5)
                continue
            url = f"{websocket_url}?clientId={urllib.parse.quote(client_id, safe='')}"
            socket = None
            try:
                socket = websocket.create_connection(url, timeout=3, http_proxy_host=None)
                socket.settimeout(1)
                while not self.stop_event.is_set():
                    with self.lock:
                        if self.client_id != client_id:
                            break
                    try:
                        message = socket.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not message:
                        break
                    if isinstance(message, bytes):
                        continue
                    try:
                        event = json.loads(message)
                    except (TypeError, ValueError):
                        continue
                    with self.lock:
                        event_data = event.get("data") if isinstance(event.get("data"), dict) else {}
                        target_prompt = self.prompt_id
                        event_prompt = event_data.get("prompt_id")
                        if not target_prompt or (event_prompt and str(event_prompt) != str(target_prompt)):
                            continue
                        updated = apply_progress_event(self.progress, event)
                        node = updated.get("node")
                        if node and node != self.current_node:
                            self.current_node = str(node)
                            self.node_started_at = time.monotonic()
                        if self.current_node and self.node_started_at is not None:
                            updated["node_elapsed_seconds"] = max(0.0, time.monotonic() - self.node_started_at)
                        self.progress = updated
            except Exception:
                self.stop_event.wait(2.0)
            finally:
                if socket is not None:
                    try:
                        socket.close()
                    except Exception:
                        pass


def _set_windows_dpi_awareness() -> None:
    """Keep Tk text vector-sharp instead of letting Windows bitmap-scale it."""
    if os.name != "nt":
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        set_context = getattr(user32, "SetProcessDpiAwarenessContext", None)
        if set_context is not None:
            set_context.argtypes = [ctypes.c_void_p]
            set_context.restype = ctypes.c_bool
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            if set_context(ctypes.c_void_p(-4)):
                return
    except Exception:
        pass
    try:
        import ctypes

        # PROCESS_PER_MONITOR_DPI_AWARE, supported by Windows 8.1+.
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(ctypes.c_int(2))
        return
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _apply_windows_modern_effects(root: Any) -> None:
    """Ask Windows for rounded corners and a backdrop, with safe fallbacks."""
    if os.name != "nt":
        return
    try:
        import ctypes

        root.update_idletasks()
        hwnd = ctypes.c_void_p(root.winfo_id())
        dwmapi = ctypes.windll.dwmapi
        corner_preference = ctypes.c_int(2)  # DWMWCP_ROUND
        dwmapi.DwmSetWindowAttribute(hwnd, ctypes.c_int(33), ctypes.byref(corner_preference), ctypes.sizeof(corner_preference))
        backdrop = ctypes.c_int(3)  # DWMSBT_TRANSIENTWINDOW / acrylic-like backdrop
        dwmapi.DwmSetWindowAttribute(hwnd, ctypes.c_int(38), ctypes.byref(backdrop), ctypes.sizeof(backdrop))
    except Exception:
        pass


def _round_windows_widget(widget: Any, radius: int = 16) -> None:
    """Clip a Tk child window to a rounded native Windows region."""
    if os.name != "nt":
        return
    try:
        import ctypes

        gdi32 = ctypes.windll.gdi32
        user32 = ctypes.windll.user32
        gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
        user32.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        user32.SetWindowRgn.restype = ctypes.c_int
        gdi32.DeleteObject.argtypes = [ctypes.c_void_p]

        def apply_region(_event: Any = None) -> None:
            try:
                width = int(widget.winfo_width())
                height = int(widget.winfo_height())
                if width <= 1 or height <= 1:
                    return
                region = gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius, radius)
                if not user32.SetWindowRgn(ctypes.c_void_p(widget.winfo_id()), region, True):
                    gdi32.DeleteObject(region)
            except Exception:
                pass

        widget.bind("<Configure>", apply_region, add="+")
        widget.after_idle(apply_region)
    except Exception:
        pass
class MonitorWindow:
    """Modern native monitor; the progress bar only moves on real progress data."""

    BG = "#EAF0F7"
    CARD = "#F9FBFF"
    BORDER = "#D8E2EF"
    TEXT = "#1F2937"
    MUTED = "#64748B"
    TRACK = "#DCE6F2"
    ACCENT = "#4F7CFF"
    ACCENT_DARK = "#315EEA"
    SUCCESS = "#138A69"
    WARNING = "#B96B00"
    ERROR = "#C24145"

    def __init__(self, backend: MonitorBackend, *, topmost: bool = False) -> None:
        _set_windows_dpi_awareness()
        import tkinter as tk

        self.tk = tk
        self.backend = backend
        self.root = tk.Tk()
        self.root.title("MiniMax H3 Lite 进度")
        self.root.geometry("760x620")
        self.root.minsize(620, 470)
        self.root.configure(bg=self.BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        if topmost:
            self.root.attributes("-topmost", True)
        _apply_windows_modern_effects(self.root)

        self.title_var = tk.StringVar(value="MiniMax H3 Lite")
        self.subtitle_var = tk.StringVar(value="本地 ComfyUI · 原生进度监控")
        self.state_var = tk.StringVar(value="等待任务")
        self.phase_var = tk.StringVar(value="等待 H3 任务")
        self.percent_var = tk.StringVar(value="--")
        self.progress_hint_var = tk.StringVar(value="等待 ComfyUI 上报可量化进度")
        self.node_var = tk.StringVar(value="当前节点：--")
        self.step_var = tk.StringVar(value="节点步骤：--")
        self.elapsed_var = tk.StringVar(value="--:--")
        self.eta_var = tk.StringVar(value="--:--")
        self.vram_var = tk.StringVar(value="--")
        self.ram_var = tk.StringVar(value="--")
        self.pagefile_var = tk.StringVar(value="页面文件：--")
        self.output_var = tk.StringVar(value="生成完成后显示输出文件")
        self.detail_var = tk.StringVar(value="")
        self.latest: dict[str, Any] = {}
        self.progress_fraction: float | None = None
        self.node_progress: tuple[int, int, float | None] | None = None

        self._build_ui()
        self.backend.start()
        self.root.after(300, self.refresh)

    def _card(self, parent: Any, *, padx: int = 16, pady: int = 14) -> Any:
        card = self.tk.Frame(
            parent,
            bg=self.CARD,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            highlightthickness=1,
            bd=0,
            padx=padx,
            pady=pady,
        )
        _round_windows_widget(card, radius=18)
        return card

    def _button(self, parent: Any, text: str, command: Any, *, primary: bool = False) -> Any:
        button = self.tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 9, "bold" if primary else "normal"),
            fg="#FFFFFF" if primary else self.TEXT,
            bg=self.ACCENT if primary else self.CARD,
            activeforeground="#FFFFFF" if primary else self.TEXT,
            activebackground=self.ACCENT_DARK if primary else "#EEF3FA",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
        )
        _round_windows_widget(button, radius=12)
        return button

    def _build_ui(self) -> None:
        tk = self.tk
        from tkinter import ttk

        scroll_host = tk.Frame(self.root, bg=self.BG)
        scroll_host.pack(fill="both", expand=True)
        canvas = tk.Canvas(scroll_host, bg=self.BG, highlightthickness=0, bd=0)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "H3.Vertical.TScrollbar",
            background="#8EA8D2",
            troughcolor="#D7E2F0",
            bordercolor="#D7E2F0",
            darkcolor="#8EA8D2",
            lightcolor="#B8CBE7",
            arrowcolor="#365B99",
        )
        scrollbar = ttk.Scrollbar(
            scroll_host,
            orient="vertical",
            command=canvas.yview,
            style="H3.Vertical.TScrollbar",
        )
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)

        outer = tk.Frame(canvas, bg=self.BG, padx=22, pady=18)
        window_id = canvas.create_window((0, 0), window=outer, anchor="nw")
        self._scroll_canvas = canvas

        def update_scroll_region(_event: Any = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event: Any) -> None:
            canvas.itemconfigure(window_id, width=max(1, event.width))

        def scroll_with_wheel(event: Any) -> None:
            delta = getattr(event, "delta", 0)
            if delta:
                canvas.yview_scroll(-int(delta / 120), "units")

        outer.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        self.root.bind_all("<MouseWheel>", scroll_with_wheel, add="+")
        self.root.after_idle(update_scroll_region)

        header = tk.Frame(outer, bg=self.BG)
        header.pack(fill="x")
        heading = tk.Frame(header, bg=self.BG)
        heading.pack(side="left", fill="x", expand=True)
        tk.Label(heading, textvariable=self.title_var, bg=self.BG, fg=self.TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w")
        tk.Label(heading, textvariable=self.subtitle_var, bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        self.state_pill = tk.Label(
            header,
            textvariable=self.state_var,
            bg="#E3EAF4",
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
            padx=13,
            pady=6,
        )
        _round_windows_widget(self.state_pill, radius=14)
        self.state_pill.pack(side="right", anchor="n", pady=2)

        progress_card = self._card(outer, padx=18, pady=16)
        progress_card.pack(fill="x", pady=(18, 10))
        progress_top = tk.Frame(progress_card, bg=self.CARD)
        progress_top.pack(fill="x")
        tk.Label(progress_top, textvariable=self.phase_var, bg=self.CARD, fg=self.TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(progress_top, textvariable=self.percent_var, bg=self.CARD, fg=self.ACCENT_DARK, font=("Segoe UI", 20, "bold")).pack(side="right")
        self.progress_canvas = tk.Canvas(progress_card, height=20, bg=self.CARD, highlightthickness=0, bd=0)
        self.progress_canvas.pack(fill="x", pady=(14, 8))
        self.progress_canvas.bind("<Configure>", lambda _event: self._draw_progress())
        tk.Label(progress_card, textvariable=self.progress_hint_var, bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        node_row = tk.Frame(progress_card, bg=self.CARD)
        node_row.pack(fill="x", pady=(12, 0))
        tk.Label(node_row, textvariable=self.node_var, bg=self.CARD, fg=self.TEXT, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(node_row, textvariable=self.step_var, bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 9)).pack(side="right")

        stats = tk.Frame(outer, bg=self.BG)
        stats.pack(fill="x", pady=(0, 10))
        for index in range(2):
            stats.columnconfigure(index, weight=1)
        self._stat_card(stats, 0, 0, "已用时间", self.elapsed_var)
        self._stat_card(stats, 0, 1, "预计剩余", self.eta_var)
        self._stat_card(stats, 1, 0, "显存占用", self.vram_var)
        self._stat_card(stats, 1, 1, "内存占用", self.ram_var)

        resource_card = self._card(outer, padx=14, pady=9)
        resource_card.pack(fill="x", pady=(0, 10))
        tk.Label(resource_card, textvariable=self.pagefile_var, bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w")

        output_card = self._card(outer, padx=14, pady=11)
        output_card.pack(fill="x", pady=(0, 12))
        tk.Label(output_card, text="输出", bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(output_card, textvariable=self.output_var, bg=self.CARD, fg=self.TEXT, font=("Segoe UI", 9), anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(4, 0))
        tk.Label(output_card, textvariable=self.detail_var, bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 8), anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(5, 0))

        buttons = tk.Frame(outer, bg=self.BG)
        buttons.pack(fill="x")
        self._button(buttons, "打开输出文件夹", self.open_output_folder, primary=True).pack(side="left")
        self._button(buttons, "复制输出路径", self.copy_output).pack(side="left", padx=(8, 0))
        self._button(buttons, "关闭监控", self.close).pack(side="right")

    def _stat_card(self, parent: Any, row: int, column: int, label: str, variable: Any) -> None:
        card = self._card(parent, padx=11, pady=10)
        card.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 5, 0 if column == 1 else 5),
            pady=(0 if row == 0 else 8, 0),
        )
        self.tk.Label(card, text=label, bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 8)).pack(anchor="w")
        self.tk.Label(card, textvariable=variable, bg=self.CARD, fg=self.TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 0))

    def _draw_progress(self) -> None:
        canvas = self.progress_canvas
        width = max(1, canvas.winfo_width())
        height = max(12, int(canvas.winfo_height()))
        radius = height / 2
        canvas.delete("all")

        def rounded_rect(x1: float, y1: float, x2: float, y2: float, fill: str) -> None:
            r = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
            canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill)
            canvas.create_oval(x1, y1, x1 + 2 * r, y2, fill=fill, outline=fill)
            canvas.create_oval(x2 - 2 * r, y1, x2, y2, fill=fill, outline=fill)

        if self.node_progress:
            finished, total, active_fraction = self.node_progress
            total = max(1, total)
            gap = 4.0
            segment_width = max(1.0, (width - gap * (total - 1)) / total)
            for index in range(total):
                x1 = index * (segment_width + gap)
                x2 = x1 + segment_width
                rounded_rect(x1, 2, x2, height - 2, self.TRACK)
                if index < finished:
                    rounded_rect(x1, 2, x2, height - 2, self.ACCENT)
                elif index == finished and isinstance(active_fraction, (int, float)) and active_fraction > 0:
                    rounded_rect(x1, 2, x1 + segment_width * min(1.0, active_fraction), height - 2, self.ACCENT)
            return

        rounded_rect(0, 2, width, height - 2, self.TRACK)
        fraction = self.progress_fraction
        if isinstance(fraction, (int, float)) and fraction > 0:
            rounded_rect(0, 2, max(height, width * float(fraction)), height - 2, self.ACCENT)

    def refresh(self) -> None:
        latest = None
        while True:
            try:
                latest = self.backend.events.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            self.latest = latest
            self.render(latest)
        try:
            if self.root.winfo_exists():
                self.root.after(500, self.refresh)
        except Exception:
            return

    def render(self, snapshot: dict[str, Any]) -> None:
        state = str(snapshot.get("state") or "waiting")
        prompt_id = str(snapshot.get("prompt_id") or "")
        self.title_var.set(f"MiniMax H3 Lite  ·  {prompt_id[:12]}" if prompt_id else "MiniMax H3 Lite")
        state_labels = {
            "waiting": "等待任务",
            "offline": "ComfyUI 未连接",
            "queued": "排队中",
            "running": "生成中",
            "success": "已完成",
            "failed": "失败",
        }
        state_colors = {
            "waiting": ("#E3EAF4", self.MUTED),
            "offline": ("#FDECEC", self.ERROR),
            "queued": ("#FFF4DB", self.WARNING),
            "running": ("#E2EBFF", self.ACCENT_DARK),
            "success": ("#DDF6EC", self.SUCCESS),
            "failed": ("#FDECEC", self.ERROR),
        }
        self.state_var.set(state_labels.get(state, state))
        pill_bg, pill_fg = state_colors.get(state, ("#E3EAF4", self.MUTED))
        self.state_pill.configure(bg=pill_bg, fg=pill_fg)
        self.phase_var.set(str(snapshot.get("stage") or stage_label(state, snapshot.get("node"))))

        node = snapshot.get("node")
        node_text = f"当前节点：{node}" if node not in (None, "") else "当前节点：等待 ComfyUI"
        node_elapsed = snapshot.get("node_elapsed_seconds")
        if node not in (None, "") and isinstance(node_elapsed, (int, float)):
            node_text += f" · 监测时长 {format_seconds(node_elapsed)}"
        self.node_var.set(node_text)
        step = snapshot.get("step")
        total = snapshot.get("total_steps")
        source = snapshot.get("progress_source")
        finished_nodes = snapshot.get("finished_nodes")
        total_nodes = snapshot.get("total_nodes")
        is_node_progress = source == "progress_state" and isinstance(finished_nodes, int) and isinstance(total_nodes, int)
        if is_node_progress and isinstance(step, (int, float)) and isinstance(total, (int, float)):
            self.step_var.set(f"当前节点步骤：{step:g} / {total:g}")
        elif isinstance(step, (int, float)) and isinstance(total, (int, float)):
            self.step_var.set(f"节点步骤：{step:g} / {total:g}")
        else:
            self.step_var.set(f"工作流节点：{finished_nodes} / {total_nodes}" if isinstance(finished_nodes, int) and isinstance(total_nodes, int) else "节点步骤：等待进度事件")

        fraction = snapshot.get("progress")
        self.progress_fraction = float(fraction) if isinstance(fraction, (int, float)) else None
        if is_node_progress:
            active_fraction = progress_fraction(step, total) if isinstance(step, (int, float)) and isinstance(total, (int, float)) else None
            self.node_progress = (finished_nodes, total_nodes, active_fraction)
            self.percent_var.set(f"{finished_nodes}/{total_nodes}")
            self.progress_hint_var.set("工作流节点完成度 · 不等于耗时百分比")
        elif self.progress_fraction is not None:
            self.node_progress = None
            self.progress_fraction = max(0.0, min(1.0, self.progress_fraction))
            self.percent_var.set(f"{self.progress_fraction * 100:.0f}%")
            if source == "log":
                self.progress_hint_var.set("采样进度（来自 ComfyUI 日志）")
            else:
                self.progress_hint_var.set("ComfyUI 原生步骤进度")
        else:
            self.node_progress = None
            self.percent_var.set("--")
            self.progress_hint_var.set("ComfyUI 尚未上报可量化进度（当前显示为静态等待状态）")
        self._draw_progress()

        self.elapsed_var.set(format_seconds(snapshot.get("elapsed_seconds")))
        eta_text = format_seconds(snapshot.get("eta_seconds"))
        self.eta_var.set(f"经验 {eta_text}" if is_node_progress and state != "success" else eta_text)
        resources = snapshot.get("resources") if isinstance(snapshot.get("resources"), dict) else {}
        vram_total = resources.get("vram_total_gb")
        vram_free = resources.get("vram_free_gb")
        vram_text = "--"
        if isinstance(vram_total, (int, float)) and isinstance(vram_free, (int, float)):
            vram_text = f"{float(vram_total) - float(vram_free):.1f} / {float(vram_total):.1f} GB"
        ram_text = "--"
        if isinstance(resources.get("ram_total_gb"), (int, float)) and isinstance(resources.get("ram_available_gb"), (int, float)):
            ram_text = f"{float(resources['ram_total_gb']) - float(resources['ram_available_gb']):.1f} / {float(resources['ram_total_gb']):.1f} GB"
        page_text = "--"
        if isinstance(resources.get("pagefile_total_gb"), (int, float)) and isinstance(resources.get("pagefile_available_gb"), (int, float)):
            page_text = f"{float(resources['pagefile_total_gb']) - float(resources['pagefile_available_gb']):.1f} / {float(resources['pagefile_total_gb']):.1f} GB"
        self.vram_var.set(vram_text)
        self.ram_var.set(ram_text)
        self.pagefile_var.set(f"页面文件占用：{page_text}")

        outputs = snapshot.get("outputs") if isinstance(snapshot.get("outputs"), list) else []
        self.output_var.set(str(outputs[0]) if outputs else "生成完成后显示输出文件")
        detail = snapshot.get("error") or snapshot.get("manifest_path") or ""
        self.detail_var.set(str(detail))

    def _first_output(self) -> Path | None:
        outputs = self.latest.get("outputs") if isinstance(self.latest.get("outputs"), list) else []
        for item in outputs:
            path = Path(str(item))
            if path.exists():
                return path
        return Path(str(outputs[0])) if outputs else None

    def open_output_folder(self) -> None:
        path = self._first_output()
        if path is None:
            return
        folder = path if path.is_dir() else path.parent
        try:
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass

    def copy_output(self) -> None:
        path = self._first_output()
        if path is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(str(path))
        self.root.update()

    def close(self) -> None:
        self.backend.stop()
        try:
            self.root.unbind_all("<MouseWheel>")
        except Exception:
            pass
        self.root.destroy()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfyui", required=True, help="absolute ComfyUI installation directory")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="ComfyUI HTTP base URL")
    parser.add_argument("--prompt-id", help="monitor one known ComfyUI prompt; omit to discover the active H3 manifest")
    parser.add_argument("--run-root", help="h3lite run-manifest root")
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--topmost", action="store_true", help="keep the monitor above other windows")
    parser.add_argument("--no-websocket", action="store_true", help="use HTTP polling only")
    parser.add_argument("--once", action="store_true", help="print one JSON snapshot and exit; useful for diagnosis")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = build_parser().parse_args(argv)
    comfyui = Path(args.comfyui).expanduser().resolve()
    run_root = Path(args.run_root).expanduser().resolve() if args.run_root else default_run_root(comfyui)
    backend = MonitorBackend(
        comfyui,
        base_url=args.base_url,
        prompt_id=args.prompt_id,
        run_root=run_root,
        poll_interval=args.poll_interval,
        use_websocket=not args.no_websocket,
    )
    if args.once:
        print(json.dumps(backend.read_snapshot(), ensure_ascii=False, indent=2))
        return 0
    try:
        window = MonitorWindow(backend, topmost=args.topmost)
        window.root.mainloop()
    except Exception as exc:
        backend.stop()
        print(f"无法启动原生监控窗口：{exc}", file=os.sys.stderr)
        print("可以加 --once 检查 ComfyUI 和运行清单是否可读。", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
