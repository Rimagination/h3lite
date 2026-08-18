#!/usr/bin/env python3
"""One-shot status and output verification for a queued ComfyUI prompt.

Run this command repeatedly from an agent instead of holding a foreground
process open for the full low-VRAM generation. It performs one HTTP request
cycle and exits quickly, so the caller can provide progress updates without
being killed by a terminal command timeout.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from h3_generate import (
    execution_error,
    execution_elapsed_seconds,
    default_run_root,
    find_manifest,
    history_record,
    json_request,
    resolve_output_paths,
    update_manifest,
    verify_outputs,
)
from h3_plan import record_timing_sample


def analyze_frame_samples(samples: list[bytes]) -> dict[str, object]:
    """Classify sampled grayscale frames without requiring Pillow or NumPy."""
    usable = [sample for sample in samples if sample]
    if not usable:
        return {"classification": "unavailable", "sample_count": 0, "max_mean_delta": None}
    means = [sum(sample) / len(sample) for sample in usable]
    deltas: list[float] = []
    for previous, current in zip(usable, usable[1:]):
        size = min(len(previous), len(current))
        if size:
            deltas.append(sum(abs(previous[index] - current[index]) for index in range(size)) / size)
    max_delta = max(deltas, default=0.0)
    if max(means) <= 3:
        classification = "black_or_flat"
    elif max_delta < 1.0:
        classification = "static_or_nearly_static"
    else:
        classification = "dynamic"
    return {
        "classification": classification,
        "sample_count": len(usable),
        "mean_brightness": [round(value, 2) for value in means],
        "mean_deltas": [round(value, 2) for value in deltas],
        "max_mean_delta": round(max_delta, 2),
    }


def analyze_rgb_frame_samples(samples: list[bytes], size: int = 64) -> dict[str, object]:
    """Detect the high-chroma spatial discontinuity seen in broken H3 decodes."""
    metrics: list[dict[str, float]] = []
    for sample in samples:
        if len(sample) != size * size * 3:
            continue
        pixels = [sample[index : index + 3] for index in range(0, len(sample), 3)]
        extreme_chroma = sum(
            1 for pixel in pixels if max(pixel) - min(pixel) >= 160 and max(pixel) >= 220
        ) / len(pixels)
        saturated = sum(1 for pixel in pixels if max(pixel) - min(pixel) >= 100) / len(pixels)
        neighbor_deltas: list[float] = []
        for y in range(size):
            for x in range(size - 1):
                left, right = pixels[y * size + x], pixels[y * size + x + 1]
                neighbor_deltas.append(sum(abs(left[channel] - right[channel]) for channel in range(3)) / 3)
        for y in range(size - 1):
            for x in range(size):
                top, bottom = pixels[y * size + x], pixels[(y + 1) * size + x]
                neighbor_deltas.append(sum(abs(top[channel] - bottom[channel]) for channel in range(3)) / 3)
        abrupt = sum(value >= 70 for value in neighbor_deltas) / len(neighbor_deltas)
        metrics.append(
            {
                "extreme_chroma_fraction": extreme_chroma,
                "saturated_fraction": saturated,
                "abrupt_neighbor_fraction": abrupt,
            }
        )
    suspicious = sum(
        item["extreme_chroma_fraction"] >= 0.06
        and item["saturated_fraction"] >= 0.20
        and item["abrupt_neighbor_fraction"] >= 0.08
        for item in metrics
    )
    return {
        "classification": "suspected_mosaic" if suspicious >= 2 else "coherent_color",
        "sample_count": len(metrics),
        "suspicious_sample_count": suspicious,
        "frame_metrics": [
            {key: round(value, 3) for key, value in item.items()} for item in metrics
        ],
    }


def extract_gray_frame(path: Path, timestamp: float, size: int = 64) -> bytes | None:
    executable = shutil.which("ffmpeg")
    if not executable or not path.exists():
        return None
    command = [
        executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, timestamp):.3f}",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={size}:{size}:force_original_aspect_ratio=decrease,pad={size}:{size}:(ow-iw)/2:(oh-ih)/2,format=gray",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout if completed.returncode == 0 and completed.stdout else None


def extract_rgb_frame(path: Path, timestamp: float, size: int = 64) -> bytes | None:
    executable = shutil.which("ffmpeg")
    if not executable or not path.exists():
        return None
    command = [
        executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, timestamp):.3f}",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={size}:{size}:force_original_aspect_ratio=decrease,pad={size}:{size}:(ow-iw)/2:(oh-ih)/2,format=rgb24",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout if completed.returncode == 0 and completed.stdout else None


def dynamic_video_quality(path: Path, duration: float | None) -> dict[str, object]:
    if duration is None or duration <= 0:
        return {"classification": "unavailable", "error": "video duration is unavailable"}
    timestamps = [0.0, max(0.01, duration / 2), max(0.01, duration - 0.05)]
    samples = [extract_gray_frame(path, timestamp) for timestamp in timestamps]
    rgb_samples = [extract_rgb_frame(path, timestamp) for timestamp in timestamps]
    if any(sample is None for sample in samples) or any(sample is None for sample in rgb_samples):
        return {"classification": "unavailable", "error": "ffmpeg could not extract all QA frames", "timestamps": timestamps}
    result = analyze_frame_samples([sample for sample in samples if sample is not None])
    color_result = analyze_rgb_frame_samples([sample for sample in rgb_samples if sample is not None])
    result["motion_classification"] = result["classification"]
    result["color_qa"] = color_result
    if color_result["classification"] == "suspected_mosaic":
        result["classification"] = "suspected_mosaic"
    result["timestamps"] = timestamps
    return result


def _frame_similarity(first: bytes | None, second: bytes | None) -> float | None:
    if not first or not second:
        return None
    size = min(len(first), len(second))
    if size <= 0:
        return None
    difference = sum(abs(first[index] - second[index]) for index in range(size)) / size
    return round(max(0.0, min(1.0, 1.0 - difference / 255.0)), 3)


def _similarity_band(value: float | None) -> str:
    if value is None:
        return "unavailable"
    if value >= 0.80:
        return "high"
    if value >= 0.50:
        return "medium"
    return "low"


def _load_anchor_sheet(manifest: dict[str, object], manifest_path: Path | None) -> dict[str, object]:
    path_value = manifest.get("anchor_sheet_path")
    if path_value:
        path = Path(str(path_value)).expanduser()
        if not path.is_absolute() and manifest_path is not None:
            path = manifest_path.parent / path
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
        except (OSError, json.JSONDecodeError):
            pass
    value = manifest.get("anchor_sheet")
    return value if isinstance(value, dict) else {}


def _reference_path(reference: dict[str, object], comfyui: Path | None) -> Path | None:
    source = reference.get("source")
    if not source and isinstance(reference.get("staged"), (str, Path)):
        source = reference.get("staged")
    if source:
        path = Path(str(source)).expanduser()
        if path.exists():
            return path
    input_name = reference.get("input_name")
    if comfyui is not None and input_name:
        candidate = comfyui / "input" / str(input_name)
        if candidate.exists():
            return candidate
    return None


def anchor_consistency_quality(
    path: Path,
    duration: float | None,
    anchor_sheet: dict[str, object],
    comfyui: Path | None = None,
) -> dict[str, object]:
    """Run an advisory temporal/reference image check; never acts as face recognition."""
    if not anchor_sheet:
        return {"classification": "not_requested"}
    identity_sensitive = bool(anchor_sheet.get("identity_sensitive"))
    multi_shot = bool(anchor_sheet.get("multi_shot"))
    references = anchor_sheet.get("references")
    references = references if isinstance(references, list) else []
    if not identity_sensitive and not multi_shot and not references:
        return {"classification": "not_requested"}
    if duration is None or duration <= 0:
        return {"classification": "unavailable", "error": "video duration is unavailable"}
    first_timestamp = 0.0
    last_timestamp = max(0.01, duration - 0.05)
    middle_timestamp = max(0.01, duration / 2)
    samples = {
        "video_first": extract_gray_frame(path, first_timestamp),
        "video_middle": extract_gray_frame(path, middle_timestamp),
        "video_last": extract_gray_frame(path, last_timestamp),
    }
    temporal = {
        "first_to_middle": _frame_similarity(samples["video_first"], samples["video_middle"]),
        "middle_to_last": _frame_similarity(samples["video_middle"], samples["video_last"]),
        "first_to_last": _frame_similarity(samples["video_first"], samples["video_last"]),
    }
    report: dict[str, object] = {
        "classification": "advisory_anchor_check",
        "acceptance": "manual_review" if identity_sensitive or multi_shot else "advisory",
        "identity_sensitive": identity_sensitive,
        "multi_shot": multi_shot,
        "temporal_similarity": temporal,
        "temporal_bands": {key: _similarity_band(value) for key, value in temporal.items()},
        "reference_comparisons": [],
        "note": "Pixel similarity is a continuity signal, not face recognition; review identity, wardrobe, markings, and composition manually.",
    }
    comparisons: list[dict[str, object]] = []
    for reference in references:
        if not isinstance(reference, dict):
            continue
        role = str(reference.get("role", "reference"))
        reference_path = _reference_path(reference, comfyui)
        if reference_path is None:
            comparisons.append({"role": role, "path": None, "similarity": None, "band": "unavailable"})
            continue
        reference_frame = extract_gray_frame(reference_path, 0.0)
        video_frame = samples["video_first" if role == "first_frame" else "video_last"]
        similarity = _frame_similarity(reference_frame, video_frame)
        comparisons.append(
            {
                "role": role,
                "path": str(reference_path),
                "similarity": similarity,
                "band": _similarity_band(similarity),
            }
        )
    report["reference_comparisons"] = comparisons
    report["sample_count"] = sum(sample is not None for sample in samples.values())
    return report


def compact_result(result: dict[str, object]) -> dict[str, object]:
    """Remove ComfyUI's large history graph from normal agent-facing output."""
    state = str(result.get("state", "unknown"))
    complete = state in {"success", "verification_failed", "error"}
    visible: dict[str, object] = {
        key: value
        for key, value in result.items()
        if key not in {"history", "status", "outputs"}
    }
    if state == "running_or_queued":
        visible["state"] = "queued_or_running"
    visible["complete"] = complete
    visible["ok"] = bool(result.get("ok")) if complete else False
    outputs = result.get("outputs")
    if isinstance(outputs, list):
        compact_outputs: list[dict[str, object]] = []
        for item in outputs:
            if not isinstance(item, dict):
                continue
            compact_outputs.append(
                {
                    key: item.get(key)
                    for key in (
                        "path",
                        "exists",
                        "has_video",
                        "has_audio",
                        "video_width",
                        "video_height",
                        "duration_seconds",
                        "frame_count",
                        "fps",
                        "duration_ok",
                        "frames_ok",
                        "fps_ok",
                        "audio_ok",
                        "verified",
                        "verification_error",
                        "dynamic_qa",
                        "anchor_qa",
                    )
                    if key in item
                }
            )
        visible["outputs"] = compact_outputs
    return visible


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-id", required=True, help="ComfyUI prompt_id returned by h3_generate.py --queue-only")
    parser.add_argument("--base-url", default="http://127.0.0.1:8188", help="ComfyUI server URL")
    parser.add_argument("--output-dir", help="local ComfyUI output directory used for verification")
    parser.add_argument("--comfyui", help="ComfyUI root used to locate a bundled ffprobe")
    parser.add_argument("--run-manifest", help="specific h3lite run manifest to update and use for expected settings")
    parser.add_argument("--run-root", help="run-manifest root used to locate a manifest by prompt id")
    parser.add_argument("--expected-duration", type=float, help="expected video duration in seconds")
    parser.add_argument("--expected-frames", type=int, help="expected video frame count")
    parser.add_argument("--expected-fps", type=float, help="expected video FPS")
    parser.add_argument("--require-audio", action="store_true", help="fail verification when the MP4 has no audio stream")
    parser.add_argument("--dynamic-check", action="store_true", help="sample first/middle/last frames and reject static or black output")
    parser.add_argument("--anchor-check", dest="anchor_check", action="store_true", default=True, help="record advisory reference/continuity anchor QA")
    parser.add_argument("--skip-anchor-check", dest="anchor_check", action="store_false", help="skip advisory anchor QA")
    parser.add_argument("--compact", action="store_true", help="use the default compact result format")
    parser.add_argument("--verbose", action="store_true", help="include the full ComfyUI history graph in output")
    parser.add_argument("--watch", action="store_true", help="poll until the prompt completes")
    parser.add_argument("--watch-interval", type=float, default=20.0, help="seconds between --watch polls")
    parser.add_argument("--watch-timeout", type=float, default=3600.0, help="maximum seconds for --watch")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result")
    return parser.parse_args()


def status_once(args: argparse.Namespace) -> dict[str, object]:
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None
    run_root = Path(args.run_root).expanduser().resolve() if args.run_root else default_run_root(output_dir)
    manifest_path = Path(args.run_manifest).expanduser().resolve() if args.run_manifest else find_manifest(run_root, args.prompt_id)
    manifest: dict[str, object] = {}
    if manifest_path and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
    if output_dir is None and manifest.get("output_dir"):
        output_dir = Path(str(manifest["output_dir"])).expanduser().resolve()
    comfyui_value = getattr(args, "comfyui", None) or manifest.get("comfyui")
    comfyui = Path(str(comfyui_value)).expanduser().resolve() if comfyui_value else None
    if comfyui is None and output_dir is not None and output_dir.name.lower() == "output":
        comfyui = output_dir.parent
    settings = manifest.get("effective_settings") if isinstance(manifest.get("effective_settings"), dict) else {}
    expected_duration = args.expected_duration if args.expected_duration is not None else settings.get("expected_duration_seconds")
    expected_frames = args.expected_frames if args.expected_frames is not None else settings.get("length")
    expected_fps = args.expected_fps if args.expected_fps is not None else settings.get("fps")
    require_audio = args.require_audio or manifest.get("audio_policy") == "require"
    anchor_sheet = _load_anchor_sheet(manifest, manifest_path)
    history = json_request(args.base_url, f"/history/{args.prompt_id}")
    record = history_record(history, args.prompt_id)
    if record is None:
        result = {"ok": False, "complete": False, "prompt_id": args.prompt_id, "state": "running_or_queued"}
        update_manifest(manifest_path, {"state": "running", "last_checked_at_utc": datetime.now(timezone.utc).isoformat()})
    else:
        error = execution_error(record)
        status = record.get("status") if isinstance(record, dict) else None
        if error:
            result = {"ok": False, "complete": True, "prompt_id": args.prompt_id, "state": "error", "error": error, "history": record}
            update_manifest(manifest_path, {"state": "failed", "error": error})
        elif isinstance(status, dict) and status.get("completed") is True:
            paths = resolve_output_paths(record, output_dir)
            outputs = verify_outputs(
                paths,
                expected_duration=float(expected_duration) if expected_duration is not None else None,
                expected_frames=int(expected_frames) if expected_frames is not None else None,
                expected_fps=float(expected_fps) if expected_fps is not None else None,
                require_audio=require_audio,
                comfyui=comfyui,
            )
            if args.dynamic_check:
                for item in outputs:
                    if item.get("has_video") and item.get("duration_seconds") is not None:
                        qa = dynamic_video_quality(Path(str(item["path"])), float(item["duration_seconds"]))
                        item["dynamic_qa"] = qa
                        item["verified"] = bool(item.get("verified") and qa.get("classification") == "dynamic")
            anchor_reports: list[dict[str, object]] = []
            anchor_check = getattr(args, "anchor_check", True)
            if anchor_check and anchor_sheet:
                for item in outputs:
                    if not item.get("has_video") or item.get("duration_seconds") is None:
                        continue
                    qa = anchor_consistency_quality(
                        Path(str(item["path"])),
                        float(item["duration_seconds"]),
                        anchor_sheet,
                        comfyui,
                    )
                    item["anchor_qa"] = qa
                    anchor_reports.append({"path": item.get("path"), **qa})
            outputs_ok = bool(outputs) and all(item.get("verified") is True for item in outputs)
            state = "success" if outputs_ok else "verification_failed"
            elapsed_seconds = execution_elapsed_seconds(record)
            result = {
                "ok": outputs_ok,
                "complete": True,
                "prompt_id": args.prompt_id,
                "state": state,
                "elapsed_seconds": elapsed_seconds,
                "expected_duration_seconds": expected_duration,
                "expected_frames": expected_frames,
                "expected_fps": expected_fps,
                "audio_policy": manifest.get("audio_policy", "require" if require_audio else "allow"),
                "require_audio": require_audio,
                "dynamic_check": args.dynamic_check,
                "anchor_check": anchor_check,
                "anchor_qa": anchor_reports,
                "outputs": outputs,
                "history": record,
            }
            update_manifest(
                manifest_path,
                {
                    "state": state,
                    "elapsed_seconds": elapsed_seconds,
                    "outputs": outputs,
                    "anchor_qa": anchor_reports,
                },
            )
            if outputs_ok:
                record_timing_sample(run_root, manifest_path, elapsed_seconds)
        else:
            status_name = status.get("status_str") if isinstance(status, dict) else None
            state = "running" if status_name in {"running", "executing"} else "queued"
            result = {"ok": False, "complete": False, "prompt_id": args.prompt_id, "state": state}
            update_manifest(manifest_path, {"state": "running" if state == "running" else "queued"})
    return result


def _print_result(result: dict[str, object], args: argparse.Namespace) -> int:
    visible = result if args.verbose else compact_result(result)
    if args.json:
        print(json.dumps(visible, ensure_ascii=False, indent=2))
    else:
        print(f"{visible.get('state', 'unknown')}: {args.prompt_id}")
        for item in visible.get("outputs", []):
            print(
                f"Output: {item.get('path')} | {item.get('video_width', '?')}x{item.get('video_height', '?')} | "
                f"duration={item.get('duration_seconds', '?')}s | audio={item.get('has_audio', 'unknown')} | verified={item.get('verified', 'unknown')}"
            )
    return 0 if visible.get("ok") or not visible.get("complete", True) else 1


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args()
    try:
        if args.watch:
            started = time.monotonic()
            last_state = None
            while True:
                result = status_once(args)
                if not args.json and result.get("state") != last_state:
                    print(f"{result.get('state', 'unknown')}: {args.prompt_id}")
                    last_state = result.get("state")
                if result.get("complete"):
                    return _print_result(result, args)
                if time.monotonic() - started >= max(1.0, args.watch_timeout):
                    timeout_result = {
                        "ok": False,
                        "complete": True,
                        "prompt_id": args.prompt_id,
                        "state": "watch_timeout",
                        "error": f"watch exceeded {args.watch_timeout:.0f} seconds",
                    }
                    return _print_result(timeout_result, args)
                time.sleep(max(1.0, args.watch_interval))
        return _print_result(status_once(args), args)
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "complete": True, "prompt_id": args.prompt_id, "state": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
