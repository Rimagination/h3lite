#!/usr/bin/env python3
r"""Per-process dedicated VRAM usage and a free-VRAM gate for NVIDIA/Windows.

On recent Windows WDDM drivers `nvidia-smi --query-compute-apps` reports
per-process memory as N/A, so this helper reads the WDDM GPU process memory
counter (`\GPU Process Memory(*)\Dedicated Usage`) through a single PowerShell
call, pairs it with nvidia-smi totals, and prints or returns a machine-readable
report. When the counter is unavailable it falls back to query-compute-apps.

Use cases:
- Diagnose a hog before another heavy CUDA job (e.g. a Topaz Video AI export)
  while ComfyUI keeps models resident:  `python scripts/h3_vram.py --json`
- Gate mode:                              `python scripts/h3_vram.py --check-free-gb 5`
- Stop the identified hog (after confirming its queue is idle):
                                           `python scripts/h3_vram.py --stop <pid>`

The script is read-only unless --stop is passed. Terminating a process is
destructive: confirm the target is idle first, and never use it to stop a
ComfyUI that still has queued or running items.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
WINDOWS = sys.platform.startswith("win")
MB = 1024 * 1024

# \GPU Process Memory(*)\Dedicated Usage reports bytes per pid instance.
# NB: Get-Counter needs the leading backslash, otherwise it fails with
# "The specified counter path could not be interpreted".
COUNTER_SET = "\\GPU Process Memory(*)\\Dedicated Usage"


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


def nvidia_totals_mb() -> dict[str, int] | None:
    """Return {total_mb, used_mb, free_mb} from nvidia-smi, or None."""
    rc, out, _ = _run(
        [
            "nvidia-smi",
            "--query-gpu=memory.total,memory.used,memory.free",
            "--format=csv,noheader,nounits",
        ]
    )
    if rc != 0 or not out.strip():
        return None
    line = out.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 3:
        return None
    try:
        total, used, free = (int(p) for p in parts)
    except ValueError:
        return None
    return {"total_mb": total, "used_mb": used, "free_mb": free}


def win_per_process_mb() -> list[dict[str, Any]] | None:
    """Per-process dedicated VRAM (bytes -> MB) via the WDDM counter."""
    script = (
        "$per=@{};"
        f"Get-Counter '{COUNTER_SET}' | ForEach-Object {{$_.CounterSamples}} | "
        "Where-Object {$_.CookedValue -gt 0} | ForEach-Object {"
        "if ($_.InstanceName -match 'pid_(\\d+)_') {"
        "$k=$matches[1]; $per[$k]=[double]$per[$k]+[double]$_.CookedValue}}; "
        "foreach ($k in $per.Keys) {"
        "$p=Get-Process -Id ([int]$k) -ErrorAction SilentlyContinue; "
        "Write-Output (\"{0}|{1}|{2}\" -f $k, $(if ($p) {$p.ProcessName} else {'?'}), [long]$per[$k])}"
    )
    rc, out, err = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])
    if rc != 0:
        return None
    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        pid, name, raw = parts
        if not pid.isdigit() or not raw.isdigit():
            continue
        rows.append({"pid": int(pid), "name": name or "?", "dedicated_mb": int(raw) // MB})
    rows.sort(key=lambda r: r["dedicated_mb"], reverse=True)
    return rows


def fallback_process_mb() -> list[dict[str, Any]] | None:
    """nvidia-smi --query-compute-apps rows, usable when the counter is missing."""
    rc, out, _ = _run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_gpu_memory",
                       "--format=csv,noheader"])
    if rc != 0:
        return None
    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3:
            continue
        pid, name, size = parts
        if not pid.isdigit():
            continue
        try:
            mb = int(size.replace("MiB", "").strip())
        except ValueError:
            mb = 0
        rows.append({"pid": int(pid), "name": name.strip('"') or "?", "dedicated_mb": mb})
    rows.sort(key=lambda r: r["dedicated_mb"], reverse=True)
    return rows


def build_report() -> dict[str, Any]:
    totals = nvidia_totals_mb()
    rows = win_per_process_mb() if WINDOWS else None
    source = "win-perfcounter"
    if rows is None:
        rows = fallback_process_mb()
        source = "query-compute-apps"
    if rows is None:
        rows = []
        source = "unavailable"
    return {"gpu": totals, "processes": rows, "source": source}


def render_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    gpu = report["gpu"]
    if gpu:
        lines.append(
            f"VRAM: {gpu['used_mb']/1024:.2f} GB used / {gpu['total_mb']/1024:.2f} GB "
            f"({gpu['free_mb']/1024:.2f} GB free)"
        )
    else:
        lines.append("VRAM: nvidia-smi totals unavailable")
    lines.append(f"processes (source: {report['source']}):")
    rows = report["processes"]
    if not rows:
        lines.append("  (none / unable to read per-process memory)")
    for row in rows[:15]:
        lines.append(
            f"  {row['pid']:>8}  {row['dedicated_mb']/1024:6.2f} GB  {row['name']}"
        )
    if len(rows) > 15:
        lines.append(f"  ... {len(rows) - 15} more")
    return "\n".join(lines)


def cmd_stop(pid: int) -> int:
    report = build_report()
    row = next((r for r in report["processes"] if r["pid"] == pid), None)
    if row is None:
        print(f"pid {pid}: not found in the process list; nothing stopped", file=sys.stderr)
        return 2
    if pid <= 4 or pid == os.getpid():
        print(f"pid {pid}: refusing to terminate a protected process", file=sys.stderr)
        return 2
    print(
        f"stopping pid {pid} ({row['name']}, "
        f"{row['dedicated_mb']/1024:.2f} GB dedicated VRAM)..."
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
    parser.add_argument("--check-free-gb", type=float, metavar="GB",
                        help="exit 1 when free VRAM is below this threshold")
    parser.add_argument("--stop", type=int, metavar="PID",
                        help="terminate the given process (destructive; confirm idle first)")
    args = parser.parse_args(argv)

    if args.stop:
        return cmd_stop(args.stop)

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))

    if args.check_free_gb is not None:
        gpu = report["gpu"]
        if not gpu or gpu["free_mb"] is None:
            print("free VRAM unknown; cannot gate", file=sys.stderr)
            return 1 if gpu is None else 0
        free_gb = gpu["free_mb"] / 1024
        if free_gb < args.check_free_gb:
            print(f"free VRAM {free_gb:.2f} GB < {args.check_free_gb} GB threshold",
                  file=sys.stderr)
            return 1
        print(f"free VRAM {free_gb:.2f} GB >= {args.check_free_gb} GB threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
