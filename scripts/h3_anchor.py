#!/usr/bin/env python3
"""Build small, auditable anchor sheets for H3 Lite image/video runs.

The anchor sheet is deliberately metadata-only.  It does not infer new story
content or rewrite the user's prompt; it records the references, identity
constraints, and multi-shot signals that the runtime can later expose to QA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


MODE_LABELS = {
    "t2v": "T2VA",
    "t2va": "T2VA",
    "i2v": "I2VA",
    "i2va": "I2VA",
    "ref2va": "Ref2VA",
    "ref2v": "Ref2VA",
}

IDENTITY_MARKERS = (
    "face",
    "identity",
    "same person",
    "same character",
    "wardrobe",
    "clothing",
    "hair",
    "保持",
    "保留",
    "一致",
    "锁定",
    "人物",
    "角色",
    "服装",
    "发型",
    "面部",
    "脸",
    "衣服",
    "花纹",
)

MULTI_SHOT_MARKERS = (
    "shot",
    "[shot",
    "cut",
    "camera cuts",
    "镜头",
    "切到",
    "转场",
    "分镜",
    "反打",
    "正反打",
)

RETENTION_MARKERS = (
    "keep",
    "preserve",
    "maintain",
    "same",
    "fully preserved",
    "retain",
    "保持",
    "保留",
    "一致",
    "锁定",
    "不得改变",
    "不要改变",
    "remain",
)

ALLOWED_CHANGE_MARKERS = (
    "allowed",
    "may change",
    "can change",
    "允许",
    "可变",
    "变化",
    "慢慢",
    "逐渐",
)

FORBIDDEN_DRIFT_MARKERS = (
    "forbidden",
    "must not",
    "no drift",
    "不得",
    "不要",
    "禁止",
    "不能出现",
    "不改变",
)


def _route_label(mode: str | None) -> str:
    value = str(mode or "t2v").strip().lower()
    return MODE_LABELS.get(value, value.upper() or "T2VA")


def _normalize_path(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return str(Path(str(value)).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        return str(value)


def _sentences(prompt: str) -> list[str]:
    chunks = re.split(r"(?:\r?\n+|(?<=[。！？!?；;])\s*|(?<=[.!?;])\s+)", prompt or "")
    result: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        sentence = " ".join(str(chunk).strip().split())
        if not sentence:
            continue
        key = sentence.casefold()
        if key not in seen:
            seen.add(key)
            result.append(sentence)
    return result


def _matching_sentences(prompt: str, markers: tuple[str, ...], limit: int = 8) -> list[str]:
    lowered_markers = tuple(marker.casefold() for marker in markers)
    matches: list[str] = []
    for sentence in _sentences(prompt):
        lowered = sentence.casefold()
        if any(marker in lowered for marker in lowered_markers):
            matches.append(sentence)
            if len(matches) >= limit:
                break
    return matches


def _extract_labels(prompt: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    patterns = (
        r"\b(?:Subject|Picture|Video|Audio)\s+[A-Za-z0-9_-]+",
        r"<(?:Subject|Picture|Video|Audio)[^>]*>",
    )
    for pattern in patterns:
        for match in re.findall(pattern, prompt or "", flags=re.IGNORECASE):
            label = " ".join(match.strip().split())
            key = label.casefold()
            if key not in seen:
                seen.add(key)
                labels.append(label)
    return labels


def load_anchor_declaration(path: str | Path | None) -> dict[str, Any]:
    """Load an optional user-authored JSON declaration without guessing fields."""
    if path is None:
        return {}
    source = Path(path).expanduser()
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("anchor declaration must be a JSON object")
    return value


def _reference_record(
    role: str,
    binding: Mapping[str, Any],
    fallback: Any = None,
    *,
    label: str | None = None,
) -> dict[str, Any]:
    source = binding.get("source") or fallback
    return {
        "role": role,
        "label": label or ("Picture 1" if role == "first_frame" else "Picture 2"),
        "source": _normalize_path(source),
        "input_name": binding.get("input_name"),
        "sha256": binding.get("sha256"),
        "staged": binding.get("staged"),
    }


def build_anchor_sheet(
    prompt: str,
    reference_inputs: Mapping[str, Any] | None = None,
    *,
    reference_mode: str = "t2v",
    first_frame: str | Path | None = None,
    last_frame: str | Path | None = None,
    reference_images: Sequence[Any] | None = None,
    settings: Mapping[str, Any] | None = None,
    anchor_file: str | Path | None = None,
) -> dict[str, Any]:
    """Return a deterministic anchor card for one effective H3 run."""
    explicit = load_anchor_declaration(anchor_file)
    inputs = reference_inputs.get("inputs", {}) if isinstance(reference_inputs, Mapping) else {}
    if not isinstance(inputs, Mapping):
        inputs = {}
    references: list[dict[str, Any]] = []
    for role, fallback in (("first_frame", first_frame), ("last_frame", last_frame)):
        binding = inputs.get(role, {})
        if fallback is not None or isinstance(binding, Mapping) and binding:
            references.append(_reference_record(role, binding if isinstance(binding, Mapping) else {}, fallback))
    ref_bindings = inputs.get("ref_images", [])
    if isinstance(ref_bindings, Sequence) and not isinstance(ref_bindings, (str, bytes)):
        for index, item in enumerate(ref_bindings, start=1):
            if not isinstance(item, Mapping):
                continue
            binding = item.get("binding", item)
            if not isinstance(binding, Mapping):
                binding = {}
            fallback = item.get("source")
            if fallback is None and reference_images is not None and index <= len(reference_images):
                fallback = reference_images[index - 1]
            references.append(
                _reference_record(
                    f"ref_image_{index}",
                    binding,
                    fallback,
                    label=f"Picture {index}",
                )
            )
    elif reference_images:
        for index, fallback in enumerate(reference_images, start=1):
            references.append(
                _reference_record(
                    f"ref_image_{index}",
                    {},
                    fallback,
                    label=f"Picture {index}",
                )
            )

    identity_sentences = _matching_sentences(prompt, IDENTITY_MARKERS)
    retention_sentences = _matching_sentences(prompt, RETENTION_MARKERS)
    allowed_change_sentences = _matching_sentences(prompt, ALLOWED_CHANGE_MARKERS)
    forbidden_drift_sentences = _matching_sentences(prompt, FORBIDDEN_DRIFT_MARKERS)
    multi_shot_sentences = _matching_sentences(prompt, MULTI_SHOT_MARKERS)
    mode_label = _route_label(reference_mode)
    identity_sensitive = bool(references) and mode_label in {"I2VA", "Ref2VA"}
    identity_sensitive = identity_sensitive or bool(identity_sentences)
    multi_shot = bool(multi_shot_sentences)
    if re.search(r"\[\s*(?:shot|镜头)\s*\d+", prompt or "", flags=re.IGNORECASE):
        multi_shot = True

    prompt_hash = hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()
    verification = {
        "policy": "advisory_anchor_check",
        "identity_sensitive": identity_sensitive,
        "multi_shot": multi_shot,
        "manual_review_required": identity_sensitive or multi_shot,
        "pixel_similarity_is_not_face_recognition": True,
        "retention_rule": "Keep reference identity, clothing, hair, markings, and scene continuity unless the prompt explicitly allows a change.",
    }
    sheet: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "h3lite.h3_anchor",
        "generation_method": "prompt_and_bound_inputs_only",
        "prompt_sha256": prompt_hash,
        "reference_mode": mode_label,
        "identity_sensitive": identity_sensitive,
        "multi_shot": multi_shot,
        "references": references,
        "subject_labels": _extract_labels(prompt),
        "identity_sentences": identity_sentences,
        "multi_shot_sentences": multi_shot_sentences,
        "retention_sentences": retention_sentences,
        "allowed_change_sentences": allowed_change_sentences,
        "forbidden_drift_sentences": forbidden_drift_sentences,
        "declared": explicit,
        "verification": verification,
        "effective_settings": dict(settings or {}),
    }
    return sheet


def anchor_summary(sheet: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(sheet, Mapping):
        return {}
    refs = sheet.get("references", [])
    return {
        "reference_mode": sheet.get("reference_mode"),
        "identity_sensitive": bool(sheet.get("identity_sensitive")),
        "multi_shot": bool(sheet.get("multi_shot")),
        "reference_count": len(refs) if isinstance(refs, list) else 0,
        "subject_labels": list(sheet.get("subject_labels", [])) if isinstance(sheet.get("subject_labels"), list) else [],
        "manual_review_required": bool((sheet.get("verification") or {}).get("manual_review_required"))
        if isinstance(sheet.get("verification"), Mapping)
        else False,
    }


def write_anchor_sheet(path: str | Path, sheet: Mapping[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(dict(sheet), ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--reference-mode", default="t2v")
    parser.add_argument("--first-frame")
    parser.add_argument("--last-frame")
    parser.add_argument("--anchor-file")
    args = parser.parse_args()
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    sheet = build_anchor_sheet(
        prompt,
        reference_mode=args.reference_mode,
        first_frame=args.first_frame,
        last_frame=args.last_frame,
        anchor_file=args.anchor_file,
    )
    write_anchor_sheet(args.output, sheet)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
