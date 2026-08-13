#!/usr/bin/env python3
"""Submit and monitor an API-format workflow through a local ComfyUI server.

The fast path uses the bundled, validated low-VRAM H3 workflow when no workflow
is supplied. It changes only explicit prompt/settings overrides in memory; it
never edits the workflow asset on disk.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from h3_plan import parse_resolution
from h3_paths import normalize_windows_path


COMPONENT_SETS = {
    "validated-low-vram-a": {
        "unet_name": "minimax_h3_fl2va_pruned_w4a8_mixed_ax1y2jp.safetensors",
        "clip_name": "qwen3vl_4b_int4_convrot.safetensors",
        "lora_name": "minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors",
    },
    "portable-16gb-b": {
        "unet_name": "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
        "clip_name": "qwen3vl_4b_fp8_scaled.safetensors",
        "lora_name": "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_resized_avg_rank_21_bf16.safetensors",
    },
}

COMPONENT_INTEGRITY = {
    "portable-16gb-b": {
        "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors": {
            "bytes": 12_540_858_008,
            "sha256": "01aa7b92c007c599890461c325f9b7e3c96fb06c36f242f95b62f7f20e538dec",
        },
        "qwen3vl_4b_fp8_scaled.safetensors": {
            "bytes": 5_242_467_968,
            "sha256": "54bd5144df0bbc25dd6ccadfcb826b521445a1b06ae5a42570bdd2974ca87094",
        },
        "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_resized_avg_rank_21_bf16.safetensors": {
            "bytes": 298_177_224,
            "sha256": "1b85da614014024a0c9507f12558917dcc69b6adb564e716324594f401723115",
        },
    },
}


COMPONENT_SET_ALIASES = {
    "auto": "auto",
    "a": "validated-low-vram-a",
    "set-a": "validated-low-vram-a",
    "validated-low-vram-a": "validated-low-vram-a",
    "b": "portable-16gb-b",
    "set-b": "portable-16gb-b",
    "portable-16gb-b": "portable-16gb-b",
}


def normalize_component_set(value: str | None) -> str:
    """Return a canonical component-set ID while keeping short aliases useful."""
    key = (value or "auto").strip().lower()
    try:
        return COMPONENT_SET_ALIASES[key]
    except KeyError as exc:
        choices = ", ".join(sorted(COMPONENT_SET_ALIASES))
        raise ValueError(f"unknown component set {value!r}; choose one of: {choices}") from exc


def component_set_candidates(available_names: set[str]) -> list[str]:
    """List registered sets whose three atomic model roles are all present."""
    return [
        set_name
        for set_name, component_set in COMPONENT_SETS.items()
        if all(component_set[field] in available_names for field in ("unet_name", "clip_name", "lora_name"))
    ]


def verify_component_integrity(comfyui: Path, component_set: str) -> dict[str, object]:
    """Verify known fragile component files once, then reuse a size/mtime cache."""
    requirements = COMPONENT_INTEGRITY.get(component_set, {})
    if not requirements:
        return {"component_set": component_set, "verified": True, "files": []}
    model_root = comfyui / "models"
    paths = {path.name: path for path in model_root.rglob("*.safetensors")}
    cache_path = comfyui / "user" / "h3lite_runs" / "_environment" / "component_integrity.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache = {"files": {}}
    cached_files = cache.setdefault("files", {})
    results: list[dict[str, object]] = []
    for name, expected in requirements.items():
        path = paths.get(name)
        if path is None:
            raise RuntimeError(f"component integrity check cannot find {name}")
        stat = path.stat()
        if stat.st_size != expected["bytes"]:
            raise RuntimeError(f"component size mismatch for {name}: {stat.st_size} != {expected['bytes']}")
        cached = cached_files.get(str(path.resolve()), {})
        valid_cache = (
            cached.get("bytes") == stat.st_size
            and cached.get("mtime_ns") == stat.st_mtime_ns
            and cached.get("sha256") == expected["sha256"]
        )
        digest = expected["sha256"] if valid_cache else _sha256_file(path)
        if digest != expected["sha256"]:
            raise RuntimeError(
                f"component SHA-256 mismatch for {name}: {digest}; expected {expected['sha256']}"
            )
        cached_files[str(path.resolve())] = {
            "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": digest,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        results.append({"path": str(path), "sha256": digest, "cache_reused": valid_cache})
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"component_set": component_set, "verified": True, "files": results}


def _workflow_model_fields(workflow: dict[str, Any]) -> dict[str, tuple[dict[str, Any], str]]:
    fields: dict[str, tuple[dict[str, Any], str]] = {}
    for node in workflow.values():
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            continue
        for field in ("unet_name", "clip_name", "lora_name"):
            if isinstance(node["inputs"].get(field), str):
                fields[field] = (node, str(node["inputs"][field]))
    return fields


def resolve_model_overrides(
    workflow: dict[str, Any],
    comfyui: Path | None,
    component_set: str = "auto",
) -> dict[str, str]:
    """Switch only to a complete registered component set.

    Independent filename matching can silently combine an incompatible W4A8
    checkpoint, encoder, and Turbo LoRA. Keep those three roles atomic. An
    explicit component set is authoritative; auto mode only substitutes when
    exactly one complete registered set is available.
    """
    requested = normalize_component_set(component_set)
    fields = _workflow_model_fields(workflow)
    if not fields:
        return {"component_set": requested} if requested != "auto" else {}
    if comfyui is None or not comfyui.exists():
        if requested != "auto":
            raise RuntimeError(f"--component-set {requested} requires an existing --comfyui path")
        return {}
    roots = [root for root in (comfyui / "models", comfyui / "custom_nodes") if root.exists()]
    candidates = [path for root in roots for path in root.rglob("*.safetensors")]
    available = {path.name for path in candidates}
    installed_sets = component_set_candidates(available)

    if requested == "auto" and len(installed_sets) > 1:
        raise RuntimeError(
            "multiple registered component sets match: "
            + ", ".join(installed_sets)
            + "; choose --component-set explicitly"
        )

    if requested != "auto":
        selected = COMPONENT_SETS[requested]
        missing = [selected[field] for field in fields if selected[field] not in available]
        if missing:
            raise RuntimeError(
                f"component set {requested} is incomplete; missing: {', '.join(missing)}"
            )
        overrides: dict[str, str] = {"component_set": requested}
        for field, (node, configured) in fields.items():
            replacement = selected[field]
            if configured != replacement:
                node["inputs"][field] = replacement
                overrides[f"{field}:{configured}"] = replacement
        return overrides

    configured = {field: value for field, (_, value) in fields.items()}
    if all(value in available for value in configured.values()):
        configured_matches = [
            set_name
            for set_name, selected in COMPONENT_SETS.items()
            if all(field in selected and selected[field] == configured[field] for field in configured)
        ]
        if configured_matches:
            return {"component_set": configured_matches[0]}
        return {}

    matches = [(set_name, COMPONENT_SETS[set_name]) for set_name in installed_sets]
    if len(matches) != 1:
        missing = [configured for _, configured in fields.values() if configured not in available]
        detail = (
            "no complete registered component set is installed"
            if not matches
            else "multiple registered component sets match"
        )
        raise RuntimeError(
            f"missing configured model files: {', '.join(missing)}; {detail}; "
            "choose --component-set explicitly"
        )

    set_name, selected = matches[0]
    overrides = {"component_set": set_name}
    for field, (node, configured) in fields.items():
        replacement = selected[field]
        if configured != replacement:
            node["inputs"][field] = replacement
            overrides[f"{field}:{configured}"] = replacement
    return overrides


def json_request(base_url: str, path: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
    url = base_url.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI HTTP {exc.code} at {path}: {body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach ComfyUI at {base_url}: {exc.reason}") from exc
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ComfyUI returned non-JSON data at {path}: {raw[:300]!r}") from exc


def load_workflow(path: Path) -> dict[str, Any]:
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Cannot read workflow {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Workflow is not valid JSON: {path}: {exc}") from exc
    if not isinstance(workflow, dict):
        raise RuntimeError("API-format workflow must be a JSON object keyed by node id")
    if "nodes" in workflow and isinstance(workflow["nodes"], list):
        raise RuntimeError("This helper expects ComfyUI API-format JSON, not a UI workflow with a nodes list")
    return workflow


def default_workflow_path(template: str) -> Path:
    skill_root = Path(__file__).resolve().parents[1]
    templates = {
        "h3_w4a8_t2v": skill_root / "assets" / "h3_w4a8_t2v_api.json",
        "h3_w4a8_t2v_compat": skill_root / "assets" / "h3_w4a8_t2v_compat_api.json",
        "h3_w4a8_i2v": skill_root / "assets" / "h3_w4a8_i2v_api.json",
        "h3_w4a8_i2v_compat": skill_root / "assets" / "h3_w4a8_i2v_compat_api.json",
    }
    try:
        path = templates[template]
    except KeyError as exc:
        raise RuntimeError(f"Unknown workflow template: {template}") from exc
    if not path.exists():
        raise RuntimeError(f"Bundled workflow template is missing: {path}")
    return path


def _is_node_reference(value: Any) -> bool:
    return isinstance(value, list) and len(value) >= 2 and value[0] is not None


def reference_mode(workflow: dict[str, Any]) -> str:
    """Infer the H3 reference route from connected first/last frame inputs."""
    has_first = False
    has_last = False
    for node in workflow.values():
        if not isinstance(node, dict) or node.get("class_type") != "MiniMaxH3ImageToVideo":
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        has_first = has_first or _is_node_reference(inputs.get("first_frame"))
        has_last = has_last or _is_node_reference(inputs.get("last_frame"))
    if has_first and has_last:
        return "FL2VA"
    if has_first:
        return "I2VA"
    if has_last:
        return "L2VA"
    return "T2VA"


def _reference_source(value: str | Path, comfyui: Path) -> Path:
    """Resolve either a local path or a filename relative to ComfyUI/input."""
    raw = str(value).strip()
    candidate = normalize_windows_path(raw)
    if candidate.is_file():
        return candidate.resolve()
    input_candidate = (comfyui / "input" / raw.replace("/", "\\")).resolve()
    if input_candidate.is_file():
        return input_candidate
    raise RuntimeError(f"reference image does not exist: {value}")


def _stage_reference_image(value: str | Path, comfyui: Path, *, stage: bool) -> dict[str, Any]:
    """Make a reference image visible to ComfyUI without clobbering user files."""
    source = _reference_source(value, comfyui)
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        raise RuntimeError(f"unsupported reference image format: {source.suffix or source.name}")
    input_dir = (comfyui / "input").resolve()
    try:
        relative = source.relative_to(input_dir)
    except ValueError:
        relative = None
    digest = _sha256_file(source)
    if digest is None:
        raise RuntimeError(f"cannot read reference image: {source}")
    if relative is not None:
        input_name = str(relative).replace("\\", "/")
        staged = False
    else:
        input_name = f"h3lite_{digest[:12]}_{source.name}"
        destination = input_dir / input_name
        staged = True
        if stage:
            input_dir.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if _sha256_file(destination) != digest:
                    raise RuntimeError(f"staged reference already exists with a different hash: {destination}")
            else:
                try:
                    shutil.copy2(source, destination)
                except OSError as exc:
                    raise RuntimeError(f"cannot stage reference image into {input_dir}: {exc}") from exc
    return {
        "source": str(source),
        "input_name": input_name,
        "sha256": digest,
        "staged": staged and stage,
    }


def _new_node_id(workflow: dict[str, Any]) -> str:
    numeric_ids = []
    for node_id in workflow:
        try:
            numeric_ids.append(int(str(node_id)))
        except (TypeError, ValueError):
            continue
    candidate = max(numeric_ids, default=0) + 1
    while str(candidate) in workflow:
        candidate += 1
    return str(candidate)


def _bind_reference_field(
    workflow: dict[str, Any],
    h3_node: dict[str, Any],
    field: str,
    input_name: str,
) -> None:
    inputs = h3_node.setdefault("inputs", {})
    existing = inputs.get(field)
    if _is_node_reference(existing):
        loader = workflow.get(str(existing[0]))
        if isinstance(loader, dict) and loader.get("class_type") == "LoadImage":
            loader_inputs = loader.setdefault("inputs", {})
            loader_inputs["image"] = input_name
            return
    loader_id = _new_node_id(workflow)
    workflow[loader_id] = {"inputs": {"image": input_name}, "class_type": "LoadImage"}
    inputs[field] = [loader_id, 0]


def _remove_placeholder_first_frame(workflow: dict[str, Any]) -> None:
    """Turn the bundled I2V graph into L2VA when only a last frame is given."""
    placeholder_loaders: set[str] = set()
    for node in workflow.values():
        if not isinstance(node, dict) or node.get("class_type") != "MiniMaxH3ImageToVideo":
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or not _is_node_reference(inputs.get("first_frame")):
            continue
        reference = inputs["first_frame"]
        loader = workflow.get(str(reference[0]))
        loader_inputs = loader.get("inputs") if isinstance(loader, dict) else None
        if isinstance(loader, dict) and loader.get("class_type") == "LoadImage" and isinstance(loader_inputs, dict) and loader_inputs.get("image") == "__H3_FIRST_FRAME__":
            inputs.pop("first_frame", None)
            placeholder_loaders.add(str(reference[0]))
    for loader_id in placeholder_loaders:
        still_used = any(
            isinstance(node, dict)
            and isinstance(node.get("inputs"), dict)
            and any(_is_node_reference(value) and str(value[0]) == loader_id for value in node["inputs"].values())
            for node in workflow.values()
        )
        if not still_used:
            workflow.pop(loader_id, None)


def bind_reference_images(
    workflow: dict[str, Any],
    *,
    first_frame: str | Path | None,
    last_frame: str | Path | None,
    comfyui: Path | None,
    stage: bool,
) -> dict[str, Any]:
    """Bind CLI frame paths to native MiniMaxH3ImageToVideo inputs."""
    requested = {"first_frame": first_frame, "last_frame": last_frame}
    if not any(value is not None for value in requested.values()):
        return {"mode": reference_mode(workflow), "inputs": {}}
    if comfyui is None:
        raise RuntimeError("--comfyui is required when --first-frame or --last-frame is used")
    if first_frame is None and last_frame is not None:
        _remove_placeholder_first_frame(workflow)
    h3_nodes = [
        node
        for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type") == "MiniMaxH3ImageToVideo"
    ]
    if not h3_nodes:
        raise RuntimeError("the workflow has no MiniMaxH3ImageToVideo node for reference frames")
    bindings: dict[str, Any] = {}
    for field, value in requested.items():
        if value is None:
            continue
        binding = _stage_reference_image(value, comfyui, stage=stage)
        for node in h3_nodes:
            _bind_reference_field(workflow, node, field, binding["input_name"])
        bindings[field] = binding
    return {"mode": reference_mode(workflow), "inputs": bindings}


def validate_reference_placeholders(workflow: dict[str, Any]) -> None:
    """Fail early when a bundled reference template was used without its frame."""
    placeholders = {
        "__H3_FIRST_FRAME__": "--first-frame",
        "__H3_LAST_FRAME__": "--last-frame",
    }
    for node in workflow.values():
        if not isinstance(node, dict) or node.get("class_type") != "LoadImage":
            continue
        image = node.get("inputs", {}).get("image") if isinstance(node.get("inputs"), dict) else None
        if image in placeholders:
            raise RuntimeError(f"this workflow requires {placeholders[image]} to be supplied")


PROFILE_STEPS = {
    "fast": 4,
    "balanced": 6,
    "quality": 8,
}


COMPLETE_SILENCE_MARKERS = (
    "完全静音",
    "无任何声音",
    "无声音",
    "no audio",
    "complete silence",
    "totally silent",
)


def has_native_audio_path(workflow: dict[str, Any]) -> bool:
    """Return whether the graph keeps H3's audio VAE connected to CreateVideo."""
    has_audio_decode = any(
        isinstance(node, dict) and "vaedecodeaudio" in str(node.get("class_type", "")).lower()
        for node in workflow.values()
    )
    has_audio_mux = any(
        isinstance(node, dict)
        and str(node.get("class_type", "")).lower() == "createvideo"
        and isinstance(node.get("inputs"), dict)
        and "audio" in node["inputs"]
        for node in workflow.values()
    )
    return has_audio_decode and has_audio_mux


def infer_audio_policy(prompt: str) -> str:
    lowered = (prompt or "").lower()
    if any(marker.lower() in lowered for marker in COMPLETE_SILENCE_MARKERS):
        return "disable"
    return "require"


def apply_audio_policy(workflow: dict[str, Any], prompt: str, policy: str = "auto") -> str:
    """Keep native audio by default; remove only for an explicit silence request."""
    resolved = infer_audio_policy(prompt) if policy == "auto" else policy
    if resolved not in {"require", "allow", "disable"}:
        raise RuntimeError(f"Unknown audio policy: {policy}")
    if resolved == "require" and not has_native_audio_path(workflow):
        raise RuntimeError("audio is required by the prompt, but the workflow has no native H3 audio path")
    if resolved == "disable":
        for node in workflow.values():
            if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
                continue
            if str(node.get("class_type", "")).lower() == "createvideo":
                node["inputs"].pop("audio", None)
    return resolved


def config_fingerprint(workflow: dict[str, Any], prompt: str) -> str:
    """Hash the effective graph and prompt so duplicate queued runs are detectable."""
    payload = {"workflow": workflow, "prompt": prompt}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def effective_workflow_settings(workflow: dict[str, Any]) -> dict[str, Any]:
    """Extract the settings that matter for later media verification."""
    settings: dict[str, Any] = {"reference_mode": reference_mode(workflow)}
    cache_ids = {
        str(node_id)
        for node_id, node in workflow.items()
        if isinstance(node, dict) and "blockcache" in str(node.get("class_type", "")).lower()
    }
    settings["block_cache"] = any(
        isinstance(node, dict)
        and isinstance(node.get("inputs"), dict)
        and any(isinstance(value, list) and value and str(value[0]) in cache_ids for value in node["inputs"].values())
        for node_id, node in workflow.items()
        if str(node_id) not in cache_ids
    )
    for node in workflow.values():
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            continue
        class_type = str(node.get("class_type", ""))
        inputs = node["inputs"]
        if class_type == "MiniMaxH3ImageToVideo":
            for key in ("width", "height", "length"):
                if key in inputs:
                    settings[key] = inputs[key]
        elif class_type == "BasicScheduler" and "steps" in inputs:
            settings["steps"] = inputs["steps"]
        elif class_type == "CreateVideo" and "fps" in inputs:
            settings["fps"] = inputs["fps"]
        elif class_type == "RandomNoise" and "noise_seed" in inputs:
            settings["seed"] = inputs["noise_seed"]
        elif class_type == "LoraLoaderModelOnly":
            if "lora_name" in inputs:
                settings["lora_name"] = inputs["lora_name"]
            if "strength_model" in inputs:
                settings["lora_strength"] = inputs["strength_model"]
        elif class_type == "MiniMaxH3SigmaShift":
            settings["shift_video"] = inputs.get("shift_video")
            settings["shift_audio"] = inputs.get("shift_audio")
    if settings.get("length") is not None and settings.get("fps"):
        settings["expected_duration_seconds"] = round(float(settings["length"]) / float(settings["fps"]), 4)
    return settings


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def default_run_root(output_dir: Path | None) -> Path | None:
    if output_dir is None:
        return None
    if output_dir.name.lower() == "output":
        return output_dir.parent / "user" / "h3lite_runs"
    return output_dir / ".h3lite_runs"


def active_manifest(run_root: Path | None, fingerprint: str) -> dict[str, Any] | None:
    if run_root is None or not run_root.exists():
        return None
    try:
        candidates = run_root.rglob("manifest.json")
    except OSError:
        return None
    for manifest_path in candidates:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("config_fingerprint") != fingerprint:
            continue
        # The atomic claim protects the short submitting window. Treat a
        # leftover `submitting` manifest as retryable after a crashed process.
        if manifest.get("state") in {"queued", "running"}:
            manifest["manifest_path"] = str(manifest_path)
            return manifest
    return None


def acquire_submission_claim(run_root: Path | None, fingerprint: str) -> Path | None:
    """Atomically reserve a fingerprint while a process is submitting it."""
    if run_root is None:
        return None
    run_root.mkdir(parents=True, exist_ok=True)
    claim = run_root / f".{fingerprint}.submit.claim"
    try:
        with claim.open("x", encoding="utf-8") as handle:
            handle.write(datetime.now(timezone.utc).isoformat())
    except FileExistsError as exc:
        try:
            stale = time.time() - claim.stat().st_mtime > 2 * 60 * 60
        except OSError:
            stale = False
        if stale:
            try:
                claim.unlink()
                return acquire_submission_claim(run_root, fingerprint)
            except OSError:
                pass
        raise RuntimeError("submission claim already exists for this H3 configuration") from exc
    return claim


def release_submission_claim(claim: Path | None) -> None:
    if claim is None:
        return
    try:
        claim.unlink(missing_ok=True)
    except OSError:
        return


def create_run_manifest(
    run_root: Path | None,
    *,
    workflow: dict[str, Any],
    prompt: str,
    workflow_path: Path,
    target: dict[str, Any],
    args: argparse.Namespace,
    audio_policy: str,
    fingerprint: str,
    model_overrides: dict[str, str] | None = None,
    reference_inputs: dict[str, Any] | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    if run_root is None:
        return None, {}
    run_root.mkdir(parents=True, exist_ok=True)
    run_dir = run_root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    run_dir.mkdir(parents=True, exist_ok=False)
    prompt_path = run_dir / "prompt.txt"
    workflow_snapshot = run_dir / "workflow.api.json"
    manifest_path = run_dir / "manifest.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    workflow_snapshot.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    record = {
        "schema_version": 1,
        "state": "submitting",
        "config_fingerprint": fingerprint,
        "workflow_sha256": _sha256_file(workflow_snapshot),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "workflow_path": str(workflow_path),
        "workflow_snapshot": str(workflow_snapshot),
        "prompt_path": str(prompt_path),
        "target": target,
        "reference_mode": effective_workflow_settings(workflow).get("reference_mode"),
        "first_frame": getattr(args, "first_frame", None),
        "last_frame": getattr(args, "last_frame", None),
        "reference_inputs": reference_inputs or {},
        "profile": args.profile,
        "audio_policy": audio_policy,
        "seed": args.seed,
        "width": args.width,
        "height": args.height,
        "length": args.length,
        "steps": args.steps,
        "fps": args.fps,
        "filename_prefix": args.filename_prefix,
        "output_dir": str(Path(args.output_dir).expanduser().resolve()) if args.output_dir else None,
        "effective_settings": effective_workflow_settings(workflow),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_overrides": model_overrides or {},
    }
    record["run_dir"] = str(run_dir)
    record["manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path, record


def update_manifest(manifest_path: Path | None, updates: dict[str, Any]) -> None:
    if manifest_path is None or not manifest_path.exists():
        return
    try:
        current = json.loads(manifest_path.read_text(encoding="utf-8"))
        current.update(updates)
        manifest_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        return


def find_manifest(run_root: Path | None, prompt_id: str) -> Path | None:
    if run_root is None or not run_root.exists():
        return None
    try:
        for candidate in run_root.rglob("manifest.json"):
            try:
                value = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(value.get("prompt_id", "")) == prompt_id:
                return candidate
    except OSError:
        return None
    return None


def bypass_block_cache(workflow: dict[str, Any]) -> int:
    """Reconnect downstream model consumers to the cache node's input model."""
    cache_ids = {
        str(node_id)
        for node_id, node in workflow.items()
        if isinstance(node, dict) and "blockcache" in str(node.get("class_type", "")).lower()
    }
    replacements: dict[str, list[Any]] = {}
    for node_id in cache_ids:
        inputs = workflow[node_id].get("inputs", {})
        model_ref = inputs.get("model") if isinstance(inputs, dict) else None
        if isinstance(model_ref, list) and len(model_ref) >= 2:
            replacements[node_id] = model_ref
    changed = 0
    if not replacements:
        return changed
    for node in workflow.values():
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            continue
        for field, value in list(node["inputs"].items()):
            if isinstance(value, list) and len(value) >= 2 and str(value[0]) in replacements:
                node["inputs"][field] = list(replacements[str(value[0])])
                changed += 1
    return changed


def apply_profile(workflow: dict[str, Any], profile: str) -> None:
    """Apply conservative generation defaults; explicit CLI overrides win later."""
    if profile not in PROFILE_STEPS:
        raise RuntimeError(f"Unknown generation profile: {profile}")
    steps = PROFILE_STEPS[profile]
    for node in workflow.values():
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            continue
        if node.get("class_type") == "BasicScheduler" and "steps" in node["inputs"]:
            node["inputs"]["steps"] = steps
    if profile != "fast":
        bypass_block_cache(workflow)


def apply_overrides(workflow: dict[str, Any], args: argparse.Namespace) -> None:
    """Apply safe, class-type-based overrides without hardcoding node ids."""
    for node in workflow.values():
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            continue
        class_type = str(node.get("class_type", ""))
        inputs = node["inputs"]
        if args.seed is not None and class_type == "RandomNoise" and "noise_seed" in inputs:
            inputs["noise_seed"] = args.seed
        if class_type == "MiniMaxH3ImageToVideo":
            if args.width is not None and "width" in inputs:
                inputs["width"] = args.width
            if args.height is not None and "height" in inputs:
                inputs["height"] = args.height
            if args.length is not None and "length" in inputs:
                inputs["length"] = args.length
        if args.steps is not None and class_type == "BasicScheduler" and "steps" in inputs:
            inputs["steps"] = args.steps
        if args.fps is not None and class_type == "CreateVideo" and "fps" in inputs:
            inputs["fps"] = args.fps
        if class_type == "LoraLoaderModelOnly":
            if args.lora_name is not None and "lora_name" in inputs:
                inputs["lora_name"] = args.lora_name
            if args.lora_strength is not None and "strength_model" in inputs:
                inputs["strength_model"] = args.lora_strength
        if class_type == "MiniMaxH3SigmaShift":
            if args.shift_video is not None and "shift_video" in inputs:
                inputs["shift_video"] = args.shift_video
            if args.shift_audio is not None and "shift_audio" in inputs:
                inputs["shift_audio"] = args.shift_audio
        if args.filename_prefix and class_type == "SaveVideo" and "filename_prefix" in inputs:
            inputs["filename_prefix"] = args.filename_prefix


def prompt_candidates(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    field_words = {"prompt", "text", "positive", "description", "input_text", "text_positive", "caption"}
    for node_id, node in workflow.items():
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            continue
        class_type = str(node.get("class_type", ""))
        class_lower = class_type.lower()
        for field, value in node["inputs"].items():
            if not isinstance(value, str):
                continue
            field_lower = str(field).lower()
            score = 0
            if field_lower == "prompt":
                score += 100
            elif field_lower in field_words:
                score += 60
            elif any(word in field_lower for word in ("prompt", "text", "caption", "description")):
                score += 30
            if "cliptextencode" in class_lower:
                score += 25
            if "prompt" in class_lower or "text" in class_lower:
                score += 10
            if score:
                candidates.append({"node": str(node_id), "field": str(field), "score": score, "class_type": class_type, "current_length": len(value)})
    return sorted(candidates, key=lambda item: (-item["score"], item["node"], item["field"]))


def choose_prompt_target(workflow: dict[str, Any], node_id: str | None, field: str | None) -> dict[str, Any]:
    if node_id is not None:
        node_key = str(node_id)
        if node_key not in workflow or not isinstance(workflow[node_key], dict):
            raise RuntimeError(f"Prompt node {node_key!r} is not present in the workflow")
        inputs = workflow[node_key].get("inputs")
        if not isinstance(inputs, dict):
            raise RuntimeError(f"Prompt node {node_key!r} has no inputs object")
        if field:
            if field not in inputs:
                raise RuntimeError(f"Prompt field {field!r} is not present on node {node_key!r}")
            if not isinstance(inputs[field], str):
                raise RuntimeError(f"Prompt field {field!r} on node {node_key!r} is not a string input")
            return {"node": node_key, "field": field, "class_type": workflow[node_key].get("class_type", "")}
        preferred = [name for name in ("prompt", "text", "positive", "description") if isinstance(inputs.get(name), str)]
        if len(preferred) == 1:
            return {"node": node_key, "field": preferred[0], "class_type": workflow[node_key].get("class_type", "")}
        if len(preferred) > 1:
            raise RuntimeError(f"Node {node_key!r} has multiple string prompt-like inputs; pass --prompt-field")
        raise RuntimeError(f"No prompt-like string input found on node {node_key!r}; pass --prompt-field")

    candidates = prompt_candidates(workflow)
    if field:
        candidates = [candidate for candidate in candidates if candidate["field"] == field]
    if not candidates:
        raise RuntimeError("No prompt-like string input found; pass --prompt-node and --prompt-field")
    best_score = candidates[0]["score"]
    best = [candidate for candidate in candidates if candidate["score"] == best_score]
    if len(best) != 1:
        choices = ", ".join(f"{item['node']}.{item['field']} ({item['class_type']})" for item in candidates[:12])
        raise RuntimeError(f"Prompt target is ambiguous. Pass --prompt-node/--prompt-field. Candidates: {choices}")
    return best[0]


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        try:
            return normalize_windows_path(args.prompt_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Cannot read prompt file {args.prompt_file}: {exc}") from exc
    if args.prompt_text is not None:
        return args.prompt_text
    raise RuntimeError("Provide --prompt-file or --prompt-text")


def history_record(history: Any, prompt_id: str) -> dict[str, Any] | None:
    if not isinstance(history, dict):
        return None
    record = history.get(prompt_id)
    return record if isinstance(record, dict) else None


def execution_error(record: dict[str, Any]) -> str | None:
    status = record.get("status")
    if isinstance(status, dict):
        messages = status.get("messages", [])
        if isinstance(messages, list):
            for message in messages:
                if isinstance(message, list) and message:
                    event = str(message[0]).lower()
                    if "error" in event or "failed" in event:
                        return json.dumps(message[1] if len(message) > 1 else message, ensure_ascii=False)
                elif isinstance(message, dict) and any("error" in str(key).lower() for key in message):
                    return json.dumps(message, ensure_ascii=False)
        for key in ("error", "exception_message", "status_str"):
            value = status.get(key)
            if value and str(value).lower() in {"error", "failed"}:
                return str(value)
    for key in ("error", "exception_message"):
        if record.get(key):
            return str(record[key])
    return None


def execution_elapsed_seconds(record: dict[str, Any]) -> float | None:
    """Read ComfyUI execution timestamps when the server exposes them."""
    status = record.get("status") if isinstance(record, dict) else None
    messages = status.get("messages", []) if isinstance(status, dict) else []
    timestamps: dict[str, int] = {}
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, list) or len(message) < 2 or not isinstance(message[1], dict):
                continue
            event = str(message[0])
            timestamp = message[1].get("timestamp")
            if isinstance(timestamp, (int, float)):
                timestamps[event] = int(timestamp)
    start = timestamps.get("execution_start")
    end = timestamps.get("execution_success") or timestamps.get("execution_error")
    if start is None or end is None or end < start:
        return None
    return round((end - start) / 1000.0, 2)


def wait_for_completion(base_url: str, prompt_id: str, timeout: float, interval: float) -> dict[str, Any]:
    started = time.monotonic()
    last_status = "queued"
    while time.monotonic() - started < timeout:
        history = json_request(base_url, f"/history/{prompt_id}")
        record = history_record(history, prompt_id)
        if record:
            status = record.get("status")
            if isinstance(status, dict):
                last_status = str(status.get("status_str", last_status))
                error = execution_error(record)
                if error:
                    raise RuntimeError(f"ComfyUI execution failed: {error}")
                if status.get("completed") is True:
                    return record
            if "outputs" in record and isinstance(record["outputs"], dict):
                return record
        time.sleep(max(0.25, interval))
    raise TimeoutError(f"Timed out after {timeout:.0f}s waiting for {prompt_id}; last status: {last_status}")


def output_entries(value: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if isinstance(value.get("filename"), str):
            entries.append(value)
        for child in value.values():
            entries.extend(output_entries(child))
    elif isinstance(value, list):
        for child in value:
            entries.extend(output_entries(child))
    return entries


def resolve_output_paths(record: dict[str, Any], output_dir: Path | None) -> list[Path]:
    if not output_dir or not isinstance(record.get("outputs"), dict):
        return []
    paths: list[Path] = []
    seen: set[str] = set()
    for entry in output_entries(record["outputs"]):
        filename = entry["filename"]
        subfolder = str(entry.get("subfolder", ""))
        candidate = output_dir / subfolder / filename
        key = str(candidate.resolve())
        if key not in seen:
            seen.add(key)
            paths.append(candidate)
    return paths


def ffprobe(path: Path) -> dict[str, Any] | None:
    executable = shutil.which("ffprobe")
    if not executable or not path.exists():
        return None
    command = [
        executable,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,nb_frames,r_frame_rate,avg_frame_rate,channels,sample_rate",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, check=False)
        if completed.returncode != 0:
            return {"error": completed.stderr.strip()[-1000:]}
        return json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return {"error": str(exc)}


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _frame_rate(stream: dict[str, Any]) -> float | None:
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = str(stream.get(key, ""))
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            try:
                if float(denominator):
                    return float(numerator) / float(denominator)
            except ValueError:
                continue
        result = _numeric(value)
        if result is not None:
            return result
    return None


def verify_outputs(
    paths: list[Path],
    *,
    expected_duration: float | None = None,
    expected_frames: int | None = None,
    expected_fps: float | None = None,
    require_audio: bool = False,
) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for path in paths:
        item: dict[str, Any] = {
            "path": str(path),
            "exists": path.exists(),
            "expected_duration_seconds": expected_duration,
            "expected_frames": expected_frames,
            "expected_fps": expected_fps,
            "audio_required": require_audio,
        }
        if path.exists():
            try:
                item["size_bytes"] = path.stat().st_size
            except OSError:
                item["size_bytes"] = None
            item["ffprobe"] = ffprobe(path)
            probe = item.get("ffprobe")
            if isinstance(probe, dict):
                streams = probe.get("streams", [])
                if isinstance(streams, list):
                    video_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"]
                    audio_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"]
                    item["has_video"] = bool(video_streams)
                    item["has_audio"] = bool(audio_streams)
                    if video_streams:
                        video = video_streams[0]
                        item["video_width"] = video.get("width")
                        item["video_height"] = video.get("height")
                        item["frame_count"] = _numeric(video.get("nb_frames"))
                        item["fps"] = _frame_rate(video)
                    duration = _numeric(probe.get("format", {}).get("duration")) if isinstance(probe.get("format"), dict) else None
                    item["duration_seconds"] = duration
                    if expected_duration is not None and duration is not None:
                        item["duration_delta_seconds"] = round(abs(duration - expected_duration), 4)
                    if expected_fps is not None and item.get("fps") is not None:
                        item["fps_delta"] = round(abs(float(item["fps"]) - expected_fps), 4)
                    if expected_frames is not None and item.get("frame_count") is not None:
                        item["frame_delta"] = int(item["frame_count"]) - int(expected_frames)
        duration_ok = True
        frames_ok = True
        fps_ok = True
        if expected_duration is not None and item.get("duration_seconds") is not None:
            duration_ok = float(item["duration_delta_seconds"]) <= max(0.25, expected_duration * 0.08)
        if expected_frames is not None and item.get("frame_count") is not None:
            frames_ok = abs(int(item["frame_delta"])) <= 2
        if expected_fps is not None and item.get("fps") is not None:
            fps_ok = float(item["fps_delta"]) <= 0.25
        item["duration_ok"] = duration_ok
        item["frames_ok"] = frames_ok
        item["fps_ok"] = fps_ok
        item["audio_ok"] = bool(item.get("has_audio")) if require_audio else True
        item["verified"] = bool(item.get("exists") and item.get("has_video") and duration_ok and frames_ok and fps_ok and item["audio_ok"])
        verified.append(item)
    return verified


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8188", help="ComfyUI server URL")
    parser.add_argument("--workflow", help="ComfyUI API-format workflow JSON")
    parser.add_argument(
        "--workflow-template",
        default="h3_w4a8_t2v",
        choices=["h3_w4a8_t2v", "h3_w4a8_t2v_compat", "h3_w4a8_i2v", "h3_w4a8_i2v_compat"],
        help="bundled workflow used when --workflow is omitted",
    )
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt-file", help="UTF-8 text file containing the H3 prompt")
    prompt_group.add_argument("--prompt-text", help="prompt text supplied directly on the command line")
    parser.add_argument("--prompt-node", help="node id whose prompt input should be replaced")
    parser.add_argument("--prompt-field", help="input field on the prompt node, such as prompt or text")
    parser.add_argument("--first-frame", help="local first-frame image; binds MiniMaxH3ImageToVideo.first_frame")
    parser.add_argument("--last-frame", help="local last-frame image; binds MiniMaxH3ImageToVideo.last_frame")
    parser.add_argument("--output-dir", help="local ComfyUI output directory used for verification")
    parser.add_argument("--comfyui", help="ComfyUI root used by --resolve-models")
    parser.add_argument(
        "--component-set",
        default="auto",
        help="registered model set: auto, A/validated-low-vram-a, or B/portable-16gb-b",
    )
    parser.add_argument("--filename-prefix", help="override SaveVideo filename_prefix")
    parser.add_argument("--profile", choices=["fast", "balanced", "quality"], default="fast", help="generation intent; fast is the validated default")
    parser.add_argument("--seed", type=int, help="override RandomNoise noise_seed")
    parser.add_argument("--resolution", help="override H3 canvas as WIDTHxHEIGHT; dimensions are aligned to 32")
    parser.add_argument("--width", type=int, help="override H3 video width")
    parser.add_argument("--height", type=int, help="override H3 video height")
    parser.add_argument("--length", type=int, help="override H3 frame count")
    parser.add_argument("--steps", type=int, help="override BasicScheduler steps")
    parser.add_argument("--fps", type=float, help="override CreateVideo fps")
    parser.add_argument("--lora-name", help="experimental LoRA filename override; default template remains unchanged")
    parser.add_argument("--lora-strength", type=float, help="experimental model-only LoRA strength override")
    parser.add_argument("--shift-video", type=float, help="experimental MiniMax H3 video shift override")
    parser.add_argument("--shift-audio", type=float, help="experimental MiniMax H3 audio shift override")
    parser.add_argument("--disable-block-cache", action="store_true", help="bypass optional H3 block-cache acceleration")
    parser.add_argument("--audio-policy", choices=["auto", "require", "allow", "disable"], default="auto", help="auto keeps native audio unless complete silence is explicit")
    parser.add_argument("--run-root", help="directory for prompt/workflow/config manifests; defaults beside ComfyUI output")
    parser.add_argument("--allow-duplicate", action="store_true", help="allow an identical queued/running configuration to be submitted again")
    parser.add_argument("--timeout", type=float, default=3600.0, help="maximum wait time in seconds")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="history polling interval in seconds")
    parser.add_argument("--dry-run", action="store_true", help="print the mutated workflow without submitting it")
    parser.add_argument("--queue-only", action="store_true", help="submit and return prompt_id immediately without waiting")
    parser.add_argument("--watch", action="store_true", help="submit, then monitor and verify in this same command")
    parser.add_argument("--resolve-models", action="store_true", help="resolve missing template filenames from unique local role matches")
    parser.add_argument("--watch-interval", type=float, default=20.0, help="seconds between --watch polls")
    parser.add_argument("--watch-timeout", type=float, default=3600.0, help="maximum seconds for --watch")
    parser.add_argument("--dynamic-check", dest="dynamic_check", action="store_true", default=True)
    parser.add_argument("--skip-dynamic-check", dest="dynamic_check", action="store_false")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result")
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args()
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    manifest_path: Path | None = None
    claim_path: Path | None = None
    try:
        workflow_path = normalize_windows_path(args.workflow).resolve() if args.workflow else default_workflow_path(args.workflow_template)
        workflow = load_workflow(workflow_path)
        comfyui_path = normalize_windows_path(args.comfyui).resolve() if args.comfyui else None
        output_dir = normalize_windows_path(args.output_dir).resolve() if args.output_dir else None
        if comfyui_path is None and output_dir is not None and output_dir.name.lower() == "output":
            comfyui_path = output_dir.parent
        requested_component_set = normalize_component_set(getattr(args, "component_set", "auto"))
        model_overrides = (
            resolve_model_overrides(workflow, comfyui_path, requested_component_set)
            if args.resolve_models or requested_component_set != "auto"
            else {}
        )
        selected_component_set = model_overrides.get("component_set")
        component_integrity = None
        if selected_component_set and comfyui_path is not None:
            component_integrity = verify_component_integrity(comfyui_path, selected_component_set)
        apply_profile(workflow, args.profile)
        if args.resolution:
            width, height = parse_resolution(args.resolution)
            if args.width is None:
                args.width = width
            if args.height is None:
                args.height = height
        if args.disable_block_cache:
            bypass_block_cache(workflow)
        prompt = read_prompt(args)
        target = choose_prompt_target(workflow, args.prompt_node, args.prompt_field)
        workflow[str(target["node"])]["inputs"][str(target["field"])] = prompt
        apply_overrides(workflow, args)
        reference_inputs = bind_reference_images(
            workflow,
            first_frame=args.first_frame,
            last_frame=args.last_frame,
            comfyui=comfyui_path,
            stage=not args.dry_run,
        )
        validate_reference_placeholders(workflow)
        resolved_reference_mode = str(reference_inputs["mode"])
        resolved_audio_policy = apply_audio_policy(workflow, prompt, args.audio_policy)
        if args.dry_run:
            result = {
                "dry_run": True,
                "workflow_path": str(workflow_path),
                "target": target,
                "reference_inputs": reference_inputs,
                "audio_policy": resolved_audio_policy,
                "config_fingerprint": config_fingerprint(workflow, prompt),
                "effective_settings": effective_workflow_settings(workflow),
                "component_set": selected_component_set,
                "model_overrides": model_overrides,
                "workflow": workflow,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        run_root = normalize_windows_path(args.run_root).resolve() if args.run_root else default_run_root(output_dir)
        fingerprint = config_fingerprint(workflow, prompt)
        if not args.allow_duplicate:
            existing = active_manifest(run_root, fingerprint)
            if existing:
                result = {
                    "ok": True,
                    "queued": False,
                    "deduplicated": True,
                    "prompt_id": existing.get("prompt_id"),
                    "run_manifest": existing.get("manifest_path"),
                    "reference_mode": resolved_reference_mode,
                    "config_fingerprint": fingerprint,
                    "message": "an identical configuration is already queued or running; submission skipped",
                }
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(f"Existing active prompt {existing.get('prompt_id')}; duplicate submission skipped")
                return 0
            try:
                claim_path = acquire_submission_claim(run_root, fingerprint)
            except RuntimeError as exc:
                existing = active_manifest(run_root, fingerprint)
                if existing:
                    result = {
                        "ok": True,
                        "queued": False,
                        "deduplicated": True,
                        "prompt_id": existing.get("prompt_id"),
                        "run_manifest": existing.get("manifest_path"),
                        "reference_mode": resolved_reference_mode,
                        "config_fingerprint": fingerprint,
                        "message": "matching task is already queued or running",
                    }
                    if args.json:
                        print(json.dumps(result, ensure_ascii=False, indent=2))
                    else:
                        print(f"Matching task already exists: prompt_id={existing.get('prompt_id')}")
                    return 0
                raise RuntimeError("another submission is preparing this configuration; no prompt_id is available yet") from exc

        manifest_path, _ = create_run_manifest(
            run_root,
            workflow=workflow,
            prompt=prompt,
            workflow_path=workflow_path,
            target=target,
            args=args,
            audio_policy=resolved_audio_policy,
            fingerprint=fingerprint,
            model_overrides=model_overrides,
            reference_inputs=reference_inputs,
        )
        if component_integrity is not None:
            update_manifest(manifest_path, {"component_integrity": component_integrity})
        client_id = str(uuid.uuid4())
        try:
            queued = json_request(args.base_url, "/prompt", method="POST", payload={"prompt": workflow, "client_id": client_id})
        except Exception:
            update_manifest(manifest_path, {"state": "failed", "failed_at_utc": datetime.now(timezone.utc).isoformat()})
            raise
        prompt_id = str(queued.get("prompt_id", "")) if isinstance(queued, dict) else ""
        if not prompt_id:
            update_manifest(manifest_path, {"state": "failed", "error": "ComfyUI did not return prompt_id"})
            raise RuntimeError(f"ComfyUI did not return prompt_id: {json.dumps(queued, ensure_ascii=False)[:1500]}")
        update_manifest(
            manifest_path,
            {
                "state": "queued",
                "prompt_id": prompt_id,
                "client_id": client_id,
                "queued_at_utc": started_at.isoformat(),
            },
        )
        if args.queue_only:
            result = {
                "ok": True,
                "queued": True,
                "prompt_id": prompt_id,
                "client_id": client_id,
                "workflow_path": str(workflow_path),
                "target": target,
                "reference_mode": resolved_reference_mode,
                "audio_policy": resolved_audio_policy,
                "config_fingerprint": fingerprint,
                "component_set": selected_component_set,
                "run_manifest": str(manifest_path) if manifest_path else None,
                "queued_at_utc": started_at.isoformat(),
            }
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Queued prompt {prompt_id}")
            return 0
        if args.watch:
            from h3_status import compact_result, status_once

            status_args = argparse.Namespace(
                prompt_id=prompt_id,
                base_url=args.base_url,
                output_dir=str(output_dir) if output_dir else None,
                run_manifest=str(manifest_path) if manifest_path else None,
                run_root=str(run_root) if run_root else None,
                expected_duration=None,
                expected_frames=None,
                expected_fps=None,
                require_audio=resolved_audio_policy == "require",
                dynamic_check=args.dynamic_check,
                compact=True,
                verbose=False,
                watch=False,
                watch_interval=args.watch_interval,
                watch_timeout=args.watch_timeout,
                json=True,
            )
            watch_started = time.monotonic()
            status_result: dict[str, Any] = {"ok": False, "complete": False, "state": "queued", "prompt_id": prompt_id}
            while time.monotonic() - watch_started < max(1.0, args.watch_timeout):
                status_result = status_once(status_args)
                if status_result.get("complete"):
                    break
                time.sleep(max(1.0, args.watch_interval))
            if not status_result.get("complete"):
                status_result = {
                    "ok": False,
                    "complete": True,
                    "prompt_id": prompt_id,
                    "state": "watch_timeout",
                    "error": f"watch exceeded {args.watch_timeout:.0f} seconds",
                }
            result = {
                "ok": bool(status_result.get("ok")),
                "prompt_id": prompt_id,
                "client_id": client_id,
                "target": target,
                "reference_mode": resolved_reference_mode,
                "audio_policy": resolved_audio_policy,
                "config_fingerprint": fingerprint,
                "run_manifest": str(manifest_path) if manifest_path else None,
                "watch": True,
                "status": compact_result(status_result),
            }
            update_manifest(
                manifest_path,
                {
                    "state": status_result.get("state", "verification_failed"),
                    "elapsed_seconds": status_result.get("elapsed_seconds"),
                    "outputs": status_result.get("outputs", []),
                    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"{result['status'].get('state', 'unknown')}: {prompt_id}")
                for item in result["status"].get("outputs", []):
                    print(f"Output: {item.get('path')} | verified={item.get('verified', 'unknown')}")
            return 0 if result["ok"] else 2
        record = wait_for_completion(args.base_url, prompt_id, args.timeout, args.poll_interval)
        output_paths = resolve_output_paths(record, output_dir)
        settings = effective_workflow_settings(workflow)
        verified = verify_outputs(
            output_paths,
            expected_duration=settings.get("expected_duration_seconds"),
            expected_frames=settings.get("length"),
            expected_fps=settings.get("fps"),
            require_audio=resolved_audio_policy == "require",
        )
        verification_ok = bool(verified) and all(item.get("verified") is True for item in verified)
        result = {
            "ok": verification_ok,
            "prompt_id": prompt_id,
            "client_id": client_id,
            "target": target,
            "reference_mode": resolved_reference_mode,
            "started_at_utc": started_at.isoformat(),
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "comfyui_execution_seconds": execution_elapsed_seconds(record),
            "audio_policy": resolved_audio_policy,
            "config_fingerprint": fingerprint,
            "run_manifest": str(manifest_path) if manifest_path else None,
            "outputs": verified,
            "history": record,
        }
        update_manifest(
            manifest_path,
            {
                "state": "success" if verification_ok else "verification_failed",
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": result["elapsed_seconds"],
                "comfyui_execution_seconds": result["comfyui_execution_seconds"],
                "outputs": verified,
            },
        )
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            report_path = output_dir / f"h3_generation_report_{prompt_id}.json"
            report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result["report_path"] = str(report_path)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Completed prompt {prompt_id} in {result['elapsed_seconds']:.1f}s")
            if target:
                print(f"Prompt input: {target['node']}.{target['field']}")
            if verified:
                for item in verified:
                    print(f"Output: {item['path']} | exists={item['exists']} | video={item.get('has_video', 'unknown')} | audio={item.get('has_audio', 'unknown')}")
            else:
                print("ComfyUI completed, but no local output path was resolved. Check the workflow output directory.")
        return 0 if verification_ok else 2
    except KeyboardInterrupt:
        update_manifest(manifest_path, {"state": "interrupted", "updated_at_utc": datetime.now(timezone.utc).isoformat()})
        print("Interrupted while waiting for ComfyUI", file=sys.stderr)
        return 130
    except Exception as exc:
        update_manifest(manifest_path, {"state": "failed", "error": str(exc), "updated_at_utc": datetime.now(timezone.utc).isoformat()})
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc), "elapsed_seconds": round(time.monotonic() - started, 2)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        release_submission_claim(claim_path)


if __name__ == "__main__":
    raise SystemExit(main())
