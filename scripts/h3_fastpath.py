"""Run the validated H3 Lite route through one bounded foreground command.

The script deliberately keeps the agent out of the generation loop.  It reuses
the cached doctor report, performs planner/preflight work in-process, queues the
workflow once, and keeps completion monitoring inside ``h3_generate --watch``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from h3_paths import normalize_windows_path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CACHE_MAX_AGE = 30 * 60
DEFAULT_WATCH_INTERVAL = 20.0
DEFAULT_WATCH_TIMEOUT = 3600.0

ACCELERATION_CLASS_REQUIREMENTS = {
    "sol_attention": ("MiniMaxH3MemoryEfficientSolAttentionPatch",),
    "sage_attention": ("MiniMaxH3MemoryEfficientSageAttentionPatch",),
    "chunk_feed_forward": ("MiniMaxH3ChunkFeedForward",),
    "block_cache": ("MiniMaxH3BlockCacheT8",),
}

# Set B is validated with the compatibility graph, but the full
# Sol/Sage/Chunk/T8 chain has no matching pinned validation record. Keep auto
# mode on the validated compatibility graph until that accelerated run exists.
COMPONENT_SET_ACCELERATION_POLICY = {
    "portable-16gb-b": "compat",
}

REFERENCE_MODE_LABELS = {
    "t2v": "T2VA",
    "i2va": "I2VA",
    "fl2va": "FL2VA",
    "l2va": "L2VA",
}


class FastPathError(RuntimeError):
    """An actionable error in the single-entry fast route."""


def _format_number(value: float | int) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def _load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def cache_is_fresh(
    path: str | Path,
    *,
    now: float | None = None,
    max_age_seconds: float = DEFAULT_CACHE_MAX_AGE,
) -> bool:
    """Return true only for a readable JSON cache within the freshness window."""
    cache = Path(path).expanduser()
    try:
        cache.stat()
        _load_json(cache)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    age = max(0.0, (time.time() if now is None else now) - cache.stat().st_mtime)
    return age <= max(0.0, max_age_seconds)


def cache_policy(
    path: str | Path,
    *,
    now: float | None = None,
    max_age_seconds: float = DEFAULT_CACHE_MAX_AGE,
    force_doctor: bool = False,
) -> str:
    """Choose cache reuse or the cold-start doctor path."""
    if force_doctor:
        return "force-doctor"
    return "reuse" if cache_is_fresh(path, now=now, max_age_seconds=max_age_seconds) else "doctor"


def build_status_command(
    *,
    scripts_dir: str | Path = SCRIPT_DIR,
    base_url: str = "http://127.0.0.1:8188",
    prompt_id: str,
    comfyui: str | Path | None = None,
    output_dir: str | Path,
    run_root: str | Path,
    watch_interval: float = DEFAULT_WATCH_INTERVAL,
    watch_timeout: float = DEFAULT_WATCH_TIMEOUT,
    require_audio: bool = True,
    dynamic_check: bool = True,
) -> list[str]:
    """Build the one and only foreground monitor command for a run."""
    command = [
        sys.executable,
        str(Path(scripts_dir) / "h3_status.py"),
        "--base-url",
        base_url,
        "--prompt-id",
        prompt_id,
        "--output-dir",
        str(output_dir),
        "--run-root",
        str(run_root),
        "--watch",
        "--watch-interval",
        _format_number(watch_interval),
        "--watch-timeout",
        _format_number(watch_timeout),
        "--compact",
        "--json",
    ]
    if comfyui is not None:
        command.extend(["--comfyui", str(comfyui)])
    if require_audio:
        command.append("--require-audio")
    if dynamic_check:
        command.append("--dynamic-check")
    return command


def build_generate_command(
    *,
    scripts_dir: str | Path = SCRIPT_DIR,
    base_url: str = "http://127.0.0.1:8188",
    prompt_file: str | Path,
    output_dir: str | Path,
    comfyui: str | Path,
    filename_prefix: str,
    run_root: str | Path,
    profile: str,
    resolution: str,
    length: int,
    steps: int,
    fps: float,
    audio_policy: str,
    seed: int | None = None,
    allow_duplicate: bool = False,
    watch_interval: float = DEFAULT_WATCH_INTERVAL,
    watch_timeout: float = DEFAULT_WATCH_TIMEOUT,
    dynamic_check: bool = True,
    workflow_template: str = "h3_w4a8_t2v",
    component_set: str = "auto",
    first_frame: str | Path | None = None,
    last_frame: str | Path | None = None,
) -> list[str]:
    """Build one end-to-end generate-and-watch command."""
    command = [
        sys.executable,
        str(Path(scripts_dir) / "h3_generate.py"),
        "--base-url",
        base_url,
        "--workflow-template",
        workflow_template,
        "--prompt-file",
        str(prompt_file),
        "--output-dir",
        str(output_dir),
        "--comfyui",
        str(comfyui),
        "--filename-prefix",
        filename_prefix,
        "--run-root",
        str(run_root),
        "--audio-policy",
        audio_policy,
        "--profile",
        profile,
        "--resolution",
        resolution,
        "--length",
        str(length),
        "--steps",
        str(steps),
        "--fps",
        _format_number(fps),
        "--watch",
        "--watch-interval",
        _format_number(watch_interval),
        "--watch-timeout",
        _format_number(watch_timeout),
        "--json",
        "--resolve-models",
        "--component-set",
        component_set,
    ]
    if seed is not None:
        command.extend(["--seed", str(seed)])
    if first_frame is not None:
        command.extend(["--first-frame", str(first_frame)])
    if last_frame is not None:
        command.extend(["--last-frame", str(last_frame)])
    if allow_duplicate:
        command.append("--allow-duplicate")
    if dynamic_check:
        command.append("--dynamic-check")
    else:
        command.append("--skip-dynamic-check")
    return command


def build_monitor_command(
    *,
    scripts_dir: str | Path = SCRIPT_DIR,
    comfyui: str | Path,
    base_url: str = "http://127.0.0.1:8188",
    run_root: str | Path | None = None,
    prompt_id: str | None = None,
    topmost: bool = False,
) -> list[str]:
    """Build a detached native monitor command for an interactive Windows run."""
    interpreter = Path(sys.executable)
    if sys.platform.startswith("win"):
        pythonw = interpreter.with_name("pythonw.exe")
        if pythonw.is_file():
            interpreter = pythonw
    command = [
        str(interpreter),
        str(Path(scripts_dir) / "h3_monitor_gui.py"),
        "--comfyui",
        str(comfyui),
        "--base-url",
        base_url,
    ]
    if run_root is not None:
        command.extend(["--run-root", str(run_root)])
    if prompt_id:
        command.extend(["--prompt-id", prompt_id])
    if topmost:
        command.append("--topmost")
    return command


def launch_monitor_gui(
    *,
    comfyui: str | Path,
    base_url: str,
    run_root: str | Path,
    scripts_dir: str | Path = SCRIPT_DIR,
    topmost: bool = False,
) -> subprocess.Popen[Any]:
    """Start the monitor without attaching it to the Agent's terminal."""
    command = build_monitor_command(
        scripts_dir=scripts_dir,
        comfyui=comfyui,
        base_url=base_url,
        run_root=run_root,
        topmost=topmost,
    )
    flags = 0
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    return subprocess.Popen(command, cwd=str(Path(scripts_dir).parent), creationflags=flags, close_fds=True)


def _parse_json_output(output: str) -> dict[str, Any]:
    text = (output or "").strip()
    if not text:
        raise FastPathError("helper returned no JSON output")
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise FastPathError(f"helper returned non-JSON output: {text[-1200:]}")


def _run_json(command: Sequence[str], *, timeout: float | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        list(command),
        cwd=str(SCRIPT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    try:
        value = _parse_json_output(completed.stdout)
    except FastPathError:
        if completed.returncode:
            detail = (completed.stderr or completed.stdout or "no diagnostic output").strip()
            raise FastPathError(f"command failed ({completed.returncode}): {detail[-1600:]}") from None
        raise
    if completed.returncode:
        detail = value.get("error") or completed.stderr or "helper failed"
        raise FastPathError(f"command failed ({completed.returncode}): {detail}")
    return value


def _prompt_file(args: argparse.Namespace, run_root: Path) -> Path:
    if args.prompt_file:
        prompt = Path(args.prompt_file).expanduser().resolve()
        if not prompt.is_file():
            raise FastPathError(f"prompt file does not exist: {prompt}")
        return prompt
    prompt_dir = run_root / "_hotpath" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prompt = prompt_dir / f"prompt-{stamp}.txt"
    prompt.write_text(args.prompt_text, encoding="utf-8")
    return prompt


def _run_doctor(args: argparse.Namespace, doctor_path: Path) -> None:
    command = [
        sys.executable,
        str(SCRIPT_DIR / "h3_doctor.py"),
        "--json",
        "--report-file",
        str(doctor_path),
        "--comfyui",
        str(args.comfyui),
    ]
    if args.root:
        command.extend(["--root", str(args.root)])
    _run_json(command, timeout=300)


def _infer_audio_requirement(prompt: str, policy: str) -> bool:
    from h3_generate import infer_audio_policy

    resolved = infer_audio_policy(prompt) if policy == "auto" else policy
    return resolved == "require"


def _build_plan(
    report: dict[str, Any],
    args: argparse.Namespace,
    *,
    comfyui: Path,
    output_dir: Path,
    run_root: Path,
    timing_file: Path,
    reference_mode: str,
) -> dict[str, Any]:
    from h3_plan import build_plan, resolve_paths

    paths = resolve_paths(
        "reuse-existing",
        comfyui=str(comfyui),
        output_dir=str(output_dir),
    )
    return build_plan(
        report,
        mode=args.profile,
        target_minutes=args.target_minutes,
        aspect=args.aspect,
        video_seconds=args.video_seconds,
        fps=args.fps,
        resolution=args.resolution,
        megapixels=args.megapixels,
        paths={**paths, "run_root": str(run_root)},
        timing_file=timing_file,
        reference_mode=REFERENCE_MODE_LABELS.get(reference_mode.lower(), reference_mode.upper()),
    )


def resolve_reference_mode(args: argparse.Namespace) -> str:
    """Resolve an explicit or inferred H3 reference route."""
    has_first = bool(getattr(args, "first_frame", None))
    has_last = bool(getattr(args, "last_frame", None))
    inferred = "fl2va" if has_first and has_last else "i2va" if has_first else "l2va" if has_last else "t2v"
    requested_mode = getattr(args, "mode", "auto")
    mode = requested_mode if requested_mode != "auto" else inferred
    requirements = {
        "t2v": (False, False),
        "i2va": (True, False),
        "fl2va": (True, True),
        "l2va": (False, True),
    }
    required = requirements[mode]
    if (has_first, has_last) != required:
        expected = {
            "t2v": "no frame images",
            "i2va": "--first-frame only",
            "fl2va": "both --first-frame and --last-frame",
            "l2va": "--last-frame only",
        }[mode]
        raise FastPathError(f"--mode {mode} requires {expected}")
    return mode


def _registered_classes(object_info: Any) -> set[str]:
    if not isinstance(object_info, dict):
        return set()
    nodes = object_info.get("nodes")
    if isinstance(nodes, dict):
        return {str(name) for name in nodes}
    return {str(name) for name in object_info}


def _acceleration_capabilities(doctor: dict[str, Any]) -> dict[str, bool]:
    """Use loaded ComfyUI classes when available; directory hints are fallback only."""
    runtime = doctor.get("runtime_capabilities") if isinstance(doctor, dict) else None
    has_object_info_probe = isinstance(runtime, dict) and "object_info" in runtime
    object_info = runtime.get("object_info") if isinstance(runtime, dict) else None
    if has_object_info_probe and object_info is None:
        return {role: False for role in ACCELERATION_CLASS_REQUIREMENTS}
    if object_info is not None:
        registered = _registered_classes(object_info)
        return {
            role: any(class_name in registered for class_name in class_names)
            for role, class_names in ACCELERATION_CLASS_REQUIREMENTS.items()
        }

    node_map = doctor.get("custom_nodes", {}).get("nodes", {})
    directory_roles = {
        "sol_attention": "sol_attention",
        "sage_attention": "sage_attention",
        "chunk_feed_forward": "h3_turbo",
        "block_cache": "block_cache",
    }
    return {
        role: isinstance(node_map.get(node_role), dict) and node_map[node_role].get("present") is True
        for role, node_role in directory_roles.items()
    }


def _component_set_candidates_from_doctor(doctor: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    models = doctor.get("models") if isinstance(doctor, dict) else None
    assets = models.get("assets") if isinstance(models, dict) else None
    if isinstance(assets, dict):
        for asset in assets.values():
            found = asset.get("found") if isinstance(asset, dict) else None
            if not isinstance(found, list):
                continue
            for item in found:
                if isinstance(item, dict) and item.get("path"):
                    names.add(Path(str(item["path"])).name)
    from h3_generate import component_set_candidates

    return component_set_candidates(names)


def select_workflow_template(
    requested: str,
    doctor: dict[str, Any],
    reference_mode: str = "t2v",
    component_set: str = "auto",
    acceleration: str = "auto",
) -> str:
    """Select a route from reference mode, component set, and loaded node classes."""
    wants_reference = reference_mode != "t2v"
    if requested != "auto":
        template_is_reference = requested.startswith("h3_w4a8_i2v")
        if template_is_reference != wants_reference:
            expected = "an I2V template" if wants_reference else "a T2V template"
            raise FastPathError(f"workflow template {requested} is incompatible with {reference_mode.upper()}; choose {expected}")
        return requested

    acceleration = (acceleration or "auto").strip().lower()
    if acceleration not in {"auto", "fast", "compat"}:
        raise FastPathError("--acceleration must be auto, fast, or compat")
    if acceleration == "compat":
        accelerated = False
    else:
        capabilities = _acceleration_capabilities(doctor)
        accelerated = all(capabilities.values())
        if acceleration == "fast" and not accelerated:
            missing = [role for role, present in capabilities.items() if not present]
            raise FastPathError("accelerated route requested but loaded node classes are missing: " + ", ".join(missing))
        normalized_set = component_set
        try:
            from h3_generate import normalize_component_set

            normalized_set = normalize_component_set(component_set)
        except ValueError as exc:
            raise FastPathError(str(exc)) from exc
        if acceleration == "auto" and COMPONENT_SET_ACCELERATION_POLICY.get(normalized_set) == "compat":
            accelerated = False
    if wants_reference:
        return "h3_w4a8_i2v" if accelerated else "h3_w4a8_i2v_compat"
    return "h3_w4a8_t2v" if accelerated else "h3_w4a8_t2v_compat"


def run_fastpath(args: argparse.Namespace) -> dict[str, Any]:
    monitor_gui = bool(getattr(args, "monitor_gui", False))
    reference_mode = resolve_reference_mode(args)
    reference_mode_label = REFERENCE_MODE_LABELS.get(reference_mode.lower(), reference_mode.upper())
    comfyui = normalize_windows_path(args.comfyui).resolve()
    output_dir = normalize_windows_path(args.output_dir).resolve() if args.output_dir else comfyui / "output"
    run_root = normalize_windows_path(args.run_root).resolve() if args.run_root else comfyui / "user" / "h3lite_runs"
    environment = run_root / "_environment"
    doctor_path = normalize_windows_path(args.doctor_json).resolve() if args.doctor_json else environment / "doctor.json"
    plan_path = normalize_windows_path(args.plan_json).resolve() if args.plan_json else environment / "plan.json"
    timing_file = normalize_windows_path(args.timing_file).resolve() if args.timing_file else environment / "timing.json"

    if not comfyui.is_dir():
        raise FastPathError(f"ComfyUI directory does not exist: {comfyui}")

    from h3_generate import json_request

    try:
        system_stats = json_request(args.base_url, "/system_stats")
    except Exception as exc:
        raise FastPathError(f"ComfyUI is not healthy at {args.base_url}: {exc}") from exc

    policy = cache_policy(
        doctor_path,
        max_age_seconds=args.cache_max_age,
        force_doctor=args.force_doctor,
    )
    if policy == "reuse":
        from h3_doctor import environment_fingerprint

        cached_fingerprint = doctor_fingerprint = None
        try:
            cached_fingerprint = _load_json(doctor_path).get("environment_fingerprint")
            doctor_fingerprint = environment_fingerprint(_load_json(doctor_path), comfyui)
        except (OSError, ValueError, json.JSONDecodeError):
            cached_fingerprint = None
        if not cached_fingerprint or cached_fingerprint != doctor_fingerprint:
            policy = "doctor"
    if policy != "reuse":
        _run_doctor(args, doctor_path)
    doctor = _load_json(doctor_path)
    try:
        object_info = json_request(args.base_url, "/object_info")
    except Exception:
        # Older or restricted ComfyUI builds may not expose object_info. Keep
        # the explicit compatibility route rather than trusting a directory
        # name to prove that an optional node imported successfully.
        object_info = None
    routing_doctor = dict(doctor)
    routing_doctor["runtime_capabilities"] = {"object_info": object_info}
    requested_component_set = getattr(args, "component_set", "auto")
    from h3_generate import normalize_component_set

    normalized_component_set = normalize_component_set(requested_component_set)
    component_candidates = _component_set_candidates_from_doctor(doctor)
    if normalized_component_set == "auto" and len(component_candidates) > 1:
        raise FastPathError(
            "multiple complete component sets are installed: "
            + ", ".join(component_candidates)
            + "; rerun with --component-set A or --component-set B"
        )
    selected_component_set = normalized_component_set
    if selected_component_set == "auto" and len(component_candidates) == 1:
        selected_component_set = component_candidates[0]

    prompt_file = _prompt_file(args, run_root)
    prompt_text = prompt_file.read_text(encoding="utf-8")
    require_audio = _infer_audio_requirement(prompt_text, args.audio_policy)
    plan = _build_plan(
        doctor,
        args,
        comfyui=comfyui,
        output_dir=output_dir,
        run_root=run_root,
        timing_file=timing_file,
        reference_mode=reference_mode,
    )
    if isinstance(plan.get("request"), dict):
        plan["request"]["reference_mode"] = reference_mode_label
    if isinstance(plan.get("decision"), dict):
        plan["decision"]["reference_mode"] = reference_mode_label
    _write_json(plan_path, plan)

    from h3_preflight import assess_runtime_risk, refresh_runtime

    runtime = refresh_runtime(doctor)
    preflight = assess_runtime_risk(runtime, plan, require_audio=require_audio)
    if preflight["status"] == "blocked":
        raise FastPathError(json.dumps({"preflight": preflight, "plan": plan}, ensure_ascii=False))

    decision = plan["decision"]
    request = plan["request"]
    resolution = decision["resolution"]
    resolution_text = f"{int(resolution['width'])}x{int(resolution['height'])}"
    profile = str(decision["mode"])
    filename_prefix = args.filename_prefix or "video/H3Lite_fastpath"
    workflow_template = select_workflow_template(
        args.workflow_template,
        routing_doctor,
        reference_mode,
        component_set=selected_component_set,
        acceleration=getattr(args, "acceleration", "auto"),
    )
    generation_command = build_generate_command(
        base_url=args.base_url,
        prompt_file=prompt_file,
        output_dir=output_dir,
        comfyui=comfyui,
        filename_prefix=filename_prefix,
        run_root=run_root,
        profile=profile,
        resolution=resolution_text,
        length=int(request["frames"]),
        steps=int(decision["steps"]),
        fps=float(request["fps"]),
        audio_policy=args.audio_policy,
        seed=args.seed,
        allow_duplicate=args.allow_duplicate,
        watch_interval=args.watch_interval,
        watch_timeout=args.watch_timeout,
        dynamic_check=args.dynamic_check,
        workflow_template=workflow_template,
        component_set=selected_component_set,
        first_frame=getattr(args, "first_frame", None),
        last_frame=getattr(args, "last_frame", None),
    )

    if args.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "cache_policy": policy,
            "system_stats": system_stats,
            "plan": plan,
            "preflight": preflight,
            "prompt_file": str(prompt_file),
            "reference_mode": reference_mode_label,
            "workflow_template": workflow_template,
            "component_set": selected_component_set,
            "component_candidates": component_candidates,
            "runtime_capabilities": {
                "object_info_available": object_info is not None,
                "acceleration": _acceleration_capabilities(routing_doctor),
            },
            "generation_command": generation_command,
            "monitor_gui": {
                "enabled": monitor_gui,
                "command": build_monitor_command(
                    comfyui=comfyui,
                    base_url=args.base_url,
                    run_root=run_root,
                )
                if monitor_gui
                else None,
            },
        }

    monitor_process = None
    monitor_error = None
    if monitor_gui:
        try:
            monitor_process = launch_monitor_gui(
                comfyui=comfyui,
                base_url=args.base_url,
                run_root=run_root,
            )
        except OSError as exc:
            # Monitoring is additive; a window launch failure must not cancel a
            # valid generation request.
            monitor_error = str(exc)

    generation = _run_json(generation_command, timeout=args.watch_timeout + 120)
    return {
        "ok": bool(generation.get("ok")),
        "cache_policy": policy,
        "preflight": preflight,
        "plan": plan,
        "reference_mode": reference_mode_label,
        "workflow_template": workflow_template,
        "component_set": selected_component_set,
        "component_candidates": component_candidates,
        "generation": generation,
        "prompt_id": generation.get("prompt_id"),
        "monitor_gui": {
            "enabled": monitor_gui,
            "pid": monitor_process.pid if monitor_process is not None else None,
            "error": monitor_error,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfyui", required=True, help="absolute ComfyUI installation directory")
    parser.add_argument("--base-url", default="http://127.0.0.1:8188", help="ComfyUI server URL")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt-file", help="UTF-8 H3 prompt file")
    prompt_group.add_argument("--prompt-text", help="H3 prompt supplied directly")
    parser.add_argument("--output-dir", help="ComfyUI output directory")
    parser.add_argument("--run-root", help="h3lite run-manifest root")
    parser.add_argument("--doctor-json", help="override cached doctor report path")
    parser.add_argument("--plan-json", help="override generated plan path")
    parser.add_argument("--timing-file", help="timing history used by the planner")
    parser.add_argument("--root", help="disk root used by a cold-start doctor scan")
    parser.add_argument("--profile", choices=["auto", "fast", "balanced", "quality"], default="auto")
    parser.add_argument(
        "--workflow-template",
        choices=["auto", "h3_w4a8_t2v", "h3_w4a8_t2v_compat", "h3_w4a8_i2v", "h3_w4a8_i2v_compat"],
        default="auto",
        help="auto selects the route from loaded node classes and component-set policy",
    )
    parser.add_argument(
        "--component-set",
        default="auto",
        help="registered model set: auto, A/validated-low-vram-a, or B/portable-16gb-b",
    )
    parser.add_argument(
        "--acceleration",
        choices=["auto", "fast", "compat"],
        default="auto",
        help="optional acceleration policy; auto uses each component set's validated graph",
    )
    parser.add_argument("--mode", choices=["auto", "t2v", "i2va", "fl2va", "l2va"], default="auto", help="reference route; inferred from frame arguments when omitted")
    parser.add_argument("--first-frame", help="local first-frame image for I2VA/FL2VA")
    parser.add_argument("--last-frame", help="local last-frame image for L2VA/FL2VA")
    parser.add_argument("--target-minutes", type=float)
    parser.add_argument("--aspect", default="landscape")
    parser.add_argument("--video-seconds", type=float, default=5.0)
    parser.add_argument("--fps", type=float, default=24.0)
    parser.add_argument("--resolution", help="explicit WIDTHxHEIGHT canvas")
    parser.add_argument("--megapixels", type=float, help="ComfyUI ResolutionSelector-style canvas target, e.g. 0.4")
    parser.add_argument("--filename-prefix", help="SaveVideo filename prefix")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--audio-policy", choices=["auto", "require", "allow", "disable"], default="auto")
    parser.add_argument("--cache-max-age", type=float, default=DEFAULT_CACHE_MAX_AGE)
    parser.add_argument("--force-doctor", action="store_true", help="invalidate the cached environment report")
    parser.add_argument("--watch-interval", type=float, default=DEFAULT_WATCH_INTERVAL)
    parser.add_argument("--watch-timeout", type=float, default=DEFAULT_WATCH_TIMEOUT)
    parser.add_argument(
        "--monitor-gui",
        action="store_true",
        help="open a native Windows progress window while the run is queued or running",
    )
    parser.add_argument("--dynamic-check", dest="dynamic_check", action="store_true", default=True)
    parser.add_argument("--skip-dynamic-check", dest="dynamic_check", action="store_false")
    parser.add_argument("--allow-duplicate", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="run checks and show the queue command without submitting")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result")
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args()
    try:
        result = run_fastpath(args)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result.get("dry_run"):
                print(f"Fast path ready; cache={result['cache_policy']} preflight={result['preflight']['status']}")
            else:
                status = result.get("status", {})
                print(f"{status.get('state', 'unknown')}: {result.get('prompt_id', '?')}")
                for item in status.get("outputs", []):
                    print(f"Output: {item.get('path')} | verified={item.get('verified', 'unknown')}")
        return 0 if result.get("ok") else 1
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
