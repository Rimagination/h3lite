# -*- coding: utf-8 -*-
"""Measure per-character voice consistency across generated shots.

Level, fundamental frequency (F0), periodicity (a harmonics-to-noise proxy),
spectral centroid and high-frequency ratio are measured inside labelled time
windows, then grouped by character. This turns "he sounds young here and old
there" into numbers: an elderly male voice sits near 85-115 Hz with a low
centroid, a younger male near 120-160 Hz with a brighter top.

Gate defaults (calibrated on a full 17-shot episode, adjust per production):
  * same character across shots: F0 median spread <= 2 semitones (~12%)
  * same character across shots: spectral centroid spread <= 25%
  * two characters sharing a shot: F0 medians >= 3 semitones apart

Usage:
    python h3_voice_audit.py --plan voice_windows.json [--json out.json]
    python h3_voice_audit.py --plan voice_windows.json --comfyui <ComfyUI-root>

Plan format (list, or {"windows": [...]}):
    [{"character": "TAMURA", "file": "video/shot05.mp4",
      "start": 3.95, "end": 7.05, "band": [70, 220], "note": "line1"}]

`band` is the F0 search range in Hz for that character. `file` may be a video
or audio file; only the audio track is decoded. Requires numpy and ffmpeg.
This script only measures. It never rewrites audio, never adds a second voice
pass, and never runs TTS.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

try:
    import numpy as np
except ImportError:  # pragma: no cover - environment guidance
    print("numpy is required: pip install numpy (present in any ComfyUI venv)", file=sys.stderr)
    raise SystemExit(2)

SR = 16000
WIN = 640          # 40 ms
HOP = 160          # 10 ms
NFFT = 2048
DEFAULT_BAND = (70, 400)


def find_ffmpeg(explicit: str | None, comfyui: Path | None) -> str | None:
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return str(candidate)
    configured = os.environ.get("H3LITE_FFMPEG")
    if configured and Path(configured).expanduser().is_file():
        return str(Path(configured).expanduser())
    found = shutil.which("ffmpeg")
    if found:
        return found
    if comfyui is not None:
        for root in (comfyui, comfyui / "bin", comfyui / "ffmpeg" / "bin",
                     comfyui / "tools" / "ffmpeg" / "bin", comfyui.parent):
            for name in ("ffmpeg.exe", "ffmpeg"):
                candidate = root / name
                if candidate.is_file():
                    return str(candidate)
    return None


def decode(ffmpeg: str, path: Path) -> "np.ndarray":
    raw = subprocess.check_output([
        ffmpeg, "-v", "error", "-i", str(path),
        "-f", "f32le", "-ac", "1", "-ar", str(SR), "-",
    ])
    return np.frombuffer(raw, dtype=np.float32)


def measure(x: "np.ndarray", a: float, b: float, band=DEFAULT_BAND) -> dict:
    s, e = int(a * SR), min(int(b * SR), len(x))
    seg = x[s:e]
    if len(seg) < WIN:
        return {}
    rms = float(np.sqrt(np.mean(seg ** 2)) + 1e-12)
    db = 20 * math.log10(rms)
    frames = np.lib.stride_tricks.sliding_window_view(seg, WIN)[::HOP]
    win = np.hanning(WIN)
    f0s, strengths, mags = [], [], []
    freqs = np.fft.rfftfreq(NFFT, 1 / SR)
    lo, hi = int(SR / band[1]), int(SR / band[0])
    for fr in frames:
        f = (fr - fr.mean()) * win
        if np.sqrt(np.mean(f ** 2)) < 1e-4:
            continue
        ac = np.correlate(f, f, "full")[WIN - 1:]
        ac /= ac[0] + 1e-9
        lag = lo + int(np.argmax(ac[lo:hi]))
        st = float(ac[lag])
        if st > 0.30:
            f0s.append(SR / lag)
            strengths.append(st)
            mags.append(np.abs(np.fft.rfft(f, NFFT)))
    if not f0s:
        return {"db": round(db, 1), "voiced": 0.0}
    f0 = np.array(f0s)
    m = np.mean(np.array(mags), axis=0)
    tot = float(m.sum()) + 1e-9
    centroid = float((freqs * m).sum() / tot)
    hf = float(m[freqs > 2000].sum() / tot)
    return {
        "db": round(db, 1),
        "voiced": round(len(f0s) / max(1, len(frames)), 2),
        "f0_med": round(float(np.median(f0)), 1),
        "f0_p10": round(float(np.percentile(f0, 10)), 1),
        "f0_p90": round(float(np.percentile(f0, 90)), 1),
        "period": round(float(np.mean(strengths)), 2),
        "centroid": round(centroid),
        "hf_ratio": round(hf, 3),
    }


def semitones(f1: float, f2: float) -> float:
    if f1 <= 0 or f2 <= 0:
        return 0.0
    return 12.0 * math.log2(f2 / f1)


def load_plan(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    windows = data.get("windows") if isinstance(data, dict) else data
    if not isinstance(windows, list) or not windows:
        raise RuntimeError("plan must be a non-empty list of windows, or {\"windows\": [...]}")
    for w in windows:
        for key in ("character", "file", "start", "end"):
            if key not in w:
                raise RuntimeError(f"window missing '{key}': {w}")
        if float(w["end"]) <= float(w["start"]):
            raise RuntimeError(f"window end must be after start: {w}")
    return windows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, help="JSON list of labelled windows")
    ap.add_argument("--json", help="write the full measurement report here")
    ap.add_argument("--ffmpeg", help="ffmpeg executable; otherwise H3LITE_FFMPEG, PATH, then <ComfyUI>")
    ap.add_argument("--comfyui", help="ComfyUI root used to locate ffmpeg")
    ap.add_argument("--max-spread-semitones", type=float, default=2.0)
    ap.add_argument("--max-centroid-spread", type=float, default=0.25, help="relative spread, 0.25 = 25%%")
    ap.add_argument("--min-separation-semitones", type=float, default=3.0)
    ap.add_argument("--no-gate", action="store_true", help="measure only, do not fail on thresholds")
    args = ap.parse_args()

    ffmpeg = find_ffmpeg(args.ffmpeg, Path(args.comfyui).expanduser() if args.comfyui else None)
    if not ffmpeg:
        print("ffmpeg not found: set H3LITE_FFMPEG or pass --ffmpeg / --comfyui", file=sys.stderr)
        return 2
    plan = load_plan(Path(args.plan).expanduser())

    cache: dict[str, np.ndarray] = {}
    rows: list[dict] = []
    for w in plan:
        path = Path(w["file"]).expanduser()
        if not path.is_file():
            print(f"missing file: {path}", file=sys.stderr)
            return 2
        key = str(path.resolve())
        if key not in cache:
            cache[key] = decode(ffmpeg, path)
        band = tuple(w.get("band") or DEFAULT_BAND)
        r = measure(cache[key], float(w["start"]), float(w["end"]), band)
        r.update({"character": str(w["character"]), "file": str(path),
                  "start": float(w["start"]), "end": float(w["end"]),
                  "band": list(band), "note": w.get("note", "")})
        rows.append(r)

    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["character"], []).append(r)

    failures: list[str] = []
    summary: dict[str, dict] = {}
    for char, items in groups.items():
        vals = [r["f0_med"] for r in items if r.get("f0_med")]
        cents = [r["centroid"] for r in items if r.get("centroid")]
        entry: dict = {"windows": len(items), "voiced_windows": len(vals)}
        print(f"\n=== {char} ===")
        print(f"{'file':>28} {'window':>13} {'dBFS':>6} {'F0med':>6} {'p10-p90':>11} "
              f"{'period':>6} {'centroid':>8} {'HF':>6}  note")
        for r in items:
            name = Path(r["file"]).name[-28:]
            if not r.get("f0_med"):
                print(f"{name:>28} {r['start']:5.2f}-{r['end']:5.2f} {r.get('db', 0):6.1f}"
                      f"   (no voiced frames)  {r['note']}")
                continue
            print(f"{name:>28} {r['start']:5.2f}-{r['end']:5.2f} {r['db']:6.1f} {r['f0_med']:6.1f} "
                  f"{r['f0_p10']:5.0f}-{r['f0_p90']:<5.0f} {r['period']:6.2f} {r['centroid']:8.0f} "
                  f"{r['hf_ratio']:6.3f}  {r['note']}")
        if len(vals) > 1:
            spread = semitones(min(vals), max(vals))
            entry["f0_min"], entry["f0_max"] = min(vals), max(vals)
            entry["f0_spread_semitones"] = round(spread, 2)
            print(f"  F0 spread: {min(vals):.0f}-{max(vals):.0f} Hz = {spread:.2f} semitones")
            if spread > args.max_spread_semitones:
                failures.append(f"{char}: F0 spread {spread:.2f} semitones > {args.max_spread_semitones}")
        if len(cents) > 1:
            rel = (max(cents) - min(cents)) / max(1.0, min(cents))
            entry["centroid_min"], entry["centroid_max"] = min(cents), max(cents)
            entry["centroid_spread_rel"] = round(rel, 3)
            print(f"  centroid spread: {min(cents)}-{max(cents)} Hz = {rel * 100:.0f}%")
            if rel > args.max_centroid_spread:
                failures.append(f"{char}: centroid spread {rel * 100:.0f}% > {args.max_centroid_spread * 100:.0f}%")
        summary[char] = entry

    # Characters sharing a file must stay acoustically apart, or the model may
    # collapse them into one voice.
    separations: list[dict] = []
    by_file: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        if r.get("f0_med"):
            by_file.setdefault(r["file"], {}).setdefault(r["character"], []).append(r["f0_med"])
    for file, chars in by_file.items():
        names = sorted(chars)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                fa = float(np.median(chars[a]))
                fb = float(np.median(chars[b]))
                sep = abs(semitones(min(fa, fb), max(fa, fb)))
                separations.append({"file": file, "a": a, "b": b,
                                    "f0_a": fa, "f0_b": fb, "separation_semitones": round(sep, 2)})
                if sep < args.min_separation_semitones:
                    failures.append(f"{Path(file).name}: {a} vs {b} only {sep:.2f} semitones apart "
                                    f"(< {args.min_separation_semitones}); voice-collapse risk")
    if separations:
        print("\n=== same-shot separation ===")
        for s in separations:
            print(f"  {Path(s['file']).name}: {s['a']} {s['f0_a']:.0f} Hz vs {s['b']} {s['f0_b']:.0f} Hz "
                  f"= {s['separation_semitones']:.2f} semitones")

    verdict = "PASS" if not failures else "FAIL"
    if args.no_gate:
        verdict = "MEASURED"
    print(f"\nvoice consistency: {verdict}")
    for f in failures:
        print("  -", f)
    if failures and not args.no_gate:
        print("  fix in h3-prompt/h3-generate first (VOICE block, casting distance, clean reference,")
        print("  duration-only retry). Bounded pitch/formant matching needs explicit user approval;")
        print("  never add a second voice pass or TTS.")

    report = {"gate": {"max_spread_semitones": args.max_spread_semitones,
                       "max_centroid_spread": args.max_centroid_spread,
                       "min_separation_semitones": args.min_separation_semitones},
              "verdict": verdict, "failures": failures,
              "characters": summary, "separations": separations, "windows": rows}
    if args.json:
        out = Path(args.json).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out}")
    return 0 if verdict != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())