#!/usr/bin/env python3
"""Choose a MiniMax H3 route from hardware, visual intent, time budget, and paths.

This planner is read-only. It returns a conservative plan for the bundled W4A8
ComfyUI graph; it does not install anything, download weights, or queue a job.
Time values are ranges, not promises. The first run can be slower because CUDA
kernels compile and low-VRAM models move between system RAM and VRAM.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import statistics
import sys
from typing import Any


ALIGNMENT = 32
BASE_PIXELS = 640 * 352
BASE_FRAMES = 124
TIMING_HISTORY_LIMIT = 8

ASPECT_RATIOS = {
    "square": (1, 1),
    "portrait": (9, 16),
    "landscape": (16, 9),
}

QUALITY_BUCKETS = {
    # Mirrors ComfyUI's ResolutionSelector idea: aspect ratio + megapixels +
    # 32-pixel multiple. The explicit fast override stays conservative for
    # low-VRAM laptops; the bucket values are used for official-style canvases.
    "smoke": 0.20,
    "fast": 0.25,
    "official": 0.40,
    "balanced": 0.40,
    "quality": 0.50,
}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def timing_key(
    profile: str,
    resolution: dict[str, int],
    frames: int,
    fps: float,
    steps: int,
    variant: str | None = None,
    reference_mode: str = "T2VA",
) -> str:
    """Return a stable key for empirical timings from comparable runs."""
    parts = [
            str(profile),
            f"{int(resolution['width'])}x{int(resolution['height'])}",
            str(int(frames)),
            f"{float(fps):g}",
            str(int(steps)),
    ]
    route = str(reference_mode or "T2VA").upper()
    if route != "T2VA":
        parts.append(route)
    if variant:
        parts.append(str(variant))
    return "|".join(parts)


def timing_variant(settings: dict[str, Any]) -> str | None:
    """Separate experimental LoRA/shift/cache timings from the default route."""
    lora = str(settings.get("lora_name") or "")
    block_cache = settings.get("block_cache")
    shift_video = _as_float(settings.get("shift_video"), 12.0)
    shift_audio = _as_float(settings.get("shift_audio"), 3.0)
    default_lora = "minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors"
    if (not lora or lora == default_lora) and block_cache is not False and shift_video == 12.0 and shift_audio == 3.0:
        return None
    lora_tag = Path(lora).stem if lora else "unknown-lora"
    return f"lora={lora_tag};cache={int(bool(block_cache))};sv={shift_video:g};sa={shift_audio:g}"


def load_timing_history(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {"schema_version": 1, "entries": {}}
    timing_path = Path(path).expanduser()
    if not timing_path.exists():
        return {"schema_version": 1, "entries": {}}
    try:
        value = json.loads(timing_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "entries": {}}
    if not isinstance(value, dict) or not isinstance(value.get("entries"), dict):
        return {"schema_version": 1, "entries": {}}
    return value


def record_timing_sample(run_root: str | Path | None, manifest_path: str | Path | None, elapsed_seconds: float | None) -> Path | None:
    """Persist a small empirical timing cache without scanning old manifests."""
    if run_root is None or manifest_path is None or elapsed_seconds is None or elapsed_seconds <= 0:
        return None
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        settings = manifest.get("effective_settings") if isinstance(manifest.get("effective_settings"), dict) else {}
        required = (settings.get("width"), settings.get("height"), settings.get("length"), settings.get("fps"), settings.get("steps"))
        if any(value is None for value in required):
            return None
        profile = str(manifest.get("profile") or "fast")
        key = timing_key(
            profile,
            {"width": int(settings["width"]), "height": int(settings["height"])},
            int(settings["length"]),
            float(settings["fps"]),
            int(settings["steps"]),
            timing_variant(settings),
            str(settings.get("reference_mode") or "T2VA"),
        )
        root = Path(run_root).expanduser().resolve()
        timing_path = root / "_environment" / "timing.json"
        history = load_timing_history(timing_path)
        entries = history.setdefault("entries", {})
        entry = entries.setdefault(
            key,
            {
                "profile": profile,
                "width": int(settings["width"]),
                "height": int(settings["height"]),
                "length": int(settings["length"]),
                "fps": float(settings["fps"]),
                "steps": int(settings["steps"]),
                "reference_mode": str(settings.get("reference_mode") or "T2VA").upper(),
                "samples_seconds": [],
            },
        )
        samples = entry.setdefault("samples_seconds", [])
        sample_id = str(manifest.get("prompt_id") or manifest.get("manifest_path") or Path(manifest_path).resolve())
        sample_ids = entry.setdefault("sample_ids", [])
        if not isinstance(sample_ids, list):
            sample_ids = []
        if sample_id in sample_ids:
            return timing_path
        if samples and not sample_ids:
            sample_ids = [f"legacy-{index}" for index in range(len(samples))]
        samples.append(round(float(elapsed_seconds), 2))
        sample_ids.append(sample_id)
        entry["samples_seconds"] = samples[-TIMING_HISTORY_LIMIT:]
        entry["sample_ids"] = sample_ids[-TIMING_HISTORY_LIMIT:]
        entry["last_seconds"] = entry["samples_seconds"][-1]
        entry["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        history["schema_version"] = 1
        timing_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = timing_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(timing_path)
        return timing_path
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def empirical_estimate(
    timing: dict[str, Any] | None,
    key: str,
    fallback_lower: int,
    fallback_upper: int,
) -> tuple[int, int, int] | None:
    """Return a conservative range from recent successful runs, if available."""
    entries = timing.get("entries") if isinstance(timing, dict) else None
    entry = entries.get(key) if isinstance(entries, dict) else None
    samples = entry.get("samples_seconds") if isinstance(entry, dict) else None
    if not isinstance(samples, list):
        return None
    values = [_as_float(item) for item in samples]
    values = [value for value in values if value > 0]
    if not values:
        return None
    median = statistics.median(values)
    if len(values) == 1:
        lower = median * 0.75
        upper = median * 1.40
    else:
        lower = min(values) * 0.85
        upper = max(values) * 1.20
    lower_int = max(30, round(lower))
    upper_int = max(lower_int + 30, round(upper))
    return lower_int, upper_int, len(values)


def max_vram_gb(report: dict[str, Any]) -> float:
    values = [
        _as_float(gpu.get("vram_total_gb"))
        for gpu in report.get("gpus", [])
        if isinstance(gpu, dict) and gpu.get("vram_total_gb") is not None
    ]
    return max(values, default=0.0)


def hardware_tier(report: dict[str, Any]) -> str:
    vram = max_vram_gb(report)
    if vram < 5.5:
        return "blocked"
    if vram < 7.5:
        return "very-low"
    if vram < 10:
        return "low"
    if vram < 16:
        return "mid"
    return "high"


def parse_resolution(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*[xX×:]\s*(\d+)\s*", value or "")
    if not match:
        raise ValueError(f"resolution must look like WIDTHxHEIGHT, got {value!r}")
    width, height = int(match.group(1)), int(match.group(2))
    if width < 256 or height < 256:
        raise ValueError("resolution must be at least 256x256")
    aligned_width = width - width % ALIGNMENT
    aligned_height = height - height % ALIGNMENT
    if aligned_width < 256 or aligned_height < 256:
        raise ValueError("resolution becomes too small after model alignment")
    return aligned_width, aligned_height


def _orientation(value: str) -> str:
    normalized = (value or "landscape").strip().lower().replace("：", ":")
    aliases = {
        "横屏": "landscape",
        "landscape": "landscape",
        "16:9": "landscape",
        "宽屏": "landscape",
        "竖屏": "portrait",
        "portrait": "portrait",
        "9:16": "portrait",
        "方形": "square",
        "square": "square",
        "1:1": "square",
    }
    if normalized not in aliases:
        raise ValueError("aspect must be landscape/portrait/square or 16:9/9:16/1:1")
    return aliases[normalized]


def resolution_from_bucket(aspect: str, megapixels: float, multiple: int = ALIGNMENT) -> dict[str, int]:
    """Match ComfyUI's ResolutionSelector: aspect + MP target + aligned size."""
    orientation = _orientation(aspect)
    width_ratio, height_ratio = ASPECT_RATIOS[orientation]
    total_pixels = float(megapixels) * 1024 * 1024
    if total_pixels <= 0:
        raise ValueError("megapixels must be positive")
    scale = (total_pixels / (width_ratio * height_ratio)) ** 0.5
    width = round(width_ratio * scale / multiple) * multiple
    height = round(height_ratio * scale / multiple) * multiple
    return {"width": max(multiple, width), "height": max(multiple, height)}


def resolution_for(mode: str, tier: str, aspect: str) -> dict[str, int]:
    orientation = _orientation(aspect)
    if tier == "very-low":
        if orientation == "landscape":
            return {"width": 608, "height": 352}
        if orientation == "portrait":
            return {"width": 352, "height": 608}
        return {"width": 448, "height": 448}
    if tier == "low":
        if mode == "fast":
            if orientation == "landscape":
                return {"width": 640, "height": 352}
            if orientation == "portrait":
                return {"width": 352, "height": 640}
            return {"width": 512, "height": 512}
        # On 8 GB laptops, spend non-fast intent on more steps before canvas.
        # This keeps quality/balanced in the known-success envelope.
        return resolution_for("fast", tier, orientation)

    if mode == "fast":
        if orientation == "landscape":
            return {"width": 640, "height": 352}
        if orientation == "portrait":
            return {"width": 352, "height": 640}
        return {"width": 512, "height": 512}

    bucket = QUALITY_BUCKETS["quality" if mode == "quality" else "balanced"]
    return resolution_from_bucket(orientation, bucket, ALIGNMENT)


def _mode_settings(mode: str) -> dict[str, Any]:
    if mode == "fast":
        return {"steps": 4, "block_cache": True}
    if mode == "balanced":
        return {"steps": 6, "block_cache": False}
    if mode == "quality":
        return {"steps": 8, "block_cache": False}
    raise ValueError(f"unknown mode: {mode}")


def launch_profile_for_tier(tier: str) -> dict[str, Any]:
    """Choose launch flags from hardware pressure, not from model filename."""
    return {
        "lowvram": tier in {"very-low", "low"},
        "fast_disk": True,
        "reason": "8GB-or-less offload profile" if tier in {"very-low", "low"} else "normal VRAM profile",
    }


def _estimate_seconds(
    mode: str,
    tier: str,
    resolution: dict[str, int],
    frames: int,
    ram_gb: float,
) -> tuple[int, int]:
    # Operational ranges anchored to the validated RTX 4070 Laptop runs. They
    # intentionally stay broad and are reported as estimates, not guarantees.
    base_ranges = {
        "fast": (240, 420),
        "balanced": (300, 600),
        "quality": (480, 900),
    }
    lower, upper = base_ranges[mode]
    tier_factor = {"very-low": 1.40, "low": 1.0, "mid": 0.78, "high": 0.62, "blocked": 1.5}[tier]
    pixel_factor = (resolution["width"] * resolution["height"]) / BASE_PIXELS
    frame_factor = max(0.25, frames / BASE_FRAMES)
    ram_factor = 1.15 if ram_gb and ram_gb < 32 else 1.0
    factor = tier_factor * pixel_factor * frame_factor * ram_factor
    return max(30, round(lower * factor)), max(60, round(upper * factor))


def resolve_paths(
    install_mode: str,
    *,
    workspace: str | None = None,
    comfyui: str | None = None,
    dedicated_folder: str | None = None,
    output_dir: str | None = None,
) -> dict[str, str]:
    """Resolve the installation-target contract without creating directories."""
    mode = (install_mode or "reuse-existing").strip().lower()
    if mode == "reuse-existing":
        if not comfyui:
            raise ValueError("reuse-existing requires --comfyui or a discovered ComfyUI path")
        root = Path(comfyui).expanduser()
    elif mode == "current-project":
        if not workspace:
            raise ValueError("current-project requires --workspace")
        root = Path(workspace).expanduser() / ".h3lite" / "ComfyUI"
    elif mode == "dedicated-folder":
        selected = dedicated_folder or comfyui
        if not selected:
            raise ValueError("dedicated-folder requires --dedicated-folder or --comfyui")
        root = Path(selected).expanduser()
        if root.name.lower() != "comfyui":
            root = root / "ComfyUI"
    else:
        raise ValueError("install mode must be reuse-existing, current-project, or dedicated-folder")

    root = root.resolve()
    output = Path(output_dir).expanduser().resolve() if output_dir else root / "output"
    return {
        "comfyui": str(root),
        "models": str(root / "models"),
        "custom_nodes": str(root / "custom_nodes"),
        "output": str(output),
        "run_root": str(root / "user" / "h3lite_runs"),
    }


def _make_decision(mode: str, report: dict[str, Any], aspect: str, resolution: str | None) -> tuple[dict[str, Any], list[str]]:
    tier = hardware_tier(report)
    warnings: list[str] = []
    selected_resolution = resolution_for(mode, tier, aspect)
    if resolution:
        width, height = parse_resolution(resolution)
        selected_resolution = {"width": width, "height": height}
        if tier in {"very-low", "low"} and width * height > BASE_PIXELS:
            warnings.append("当前显存档位对显式高分辨率存在 OOM 或长时间 CPU 卸载风险。")
    settings = _mode_settings(mode)
    if tier == "blocked":
        warnings.append("显存低于约 6 GB，当前本地 H3 路线没有足够证据支持。")
    if tier == "very-low":
        warnings.append("6 GB 显存属于社区实跑支持的实验档，不是 H3 Lite 已验证档；默认从 608x352、4 步开始，并预留较长时间。")
        if mode != "fast":
            warnings.append("6 GB 实验档不自动提高分辨率；先完成 fast 基线，再逐项增加画布或步数。")
    if tier == "low" and mode == "quality":
        warnings.append("8 GB VRAM 下质量模式保留 640x352，以优先保证成功率；需要更大画布时应先确认时间和 OOM 风险。")
        warnings.append("当前质量模式仍使用 W4A8/4B 低显存模型，不等同于原生高精度 H3。")
    if mode != "fast":
        warnings.append("非 fast 模式会关闭 T8 Block Cache，并增加采样步数；预计耗时是范围估计。")
    return {
        "mode": mode,
        "resolution": selected_resolution,
        "steps": settings["steps"],
        "block_cache": settings["block_cache"],
        "workflow_template": "h3_w4a8_t2v",
        "hardware_tier": tier,
        "launch_profile": launch_profile_for_tier(tier),
    }, warnings


def _resolve_megapixel_override(
    *,
    aspect: str,
    megapixels: float | None,
    resolution: str | None,
) -> str | None:
    """Convert an explicit MP bucket into a concrete aligned resolution."""
    if resolution or megapixels is None:
        return resolution
    if megapixels <= 0:
        raise ValueError("megapixels must be positive")
    selected = resolution_from_bucket(aspect, megapixels, ALIGNMENT)
    return f"{selected['width']}x{selected['height']}"


def build_plan(
    report: dict[str, Any],
    *,
    mode: str = "auto",
    target_minutes: float | None = None,
    aspect: str = "landscape",
    video_seconds: float = 5.0,
    fps: float = 24.0,
    resolution: str | None = None,
    megapixels: float | None = None,
    paths: dict[str, str] | None = None,
    timing_file: str | Path | None = None,
    reference_mode: str = "T2VA",
) -> dict[str, Any]:
    """Return a conservative generation plan and alternatives."""
    requested_mode = (mode or "auto").lower()
    if requested_mode not in {"auto", "fast", "balanced", "quality"}:
        raise ValueError("mode must be auto, fast, balanced, or quality")
    if video_seconds <= 0 or fps <= 0:
        raise ValueError("video_seconds and fps must be positive")
    reference_route = str(reference_mode or "T2VA").upper()
    if reference_route not in {"T2VA", "I2VA", "FL2VA", "L2VA", "REF2VA"}:
        raise ValueError("reference_mode must be T2VA, I2VA, FL2VA, L2VA, or REF2VA")
    had_explicit_resolution = resolution is not None
    resolution = _resolve_megapixel_override(aspect=aspect, megapixels=megapixels, resolution=resolution)

    tier = hardware_tier(report)
    ram_gb = _as_float(report.get("system_memory", {}).get("total_gb"))
    frames = max(1, round(video_seconds * fps) + 4)
    timing_path = Path(timing_file).expanduser() if timing_file else None
    timing = load_timing_history(timing_path)

    def estimate_for(candidate: str, candidate_decision: dict[str, Any]) -> tuple[int, int, int, str, str]:
        fallback_lower, fallback_upper = _estimate_seconds(
            candidate,
            tier,
            candidate_decision["resolution"],
            frames,
            ram_gb,
        )
        candidate_key = timing_key(
            candidate,
            candidate_decision["resolution"],
            frames,
            fps,
            candidate_decision["steps"],
            reference_mode=reference_route,
        )
        calibrated = empirical_estimate(timing, candidate_key, fallback_lower, fallback_upper)
        if calibrated:
            return (*calibrated, "empirical", candidate_key)
        return fallback_lower, fallback_upper, 0, "heuristic-range", candidate_key

    candidates = ["fast", "balanced", "quality"]
    if requested_mode == "auto":
        if target_minutes is None:
            selected_mode = "fast"
        else:
            budget_seconds = target_minutes * 60
            selected_mode = "fast"
            for candidate in candidates:
                candidate_decision, _ = _make_decision(candidate, report, aspect, resolution)
                _, upper, _, _, _ = estimate_for(candidate, candidate_decision)
                if upper <= budget_seconds and tier != "blocked":
                    selected_mode = candidate
    else:
        selected_mode = requested_mode

    decision, warnings = _make_decision(selected_mode, report, aspect, resolution)
    lower, upper, sample_count, estimate_source, key = estimate_for(selected_mode, decision)
    budget_fit = target_minutes is None or upper <= target_minutes * 60
    if target_minutes is not None and not budget_fit:
        warnings.append(f"当前选档的预计上限约 {upper / 60:.1f} 分钟，超过 {target_minutes:.1f} 分钟预算。")
    if target_minutes is not None and target_minutes * 60 < lower:
        warnings.append("时间预算低于当前设备的保守下限；应切回 fast、缩短视频，或改用远程/API 后端。")

    alternatives: list[dict[str, Any]] = []
    for candidate in candidates:
        alt_decision, alt_warnings = _make_decision(candidate, report, aspect, resolution)
        alt_lower, alt_upper, _, _, _ = estimate_for(candidate, alt_decision)
        alternatives.append(
            {
                "mode": candidate,
                "resolution": alt_decision["resolution"],
                "steps": alt_decision["steps"],
                "block_cache": alt_decision["block_cache"],
                "estimate": {"lower_seconds": alt_lower, "upper_seconds": alt_upper},
                "warnings": alt_warnings,
            }
        )

    return {
        "schema_version": 1,
        "request": {
            "mode": requested_mode,
            "target_minutes": target_minutes,
            "aspect": _orientation(aspect),
            "megapixels": megapixels,
            "video_seconds": video_seconds,
            "fps": fps,
            "frames": frames,
            "reference_mode": reference_route,
        },
        "hardware": {
            "tier": tier,
            "vram_gb": max_vram_gb(report),
            "ram_gb": ram_gb,
            "recommended_profile": report.get("recommendation", {}).get("name"),
        },
        "paths": paths or {},
        "decision": {
            **decision,
            "budget_fit": budget_fit,
            "explicit_resolution": had_explicit_resolution,
            "explicit_megapixels": megapixels is not None,
            "confirmation_required": False,
            "reference_mode": reference_route,
        },
        "estimate": {
            "lower_seconds": lower,
            "upper_seconds": upper,
            "lower_minutes": round(lower / 60, 1),
            "upper_minutes": round(upper / 60, 1),
            "confidence": "empirical" if estimate_source == "empirical" else "heuristic-range",
            "source": estimate_source,
            "sample_count": sample_count,
            "timing_key": key,
            "cold_start_note": "首次运行、模型换入和 CUDA 编译可能超过上限；完成后以实际 elapsed_seconds 更新判断。",
        },
        "warnings": warnings,
        "alternatives": alternatives,
    }


def _doctor_report(args: argparse.Namespace) -> dict[str, Any]:
    if args.doctor_json:
        return json.loads(Path(args.doctor_json).expanduser().read_text(encoding="utf-8"))
    try:
        import h3_doctor
    except ImportError as exc:  # pragma: no cover - only occurs in a broken install
        raise RuntimeError(f"cannot import h3_doctor from {Path(__file__).parent}: {exc}") from exc
    doctor_args = argparse.Namespace(
        root=args.root,
        comfyui=args.comfyui,
        json=False,
        no_model_scan=args.no_model_scan,
        no_node_scan=args.no_node_scan,
    )
    return h3_doctor.build_report(doctor_args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doctor-json", help="existing h3_doctor JSON report")
    parser.add_argument("--root", help="disk/project root for the read-only doctor scan")
    parser.add_argument("--comfyui", help="existing ComfyUI directory")
    parser.add_argument("--install-mode", choices=["reuse-existing", "current-project", "dedicated-folder"], default="reuse-existing")
    parser.add_argument("--workspace", help="workspace used by current-project mode")
    parser.add_argument("--dedicated-folder", help="dedicated install parent or ComfyUI directory")
    parser.add_argument("--output-dir", help="optional output directory override")
    parser.add_argument("--mode", choices=["auto", "fast", "balanced", "quality"], default="auto")
    parser.add_argument("--target-minutes", type=float, help="maximum wall-clock budget for one generation")
    parser.add_argument("--aspect", default="landscape", help="landscape/portrait/square or 16:9/9:16/1:1")
    parser.add_argument("--resolution", help="explicit WIDTHxHEIGHT override; model alignment rounds down to 32")
    parser.add_argument("--megapixels", type=float, help="ComfyUI ResolutionSelector-style canvas target, e.g. 0.4 for 16:9 864x480")
    parser.add_argument("--video-seconds", type=float, default=5.0, help="requested clip duration")
    parser.add_argument("--fps", type=float, default=24.0, help="output video FPS")
    parser.add_argument("--no-model-scan", action="store_true")
    parser.add_argument("--no-node-scan", action="store_true")
    parser.add_argument("--report-file", help="also save the JSON plan for preflight reuse")
    parser.add_argument("--timing-file", help="optional empirical timing cache; defaults beside --doctor-json")
    parser.add_argument("--reference-mode", choices=["t2va", "i2va", "fl2va", "l2va", "ref2va"], default="t2va")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def print_human(plan: dict[str, Any]) -> None:
    decision = plan["decision"]
    estimate = plan["estimate"]
    resolution = decision["resolution"]
    print(f"Selected mode: {decision['mode']}")
    print(f"Resolution: {resolution['width']}x{resolution['height']} | steps={decision['steps']} | block_cache={decision['block_cache']}")
    print(f"Estimated generation time: {estimate['lower_minutes']:.1f}-{estimate['upper_minutes']:.1f} minutes ({estimate['confidence']})")
    if plan.get("paths"):
        print("ComfyUI: " + plan["paths"].get("comfyui", ""))
        print("Output: " + plan["paths"].get("output", ""))
    for warning in plan.get("warnings", []):
        print("WARNING: " + warning)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args()
    try:
        report = _doctor_report(args)
        discovered_comfyui = report.get("comfyui", {}).get("path") if isinstance(report.get("comfyui"), dict) else None
        paths = resolve_paths(
            args.install_mode,
            workspace=args.workspace,
            comfyui=args.comfyui or discovered_comfyui,
            dedicated_folder=args.dedicated_folder,
            output_dir=args.output_dir,
        )
        timing_file = args.timing_file
        if timing_file is None and args.doctor_json:
            timing_file = str(Path(args.doctor_json).expanduser().resolve().parent / "timing.json")
        plan = build_plan(
            report,
            mode=args.mode,
            target_minutes=args.target_minutes,
            aspect=args.aspect,
            video_seconds=args.video_seconds,
            fps=args.fps,
            resolution=args.resolution,
            megapixels=args.megapixels,
            paths=paths,
            timing_file=timing_file,
            reference_mode=args.reference_mode,
        )
        if args.report_file:
            plan_path = Path(args.report_file).expanduser().resolve()
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print_human(plan)
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
