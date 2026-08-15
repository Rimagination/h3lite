#!/usr/bin/env python3
"""Evaluate runtime risk before a low-VRAM MiniMax H3 generation.

This is a read-only gate. It distinguishes a recoverable low-memory warning
from a condition that is likely to exhaust Windows pagefile or make a run
unreliable. It consumes the JSON report produced by h3_doctor.py.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _max_value(items: list[dict[str, Any]], key: str) -> float | None:
    values = [_number(item.get(key)) for item in items if isinstance(item, dict)]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _external_gpu_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ignore the usual ComfyUI Python process and zero-memory desktop helpers."""
    python_names = {"python", "python.exe", "python3", "python3.exe"}
    benign_names = {"gameviewer.exe", "nvcontainer.exe", "dwm.exe", "explorer.exe"}
    external: list[dict[str, Any]] = []
    for process in processes:
        if not isinstance(process, dict):
            continue
        raw_name = str(process.get("process_name", "")).strip().lower().replace("\\", "/")
        name = raw_name.rsplit("/", 1)[-1]
        if name in python_names or name in benign_names:
            continue
        used_memory = _number(process.get("used_gpu_memory_mb"))
        if used_memory is not None and used_memory < 128:
            continue
        external.append(process)
    return external


def _append_missing_asset_checks(report: dict[str, Any], errors: list[str], warnings: list[str], require_audio: bool) -> None:
    models = report.get("models")
    if isinstance(models, dict) and models.get("available"):
        assets = models.get("assets")
        if isinstance(assets, dict) and assets:
            required = {
                "low_vram_diffusion",
                "low_vram_text_encoder",
                "video_vae_fp16",
                "clipproj",
                "lightx2v_lora",
            }
            if require_audio:
                required.add("audio_vae_fp32")
            missing = [key for key in sorted(required) if key in assets and assets[key].get("present") is False]
            if missing:
                errors.append("missing required model roles: " + ", ".join(missing))

    nodes = report.get("custom_nodes")
    if not isinstance(nodes, dict) or not nodes.get("available"):
        return
    node_map = nodes.get("nodes")
    if not isinstance(node_map, dict) or not node_map:
        return
    # The compatibility workflow only requires ClipProj. Attention and block
    # cache nodes are optional accelerators and must never block a baseline run.
    required_nodes = {"clipproj_node"}
    missing_nodes = [key for key in sorted(required_nodes) if key in node_map and node_map[key].get("present") is False]
    if missing_nodes:
        errors.append("missing required custom-node roles: " + ", ".join(missing_nodes))

    optional_nodes = {"kj_nodes", "h3_turbo", "sol_attention", "block_cache"}
    unavailable_optional = [key for key in sorted(optional_nodes) if key in node_map and node_map[key].get("present") is False]
    if unavailable_optional:
        warnings.append("optional acceleration node roles unavailable: " + ", ".join(unavailable_optional) + "; use the compatibility workflow")


def assess_runtime_risk(report: dict[str, Any], plan: dict[str, Any] | None = None, *, require_audio: bool = True) -> dict[str, Any]:
    """Return ``ready``, ``caution`` or ``blocked`` with actionable evidence.

    The thresholds are deliberately asymmetric: low *available* RAM is a
    warning because a validated 8 GB laptop can still finish a run, while a
    nearly exhausted pagefile is a blocker because it previously caused
    ``hostbuf_file_reader_read failed`` and system-level paging failures.
    """

    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    recommendation = report.get("recommendation") if isinstance(report.get("recommendation"), dict) else {}
    if recommendation.get("name") in {"no-nvidia-cuda", "blocked-or-alternative"}:
        errors.append("doctor recommendation does not support the local low-VRAM CUDA route")

    gpus = report.get("gpus") if isinstance(report.get("gpus"), list) else []
    total_vram = _max_value(gpus, "vram_total_gb")
    free_vram = _max_value(gpus, "vram_free_gb")
    checks["vram_total_gb"] = total_vram
    checks["vram_free_gb"] = free_vram
    if total_vram is None or total_vram < 5.5:
        errors.append("reported VRAM is below the experimental 6 GB floor")
    elif total_vram < 7.5:
        warnings.append("6 GB-class VRAM is an experimental route; use 608x352, 4 steps, low-VRAM offload, and a generous time budget")
    elif free_vram is not None and free_vram < 0.5:
        errors.append(f"currently free VRAM is only {free_vram:.2f} GB")
    elif free_vram is not None and free_vram < 1.5:
        warnings.append(f"currently free VRAM is only {free_vram:.2f} GB; close other GPU jobs before queueing")

    memory = report.get("system_memory") if isinstance(report.get("system_memory"), dict) else {}
    total_ram = _number(memory.get("total_gb"))
    available_ram = _number(memory.get("available_gb"))
    available_pagefile = _number(memory.get("page_file_available_gb"))
    checks.update({
        "ram_total_gb": total_ram,
        "ram_available_gb": available_ram,
        "page_file_available_gb": available_pagefile,
    })
    if total_ram is not None and total_ram < 16:
        errors.append(f"system RAM is only {total_ram:.1f} GB; the tested route expects at least 16 GB")
    elif total_vram is not None and total_vram < 7.5 and total_ram is not None and total_ram < 31:
        errors.append(f"6 GB-class VRAM needs about 32 GB system RAM for the community-tested offload route; only {total_ram:.1f} GB was reported")
    elif total_vram is not None and 7.5 <= total_vram < 10 and total_ram is not None and total_ram < 24:
        warnings.append("8 GB W4A8 with 16 GB system RAM is validated on RTX 3060 Ti; use the 640x352/4-step fast baseline and do not generalize this result to other GPUs")
    if available_ram is not None and available_ram < 2:
        errors.append(f"currently available RAM is only {available_ram:.2f} GB")
    elif available_ram is not None and available_ram < 6:
        warnings.append(f"currently available RAM is only {available_ram:.2f} GB; model offload may be slow")
    if available_pagefile is not None:
        if available_pagefile < 2:
            errors.append(f"available Windows pagefile is only {available_pagefile:.2f} GB; do not start a long H3 run")
        elif available_pagefile < 8:
            warnings.append(f"available Windows pagefile is only {available_pagefile:.2f} GB; host-buffer paging may fail")

    disk = report.get("disk") if isinstance(report.get("disk"), dict) else {}
    free_disk = _number(disk.get("free_gb"))
    checks["disk_free_gb"] = free_disk
    if free_disk is not None and free_disk < 35:
        errors.append(f"free disk is only {free_disk:.1f} GB; keep at least 35 GB for models, cache and temporary files")

    gpu_processes = report.get("gpu_processes")
    if isinstance(gpu_processes, list):
        external_processes = _external_gpu_processes(gpu_processes)
        checks["gpu_process_count"] = len(external_processes)
        checks["gpu_process_total_count"] = len(gpu_processes)
        if external_processes:
            warnings.append(
                f"{len(external_processes)} external GPU process(es) were detected; their VRAM use can change the result"
            )

    _append_missing_asset_checks(report, errors, warnings, require_audio)

    compatibility = report.get("runtime_compatibility") if isinstance(report.get("runtime_compatibility"), dict) else {}
    errors.extend(str(item) for item in compatibility.get("errors", []) if item)
    warnings.extend(str(item) for item in compatibility.get("warnings", []) if item)

    if plan and isinstance(plan.get("warnings"), list):
        plan_warnings = [str(item) for item in plan["warnings"]]
        if any("OOM" in item or "page" in item.lower() for item in plan_warnings):
            warnings.extend(plan_warnings)

    status = "blocked" if errors else ("caution" if warnings else "ready")
    return {
        "schema_version": 1,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "require_audio": require_audio,
    }


def refresh_runtime(report: dict[str, Any]) -> dict[str, Any]:
    """Refresh volatile resource fields without rescanning models or nodes."""
    try:
        import h3_doctor
    except ImportError as exc:  # pragma: no cover - only occurs in a broken install
        raise RuntimeError(f"cannot import h3_doctor for runtime refresh: {exc}") from exc
    refreshed = copy.deepcopy(report)
    refreshed["gpus"] = h3_doctor.nvidia_gpus()
    refreshed["gpu_processes"] = h3_doctor.nvidia_processes()
    refreshed["system_memory"] = h3_doctor.system_memory()
    root = refreshed.get("root")
    if root:
        refreshed["disk"] = h3_doctor.path_disk(Path(str(root)))
    return refreshed


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doctor-json", help="existing h3_doctor JSON report")
    parser.add_argument("--plan-json", help="optional h3_plan JSON report")
    parser.add_argument("--refresh-runtime", action="store_true", help="refresh RAM/VRAM/pagefile/processes without rescanning assets")
    parser.add_argument("--require-audio", action="store_true", help="require an audio VAE asset in the doctor report")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if not args.doctor_json:
            raise ValueError("--doctor-json is required; run h3_doctor.py --json first")
        report = _load_json(args.doctor_json)
        if args.refresh_runtime:
            report = refresh_runtime(report)
        plan = _load_json(args.plan_json) if args.plan_json else None
        result = assess_runtime_risk(report, plan, require_audio=args.require_audio)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Preflight: {result['status']}")
            for item in result["errors"]:
                print("ERROR: " + item)
            for item in result["warnings"]:
                print("WARNING: " + item)
        return 0 if result["status"] != "blocked" else 2
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
