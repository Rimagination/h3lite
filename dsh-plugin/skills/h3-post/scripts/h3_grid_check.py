#!/usr/bin/env python3
"""Screen an H3 video for fixed decoder-window grid seams.

Measures two independent signals at native resolution:
  1. mean absolute Rec.709 luma step at each pixel boundary;
  2. mean second-difference response (thin-line response) at each pixel.

Profiles are folded modulo 16/32/64/128/256. A decoder-window seam should recur
at the same coordinates in most frames, especially modulo 128, instead of moving
with the characters. This is a screening measurement, not a same-latent VAE A/B
proof.

Usage:
  python h3_grid_check.py --video output/shot.mp4 --comfyui E:/MiniMax-H3/ComfyUI
  python h3_grid_check.py --video shot.mp4 --period 128 --fail-on-suspected --json
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PERIODS = (16, 32, 64, 128, 256)
DEFAULT_PERIOD = 128


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_ffmpeg(args: argparse.Namespace, comfyui: Path | None) -> Path:
    candidates = [args.ffmpeg, os.environ.get("H3LITE_FFMPEG")]
    if comfyui:
        candidates.extend([comfyui / "ffmpeg.exe", comfyui / "bin" / "ffmpeg.exe", comfyui / "ffmpeg" / "bin" / "ffmpeg.exe"])
    which = shutil.which("ffmpeg")
    if which:
        candidates.append(which)
    for value in candidates:
        if value and Path(value).is_file():
            return Path(value)
    raise FileNotFoundError("ffmpeg not found; pass --ffmpeg or --comfyui")


def _resolve_ffprobe(args: argparse.Namespace, comfyui: Path | None) -> Path:
    candidates = [args.ffprobe, os.environ.get("H3LITE_FFPROBE")]
    if comfyui:
        candidates.extend([comfyui / "ffprobe.exe", comfyui / "bin" / "ffprobe.exe", comfyui / "ffmpeg" / "bin" / "ffprobe.exe"])
    which = shutil.which("ffprobe")
    if which:
        candidates.append(which)
    for value in candidates:
        if value and Path(value).is_file():
            return Path(value)
    raise FileNotFoundError("ffprobe not found; pass --ffprobe or --comfyui")


def _probe(ffprobe: Path, video: Path) -> dict[str, Any]:
    raw = subprocess.check_output(
        [str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]
    )
    return json.loads(raw.decode("utf-8", errors="replace"))


def _read_exact(stream, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _stats(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p10": float(np.percentile(values, 10)),
        "p90": float(np.percentile(values, 90)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def _period_metrics(profile: np.ndarray, period: int, coordinate_offset: int) -> dict[str, Any]:
    coordinates = np.arange(profile.shape[1]) + coordinate_offset
    seam_mask = coordinates % period == 0
    if not np.any(seam_mask):
        return {"available": False}
    per_frame_seam = profile[:, seam_mask].mean(axis=1)
    per_frame_all = profile.mean(axis=1)
    per_frame_ratio = per_frame_seam / np.maximum(per_frame_all, 1e-6)
    mean_profile = profile.mean(axis=0)
    seam_mean = float(mean_profile[seam_mask].mean())
    all_mean = float(mean_profile.mean())
    adjacent = np.zeros(profile.shape[1], dtype=bool)
    for index in np.flatnonzero(seam_mask):
        adjacent[max(0, index - 2) : min(profile.shape[1], index + 3)] = True
    adjacent[seam_mask] = False
    adjacent_mean = float(mean_profile[adjacent].mean()) if np.any(adjacent) else all_mean
    return {
        "available": True,
        "period_pixels": period,
        "seam_coordinates": [int(value) for value in coordinates[seam_mask]],
        "mean_seam_strength_8bit": seam_mean,
        "mean_all_position_strength_8bit": all_mean,
        "ratio_to_all_positions": seam_mean / max(all_mean, 1e-6),
        "ratio_to_adjacent_positions": seam_mean / max(adjacent_mean, 1e-6),
        "per_frame_ratio_to_all_positions": _stats(per_frame_ratio),
        "fraction_frames_ratio_above_1": float(np.mean(per_frame_ratio > 1.0)),
        "fraction_frames_ratio_above_1_05": float(np.mean(per_frame_ratio > 1.05)),
    }


def _fold_metrics(profile: np.ndarray, period: int, coordinate_offset: int) -> dict[str, Any]:
    coordinates = np.arange(profile.shape[1]) + coordinate_offset
    bins = coordinates % period
    sums = np.zeros(period, dtype=np.float64)
    counts = np.zeros(period, dtype=np.int64)
    np.add.at(sums, bins, profile.mean(axis=0))
    np.add.at(counts, bins, 1)
    fold = sums / np.maximum(counts, 1)
    median = float(np.median(fold))
    top = np.argsort(fold)[::-1][:8]
    return {
        "values_8bit": [round(float(value), 6) for value in fold],
        "peak_modulo": int(top[0]),
        "peak_ratio_to_median": float(fold[top[0]] / max(median, 1e-6)),
        "main_grid_modulo_0_ratio": float(fold[0] / max(median, 1e-6)),
        "half_shift_modulo_ratio": float(fold[period // 2] / max(median, 1e-6)),
        "top_moduli": [
            {
                "modulo": int(index),
                "strength_8bit": round(float(fold[index]), 6),
                "ratio_to_median": round(float(fold[index] / max(median, 1e-6)), 6),
            }
            for index in top
        ],
    }


def _font(size: int = 14):
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\arial.ttf"):
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _profile_plot(metrics: dict[str, Any], period: int, width: int, height: int, out: Path) -> None:
    W, H = 1100, 520
    sheet = Image.new("RGB", (W, H), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    font = _font(14)
    draw.text((16, 12), f"grid profile | period {period}px | {width}x{height}", fill=(240, 220, 150), font=font)

    panels = [
        ("x step", metrics["x_step"]["mean_profile"], width - 1, 1),
        ("y step", metrics["y_step"]["mean_profile"], height - 1, 1),
        ("x line", metrics["x_line"]["mean_profile"], width, 0),
        ("y line", metrics["y_line"]["mean_profile"], height, 0),
    ]
    top = 44
    panel_h = 105
    for index, (name, values, count, offset) in enumerate(panels):
        y0 = top + index * (panel_h + 10)
        draw.text((16, y0), name, fill=(200, 220, 255), font=font)
        arr = np.asarray(values, dtype=np.float64)
        if arr.size < 2:
            continue
        peak = max(float(arr.max()), 1e-6)
        points = []
        for x, value in enumerate(arr):
            px = 90 + int(x * (W - 120) / max(arr.size - 1, 1))
            py = y0 + 18 + int((panel_h - 24) * (1.0 - value / peak))
            points.append((px, py))
        draw.line(points, fill=(120, 220, 160), width=1)
        for coordinate in range(0, count + offset, period):
            px = 90 + int((coordinate - offset) * (W - 120) / max(arr.size - 1, 1))
            draw.line([(px, y0 + 18), (px, y0 + panel_h - 2)], fill=(230, 90, 90), width=1)
        draw.text((16, y0 + panel_h - 2), f"peak {peak:.1f}", fill=(150, 150, 150), font=font)
    draw.text((16, H - 22), "red = period boundaries; green = mean profile", fill=(150, 150, 150), font=font)
    sheet.save(out)


def _overlay(frame: np.ndarray, period: int, frame_index: int, out: Path) -> None:
    image = Image.fromarray(frame, "RGB").convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for x in range(0, image.width, period):
        draw.line([(x, 0), (x, image.height)], fill=(255, 40, 40, 110), width=1)
    for y in range(0, image.height, period):
        draw.line([(0, y), (image.width, y)], fill=(255, 40, 40, 110), width=1)
    composed = Image.alpha_composite(image, overlay).convert("RGB")
    dr = ImageDraw.Draw(composed)
    dr.text((12, 12), f"frame {frame_index} | period {period}px", fill=(255, 230, 120), font=_font(18))
    composed.save(out)


def _analyse(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    video = Path(args.video).expanduser().resolve()
    if not video.is_file():
        print(f"ERROR: video not found: {video}", file=sys.stderr)
        return {}, 2
    comfyui = Path(args.comfyui).expanduser().resolve() if args.comfyui else None
    ffmpeg = _resolve_ffmpeg(args, comfyui)
    ffprobe = _resolve_ffprobe(args, comfyui)
    metadata = _probe(ffprobe, video)
    streams = metadata.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        print("ERROR: no video stream", file=sys.stderr)
        return {}, 2
    width, height = int(video_stream["width"]), int(video_stream["height"])
    frame_count = int(video_stream.get("nb_frames") or 0)
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (video.parent / f"{video.stem}_grid_qa")
    out_dir.mkdir(parents=True, exist_ok=True)
    period = int(args.period)
    periods = sorted({int(value) for value in str(args.periods).split(",") if value.strip()} | {period})

    command = [
        str(ffmpeg), "-v", "error", "-i", str(video), "-an",
        "-vf", "format=rgb24", "-fps_mode", "passthrough", "-f", "rawvideo", "-",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    frame_bytes = width * height * 3
    x_steps: list[np.ndarray] = []
    y_steps: list[np.ndarray] = []
    x_lines: list[np.ndarray] = []
    y_lines: list[np.ndarray] = []
    middle_frame = None
    best_score = -1.0
    best_frame = None
    best_index = -1
    index = 0
    try:
        while True:
            raw = _read_exact(process.stdout, frame_bytes)
            if len(raw) != frame_bytes:
                break
            rgb = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
            pixels = rgb.astype(np.float32)
            luma = pixels[..., 0] * 0.2126 + pixels[..., 1] * 0.7152 + pixels[..., 2] * 0.0722
            xs = np.abs(np.diff(luma, axis=1)).mean(axis=0)
            ys = np.abs(np.diff(luma, axis=0)).mean(axis=1)
            xl = np.zeros(width, dtype=np.float32)
            yl = np.zeros(height, dtype=np.float32)
            residual_x = np.abs(2.0 * luma[:, 1:-1] - luma[:, :-2] - luma[:, 2:])
            residual_y = np.abs(2.0 * luma[1:-1, :] - luma[:-2, :] - luma[2:, :])
            xl[1:-1] = residual_x.mean(axis=0)
            yl[1:-1] = residual_y.mean(axis=1)
            x_steps.append(xs)
            y_steps.append(ys)
            x_lines.append(xl)
            y_lines.append(yl)
            x_boundaries = np.arange(1, width)
            y_boundaries = np.arange(1, height)
            score = float(xs[x_boundaries % period == 0].mean() / max(float(xs.mean()), 1e-6)) + float(
                ys[y_boundaries % period == 0].mean() / max(float(ys.mean()), 1e-6)
            )
            if args.keep_visuals and score > best_score:
                best_score, best_frame, best_index = score, rgb.copy(), index
            if args.keep_visuals and frame_count and index == frame_count // 2:
                middle_frame = rgb.copy()
            index += 1
            if args.max_frames and index >= args.max_frames:
                break
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        code = process.wait()
        if code:
            raise RuntimeError(f"ffmpeg failed: {stderr[-1000:]}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    if not x_steps:
        print("ERROR: no frames decoded", file=sys.stderr)
        return {}, 2
    arrays = {
        "x_step": np.stack(x_steps),
        "y_step": np.stack(y_steps),
        "x_line": np.stack(x_lines),
        "y_line": np.stack(y_lines),
    }
    metrics: dict[str, Any] = {}
    for name, array, offset in (("x_step", arrays["x_step"], 1), ("y_step", arrays["y_step"], 1), ("x_line", arrays["x_line"], 0), ("y_line", arrays["y_line"], 0)):
        metrics[name] = {
            "mean_profile": [round(float(value), 6) for value in array.mean(axis=0)],
            "periods": {str(value): _period_metrics(array, value, offset) for value in periods},
        }
    fold = {name: _fold_metrics(array, period, 1 if name.endswith("step") else 0) for name, array in arrays.items()}

    x_ratio = metrics["x_step"]["periods"][str(period)]["ratio_to_all_positions"]
    y_ratio = metrics["y_step"]["periods"][str(period)]["ratio_to_all_positions"]
    x_fraction = metrics["x_step"]["periods"][str(period)]["fraction_frames_ratio_above_1"]
    y_fraction = metrics["y_step"]["periods"][str(period)]["fraction_frames_ratio_above_1"]
    max_ratio = max(x_ratio, y_ratio)
    min_fraction = min(x_fraction, y_fraction)
    if max_ratio >= args.suspect_threshold and min_fraction >= 0.8:
        status = "suspected"
    elif max_ratio >= args.residual_threshold:
        status = "residual"
    else:
        status = "clean"

    visuals: dict[str, Any] = {}
    if args.keep_visuals:
        profile_path = out_dir / f"{video.stem}_grid_profile.png"
        _profile_plot(metrics, period, width, height, profile_path)
        visuals["profile"] = str(profile_path)
        source = best_frame if best_frame is not None else middle_frame
        if source is not None:
            overlay_path = out_dir / f"{video.stem}_grid_overlay_f{best_index}.png"
            _overlay(source, period, best_index, overlay_path)
            visuals["overlay"] = str(overlay_path)

    report = {
        "schema_version": 1,
        "tool": "h3_grid_check",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "video": str(video),
        "sha256": _sha256(video),
        "ffprobe": metadata,
        "width": width,
        "height": height,
        "frame_count": len(x_steps),
        "period": period,
        "periods": periods,
        "metrics": metrics,
        "fold": fold,
        "verdict": {
            "status": status,
            "x_step_ratio": x_ratio,
            "y_step_ratio": y_ratio,
            "x_fraction_frames_above_1": x_fraction,
            "y_fraction_frames_above_1": y_fraction,
            "max_step_ratio": max_ratio,
            "min_fraction_frames_above_1": min_fraction,
            "suspect_threshold": args.suspect_threshold,
            "residual_threshold": args.residual_threshold,
            "notes": [
                "Screening only; a same-latent VAE A/B is the stronger proof.",
                "If suspected and this run used Sol VAE, test minimax_h3_video_vae_fp16.safetensors as the only changed variable.",
                "Sol fp16 has the same reported seam; do not treat it as the fix.",
            ],
        },
        "visuals": visuals,
    }
    report_path = out_dir / f"{video.stem}_grid_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    return report, 1 if (status == "suspected" and args.fail_on_suspected) else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--out-dir")
    parser.add_argument("--period", type=int, default=DEFAULT_PERIOD)
    parser.add_argument("--periods", default="16,32,64,128,256")
    parser.add_argument("--max-frames", type=int, default=0, help="0 = all frames")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    parser.add_argument("--comfyui")
    parser.add_argument("--no-visuals", dest="keep_visuals", action="store_false")
    parser.add_argument("--suspect-threshold", type=float, default=1.20)
    parser.add_argument("--residual-threshold", type=float, default=1.10)
    parser.add_argument("--fail-on-suspected", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args()
    report, code = _analyse(args)
    if not report:
        return code
    if args.json:
        summary = {k: report[k] for k in ("video", "sha256", "width", "height", "frame_count", "period", "verdict", "visuals", "report_path")}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        v = report["verdict"]
        print(f"grid check: {v['status'].upper()} | {report['width']}x{report['height']} | {report['frame_count']} frames")
        print(f"x step ratio {v['x_step_ratio']:.3f} | y step ratio {v['y_step_ratio']:.3f}")
        print(f"x frames >1.0: {v['x_fraction_frames_above_1']:.3f} | y: {v['y_fraction_frames_above_1']:.3f}")
        if report["visuals"].get("profile"):
            print(f"profile: {report['visuals']['profile']}")
        if report["visuals"].get("overlay"):
            print(f"overlay: {report['visuals']['overlay']}")
        print(f"report: {report['report_path']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
