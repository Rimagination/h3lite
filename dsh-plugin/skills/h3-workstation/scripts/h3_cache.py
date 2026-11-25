#!/usr/bin/env python3
"""Small, explicit cache for H3 Lite doctor/preflight/QA reports.

The cache is opt-in and keyed by the caller. It never decides what is safe to
reuse; callers must choose a key that includes the environment or output
fingerprint. Defaults are conservative: successful commands only, short TTL,
and a plain JSON envelope that can be inspected or deleted.

Usage:
  python h3_cache.py fingerprint <file> [<file> ...] --sha
  python h3_cache.py get --cache-dir <dir> --key doctor:20261125
  python h3_cache.py put --cache-dir <dir> --key qa:shot01 --payload-file qa.json --ttl 86400
  python h3_cache.py run --cache-dir <dir> --key doctor:20261125 --ttl 1800 -- <command...>
  python h3_cache.py prune --cache-dir <dir> --older-than-days 14
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


def _now() -> float:
    return time.time()


def _iso(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _cache_path(cache_dir: Path, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return cache_dir / f"{digest}.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_envelope(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _expired(envelope: dict[str, Any]) -> bool:
    try:
        return float(envelope.get("expires_at", 0)) <= _now()
    except (TypeError, ValueError):
        return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(paths: list[str], *, with_sha: bool) -> dict[str, Any]:
    files: dict[str, Any] = {}
    errors: list[str] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        entry: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
        if path.is_file():
            stat = path.stat()
            entry.update({"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
            if with_sha:
                entry["sha256"] = _sha256(path)
        else:
            errors.append(f"missing file: {path}")
        files[raw] = entry
    return {"generated_at": _iso(_now()), "files": files, "errors": errors}


def _get(args: argparse.Namespace) -> int:
    path = _cache_path(Path(args.cache_dir).expanduser().resolve(), args.key)
    envelope = _read_envelope(path)
    if envelope is None:
        print(f"cache miss: {args.key}", file=sys.stderr)
        return 1
    if _expired(envelope):
        print(f"cache expired: {args.key}", file=sys.stderr)
        return 1
    print(json.dumps(envelope, ensure_ascii=False, indent=2))
    return 0


def _put(args: argparse.Namespace) -> int:
    if args.payload_file:
        payload = json.loads(Path(args.payload_file).expanduser().read_text(encoding="utf-8"))
    else:
        payload = json.loads(sys.stdin.read())
    envelope = {
        "key": args.key,
        "created_at": _now(),
        "expires_at": _now() + max(0, args.ttl),
        "payload": payload,
    }
    path = _cache_path(Path(args.cache_dir).expanduser().resolve(), args.key)
    _atomic_write(path, envelope)
    print(str(path))
    return 0


def _run(args: argparse.Namespace) -> int:
    command = list(args.command)
    while command and command[0] == "--":
        command.pop(0)
    if not command:
        print("ERROR: run needs a command after --", file=sys.stderr)
        return 2
    cache_dir = Path(args.cache_dir).expanduser().resolve()
    path = _cache_path(cache_dir, args.key)
    envelope = _read_envelope(path)
    if envelope is not None and not _expired(envelope):
        stdout = str(envelope.get("stdout", ""))
        stderr = str(envelope.get("stderr", ""))
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")
        if stderr:
            print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)
        return int(envelope.get("returncode", 0))
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr)
    if completed.returncode == 0:
        _atomic_write(
            path,
            {
                "key": args.key,
                "created_at": _now(),
                "expires_at": _now() + max(0, args.ttl),
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )
    return completed.returncode


def _prune(args: argparse.Namespace) -> int:
    cache_dir = Path(args.cache_dir).expanduser().resolve()
    if not cache_dir.is_dir():
        print("0 files removed")
        return 0
    cutoff = _now() - max(0, args.older_than_days) * 86400
    removed = 0
    for path in sorted(cache_dir.glob("*.json")):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if args.expired_only:
            envelope = _read_envelope(path)
            if envelope is None or not _expired(envelope):
                continue
        elif mtime >= cutoff:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    print(f"{removed} files removed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)

    fp = sub.add_parser("fingerprint", help="print size/mtime/sha256 for files")
    fp.add_argument("paths", nargs="+")
    fp.add_argument("--sha", action="store_true", help="also compute sha256 (reads the file)")

    get = sub.add_parser("get", help="read a non-expired cache entry")
    get.add_argument("--cache-dir", required=True)
    get.add_argument("--key", required=True)

    put = sub.add_parser("put", help="write a JSON payload under a key")
    put.add_argument("--cache-dir", required=True)
    put.add_argument("--key", required=True)
    put.add_argument("--payload-file", help="JSON file; omit to read stdin")
    put.add_argument("--ttl", type=float, default=1800.0)

    run = sub.add_parser("run", help="cache a successful command's stdout/stderr")
    run.add_argument("--cache-dir", required=True)
    run.add_argument("--key", required=True)
    run.add_argument("--ttl", type=float, default=1800.0)
    run.add_argument("command", nargs=argparse.REMAINDER)

    prune = sub.add_parser("prune", help="remove expired or old cache files")
    prune.add_argument("--cache-dir", required=True)
    prune.add_argument("--older-than-days", type=float, default=14.0)
    prune.add_argument("--expired-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args()
    if args.action == "fingerprint":
        result = _fingerprint(args.paths, with_sha=args.sha)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result["errors"] else 1
    if args.action == "get":
        return _get(args)
    if args.action == "put":
        return _put(args)
    if args.action == "run":
        return _run(args)
    if args.action == "prune":
        return _prune(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
