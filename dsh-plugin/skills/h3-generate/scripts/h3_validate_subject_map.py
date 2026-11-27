#!/usr/bin/env python3
"""Validate BFSNodes hybrid-color subject maps frame by frame.

The checker is intentionally independent of OpenCV. It decodes RGB frames with
ffmpeg, applies the same 0.1 max-channel color-distance rule as BFSNodes, and can
compare the detected color sequence with an accepted reference map.

Usage:
  python h3_validate_subject_map.py --map map.mp4 --allowed-colors 0,1
  python h3_validate_subject_map.py --map map.mp4 --reference accepted_map.mp4 \
      --guide guide.mp4 --json qa/subject_map_validation.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised only in minimal Python envs
    np = None


HYBRID_COLORS_RGB: tuple[tuple[int, int, int], ...] = (
    (235, 40, 40),
    (35, 110, 235),
    (60, 205, 60),
    (240, 205, 30),
    (220, 50, 220),
    (30, 205, 225),
)
DEFAULT_ALLOWED_COLORS = (0, 1)
DEFAULT_COLOR_DISTANCE = 0.1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_tool(name: str, explicit: str | None, comfyui: Path | None) -> str:
    candidates = [explicit, os.environ.get(f"H3LITE_{name.upper()}")]
    if comfyui:
        candidates.extend(
            [
                comfyui / f"{name}.exe",
                comfyui / "bin" / f"{name}.exe",
                comfyui / "ffmpeg" / "bin" / f"{name}.exe",
                comfyui / "tools" / "ffmpeg" / "bin" / f"{name}.exe",
            ]
        )
    found = shutil.which(name)
    if found:
        candidates.append(found)
    for value in candidates:
        if value and Path(value).is_file():
            return str(Path(value))
    raise FileNotFoundError(f"{name} not found; pass --{name}, set H3LITE_{name.upper()}, or pass --comfyui")


def _fraction(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        numerator, denominator = value.split("/", 1)
        denominator_value = float(denominator)
        return float(numerator) / denominator_value if denominator_value else None
    except (ValueError, AttributeError):
        return None


def probe_video(ffprobe: str, path: Path) -> dict[str, Any]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-count_frames",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,pix_fmt,sample_aspect_ratio,r_frame_rate,avg_frame_rate,nb_read_frames,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr.strip()[-1000:]}")
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError(f"no video stream in {path}")
    stream = streams[0]
    fps = _fraction(stream.get("avg_frame_rate")) or _fraction(stream.get("r_frame_rate"))
    duration = stream.get("duration")
    if duration is None:
        duration = (data.get("format") or {}).get("duration")
    try:
        duration_value = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_value = None
    return {
        "codec_name": stream.get("codec_name"),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "pix_fmt": stream.get("pix_fmt"),
        "sample_aspect_ratio": stream.get("sample_aspect_ratio"),
        "fps": round(fps, 6) if fps is not None else None,
        "frames": int(stream.get("nb_read_frames") or 0),
        "duration": round(duration_value, 6) if duration_value is not None else None,
    }


def detect_frame_colors(rgb_frame: Any, threshold: float = DEFAULT_COLOR_DISTANCE) -> tuple[list[int], list[int]]:
    """Return detected hybrid-color indices and per-color pixel counts."""
    if np is None:
        raise RuntimeError("numpy is required for subject-map color validation")
    frame = np.asarray(rgb_frame, dtype=np.float32) / 255.0
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("RGB frame must have shape (height, width, 3)")
    counts: list[int] = []
    for color in HYBRID_COLORS_RGB:
        reference = np.asarray(color, dtype=np.float32) / 255.0
        distance = np.max(np.abs(frame - reference), axis=-1)
        counts.append(int(np.count_nonzero(distance < threshold)))
    return [index for index, count in enumerate(counts) if count > 0], counts


def _read_exact(stream: Any, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def decode_color_sequence(
    ffmpeg: str,
    path: Path,
    width: int,
    height: int,
    threshold: float = DEFAULT_COLOR_DISTANCE,
) -> dict[str, Any]:
    if np is None:
        raise RuntimeError("numpy is required for subject-map color validation")
    if width <= 0 or height <= 0:
        raise RuntimeError(f"invalid video geometry for {path}: {width}x{height}")
    command = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    frame_size = width * height * 3
    sequence: list[list[int]] = []
    counts_by_frame: list[list[int]] = []
    with tempfile.TemporaryFile() as error_file:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_file)
        try:
            assert process.stdout is not None
            while True:
                raw = _read_exact(process.stdout, frame_size)
                if not raw:
                    break
                if len(raw) != frame_size:
                    raise RuntimeError(f"incomplete raw frame {len(sequence)} from {path}")
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
                detected, counts = detect_frame_colors(frame, threshold)
                sequence.append(detected)
                counts_by_frame.append(counts)
            return_code = process.wait(timeout=60)
            error_file.seek(0)
            error_text = error_file.read().decode("utf-8", errors="replace").strip()
            if return_code != 0:
                raise RuntimeError(f"ffmpeg failed for {path}: {error_text[-1000:]}")
        except Exception:
            process.kill()
            process.wait(timeout=10)
            raise
    if not sequence:
        raise RuntimeError(f"no decoded frames from {path}")
    return {"sequence": sequence, "counts_by_frame": counts_by_frame}


def _metadata_compatible(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool, list[str]]:
    differences: list[str] = []
    if left.get("frames") != right.get("frames"):
        differences.append(f"frames {left.get('frames')} != {right.get('frames')}")
    left_fps = left.get("fps")
    right_fps = right.get("fps")
    if left_fps is None or right_fps is None or abs(float(left_fps) - float(right_fps)) > 0.001:
        differences.append(f"fps {left_fps} != {right_fps}")
    left_duration = left.get("duration")
    right_duration = right.get("duration")
    if left_duration is None or right_duration is None or abs(float(left_duration) - float(right_duration)) > 0.05:
        differences.append(f"duration {left_duration} != {right_duration}")
    return not differences, differences


def parse_allowed_colors(value: str) -> tuple[int, ...]:
    try:
        colors = tuple(sorted({int(item.strip()) for item in value.split(",") if item.strip()}))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("allowed colors must be comma-separated integers") from exc
    if not colors or any(index < 0 or index >= len(HYBRID_COLORS_RGB) for index in colors):
        raise argparse.ArgumentTypeError(f"allowed colors must be between 0 and {len(HYBRID_COLORS_RGB) - 1}")
    return colors


def analyse(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    errors: list[str] = []
    warnings: list[str] = []
    map_path = Path(args.map).expanduser().resolve()
    reference_path = Path(args.reference).expanduser().resolve() if args.reference else None
    guide_path = Path(args.guide).expanduser().resolve() if args.guide else None
    for label, path in (("map", map_path), ("reference", reference_path), ("guide", guide_path)):
        if path is not None and not path.is_file():
            errors.append(f"{label}: file not found: {path}")
    if errors:
        return {"status": "failed", "errors": errors, "warnings": warnings}, 1

    ffmpeg = find_tool("ffmpeg", args.ffmpeg, Path(args.comfyui).expanduser() if args.comfyui else None)
    ffprobe = find_tool("ffprobe", args.ffprobe, Path(args.comfyui).expanduser() if args.comfyui else None)
    metadata = probe_video(ffprobe, map_path)
    decoded = decode_color_sequence(ffmpeg, map_path, metadata["width"], metadata["height"], args.color_distance)
    sequence = decoded["sequence"]
    counts_by_frame = decoded["counts_by_frame"]
    if metadata["frames"] and metadata["frames"] != len(sequence):
        errors.append(f"decoded {len(sequence)} frames but ffprobe counted {metadata['frames']}")

    unexpected_frames = [
        index for index, detected in enumerate(sequence)
        if any(color not in args.allowed_colors for color in detected)
    ]
    empty_frames = [index for index, detected in enumerate(sequence) if not detected]
    observed_colors = {color for detected in sequence for color in detected}
    missing_allowed_colors = [color for color in args.allowed_colors if color not in observed_colors]
    if unexpected_frames:
        errors.append(f"unexpected hybrid colors in frames: {unexpected_frames[:20]}")
    if missing_allowed_colors:
        errors.append(f"allowed subject colors never detected: {missing_allowed_colors}")
    if not any(sequence):
        errors.append("no allowed hybrid color was detected in any frame")

    reference_result: dict[str, Any] | None = None
    reference_sequence_equal: bool | None = None
    if reference_path:
        reference_metadata = probe_video(ffprobe, reference_path)
        reference_decoded = decode_color_sequence(
            ffmpeg,
            reference_path,
            reference_metadata["width"],
            reference_metadata["height"],
            args.color_distance,
        )
        compatible, differences = _metadata_compatible(metadata, reference_metadata)
        if not compatible:
            errors.extend(f"reference metadata mismatch: {item}" for item in differences)
        sequence_equal = sequence == reference_decoded["sequence"]
        reference_sequence_equal = sequence_equal
        if not sequence_equal:
            first_difference = next(
                (index for index, pair in enumerate(zip(sequence, reference_decoded["sequence"])) if pair[0] != pair[1]),
                min(len(sequence), len(reference_decoded["sequence"])),
            )
            errors.append(f"detected color sequence differs from reference at frame {first_difference}")
        reference_result = {
            "path": str(reference_path),
            "sha256": sha256_file(reference_path),
            "metadata": reference_metadata,
            "metadata_compatible": compatible,
            "sequence_equal": sequence_equal,
            "empty_frames": [index for index, detected in enumerate(reference_decoded["sequence"]) if not detected],
        }

    guide_result: dict[str, Any] | None = None
    if guide_path:
        guide_metadata = probe_video(ffprobe, guide_path)
        compatible, differences = _metadata_compatible(metadata, guide_metadata)
        if not compatible:
            errors.extend(f"guide metadata mismatch: {item}" for item in differences)
        guide_result = {
            "path": str(guide_path),
            "sha256": sha256_file(guide_path),
            "metadata": guide_metadata,
            "metadata_compatible": compatible,
        }

    if empty_frames and reference_sequence_equal is None:
        errors.append("empty subject-map frames require --reference to prove the accepted input has the same sequence")
    elif empty_frames and not reference_sequence_equal:
        errors.append("empty subject-map frames do not match the accepted reference sequence")

    if empty_frames:
        warnings.append(
            f"{len(empty_frames)} frame(s) have no hybrid color; accepted only when the reference sequence matches"
        )
    status = "passed" if not errors else "failed"
    report = {
        "status": status,
        "map": {
            "path": str(map_path),
            "sha256": sha256_file(map_path),
            "metadata": metadata,
        },
        "allowed_colors": list(args.allowed_colors),
        "allowed_colors_rgb": [HYBRID_COLORS_RGB[index] for index in args.allowed_colors],
        "color_distance": args.color_distance,
        "decoded_frames": len(sequence),
        "sequence": sequence,
        "counts_by_frame": counts_by_frame,
        "empty_frames": empty_frames,
        "unexpected_color_frames": unexpected_frames,
        "missing_allowed_colors": missing_allowed_colors,
        "reference": reference_result,
        "guide": guide_result,
        "errors": errors,
        "warnings": warnings,
    }
    return report, 0 if status == "passed" else 1


def parse_color_distance(value: str) -> float:
    try:
        distance = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("color distance must be a number") from exc
    if not 0.0 < distance <= 1.0:
        raise argparse.ArgumentTypeError("color distance must be greater than 0 and at most 1")
    return distance


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True)
    parser.add_argument("--reference")
    parser.add_argument("--guide")
    parser.add_argument("--allowed-colors", type=parse_allowed_colors, default=DEFAULT_ALLOWED_COLORS)
    parser.add_argument("--color-distance", type=parse_color_distance, default=DEFAULT_COLOR_DISTANCE)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    parser.add_argument("--comfyui")
    parser.add_argument("--json", metavar="PATH", help="write the full report to PATH")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args(argv)
    try:
        report, code = analyse(args)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        report = {"status": "failed", "errors": [str(exc)], "warnings": []}
        code = 1
    if args.json:
        report_path = Path(args.json).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report["report_path"] = str(report_path)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if code == 0:
        print(f"subject map: PASS | {report['decoded_frames']} frames | {report['map']['metadata']['width']}x{report['map']['metadata']['height']}")
        if report.get("report_path"):
            print(f"report: {report['report_path']}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
