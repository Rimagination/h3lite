#!/usr/bin/env python3
"""QA a white-model / H3 vertical comparison against its source panels."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def find_tool(name: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    env_value = os.environ.get(f"H3LITE_{name.upper()}")
    if env_value:
        return env_value
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(
        f"Cannot find {name}. Pass --{name} or set H3LITE_{name.upper()}."
    )


def probe(ffprobe: str, path: Path) -> dict:
    command = [
        ffprobe,
        "-v",
        "error",
        "-count_frames",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,pix_fmt,sample_aspect_ratio,"
        "r_frame_rate,avg_frame_rate,nb_read_frames,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise SystemExit(f"No video stream found in {path}")
    stream = streams[0]
    rate_text = stream.get("r_frame_rate") or "0/1"
    try:
        numerator, denominator = rate_text.split("/")
        fps = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return {
        "codec_name": stream.get("codec_name"),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "pix_fmt": stream.get("pix_fmt"),
        "sample_aspect_ratio": stream.get("sample_aspect_ratio"),
        "r_frame_rate": rate_text,
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "fps": round(fps, 6),
        "nb_read_frames": int(stream.get("nb_read_frames") or 0),
        "duration": float(stream.get("duration") or data.get("format", {}).get("duration") or 0),
    }


def decode_gray(ffmpeg: str, path: Path, width: int, height: int) -> np.ndarray:
    command = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(path),
        "-an",
        "-sn",
        "-vf",
        f"scale={width}:{height}:flags=lanczos",
        "-pix_fmt",
        "gray",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    result = subprocess.run(command, check=True, capture_output=True)
    frame_size = width * height
    if len(result.stdout) == 0 or len(result.stdout) % frame_size:
        raise SystemExit(f"Incomplete raw frames from {path}")
    return np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, height, width)


def mad(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def consecutive_mad(frames: np.ndarray) -> np.ndarray:
    if len(frames) < 2:
        return np.zeros(0, dtype=np.float64)
    return np.array(
        [mad(frames[i - 1], frames[i]) for i in range(1, len(frames))],
        dtype=np.float64,
    )


def longest_below(values: np.ndarray, threshold: float) -> int:
    longest = 0
    current = 0
    for value in values:
        if value < threshold:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def selected_indices(total: int, last_reference: int, count: int = 5) -> list[int]:
    if count < 2:
        raise ValueError("count must be at least 2")
    if last_reference <= 0:
        return [0]
    indices = [round((last_reference - 1) * i / (count - 1)) for i in range(count)]
    indices = sorted(set(indices))
    indices[-1] = max(indices[-1], min(last_reference, total) - 1)
    return indices


def extract_color_frames(
    ffmpeg: str, path: Path, indices: list[int], cell_width: int, panel_height: int
) -> np.ndarray:
    expression = "+".join(f"eq(n,{index})" for index in indices)
    command = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(path),
        "-an",
        "-sn",
        "-vf",
        f"select='{expression}',scale={cell_width}:{panel_height}:flags=lanczos",
        "-fps_mode",
        "passthrough",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    result = subprocess.run(command, check=True, capture_output=True)
    frame_size = cell_width * panel_height * 3
    if len(result.stdout) != frame_size * len(indices):
        got = len(result.stdout) / frame_size if frame_size else 0
        raise RuntimeError(f"Expected {len(indices)} selected frames, got {got}")
    return np.frombuffer(result.stdout, dtype=np.uint8).reshape(
        len(indices), panel_height, cell_width, 3
    )


def load_font(size: int) -> ImageFont.ImageFont:
    fonts_dir = Path(os.environ.get("WINDIR", "")) / "Fonts"
    for name in ("msyh.ttc", "arial.ttf"):
        try:
            return ImageFont.truetype(str(fonts_dir / name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_contact_sheet(
    ffmpeg: str,
    stack: Path,
    indices: list[int],
    fps: float,
    output: Path,
    columns: int,
    cell_width: int,
    panel_height: int,
) -> None:
    frames = extract_color_frames(ffmpeg, stack, indices, cell_width, panel_height)
    label_height = 42
    rows = (len(indices) + columns - 1) // columns
    canvas = Image.new(
        "RGB", (cell_width * columns, (panel_height + label_height) * rows), (20, 20, 20)
    )
    draw = ImageDraw.Draw(canvas)
    font = load_font(24)
    for i, (frame, index) in enumerate(zip(frames, indices)):
        x = (i % columns) * cell_width
        y = (i // columns) * (panel_height + label_height)
        canvas.paste(Image.fromarray(frame), (x, y + label_height))
        seconds = index / fps if fps else 0.0
        draw.text(
            (x + 14, y + 8),
            f"f{index}  {seconds:.2f}s",
            fill=(245, 245, 245),
            font=font,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=94, subsampling=0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--h3", required=True, type=Path)
    parser.add_argument("--old-reference", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--contact-sheet", type=Path, default=None)
    parser.add_argument("--sample-width", type=int, default=336)
    parser.add_argument("--max-source-mae", type=float, default=5.0)
    parser.add_argument("--ffmpeg", default=None)
    parser.add_argument("--ffprobe", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    stack_path = args.stack.resolve()
    reference_path = args.reference.resolve()
    h3_path = args.h3.resolve()
    old_path = args.old_reference.resolve() if args.old_reference else None
    for path in [stack_path, reference_path, h3_path] + ([old_path] if old_path else []):
        if not path.is_file():
            raise SystemExit(f"Input does not exist: {path}")

    out_json = (
        args.out_json.resolve()
        if args.out_json
        else stack_path.with_name(f"{stack_path.stem}_qa.json")
    )
    if out_json.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite: {out_json} (pass --force)")
    if args.contact_sheet and args.contact_sheet.exists() and not args.force:
        raise SystemExit(
            f"Refusing to overwrite: {args.contact_sheet} (pass --force)"
        )

    ffmpeg = find_tool("ffmpeg", args.ffmpeg)
    ffprobe = find_tool("ffprobe", args.ffprobe)
    stack_info = probe(ffprobe, stack_path)
    reference_info = probe(ffprobe, reference_path)
    h3_info = probe(ffprobe, h3_path)
    old_info = probe(ffprobe, old_path) if old_path else None

    if stack_info["width"] <= 0 or stack_info["height"] <= 0:
        raise SystemExit("Stack has no usable dimensions")
    panel_height = round(args.sample_width * reference_info["height"] / reference_info["width"])
    if panel_height <= 0:
        raise SystemExit("Reference has no usable dimensions")
    stack_ratio = stack_info["height"] / stack_info["width"]
    expected_ratio = 2.0 * reference_info["height"] / reference_info["width"]
    if abs(stack_ratio - expected_ratio) > 0.01:
        raise SystemExit(
            "Stack is not a two-panel vertical stack with the reference aspect: "
            f"stack={stack_info['width']}x{stack_info['height']}, "
            f"reference={reference_info['width']}x{reference_info['height']}, "
            f"stack aspect={stack_ratio:.4f}, expected={expected_ratio:.4f}"
        )

    stack = decode_gray(ffmpeg, stack_path, args.sample_width, panel_height * 2)
    reference = decode_gray(ffmpeg, reference_path, args.sample_width, panel_height)
    h3 = decode_gray(ffmpeg, h3_path, args.sample_width, panel_height)
    old = (
        decode_gray(ffmpeg, old_path, args.sample_width, panel_height)
        if old_path
        else None
    )

    top = stack[:, :panel_height, :]
    bottom = stack[:, panel_height:, :]
    top_mad = consecutive_mad(top)
    bottom_mad = consecutive_mad(bottom)

    common = min(len(top), len(reference))
    common_h3 = min(len(bottom), len(h3))
    common_old = min(len(top), len(old)) if old is not None else 0
    if common == 0 or common_h3 == 0:
        raise SystemExit("No common frames to compare")

    reference_transition_count = max(common - 1, 0)
    reference_top_mad = top_mad[:reference_transition_count]

    top_errors = [mad(top[i], reference[i]) for i in range(common)]
    bottom_errors = [mad(bottom[i], h3[i]) for i in range(common_h3)]
    old_errors = (
        [mad(top[i], old[i]) for i in range(common_old)] if old is not None else []
    )

    tail_count = min(20, max(len(top_mad) - common + 1, 0))
    top_tail = top_mad[-tail_count:] if tail_count else np.zeros(0)
    bottom_tail = bottom_mad[-20:] if len(bottom_mad) else np.zeros(0)

    indices = selected_indices(len(stack), min(common, len(stack)), 5)
    selected = []
    for index in indices:
        item = {
            "frame": index,
            "time_seconds": round(index / stack_info["fps"], 4) if stack_info["fps"] else None,
            "top_vs_reference_mae": round(mad(top[index], reference[index]), 6)
            if index < common
            else None,
            "bottom_vs_h3_mae": round(mad(bottom[index], h3[index]), 6)
            if index < common_h3
            else None,
        }
        if old is not None and index < common_old:
            item["top_vs_old_reference_mae"] = round(mad(top[index], old[index]), 6)
        selected.append(item)

    problems: list[str] = []
    if len(stack) < len(reference):
        problems.append(
            f"stack has {len(stack)} frames but reference has {len(reference)}"
        )
    if len(stack) < len(h3):
        problems.append(f"stack has {len(stack)} frames but H3 has {len(h3)}")
    if float(np.mean(top_errors)) > args.max_source_mae:
        problems.append(
            f"top panel does not match reference (mean MAE {np.mean(top_errors):.3f} > {args.max_source_mae})"
        )
    if float(np.mean(bottom_errors)) > args.max_source_mae:
        problems.append(
            f"bottom panel does not match H3 (mean MAE {np.mean(bottom_errors):.3f} > {args.max_source_mae})"
        )

    warnings: list[str] = []
    if len(reference_top_mad) and float(np.mean(reference_top_mad < 1.0)) > 0.2:
        warnings.append("top panel is near-static for more than 20% of the reference window")
    if len(bottom_mad) and float(np.mean(bottom_mad < 1.0)) > 0.2:
        warnings.append("bottom panel is near-static for more than 20% of frames")

    report = {
        "inputs": {
            "stack": str(stack_path),
            "reference": str(reference_path),
            "h3": str(h3_path),
            "old_reference": str(old_path) if old_path else None,
        },
        "probe": {
            "stack": stack_info,
            "reference": reference_info,
            "h3": h3_info,
            "old_reference": old_info,
        },
        "frame_counts": {
            "stack": len(stack),
            "reference": len(reference),
            "h3": len(h3),
            "old_reference": len(old) if old is not None else None,
        },
        "panel_source_mae": {
            "top_vs_reference": round(float(np.mean(top_errors)), 6),
            "bottom_vs_h3": round(float(np.mean(bottom_errors)), 6),
            "top_vs_old_reference": round(float(np.mean(old_errors)), 6)
            if old_errors
            else None,
            "compared_frames": {
                "top": common,
                "bottom": common_h3,
                "old_reference": common_old if old_errors else None,
            },
        },
        "motion": {
            "top_mean_mad_reference_transitions": round(
                float(reference_top_mad.mean()), 6
            )
            if len(reference_top_mad)
            else None,
            "top_near_static_ratio_reference": round(
                float(np.mean(reference_top_mad < 1.0)), 6
            )
            if len(reference_top_mad)
            else None,
            "top_longest_near_static_reference": longest_below(
                reference_top_mad, 1.0
            ),
            "top_mean_mad_all_transitions": round(float(top_mad.mean()), 6)
            if len(top_mad)
            else None,
            "top_near_static_ratio_all": round(float(np.mean(top_mad < 1.0)), 6)
            if len(top_mad)
            else None,
            "top_longest_near_static_all": longest_below(top_mad, 1.0),
            "top_tail_mean_mad": round(float(top_tail.mean()), 6)
            if len(top_tail)
            else None,
            "top_tail_max_mad": round(float(top_tail.max()), 6)
            if len(top_tail)
            else None,
            "bottom_mean_mad_transitions": round(float(bottom_mad.mean()), 6)
            if len(bottom_mad)
            else None,
            "bottom_near_static_ratio": round(float(np.mean(bottom_mad < 1.0)), 6)
            if len(bottom_mad)
            else None,
            "bottom_longest_near_static": longest_below(bottom_mad, 1.0),
            "bottom_tail_mean_mad": round(float(bottom_tail.mean()), 6)
            if len(bottom_tail)
            else None,
        },
        "selected_frame_checks": selected,
        "problems": problems,
        "warnings": warnings,
        "contact_sheet": None,
    }

    if args.contact_sheet:
        contact_sheet = args.contact_sheet.resolve()
        try:
            make_contact_sheet(
                ffmpeg,
                stack_path,
                indices,
                stack_info["fps"],
                contact_sheet,
                columns=3,
                cell_width=args.sample_width * 2,
                panel_height=panel_height * 2,
            )
            report["contact_sheet"] = str(contact_sheet)
        except Exception as error:  # noqa: BLE001 - report and keep numeric QA
            warnings.append(f"contact sheet failed: {error}")
            report["warnings"] = warnings

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
