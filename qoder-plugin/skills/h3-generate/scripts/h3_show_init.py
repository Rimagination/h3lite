#!/usr/bin/env python3
"""Create a show-contract project skeleton from the bundled examples.

Usage:
  python h3_show_init.py --dir projects/ep04 --project ep04
  python h3_show_init.py --dir projects/ep04 --force

The skeleton is deliberately non-destructive: existing show.json / canon.json
are only overwritten with --force. Prompt, image and audio files are never
created or deleted; the command prints what still has to be authored.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSETS = SKILL_ROOT / "assets"
SHOW_EXAMPLE = ASSETS / "show.example.json"
CANON_EXAMPLE = ASSETS / "canon.example.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an H3 show-contract project skeleton")
    parser.add_argument("--dir", required=True, help="project directory (created if absent)")
    parser.add_argument("--project", help="project name written into show.json; defaults to directory name")
    parser.add_argument("--force", action="store_true", help="overwrite existing show.json / canon.json")
    parser.add_argument("--json", action="store_true", help="machine-readable summary")
    args = parser.parse_args()

    if not SHOW_EXAMPLE.is_file() or not CANON_EXAMPLE.is_file():
        print(f"ERROR missing bundled examples under {ASSETS}", file=sys.stderr)
        return 1

    root = Path(args.dir).expanduser().resolve()
    project = (args.project or root.name).strip()
    if not project:
        print("ERROR --project cannot be empty", file=sys.stderr)
        return 1

    show_path = root / "show.json"
    canon_path = root / "canon.json"
    if root.exists():
        occupancy = [show_path, canon_path]
        occupied = [p for p in occupancy if p.exists()]
        if occupied and not args.force:
            print(
                "ERROR project already has show.json/canon.json; pass --force to overwrite",
                file=sys.stderr,
            )
            for p in occupied:
                print(f"  {p}", file=sys.stderr)
            return 1
        if not root.is_dir():
            print(f"ERROR not a directory: {root}", file=sys.stderr)
            return 1

    root.mkdir(parents=True, exist_ok=True)
    for sub in ("prompts", "refs", "frames", "qa", "subs", "output"):
        (root / sub).mkdir(exist_ok=True)

    show = load_json(SHOW_EXAMPLE)
    canon = load_json(CANON_EXAMPLE)
    show["project"] = project
    if isinstance(show.get("version_lock"), dict) and not show["version_lock"].get("reference_pack_sha256"):
        show["version_lock"]["reference_pack_sha256"] = ""

    write_json(show_path, show)
    write_json(canon_path, canon)

    summary = {
        "ok": True,
        "root": str(root),
        "project": project,
        "created": [str(show_path), str(canon_path)],
        "directories": ["prompts", "refs", "frames", "qa", "subs", "output"],
        "next": [
            "replace placeholder character A in canon.json with the real identity block and VOICE block",
            "write prompts/s01.txt and prompts/s02.txt (or edit show.json to your shot list)",
            "put the referenced images/audio under refs/ and generate refs.sha256",
            "run: python h3_show_validate.py --spec show.json --check-sha --strict",
        ],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Created show contract: {root}")
        print(f"  {show_path}")
        print(f"  {canon_path}")
        print("Next:")
        for item in summary["next"]:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
