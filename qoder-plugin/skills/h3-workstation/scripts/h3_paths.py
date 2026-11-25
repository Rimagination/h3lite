"""Small Windows path helpers shared by the H3 Lite command-line tools."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


_GIT_BASH_DRIVE = re.compile(r"^/(?P<drive>[a-zA-Z])(?:/(?P<rest>.*))?$")

COMFYUI_ENV = "H3LITE_COMFYUI"
CONFIG_ENV = "H3LITE_CONFIG"


def normalize_windows_path(value: str | Path) -> Path:
    """Normalize Git Bash ``/f/...`` input before pathlib sees it on Windows."""
    text = str(value).strip()
    match = _GIT_BASH_DRIVE.match(text)
    if match:
        rest = match.group("rest") or ""
        text = f"{match.group('drive').upper()}:/{rest}"
    return Path(text).expanduser()


def default_config_path() -> Path:
    """Machine-level config, deliberately outside any agent task workspace.

    Qoder, WorkBuddy and DeepSeek Harness may open a new task with a different working directory
    and no memory of the previous one; ``~/.h3lite/config.json`` survives that.
    """
    override = os.environ.get(CONFIG_ENV)
    if override:
        return normalize_windows_path(override)
    return Path.home() / ".h3lite" / "config.json"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    target = normalize_windows_path(path) if path else default_config_path()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def save_config(updates: dict[str, Any], path: str | Path | None = None) -> Path:
    """Merge and atomically write config updates; returns the config path."""
    target = normalize_windows_path(path) if path else default_config_path()
    current = load_config(target)
    current.update(updates)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def is_comfyui_root(path: Path | None) -> bool:
    return bool(path and path.is_dir() and (path / "main.py").is_file() and (path / "models").is_dir())


def _resolve_from_config(value: Any, config_file: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = normalize_windows_path(value)
    if not candidate.is_absolute():
        candidate = config_file.parent / candidate
    return candidate


def find_comfyui(
    explicit: str | Path | None = None,
    root: str | Path | None = None,
    *,
    search_roots: bool = True,
) -> tuple[Path | None, str]:
    """Resolve ComfyUI in a stable order, independent of the current task folder.

    Order: ``--comfyui`` -> ``H3LITE_COMFYUI`` -> ``~/.h3lite/config.json`` ->
    ``<root>/ComfyUI`` -> ``<root>/comfyui`` -> ``<root>`` -> ``~/ComfyUI``.

    The returned source label is reported by ``h3_doctor.py`` so a new agent
    task can tell the user why a path was chosen instead of offering to
    download another 11-15 GB ComfyUI bundle.
    """
    if explicit:
        return normalize_windows_path(explicit), "explicit"

    env_value = os.environ.get(COMFYUI_ENV)
    if env_value:
        candidate = normalize_windows_path(env_value)
        if is_comfyui_root(candidate):
            return candidate, f"env:{COMFYUI_ENV}"

    config_file = default_config_path()
    configured = _resolve_from_config(load_config(config_file).get("comfyui"), config_file)
    if configured is not None and is_comfyui_root(configured):
        return configured, f"config:{config_file}"

    if search_roots:
        search_root = normalize_windows_path(root) if root else Path.cwd()
        for candidate in (search_root / "ComfyUI", search_root / "comfyui", search_root):
            if is_comfyui_root(candidate):
                return candidate, f"root:{search_root}"

        home_candidate = Path.home() / "ComfyUI"
        if is_comfyui_root(home_candidate):
            return home_candidate, "home"

    return None, "not-found"
