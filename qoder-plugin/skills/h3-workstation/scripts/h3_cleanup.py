#!/usr/bin/env python3
"""Safely preview or remove old H3 Lite timestamped run snapshots."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


RUN_ID = re.compile(r"^\d{8}T\d{6}Z_[0-9A-Za-z-]+$")


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def cleanup_plan(
    run_root: str | Path,
    *,
    older_than_days: int = 30,
    keep_last: int = 20,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(run_root).expanduser().resolve()
    if older_than_days < 0:
        raise ValueError("older_than_days must be non-negative")
    if keep_last < 0:
        raise ValueError("keep_last must be non-negative")
    if not root.is_dir():
        raise FileNotFoundError(f"run root does not exist: {root}")

    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=older_than_days)
    candidates: list[tuple[datetime, Path]] = []
    ignored: list[str] = []
    for child in root.iterdir():
        if not child.is_dir() or not RUN_ID.fullmatch(child.name):
            ignored.append(child.name)
            continue
        stamp = datetime.strptime(child.name[:16], "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
        candidates.append((stamp, child))

    candidates.sort(key=lambda item: item[0], reverse=True)
    protected = {path for _, path in candidates[:keep_last]}
    selected = [
        {"path": str(path), "timestamp": stamp.isoformat(), "bytes": directory_size(path)}
        for stamp, path in candidates
        if path not in protected and stamp < cutoff
    ]
    return {
        "run_root": str(root),
        "dry_run": True,
        "older_than_days": older_than_days,
        "keep_last": keep_last,
        "eligible": selected,
        "eligible_bytes": sum(item["bytes"] for item in selected),
        "protected_recent": [str(path) for _, path in candidates[:keep_last]],
        "ignored": sorted(ignored),
    }


def apply_cleanup(plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(plan["run_root"]).resolve()
    removed: list[str] = []
    for item in plan["eligible"]:
        target = Path(item["path"]).resolve()
        if target.parent != root or not RUN_ID.fullmatch(target.name):
            raise ValueError(f"refusing unsafe cleanup target: {target}")
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(str(target))
    result = dict(plan)
    result["dry_run"] = False
    result["removed"] = removed
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, help="Path to ComfyUI/user/h3lite_runs")
    parser.add_argument("--older-than-days", type=int, default=30)
    parser.add_argument("--keep-last", type=int, default=20)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete eligible snapshots; omission is always a dry run",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        plan = cleanup_plan(
            args.run_root,
            older_than_days=args.older_than_days,
            keep_last=args.keep_last,
        )
        result = apply_cleanup(plan) if args.apply else plan
    except (OSError, ValueError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}")
        return 2

    result["ok"] = True
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        action = "removed" if args.apply else "would remove"
        print(f"{action} {len(result['eligible'])} run(s), {result['eligible_bytes']} bytes")
        for item in result["eligible"]:
            print(item["path"])
        if not args.apply:
            print("dry run only; pass --apply to delete these snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
