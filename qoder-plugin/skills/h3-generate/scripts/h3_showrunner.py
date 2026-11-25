#!/usr/bin/env python3
"""Run a show.json as a batch: validate once, submit every shot, monitor, verify.

Minimal showrunner for the H3lite show contract. It does not invent prompts or
change model settings; it translates each shot card into the existing
h3_generate.py CLI, submits with --queue-only, then verifies every prompt with
h3_status.py. State is kept in show_manifest.json so a failed run can resume
without resubmitting completed shots.

Usage:
  python h3_showrunner.py --spec projects/ep04/show.json --output-dir E:/MiniMax-H3/ComfyUI/output
  python h3_showrunner.py --spec projects/ep04/show.json --only s02 --resume
  python h3_showrunner.py --spec projects/ep04/show.json --dry-run --strict --check-sha
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
GENERATE = SCRIPTS / "h3_generate.py"
STATUS = SCRIPTS / "h3_status.py"
VALIDATE = SCRIPTS / "h3_show_validate.py"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def _resolve(root: Path, value: str | None) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    expanded = Path(os.path.expandvars(str(value))).expanduser()
    return expanded if expanded.is_absolute() else (root / expanded)


def _sanitize(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._-")
    return cleaned or "shot"


def _merge(defaults: dict[str, Any], shot: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    merged.update(shot)
    return merged


def _run(command: list[str], *, cwd: Path, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout="",
            stderr=f"command timed out after {timeout or 0:.0f}s",
        )


def _json_from_stdout(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(text[start : end + 1])
                return value if isinstance(value, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def validate_show(args: argparse.Namespace, spec_path: Path) -> tuple[bool, str, dict[str, Any] | None]:
    command = [sys.executable, str(VALIDATE), "--spec", str(spec_path), "--json"]
    if args.strict:
        command.append("--strict")
    if args.check_sha:
        command.append("--check-sha")
    if args.ffprobe:
        command.extend(["--ffprobe", str(args.ffprobe)])
    completed = _run(command, cwd=SCRIPTS, timeout=max(60.0, args.timeout))
    report = _json_from_stdout(completed.stdout)
    if completed.returncode != 0:
        detail = completed.stdout.strip() or completed.stderr.strip()
        return False, detail[-4000:], report
    return True, "", report


def _acceptance_requires_audio(merged: dict[str, Any], deliverable: dict[str, Any]) -> bool:
    acceptance = merged.get("acceptance") if isinstance(merged.get("acceptance"), dict) else {}
    if "requires_audio" in acceptance:
        return bool(acceptance["requires_audio"])
    return str(deliverable.get("audio", "native")).lower() == "native"


def build_generate_command(
    *,
    spec: dict[str, Any],
    defaults: dict[str, Any],
    shot: dict[str, Any],
    spec_path: Path,
    project_root: Path,
    args: argparse.Namespace,
    run_root: Path,
) -> tuple[list[str] | None, str | None, dict[str, Any]]:
    merged = _merge(defaults, shot)
    shot_id = str(merged.get("id") or shot.get("id") or "").strip()
    if not shot_id:
        return None, "shot is missing id", merged
    white_model = merged.get("white_model")
    ref_video_path: Path | None = None
    if white_model:
        if not isinstance(white_model, dict):
            return None, f"{shot_id}: white_model must be an object", merged
        proxy_value = white_model.get("proxy")
        if not proxy_value:
            return None, f"{shot_id}: white_model.proxy is missing", merged
        ref_video_path = _resolve(project_root, str(proxy_value))
        if ref_video_path is None or not ref_video_path.is_file():
            return None, f"{shot_id}: white model proxy not found: {ref_video_path}", merged
        if not args.comfyui:
            return None, f"{shot_id}: --comfyui is required for white_model reference video staging", merged

    prompt_value = merged.get("prompt")
    if not prompt_value:
        return None, f"{shot_id}: prompt is missing", merged
    prompt_path = _resolve(project_root, str(prompt_value))
    if prompt_path is None or not prompt_path.is_file():
        return None, f"{shot_id}: prompt file not found: {prompt_path}", merged

    command = [
        sys.executable,
        str(GENERATE),
        "--prompt-file",
        str(prompt_path),
        "--workflow-template",
        str(merged.get("template") or defaults.get("template") or "h3_c_ref2va768"),
        "--component-set",
        str(merged.get("component_set") or defaults.get("component_set") or "auto"),
        "--run-root",
        str(run_root),
        "--filename-prefix",
        _sanitize(f"{_sanitize(spec.get('project', 'show'))}_{shot_id}"),
        "--queue-only",
        "--json",
    ]
    if args.base_url:
        command.extend(["--base-url", str(args.base_url)])
    if args.output_dir:
        command.extend(["--output-dir", str(args.output_dir)])
    if args.comfyui:
        command.extend(["--comfyui", str(args.comfyui)])

    resolution = merged.get("resolution") or spec.get("deliverable", {}).get("resolution")
    if resolution:
        command.extend(["--resolution", str(resolution)])
    length = merged.get("length")
    if length is not None:
        command.extend(["--length", str(int(length))])
    seed = merged.get("seed")
    if seed is not None:
        command.extend(["--seed", str(int(seed))])
    fps = merged.get("fps") or spec.get("deliverable", {}).get("fps")
    if fps is not None:
        command.extend(["--fps", str(float(fps))])
    video_vae = merged.get("video_vae") or defaults.get("video_vae")
    if video_vae:
        command.extend(["--video-vae", str(video_vae)])

    for value in merged.get("ref_images") or []:
        path = _resolve(project_root, str(value))
        if path is None or not path.is_file():
            return None, f"{shot_id}: ref image not found: {path}", merged
        command.extend(["--ref-image", str(path)])
    for value in merged.get("ref_audios") or []:
        path = _resolve(project_root, str(value))
        if path is None or not path.is_file():
            return None, f"{shot_id}: ref audio not found: {path}", merged
        command.extend(["--ref-audio", str(path)])
    if ref_video_path is not None:
        command.extend(["--ref-video", str(ref_video_path)])
    for key, flag in (("first_frame", "--first-frame"), ("last_frame", "--last-frame")):
        value = merged.get(key)
        if value:
            path = _resolve(project_root, str(value))
            if path is None or not path.is_file():
                return None, f"{shot_id}: {key} not found: {path}", merged
            command.extend([flag, str(path)])

    deliverable = spec.get("deliverable") if isinstance(spec.get("deliverable"), dict) else {}
    if _acceptance_requires_audio(merged, deliverable):
        command.extend(["--audio-policy", "require"])
    return command, None, merged


def build_status_command(
    *,
    prompt_id: str,
    merged: dict[str, Any],
    spec: dict[str, Any],
    args: argparse.Namespace,
    run_root: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(STATUS),
        "--prompt-id",
        prompt_id,
        "--watch",
        "--json",
        "--run-root",
        str(run_root),
        "--watch-interval",
        str(max(1.0, args.poll_interval)),
        "--watch-timeout",
        str(max(1.0, args.timeout)),
    ]
    if args.base_url:
        command.extend(["--base-url", str(args.base_url)])
    if args.output_dir:
        command.extend(["--output-dir", str(args.output_dir)])
    if args.comfyui:
        command.extend(["--comfyui", str(args.comfyui)])
    length = merged.get("length")
    if length is not None:
        command.extend(["--expected-frames", str(int(length))])
    fps = merged.get("fps") or spec.get("deliverable", {}).get("fps")
    if fps is not None:
        command.extend(["--expected-fps", str(float(fps))])
    deliverable = spec.get("deliverable") if isinstance(spec.get("deliverable"), dict) else {}
    if _acceptance_requires_audio(merged, deliverable):
        command.append("--require-audio")
    command.append("--dynamic-check")
    return command


def _selected_shots(shots: list[dict[str, Any]], only: list[str] | None) -> list[dict[str, Any]]:
    if not only:
        return shots
    wanted = {value.strip() for group in only for value in str(group).split(",") if value.strip()}
    return [shot for shot in shots if str(shot.get("id", "")).strip() in wanted]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="path to show.json")
    parser.add_argument("--project-root", help="project root; defaults to the show.json directory")
    parser.add_argument("--manifest", help="show_manifest.json path; defaults inside the project root")
    parser.add_argument("--base-url", default="http://127.0.0.1:8188", help="ComfyUI server URL")
    parser.add_argument("--output-dir", help="local ComfyUI output directory for verification")
    parser.add_argument("--comfyui", help="ComfyUI root used for reference staging")
    parser.add_argument("--run-root", help="run manifest root; defaults to <project>/runs")
    parser.add_argument("--only", action="append", help="shot id or comma-separated ids; repeatable")
    parser.add_argument("--resume", action="store_true", help="skip completed shots and continue submitted but unverified shots")
    parser.add_argument("--force", action="store_true", help="ignore completed state and resubmit")
    parser.add_argument("--dry-run", action="store_true", help="validate and print commands without submitting")
    parser.add_argument("--no-watch", action="store_true", help="submit only; write prompt ids and exit")
    parser.add_argument("--strict", action="store_true", help="treat validator warnings as failures")
    parser.add_argument("--check-sha", action="store_true", help="verify refs.sha256 during validation")
    parser.add_argument("--ffprobe", help="ffprobe path for the show validator")
    parser.add_argument("--timeout", type=float, default=3600.0, help="per-shot monitor timeout in seconds")
    parser.add_argument("--poll-interval", type=float, default=20.0, help="seconds between status polls")
    parser.add_argument("--json", action="store_true", help="print a machine-readable summary")
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args()
    spec_path = Path(args.spec).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else spec_path.parent
    run_root = Path(args.run_root).expanduser().resolve() if args.run_root else (project_root / "runs")
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else (project_root / "show_manifest.json")

    try:
        spec = _read_json(spec_path)
    except Exception as exc:
        print(f"ERROR: cannot read show spec: {exc}", file=sys.stderr)
        return 2

    ok, detail, validation = validate_show(args, spec_path)
    if not ok:
        print("ERROR: show validation failed", file=sys.stderr)
        if detail:
            print(detail, file=sys.stderr)
        if args.json:
            print(json.dumps({"ok": False, "stage": "validate", "report": validation}, ensure_ascii=False, indent=2))
        return 1
    if not args.json and validation and validation.get("warnings"):
        print(f"validation: PASS with {len(validation.get('warnings', []))} warning(s)")

    shots = spec.get("shots")
    if not isinstance(shots, list) or not shots:
        print("ERROR: show spec has no shots", file=sys.stderr)
        return 2
    defaults = spec.get("defaults") if isinstance(spec.get("defaults"), dict) else {}
    selected = _selected_shots(shots, args.only)
    if not selected:
        print("ERROR: --only matched no shots", file=sys.stderr)
        return 2

    previous: dict[str, Any] = {}
    if args.resume and manifest_path.is_file():
        try:
            existing = _read_json(manifest_path)
            entries = existing.get("shots")
            if isinstance(entries, dict):
                previous = entries
        except Exception as exc:
            print(f"WARNING: cannot read existing manifest, starting fresh: {exc}", file=sys.stderr)

    state: dict[str, Any] = {
        "schema_version": 1,
        "project": spec.get("project"),
        "spec": str(spec_path),
        "updated_at": _now(),
        "shots": dict(previous),
    }

    monitor: list[tuple[str, dict[str, Any]]] = []
    submitted = 0
    failures: list[str] = []

    for shot in selected:
        merged = _merge(defaults, shot)
        shot_id = str(merged.get("id") or shot.get("id") or "").strip()
        if not shot_id:
            failures.append("shot without id")
            continue
        prior = previous.get(shot_id) if isinstance(previous.get(shot_id), dict) else {}
        if args.resume and not args.force and prior.get("state") == "completed" and prior.get("ok"):
            state["shots"][shot_id] = prior
            if not args.json:
                print(f"skip {shot_id}: completed")
            continue
        if args.resume and not args.force and prior.get("state") == "submitted" and prior.get("prompt_id"):
            monitor.append((shot_id, merged))
            state["shots"][shot_id] = prior
            if not args.json:
                print(f"resume {shot_id}: queued {prior.get('prompt_id')}")
            continue

        command, error, merged = build_generate_command(
            spec=spec,
            defaults=defaults,
            shot=shot,
            spec_path=spec_path,
            project_root=project_root,
            args=args,
            run_root=run_root,
        )
        if error or command is None:
            failures.append(f"{shot_id}: {error}")
            state["shots"][shot_id] = {
                "id": shot_id,
                "state": "failed",
                "ok": False,
                "error": error,
                "updated_at": _now(),
            }
            if not args.json:
                print(f"fail {shot_id}: {error}", file=sys.stderr)
            continue

        if args.dry_run:
            if not args.json:
                print(f"dry-run {shot_id}: {subprocess.list2cmdline(command)}")
            state["shots"][shot_id] = {
                "id": shot_id,
                "state": "dry_run",
                "ok": True,
                "command": command,
                "updated_at": _now(),
            }
            continue

        completed = _run(command, cwd=SCRIPTS, timeout=max(60.0, args.timeout))
        result = _json_from_stdout(completed.stdout)
        if completed.returncode != 0 or not result or not result.get("ok"):
            detail_text = (completed.stdout.strip() or completed.stderr.strip())[-2000:]
            failures.append(f"{shot_id}: submit failed: {detail_text}")
            state["shots"][shot_id] = {
                "id": shot_id,
                "state": "failed",
                "ok": False,
                "error": detail_text,
                "updated_at": _now(),
            }
            if not args.json:
                print(f"fail {shot_id}: submit failed", file=sys.stderr)
            continue

        prompt_id = str(result.get("prompt_id", ""))
        state["shots"][shot_id] = {
            "id": shot_id,
            "state": "submitted",
            "ok": False,
            "prompt_id": prompt_id,
            "queued_at_utc": result.get("queued_at_utc"),
            "run_manifest": result.get("run_manifest"),
            "anchor_sheet": result.get("anchor_sheet_path"),
            "template": result.get("target", {}).get("template") if isinstance(result.get("target"), dict) else None,
            "updated_at": _now(),
        }
        monitor.append((shot_id, merged))
        submitted += 1
        _write_json_atomic(manifest_path, state)
        if not args.json:
            print(f"queued {shot_id}: {prompt_id}")

    _write_json_atomic(manifest_path, state)

    if args.dry_run or args.no_watch:
        summary = {
            "ok": not failures,
            "stage": "dry_run" if args.dry_run else "submitted",
            "submitted": submitted,
            "monitored": len(monitor),
            "failures": failures,
            "manifest": str(manifest_path),
            "shots": state["shots"],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json else f"manifest: {manifest_path}")
        return 0 if not failures else 1

    for shot_id, merged in monitor:
        entry = state["shots"].get(shot_id)
        if not isinstance(entry, dict) or not entry.get("prompt_id"):
            continue
        if not args.json:
            print(f"monitor {shot_id}: {entry['prompt_id']}")
        command = build_status_command(
            prompt_id=str(entry["prompt_id"]),
            merged=merged,
            spec=spec,
            args=args,
            run_root=run_root,
        )
        completed = _run(command, cwd=SCRIPTS, timeout=max(60.0, args.timeout + 120.0))
        result = _json_from_stdout(completed.stdout)
        if completed.returncode != 0 or not result or not result.get("ok"):
            detail_text = (completed.stdout.strip() or completed.stderr.strip())[-2000:]
            failures.append(f"{shot_id}: verification failed: {detail_text}")
            entry.update(
                {
                    "state": "failed",
                    "ok": False,
                    "error": detail_text,
                    "verified_at_utc": _now(),
                }
            )
            if not args.json:
                print(f"fail {shot_id}: verification failed", file=sys.stderr)
        else:
            entry.update(
                {
                    "state": "completed",
                    "ok": True,
                    "verified_at_utc": _now(),
                    "outputs": result.get("outputs"),
                    "elapsed_seconds": result.get("elapsed_seconds"),
                }
            )
            if not args.json:
                print(f"done {shot_id}: verified")
        state["updated_at"] = _now()
        _write_json_atomic(manifest_path, state)

    _write_json_atomic(manifest_path, state)
    summary = {
        "ok": not failures,
        "stage": "completed",
        "submitted": submitted,
        "monitored": len(monitor),
        "failures": failures,
        "manifest": str(manifest_path),
        "shots": state["shots"],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"manifest: {manifest_path}")
        if failures:
            print("failures:", file=sys.stderr)
            for failure in failures:
                print(f"- {failure}", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
