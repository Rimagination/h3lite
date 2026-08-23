#!/usr/bin/env python3
r"""Report NVIDIA/WDDM GPU memory and provide a guarded free-VRAM gate.

Windows WDDM exposes per-process dedicated-memory counters separately from
nvidia-smi's per-GPU totals. The two views can cover different adapters, so
this helper preserves WDDM LUIDs, reports scope mismatches, and refuses the
free-VRAM gate when the scopes cannot be compared safely.

The command is read-only by default:

    python scripts/h3_vram.py --json
    python scripts/h3_vram.py --check-free-gb 5

Stopping a process requires an explicit confirmation flag, an exact process
name, and (for ComfyUI) an optional queue URL:

    python scripts/h3_vram.py --stop <pid> --process-name python --queue-url http://127.0.0.1:8188/queue --confirm-stop

--stop is destructive. It is never a substitute for checking that the target
application is idle.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import urllib.request
from typing import Any


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
WINDOWS = sys.platform.startswith("win")
MB = 1024 * 1024
COUNTER_SET = r"\GPU Process Memory(*)\Dedicated Usage"

# These processes can appear in the WDDM counter because they own desktop
# surfaces. They are never valid automatic stop targets.
PROTECTED_PROCESS_NAMES = frozenset(
    {
        "system",
        "csrss",
        "dwm",
        "explorer",
        "wininit",
        "services",
        "lsass",
        "smss",
        "winlogon",
        "svchost",
    }
)


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except Exception as exc:  # noqa: BLE001 - reporting failure is the job here
        return -1, "", str(exc)


def _parse_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def nvidia_totals_mb() -> list[dict[str, Any]] | None:
    """Return all NVIDIA GPU totals, or None when nvidia-smi is unavailable."""
    rc, out, _ = _run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.used,memory.free",
            "--format=csv,noheader,nounits",
        ]
    )
    if rc != 0 or not out.strip():
        return None

    rows: list[dict[str, Any]] = []
    for parts in csv.reader(out.splitlines()):
        if len(parts) != 5:
            continue
        index = _parse_int(parts[0])
        total = _parse_int(parts[2])
        used = _parse_int(parts[3])
        free = _parse_int(parts[4])
        if index is None or total is None or used is None or free is None:
            continue
        rows.append(
            {
                "index": index,
                "name": parts[1].strip(),
                "total_mb": total,
                "used_mb": used,
                "free_mb": free,
            }
        )
    return rows or None


def _parse_wddm_json(output: str) -> list[dict[str, Any]] | None:
    if not output.strip():
        return []
    try:
        payload = json.loads(output.strip())
    except json.JSONDecodeError:
        return None
    items = payload if isinstance(payload, list) else [payload]
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        pid = _parse_int(item.get("pid"))
        raw = _parse_int(item.get("dedicated_bytes"))
        if pid is None or raw is None or raw < 0:
            continue
        rows.append(
            {
                "pid": pid,
                "name": str(item.get("name") or "?"),
                "luid": str(item.get("luid") or "unknown"),
                "phys": _parse_int(item.get("phys")),
                "dedicated_mb": raw // MB,
            }
        )
    rows.sort(key=lambda row: row["dedicated_mb"], reverse=True)
    return rows


def win_per_process_mb() -> list[dict[str, Any]] | None:
    """Return WDDM per-process dedicated memory while preserving adapter LUID."""
    script = (
        "$per=@{};"
        f"Get-Counter '{COUNTER_SET}' | ForEach-Object {{$_.CounterSamples}} | "
        "Where-Object {$_.CookedValue -gt 0} | ForEach-Object {"
        "if ($_.InstanceName -match '^pid_(\\d+)_luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)_phys_(\\d+)$') {"
        "$key=('' + $matches[1] + '|' + $matches[2].ToLowerInvariant() + '|' + $matches[3]);"
        "$per[$key]=[double]$per[$key]+[double]$_.CookedValue"
        "}};"
        "$items=@();"
        "foreach ($key in $per.Keys) {"
        "$parts=$key -split '\\|';"
        "$p=Get-Process -Id ([int]$parts[0]) -ErrorAction SilentlyContinue;"
        "$items += [pscustomobject]@{"
        "pid=[int]$parts[0];"
        "name=if ($p) {$p.ProcessName} else {'?'};"
        "luid=$parts[1];"
        "phys=[int]$parts[2];"
        "dedicated_bytes=[long]$per[$key]"
        "}"
        "};"
        "if ($items.Count -gt 0) {$items | ConvertTo-Json -Compress}"
    )
    rc, out, _ = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    )
    if rc != 0:
        return None
    return _parse_wddm_json(out)


def fallback_process_mb() -> list[dict[str, Any]] | None:
    """Use nvidia-smi compute rows when the WDDM counter is unavailable."""
    rc, out, _ = _run(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_gpu_memory",
            "--format=csv,noheader",
        ]
    )
    if rc != 0:
        return None
    rows: list[dict[str, Any]] = []
    for parts in csv.reader(out.splitlines()):
        if len(parts) != 3:
            continue
        pid = _parse_int(parts[0])
        if pid is None:
            continue
        size = parts[2].strip().replace("MiB", "").strip()
        rows.append(
            {
                "pid": pid,
                "name": parts[1].strip().strip('"') or "?",
                "luid": None,
                "phys": None,
                "dedicated_mb": _parse_int(size),
            }
        )
    rows.sort(key=lambda row: row["dedicated_mb"] or -1, reverse=True)
    return rows


def _wddm_luids(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row["luid"])
            for row in rows
            if row.get("luid") and str(row["luid"]) != "unknown"
        }
    )


def build_report() -> dict[str, Any]:
    gpus = nvidia_totals_mb() or []
    rows = win_per_process_mb() if WINDOWS else None
    source = "win-perfcounter"
    if rows is None:
        rows = fallback_process_mb()
        source = "query-compute-apps"
    if rows is None:
        rows = []
        source = "unavailable"

    luids = _wddm_luids(rows)
    process_sum_mb = sum(
        int(row["dedicated_mb"])
        for row in rows
        if isinstance(row.get("dedicated_mb"), int)
    )
    nvidia_used_mb = sum(int(gpu["used_mb"]) for gpu in gpus)
    scope_mismatch = False
    warnings: list[str] = []
    process_scope = source

    if source == "win-perfcounter":
        process_scope = (
            "wddm-multiple-luids"
            if len(luids) > 1
            else "wddm-single-luid"
            if len(luids) == 1
            else "wddm-no-luid"
        )
        if len(luids) > 1:
            scope_mismatch = True
            warnings.append(
                "WDDM process memory spans multiple adapter LUIDs; it cannot be "
                "compared directly with one nvidia-smi GPU total."
            )
        if gpus and process_sum_mb > nvidia_used_mb + max(256, nvidia_used_mb // 4):
            scope_mismatch = True
            warnings.append(
                "WDDM process-memory sum is materially larger than nvidia-smi "
                "totals; treat process rows as diagnostic only."
            )

    return {
        # Keep the old single-GPU key for consumers that already read it.
        "gpu": gpus[0] if len(gpus) == 1 else None,
        "gpus": gpus,
        "processes": rows,
        "source": source,
        "process_scope": process_scope,
        "wddm_luids": luids,
        "scope_mismatch": scope_mismatch,
        "warnings": warnings,
    }


def render_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    gpus = report.get("gpus") or []
    if not gpus:
        lines.append("VRAM: nvidia-smi totals unavailable")
    else:
        for gpu in gpus:
            lines.append(
                f"GPU {gpu['index']} {gpu['name']}: "
                f"{gpu['used_mb']/1024:.2f} GB used / "
                f"{gpu['total_mb']/1024:.2f} GB "
                f"({gpu['free_mb']/1024:.2f} GB free)"
            )

    lines.append(
        f"processes (source: {report['source']}; "
        f"scope: {report['process_scope']}):"
    )
    rows = report["processes"]
    if not rows:
        lines.append("  (none / unable to read per-process memory)")
    for row in rows[:15]:
        memory = row.get("dedicated_mb")
        memory_text = "unknown" if memory is None else f"{memory/1024:.2f} GB"
        luid = row.get("luid")
        scope = f" [{luid}]" if luid else ""
        lines.append(
            f"  {row['pid']:>8}  {memory_text:>9}  "
            f"{row['name']}{scope}"
        )
    if len(rows) > 15:
        lines.append(f"  ... {len(rows) - 15} more")
    for warning in report.get("warnings") or []:
        lines.append(f"warning: {warning}")
    return "\n".join(lines)


def _select_gpu(report: dict[str, Any], gpu_index: int | None) -> dict[str, Any] | None:
    gpus = report.get("gpus") or []
    if gpu_index is None:
        return gpus[0] if len(gpus) == 1 else None
    return next((gpu for gpu in gpus if gpu.get("index") == gpu_index), None)


def _normal_name(name: Any) -> str:
    value = str(name or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
    return value.casefold().removesuffix(".exe")


def _current_process_name(pid: int) -> str | None:
    if not WINDOWS:
        return None
    command = f"(Get-Process -Id {pid} -ErrorAction Stop).ProcessName"
    rc, out, _ = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    )
    if rc != 0 or not out.strip():
        return None
    return out.strip().splitlines()[-1].strip()


def _queue_is_idle(queue_url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(queue_url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - fail closed for a destructive action
        return False, f"could not read queue: {exc}"
    if not isinstance(payload, dict):
        return False, "queue response was not a JSON object"
    running = payload.get("queue_running")
    pending = payload.get("queue_pending")
    if not isinstance(running, list) or not isinstance(pending, list):
        return False, "queue response did not contain queue_running/queue_pending"
    if running or pending:
        return False, f"queue is not empty ({len(running)} running, {len(pending)} pending)"
    return True, "queue is empty"


def cmd_stop(
    pid: int,
    *,
    confirm_stop: bool,
    expected_name: str | None,
    queue_url: str | None,
) -> int:
    if not confirm_stop:
        print(
            "refusing to terminate a process without --confirm-stop; "
            "inspect --json first",
            file=sys.stderr,
        )
        return 2
    if not expected_name:
        print(
            "refusing to terminate without --process-name; "
            "copy the exact name from --json",
            file=sys.stderr,
        )
        return 2
    if not WINDOWS:
        print("--stop is supported only on Windows", file=sys.stderr)
        return 2
    if pid <= 4 or pid == os.getpid():
        print(f"pid {pid}: refusing to terminate a protected process", file=sys.stderr)
        return 2

    report = build_report()
    rows = [row for row in report["processes"] if row["pid"] == pid]
    if not rows:
        print(f"pid {pid}: not found in the process list; nothing stopped", file=sys.stderr)
        return 2
    observed_name = _normal_name(rows[0].get("name"))
    requested_name = _normal_name(expected_name)
    if observed_name != requested_name:
        print(
            f"pid {pid}: process name changed or does not match "
            f"{expected_name!r} (reported {rows[0].get('name')!r})",
            file=sys.stderr,
        )
        return 2
    if observed_name in PROTECTED_PROCESS_NAMES:
        print(f"pid {pid}: refusing to terminate protected process {observed_name}", file=sys.stderr)
        return 2

    current_name = _current_process_name(pid)
    if current_name is None or _normal_name(current_name) != requested_name:
        print(f"pid {pid}: could not revalidate the current process identity", file=sys.stderr)
        return 2
    if queue_url:
        idle, detail = _queue_is_idle(queue_url)
        if not idle:
            print(f"pid {pid}: {detail}; nothing stopped", file=sys.stderr)
            return 2

    dedicated_mb = sum(
        int(row["dedicated_mb"])
        for row in rows
        if isinstance(row.get("dedicated_mb"), int)
    )
    print(
        f"stopping pid {pid} ({observed_name}, "
        f"{dedicated_mb/1024:.2f} GB reported dedicated VRAM)..."
    )
    rc, out, err = _run(["taskkill", "/PID", str(pid), "/F"])
    if rc != 0:
        print(f"taskkill failed: {err or out}", file=sys.stderr)
        return 1
    print("stopped.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument(
        "--gpu-index",
        type=int,
        help="NVIDIA GPU index used by --check-free-gb when multiple GPUs exist",
    )
    parser.add_argument(
        "--check-free-gb",
        type=float,
        metavar="GB",
        help="exit 1 below the threshold; exit 2 when adapter scope is unknown",
    )
    parser.add_argument(
        "--allow-scope-mismatch",
        action="store_true",
        help="allow the free-VRAM gate to use nvidia-smi totals despite WDDM scope warnings",
    )
    parser.add_argument("--stop", type=int, metavar="PID", help="terminate a confirmed idle process")
    parser.add_argument(
        "--process-name",
        help="exact process name from --json; required with --stop",
    )
    parser.add_argument(
        "--queue-url",
        help="ComfyUI /queue URL; --stop fails closed unless running and pending queues are empty",
    )
    parser.add_argument(
        "--confirm-stop",
        action="store_true",
        help="required acknowledgement for the destructive --stop operation",
    )
    args = parser.parse_args(argv)

    if args.stop is not None:
        return cmd_stop(
            args.stop,
            confirm_stop=args.confirm_stop,
            expected_name=args.process_name,
            queue_url=args.queue_url,
        )

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))

    if args.check_free_gb is not None:
        gpus = report.get("gpus") or []
        if len(gpus) > 1 and args.gpu_index is None:
            print("free VRAM unknown; choose --gpu-index when multiple NVIDIA GPUs exist", file=sys.stderr)
            return 2
        gpu = _select_gpu(report, args.gpu_index)
        if gpu is None or gpu.get("free_mb") is None:
            print("free VRAM unknown; nvidia-smi totals unavailable", file=sys.stderr)
            return 2
        if report.get("scope_mismatch") and not args.allow_scope_mismatch:
            print(
                "free VRAM unknown; WDDM per-process memory does not share a "
                "safe adapter scope with nvidia-smi totals. Use --json to "
                "inspect it, or explicitly pass --allow-scope-mismatch.",
                file=sys.stderr,
            )
            return 2
        free_gb = gpu["free_mb"] / 1024
        if free_gb < args.check_free_gb:
            print(
                f"free VRAM {free_gb:.2f} GB < {args.check_free_gb} GB threshold",
                file=sys.stderr,
            )
            return 1
        print(f"free VRAM {free_gb:.2f} GB >= {args.check_free_gb} GB threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
