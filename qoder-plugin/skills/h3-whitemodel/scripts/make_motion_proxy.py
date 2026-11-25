#!/usr/bin/env python3
"""Make a lightweight white-model motion proxy for H3 Ref2VA and verify it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        "r_frame_rate,nb_read_frames,duration:format=duration",
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
    return {
        "codec_name": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "pix_fmt": stream.get("pix_fmt"),
        "sample_aspect_ratio": stream.get("sample_aspect_ratio"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "nb_read_frames": int(stream.get("nb_read_frames") or 0),
        "duration": float(stream.get("duration") or data.get("format", {}).get("duration") or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--width", type=int, default=864)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--ffmpeg", default=None)
    parser.add_argument("--ffprobe", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source = args.input.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise SystemExit(f"Input does not exist: {source}")
    if source == output:
        raise SystemExit("Input and output must be different files")
    if output.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite: {output} (pass --force)")
    output.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = find_tool("ffmpeg", args.ffmpeg)
    ffprobe = find_tool("ffprobe", args.ffprobe)
    source_info = probe(ffprobe, source)

    command = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    if args.force:
        command.append("-y")
    else:
        command.append("-n")
    if args.start:
        command += ["-ss", f"{args.start:.6f}"]
    command += ["-i", str(source)]
    if args.duration:
        command += ["-t", f"{args.duration:.6f}"]
    command += [
        "-an",
        "-sn",
        "-vf",
        f"fps={args.fps},scale={args.width}:{args.height}:flags=lanczos,setsar=1",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    subprocess.run(command, check=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise SystemExit(f"ffmpeg reported success but output is missing: {output}")

    info = probe(ffprobe, output)
    duration = args.duration or source_info["duration"] - args.start
    expected_frames = round(duration * args.fps) if duration > 0 else None
    problems: list[str] = []
    if info["width"] != args.width or info["height"] != args.height:
        problems.append(f"expected {args.width}x{args.height}, got {info['width']}x{info['height']}")
    if info["sample_aspect_ratio"] not in ("1:1", "1/1"):
        problems.append(f"expected SAR 1:1, got {info['sample_aspect_ratio']}")
    if expected_frames is not None and abs(info["nb_read_frames"] - expected_frames) > 1:
        problems.append(
            f"expected about {expected_frames} frames, got {info['nb_read_frames']}"
        )

    report = {
        "input": str(source),
        "input_sha256": sha256(source),
        "input_video": source_info,
        "output": str(output),
        "output_sha256": sha256(output),
        "output_video": info,
        "expected_frames": expected_frames,
        "problems": problems,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
