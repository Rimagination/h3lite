#!/usr/bin/env python3
"""Validate a show.json before any H3 submission.

Structural failures and route conflicts are errors. Style/robustness issues are
warnings; --strict turns warnings into a non-zero exit for a locked production.

Usage:
  python h3_show_validate.py --spec projects/ep04/show.json
  python h3_show_validate.py --spec projects/ep04/show.json --check-sha --strict --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA_VERSION = 1

MODES = {"t2v", "i2va", "fl2va", "l2va", "ref2va", "auto"}
COMPONENT_SETS = {"auto", "a", "b", "validated-low-vram-a", "portable-16gb-b"}
AUDIO_POLICIES = {"native", "silent"}
ASPECTS = {"16:9": 16 / 9, "9:16": 9 / 16, "4:3": 4 / 3, "1:1": 1.0}

SETC = {
    "h3_c_speed640",
    "h3_c_t2va768",
    "h3_c_quality864",
    "h3_c_i2va768",
    "h3_c_fl2va768",
    "h3_c_ref2va768",
}
ALL_TEMPLATES = SETC | {
    "auto",
    "h3_w4a8_t2v",
    "h3_w4a8_t2v_compat",
    "h3_w4a8_i2v",
    "h3_w4a8_i2v_compat",
    "h3_w4a8_ref2va",
    "h3_w4a8_ref2va_compat",
}
MODE_TEMPLATES = {
    "t2v": {"h3_c_speed640", "h3_c_t2va768", "h3_c_quality864", "h3_w4a8_t2v", "h3_w4a8_t2v_compat"},
    "i2va": {"h3_c_i2va768", "h3_w4a8_i2v", "h3_w4a8_i2v_compat"},
    "fl2va": {"h3_c_fl2va768", "h3_c_i2va768", "h3_w4a8_i2v", "h3_w4a8_i2v_compat"},
    "l2va": {"h3_c_i2va768", "h3_w4a8_i2v", "h3_w4a8_i2v_compat"},
    "ref2va": {"h3_c_ref2va768", "h3_w4a8_ref2va", "h3_w4a8_ref2va_compat"},
    "auto": set(ALL_TEMPLATES),
}
IMAGE_MODES = {"i2va", "fl2va", "l2va", "ref2va"}
ABSOLUTE_WIN = re.compile(r"^[A-Za-z]:[\\/]")
FRAME_RE = re.compile(r"^(\d+)x(\d+)$")


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)


def resolve(base: Path, value: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    path = Path(expanded)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def rel_display(base: Path, path: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def is_path_like(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_rel_path(value: str, label: str, report: Report) -> None:
    if ABSOLUTE_WIN.match(value) or Path(value).is_absolute():
        report.warn(f"{label}: absolute path reduces portability: {value}")


def check_file(
    base: Path,
    value: str | None,
    label: str,
    report: Report,
    *,
    required: bool = True,
) -> Path | None:
    if not is_path_like(value):
        if required:
            report.error(f"{label}: missing")
        return None
    assert isinstance(value, str)
    check_rel_path(value, label, report)
    path = resolve(base, value)
    if not path.is_file():
        report.error(f"{label}: file not found: {value}")
        return None
    return path


def parse_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
        return int(value.strip())
    return None


def read_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_sha_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts
        name = name.lstrip("*").strip().replace("\\", "/")
        if re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            entries[name] = digest.lower()
    return entries


def find_ffprobe(explicit: str | None) -> str | None:
    candidates = [explicit, os.environ.get("H3LITE_FFPROBE"), shutil.which("ffprobe")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    return None


def probe_media(path: Path, ffprobe: str, stream: str = "v:0") -> dict | None:
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        stream,
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None
    streams = data.get("streams") or []
    stream_info = streams[0] if streams else {}
    duration = None
    try:
        duration = float((data.get("format") or {}).get("duration"))
    except (TypeError, ValueError):
        pass
    fps = None
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = stream_info.get(key)
        if not raw or raw in ("0/0", "N/A"):
            continue
        try:
            num, den = raw.split("/", 1)
            if float(den) != 0:
                fps = float(num) / float(den)
                break
        except (ValueError, AttributeError):
            continue
    return {
        "width": stream_info.get("width"),
        "height": stream_info.get("height"),
        "fps": fps,
        "duration": duration,
    }


def check_prompt(
    path: Path | None,
    mode: str,
    template: str,
    ref_audios: list,
    report: Report,
) -> None:
    if path is None:
        return
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:
        report.error(f"prompt: cannot read {path.name}: {exc}")
        return
    if not text.strip():
        report.error("prompt: file is empty")
        return

    lower = text.lower()
    official_graph = template in SETC or template.startswith("h3_w4a8_")

    if "integrated_multimodal_description" not in lower:
        report.warn("prompt: missing integrated_multimodal_description field")
    if "overall_soundscape" not in lower:
        report.warn("prompt: missing overall_soundscape field")
    if "non_diegetic_music" not in lower:
        report.warn("prompt: missing non_diegetic_music field")

    if official_graph and mode in IMAGE_MODES:
        if "<picture 1>" not in lower:
            report.error(f"prompt: {mode} with {template} must reference <Picture 1>")
        if mode == "fl2va" and "<picture 2>" not in lower:
            report.error(f"prompt: fl2va with {template} must reference <Picture 2>")

    if mode == "ref2va" and "<picture 1>" not in lower:
        report.warn("prompt: ref2va prompt has no <Picture 1> reference")

    shot_labels = re.findall(r"\[\s*shot\s*\d+\s*\]", text, flags=re.IGNORECASE)
    cuts = lower.count("this is a hard cut")
    if len(shot_labels) >= 2 and cuts < len(shot_labels) - 1:
        report.warn(
            f"prompt: {len(shot_labels)} [Shot] blocks but only {cuts} 'This is a hard cut.' markers"
        )

    has_audio_tag = "<audio" in lower
    if has_audio_tag and mode != "ref2va":
        report.warn(f"prompt: <Audio N> tag on {mode} route has no audio input; remove or route through ref2va")
    if has_audio_tag and mode == "ref2va" and not ref_audios:
        report.warn("prompt: <Audio N> tag but no ref_audios in shot card")


def check_canon(
    base: Path,
    canon_value,
    report: Report,
    ffprobe: str | None,
) -> tuple[dict, list[Path]]:
    characters: dict = {}
    paths: list[Path] = []
    if not is_path_like(canon_value):
        report.warn("canon: show.json has no canon.json; identity and VOICE are not centrally locked")
        return characters, paths
    canon_path = check_file(base, canon_value, "canon", report, required=True)
    if canon_path is None:
        return characters, paths
    try:
        canon = read_json(canon_path)
    except Exception as exc:
        report.error(f"canon: cannot read {canon_value}: {exc}")
        return characters, paths
    if not isinstance(canon, dict):
        report.error("canon: root must be an object")
        return characters, paths

    raw_characters = canon.get("characters")
    if not isinstance(raw_characters, dict) or not raw_characters:
        report.warn("canon: characters object is missing or empty")
        return characters, paths

    for cid, data in raw_characters.items():
        label = f"canon.characters.{cid}"
        if not isinstance(data, dict):
            report.error(f"{label}: must be an object")
            continue
        for key in ("identity", "voice"):
            value = data.get(key)
            if not is_path_like(value):
                report.error(f"{label}.{key}: missing or empty")
        refs = data.get("ref_images") or []
        if not isinstance(refs, list):
            report.error(f"{label}.ref_images: must be a list")
            refs = []
        for idx, ref in enumerate(refs, start=1):
            if not is_path_like(ref):
                report.error(f"{label}.ref_images[{idx}]: must be a path string")
                continue
            ref_path = check_file(base, ref, f"{label}.ref_images[{idx}]", report, required=True)
            if ref_path:
                paths.append(ref_path)
        ref_audio = data.get("ref_audio")
        if is_path_like(ref_audio):
            audio_path = check_file(base, ref_audio, f"{label}.ref_audio", report, required=True)
            if audio_path:
                paths.append(audio_path)
                if ffprobe:
                    probe = probe_media(audio_path, ffprobe, stream="a:0")
                    if probe and probe.get("duration") is not None:
                        if not 2.0 <= probe["duration"] <= 15.0:
                            report.warn(f"{label}.ref_audio: duration {probe['duration']:.2f}s is outside 2–15 s")
        elif ref_audio not in (None, ""):
            report.error(f"{label}.ref_audio: must be a path string or null")
        characters[cid] = data
    return characters, paths


def check_sha_pack(base: Path, ref_paths: list[Path], report: Report) -> None:
    sha_path = base / "refs.sha256"
    if not sha_path.is_file():
        report.warn("refs.sha256 not found; reference pack is not frozen")
        return
    entries = load_sha_entries(sha_path)
    if not entries:
        report.warn("refs.sha256 has no valid entries")
        return
    seen = set()
    for path in ref_paths:
        if path is None:
            continue
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        rel = rel_display(base, path)
        expected = entries.get(rel) or entries.get(path.name)
        if expected is None:
            report.warn(f"refs.sha256: no hash for {rel}")
            continue
        actual = sha256_file(path)
        if actual.lower() != expected:
            report.error(f"refs.sha256: hash mismatch for {rel}")


def validate(
    spec_path: Path,
    *,
    check_sha: bool,
    ffprobe: str | None,
) -> tuple[Report, dict]:
    report = Report()
    base = spec_path.parent
    try:
        spec = read_json(spec_path)
    except Exception as exc:
        report.error(f"spec: cannot read {spec_path.name}: {exc}")
        return report, {}

    if not isinstance(spec, dict):
        report.error("spec: root must be an object")
        return report, {}

    summary = {"project": spec.get("project"), "shots": 0, "modes": {}, "templates": {}}

    version = parse_int(spec.get("schema_version"))
    if version != SCHEMA_VERSION:
        report.error(f"spec.schema_version: expected {SCHEMA_VERSION}, got {spec.get('schema_version')!r}")

    project = spec.get("project")
    if not is_path_like(project):
        report.error("spec.project: missing or empty")

    deliverable = spec.get("deliverable")
    if not isinstance(deliverable, dict):
        report.error("spec.deliverable: missing or not an object")
        deliverable = {}

    resolution = deliverable.get("resolution")
    width = height = None
    if not is_path_like(resolution):
        report.error("deliverable.resolution: missing")
    else:
        match = FRAME_RE.fullmatch(str(resolution).strip())
        if not match:
            report.error(f"deliverable.resolution: expected WIDTHxHEIGHT, got {resolution!r}")
        else:
            width, height = int(match.group(1)), int(match.group(2))
            if width <= 0 or height <= 0:
                report.error("deliverable.resolution: width/height must be positive")
            elif width % 32 or height % 32:
                report.error(f"deliverable.resolution: {width}x{height} is not 32-pixel aligned")
            aspect = deliverable.get("aspect")
            if aspect in ASPECTS:
                actual = width / height
                if abs(actual - ASPECTS[aspect]) > 0.05:
                    report.warn(f"deliverable.aspect: {aspect} does not match {width}x{height}")
            elif aspect is not None:
                report.warn(f"deliverable.aspect: unknown value {aspect!r}")

    audio_policy = deliverable.get("audio", "native")
    if audio_policy not in AUDIO_POLICIES:
        report.error(f"deliverable.audio: expected native or silent, got {audio_policy!r}")

    fps = deliverable.get("fps", 24)
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or fps <= 0:
        report.error("deliverable.fps: must be a positive number")
        fps = 24
    elif abs(float(fps) - 24.0) > 0.01:
        report.warn(f"deliverable.fps: {fps} is not the local 24 fps default")

    duration = deliverable.get("duration_seconds")
    if duration is not None:
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
            report.error("deliverable.duration_seconds: must be a positive number")
            duration = None

    cover = deliverable.get("cover")
    if cover is not None and not isinstance(cover, bool):
        report.error("deliverable.cover: must be true/false")

    delivery_dir = deliverable.get("delivery_dir")
    if not is_path_like(delivery_dir):
        report.error("deliverable.delivery_dir: missing")

    deliverable_subs = deliverable.get("subtitles")
    deliverable_subs_path = None
    if deliverable_subs not in (None, ""):
        deliverable_subs_path = check_file(base, deliverable_subs, "deliverable.subtitles", report, required=True)
    elif deliverable_subs is None:
        report.note("deliverable.subtitles: null (no subtitles planned)")

    defaults = spec.get("defaults") if isinstance(spec.get("defaults"), dict) else {}

    characters, canon_paths = check_canon(base, spec.get("canon"), report, ffprobe)

    shots = spec.get("shots")
    if not isinstance(shots, list) or not shots:
        report.error("spec.shots: missing or empty")
        shots = []
    summary["shots"] = len(shots)

    seen_ids: set[str] = set()
    all_ref_paths: list[Path] = list(canon_paths)
    total_frames = 0
    valid_lengths = 0

    for index, shot in enumerate(shots, start=1):
        label = f"shot[{index}]"
        if not isinstance(shot, dict):
            report.error(f"{label}: must be an object")
            continue

        sid = shot.get("id")
        if not is_path_like(sid):
            report.error(f"{label}.id: missing")
            sid = f"<shot{index}>"
        else:
            sid = str(sid).strip()
            if len(sid) > 64 or re.search(r'[\s/\\:*?"<>|]', sid):
                report.error(f"{label}.id: unsafe filename {sid!r}")
            if sid in seen_ids:
                report.error(f"{label}.id: duplicate {sid!r}")
            seen_ids.add(sid)
        label = f"shot {sid}"

        mode = shot.get("mode", defaults.get("mode"))
        if not is_path_like(mode):
            report.error(f"{label}: mode missing")
            mode = "auto"
        else:
            mode = str(mode).strip().lower()
            if mode == "t2va":
                report.warn(f"{label}: mode t2va is a display alias; use t2v")
                mode = "t2v"
            if mode not in MODES:
                report.error(f"{label}: unknown mode {mode!r}")
            elif mode == "auto":
                raw_ref_images = shot.get("ref_images") or []
                raw_first = shot.get("first_frame")
                raw_last = shot.get("last_frame")
                if raw_ref_images:
                    inferred = "ref2va"
                elif raw_first and raw_last:
                    inferred = "fl2va"
                elif raw_first:
                    inferred = "i2va"
                elif raw_last:
                    inferred = "l2va"
                else:
                    inferred = "t2v"
                report.warn(f"{label}: mode auto inferred as {inferred}; pin the route in show.json")
                mode = inferred
        summary["modes"][mode] = summary["modes"].get(mode, 0) + 1

        template = shot.get("template", defaults.get("template"))
        if not is_path_like(template):
            report.error(f"{label}: template missing")
            template = "auto"
        else:
            template = str(template).strip()
            if template not in ALL_TEMPLATES:
                report.error(f"{label}: unknown template {template!r}")
            elif template == "auto":
                report.warn(f"{label}: template auto is not reproducible; pin a template")
        summary["templates"][template] = summary["templates"].get(template, 0) + 1

        component_set = shot.get("component_set", defaults.get("component_set", "auto"))
        if not is_path_like(component_set):
            report.error(f"{label}: component_set missing")
            component_set = "auto"
        else:
            component_set = str(component_set).strip().lower()
            if component_set not in COMPONENT_SETS:
                report.error(f"{label}: unknown component_set {component_set!r}")
            if template in SETC and component_set != "auto":
                report.error(f"{label}: Set C template {template} requires component_set=auto (got {component_set})")

        if mode in MODE_TEMPLATES and template != "auto" and template not in MODE_TEMPLATES[mode]:
            report.error(f"{label}: template {template} is not valid for mode {mode}")

        length = shot.get("length", defaults.get("length"))
        length_int = parse_int(length)
        if length_int is None:
            report.error(f"{label}: length missing or not an integer")
        else:
            if length_int < 1:
                report.error(f"{label}: length must be positive")
            elif length_int == 481:
                report.error(f"{label}: 481 frames is forbidden on this workstation (spin deadlock); use <=362")
            elif length_int > 362:
                report.error(f"{label}: {length_int} frames exceeds the 362-frame single-segment limit")
            else:
                total_frames += length_int
                valid_lengths += 1
        shot_fps = shot.get("fps", defaults.get("fps", fps))
        if isinstance(shot_fps, bool) or not isinstance(shot_fps, (int, float)) or shot_fps <= 0:
            report.error(f"{label}: fps invalid")
        elif abs(float(shot_fps) - 24.0) > 0.01:
            report.warn(f"{label}: fps {shot_fps} is not the local 24 fps default")

        prompt_path = check_file(base, shot.get("prompt"), f"{label}.prompt", report, required=True)
        ref_images = shot.get("ref_images") or []
        ref_audios = shot.get("ref_audios") or []
        if not isinstance(ref_images, list):
            report.error(f"{label}.ref_images: must be a list")
            ref_images = []
        if not isinstance(ref_audios, list):
            report.error(f"{label}.ref_audios: must be a list")
            ref_audios = []
        if len(ref_images) > 9:
            report.error(f"{label}.ref_images: {len(ref_images)} exceeds the H3 limit of 9")
        if len(ref_audios) > 3:
            report.error(f"{label}.ref_audios: {len(ref_audios)} exceeds the H3 limit of 3")
        if len(ref_images) + len(ref_audios) > 12:
            report.error(f"{label}: mixed reference files exceed the H3 limit of 12")

        image_paths: list[Path] = []
        for idx, ref in enumerate(ref_images, start=1):
            if not is_path_like(ref):
                report.error(f"{label}.ref_images[{idx}]: must be a path string")
                continue
            path = check_file(base, ref, f"{label}.ref_images[{idx}]", report, required=True)
            if path:
                image_paths.append(path)
                all_ref_paths.append(path)
        audio_paths: list[Path] = []
        audio_total = 0.0
        for idx, ref in enumerate(ref_audios, start=1):
            if not is_path_like(ref):
                report.error(f"{label}.ref_audios[{idx}]: must be a path string")
                continue
            path = check_file(base, ref, f"{label}.ref_audios[{idx}]", report, required=True)
            if path:
                audio_paths.append(path)
                all_ref_paths.append(path)
                if ffprobe:
                    probe = probe_media(path, ffprobe, stream="a:0")
                    if probe is None:
                        report.warn(f"{label}.ref_audios[{idx}]: ffprobe could not read an audio stream")
                    elif probe.get("duration") is not None:
                        audio_total += probe["duration"]
                        if not 2.0 <= probe["duration"] <= 15.0:
                            report.warn(
                                f"{label}.ref_audios[{idx}]: duration {probe['duration']:.2f}s is outside 2–15 s"
                            )
        if audio_total > 15.0 + 0.01:
            report.warn(f"{label}: total reference audio {audio_total:.2f}s exceeds 15 s")

        first_path = None
        last_path = None
        if shot.get("first_frame") not in (None, ""):
            first_path = check_file(base, shot.get("first_frame"), f"{label}.first_frame", report, required=True)
            if first_path:
                all_ref_paths.append(first_path)
        if shot.get("last_frame") not in (None, ""):
            last_path = check_file(base, shot.get("last_frame"), f"{label}.last_frame", report, required=True)
            if last_path:
                all_ref_paths.append(last_path)

        if mode == "ref2va":
            if not ref_images:
                report.error(f"{label}: ref2va requires at least one ref_image")
            if first_path or last_path:
                report.error(f"{label}: ref2va must not mix first_frame/last_frame")
        elif mode in IMAGE_MODES:
            if ref_images or ref_audios:
                report.error(f"{label}: {mode} does not accept ref_images/ref_audios; use ref2va")
            if mode == "i2va" and not first_path:
                report.error(f"{label}: i2va requires first_frame")
            if mode == "fl2va" and not (first_path and last_path):
                report.error(f"{label}: fl2va requires first_frame and last_frame")
            if mode == "l2va" and not last_path:
                report.error(f"{label}: l2va requires last_frame")
            if mode == "i2va" and last_path:
                report.warn(f"{label}: i2va has a last_frame; use mode fl2va for clarity")
        elif mode == "t2v":
            if ref_images or ref_audios or first_path or last_path:
                report.error(f"{label}: t2v must not carry image/audio/frame references")

        white = shot.get("white_model")
        if white not in (None, {}):
            if not isinstance(white, dict):
                report.error(f"{label}.white_model: must be an object or null")
            else:
                if mode != "ref2va":
                    report.error(f"{label}.white_model: white-model references must run through ref2va")
                if not ref_images:
                    report.error(f"{label}.white_model: ref2va needs an identity image alongside the white model")
                source = check_file(base, white.get("source"), f"{label}.white_model.source", report, required=True)
                proxy = check_file(base, white.get("proxy"), f"{label}.white_model.proxy", report, required=True)
                if source:
                    all_ref_paths.append(source)
                if proxy:
                    all_ref_paths.append(proxy)
                if source and proxy and source.resolve() == proxy.resolve():
                    report.error(f"{label}.white_model: source and proxy must be different files")
                if not is_path_like(white.get("version")):
                    report.warn(f"{label}.white_model: version missing; cannot pair with the H3 rerun")
                wm_fps = white.get("fps")
                if wm_fps is not None and (isinstance(wm_fps, bool) or not isinstance(wm_fps, (int, float))):
                    report.error(f"{label}.white_model.fps: must be a number")
                elif wm_fps is not None and abs(float(wm_fps) - 12.0) > 0.01:
                    report.warn(f"{label}.white_model.fps: {wm_fps} is not the 12 fps proxy default")
                wm_res = white.get("resolution")
                if wm_res is not None and str(wm_res) != "864x480":
                    report.warn(f"{label}.white_model.resolution: {wm_res} is not the 864x480 proxy default")
                if proxy and ffprobe:
                    probe = probe_media(proxy, ffprobe, stream="v:0")
                    if probe is None:
                        report.warn(f"{label}.white_model.proxy: ffprobe could not read a video stream")
                    else:
                        if probe.get("fps") is not None and abs(probe["fps"] - 12.0) > 0.1:
                            report.warn(f"{label}.white_model.proxy: actual fps is {probe['fps']:.3f}, expected 12")
                        if probe.get("width") and probe.get("height") and (
                            probe["width"] != 864 or probe["height"] != 480
                        ):
                            report.warn(
                                f"{label}.white_model.proxy: actual size is "
                                f"{probe['width']}x{probe['height']}, expected 864x480"
                            )

        acceptance = shot.get("acceptance")
        if not isinstance(acceptance, dict):
            report.error(f"{label}: acceptance block is required")
            acceptance = {}
        identity = acceptance.get("identity")
        if identity not in (None, ""):
            if not is_path_like(identity):
                report.error(f"{label}.acceptance.identity: must be a character id")
            elif not characters:
                report.error(f"{label}.acceptance.identity: {identity!r} has no canon characters")
            elif identity not in characters:
                report.error(f"{label}.acceptance.identity: {identity!r} not found in canon.json")
        for key in ("requires_audio", "requires_dialogue"):
            if key in acceptance and not isinstance(acceptance[key], bool):
                report.error(f"{label}.acceptance.{key}: must be true/false")
        min_events = acceptance.get("min_action_events", 0)
        min_events_int = parse_int(min_events)
        if min_events_int is None:
            report.error(f"{label}.acceptance.min_action_events: must be an integer")
        else:
            if min_events_int < 0:
                report.error(f"{label}.acceptance.min_action_events: must be >=0")
            if min_events_int >= 5 and (length_int is None or length_int < 124):
                report.warn(f"{label}: {min_events_int} action events do not fit a sub-5-second generation")
            if min_events_int >= 9 and (length_int is None or length_int < 243):
                report.warn(f"{label}: {min_events_int} action events need a longer generation or a split")
        if acceptance.get("requires_dialogue") is True and (length_int is None or length_int < 72):
            report.warn(f"{label}: dialogue planned in a generation shorter than ~3 seconds")
        if prompt_path:
            check_prompt(prompt_path, mode, template, ref_audios, report)

    if duration is not None and valid_lengths:
        minimum = total_frames / float(fps)
        maximum = (total_frames + 16 * valid_lengths) / float(fps)
        if not (minimum - 0.25 <= float(duration) <= maximum + 0.25):
            report.warn(
                f"deliverable.duration_seconds: {duration}s is outside the expected "
                f"{minimum:.2f}–{maximum:.2f}s window for {total_frames} requested frames"
            )

    post = spec.get("post")
    if post is not None and not isinstance(post, dict):
        report.error("spec.post: must be an object")
    elif isinstance(post, dict):
        for key in ("concat", "loudnorm", "cover"):
            if key in post and not isinstance(post[key], bool):
                report.error(f"post.{key}: must be true/false")
        post_subs = post.get("subtitles")
        if post_subs not in (None, ""):
            check_file(base, post_subs, "post.subtitles", report, required=True)
            if deliverable_subs not in (None, "") and str(post_subs) != str(deliverable_subs):
                report.warn("post.subtitles differs from deliverable.subtitles")
            if deliverable_subs is None:
                report.warn("post.subtitles is set but deliverable.subtitles is null")
        if post.get("concat") is False and len(shots) > 1:
            report.warn("post.concat is false but the show has multiple generation units")

    version_lock = spec.get("version_lock")
    if version_lock is not None:
        if not isinstance(version_lock, dict):
            report.error("spec.version_lock: must be an object")
        elif not is_path_like(version_lock.get("reference_pack_sha256")):
            report.warn("version_lock.reference_pack_sha256: empty; reference pack is not frozen")
    if len(shots) > 1 and version_lock is None:
        report.warn("version_lock: missing for a multi-shot show")

    if not ffprobe:
        report.note("ffprobe not found; audio duration and white-model proxy specs were not probed")

    if check_sha:
        check_sha_pack(base, all_ref_paths, report)
        lock = version_lock if isinstance(version_lock, dict) else {}
        locked_hash = lock.get("reference_pack_sha256")
        if is_path_like(locked_hash):
            locked_hash = str(locked_hash).strip()
            if not re.fullmatch(r"[0-9a-fA-F]{64}", locked_hash):
                report.warn("version_lock.reference_pack_sha256 is not a 64-character SHA-256 hex string")
            else:
                sha_path = base / "refs.sha256"
                if sha_path.is_file():
                    actual = sha256_file(sha_path)
                    if actual.lower() != locked_hash.lower():
                        report.error("version_lock.reference_pack_sha256 does not match refs.sha256")

    return report, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an H3 show contract before submission")
    parser.add_argument("--spec", required=True, help="path to show.json")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--strict", action="store_true", help="treat warnings as a failed gate")
    parser.add_argument("--check-sha", action="store_true", help="verify referenced files against refs.sha256")
    parser.add_argument("--ffprobe", help="explicit ffprobe path for audio/proxy probes")
    args = parser.parse_args()

    spec_path = Path(args.spec).expanduser().resolve()
    if not spec_path.is_file():
        print(f"ERROR spec not found: {spec_path}", file=sys.stderr)
        return 1

    ffprobe = find_ffprobe(args.ffprobe)
    report, summary = validate(spec_path, check_sha=args.check_sha, ffprobe=ffprobe)
    fatal = bool(report.errors) or (args.strict and bool(report.warnings))
    status = "FAIL" if fatal else ("PASS_WITH_WARNINGS" if report.warnings else "PASS")

    payload = {
        "ok": not fatal,
        "status": status,
        "strict": bool(args.strict),
        "spec": str(spec_path),
        "project": summary.get("project"),
        "shots": summary.get("shots", 0),
        "modes": summary.get("modes", {}),
        "templates": summary.get("templates", {}),
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
        "errors": report.errors,
        "warnings": report.warnings,
        "notes": report.notes,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Show contract: {spec_path}")
        print(f"Project: {summary.get('project')}  Shots: {summary.get('shots', 0)}")
        print(f"Status: {status}  ({len(report.errors)} errors, {len(report.warnings)} warnings)")
        if report.errors:
            print("\nErrors:")
            for item in report.errors:
                print(f"  - {item}")
        if report.warnings:
            print("\nWarnings:")
            for item in report.warnings:
                print(f"  - {item}")
        if report.notes:
            print("\nNotes:")
            for item in report.notes:
                print(f"  - {item}")
        if not fatal:
            print("\nGate passed. The show may proceed to preview generation.")
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
