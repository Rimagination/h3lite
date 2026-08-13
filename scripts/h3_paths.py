"""Small Windows path helpers shared by the H3 Lite command-line tools."""

from __future__ import annotations

import re
from pathlib import Path


_GIT_BASH_DRIVE = re.compile(r"^/(?P<drive>[a-zA-Z])(?:/(?P<rest>.*))?$")


def normalize_windows_path(value: str | Path) -> Path:
    """Normalize Git Bash ``/f/...`` input before pathlib sees it on Windows."""
    text = str(value).strip()
    match = _GIT_BASH_DRIVE.match(text)
    if match:
        rest = match.group("rest") or ""
        text = f"{match.group('drive').upper()}:/{rest}"
    return Path(text).expanduser()
