#!/usr/bin/env python3
"""Clone a ComfyUI API workflow under an explicit minimal-change contract.

The plan JSON declares which top-level node IDs may change, the exact nested
values to set, required classes/values/links, optional forbidden classes, output
geometry, and reference-file hashes. The script refuses to write a candidate if
any extra node changes or any contract check fails.

Usage:
  python h3_prepare_regional_workflow.py --base accepted.json \
      --plan regional_plan.json --output candidate.json --report qa/workflow.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def natural_node_key(value: str) -> tuple[int, Any]:
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


def changed_nodes(base: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    keys = set(base) | set(candidate)
    return sorted((str(key) for key in keys if base.get(key) != candidate.get(key)), key=natural_node_key)


def get_path(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise KeyError(dotted_path)
        current = current[part]
    return current


def merge_nested(target: dict[str, Any], updates: Mapping[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, Mapping):
            existing = target.get(key)
            if existing is None:
                existing = {}
                target[key] = existing
            if not isinstance(existing, dict):
                raise ValueError(f"cannot merge object into non-object field: {key}")
            merge_nested(existing, value)
        else:
            target[key] = copy.deepcopy(value)


def apply_plan(base: Mapping[str, Any], plan: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    candidate = copy.deepcopy(dict(base))
    errors: list[str] = []
    set_spec = plan.get("set", {})
    if not isinstance(set_spec, Mapping):
        return candidate, ["plan.set must be an object"]
    for node_id, updates in set_spec.items():
        node_key = str(node_id)
        if node_key not in candidate:
            errors.append(f"plan.set references missing node: {node_key}")
            continue
        if not isinstance(candidate[node_key], dict):
            errors.append(f"plan.set target is not a node object: {node_key}")
            continue
        if not isinstance(updates, Mapping):
            errors.append(f"plan.set.{node_key} must be an object")
            continue
        try:
            merge_nested(candidate[node_key], updates)
        except ValueError as exc:
            errors.append(f"plan.set.{node_key}: {exc}")
    return candidate, errors


def iter_graph_links(workflow: Mapping[str, Any]):
    node_ids = {str(key) for key in workflow}

    def visit(value: Any, path: str):
        if isinstance(value, list):
            if len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int) and not isinstance(value[1], bool):
                if value[0] in node_ids or value[0].isdigit():
                    yield path, value
            for index, item in enumerate(value):
                yield from visit(item, f"{path}[{index}]")
        elif isinstance(value, Mapping):
            for key, item in value.items():
                yield from visit(item, f"{path}.{key}" if path else str(key))

    for node_id, node in workflow.items():
        yield from visit(node, str(node_id))


def validate_links(workflow: Mapping[str, Any], errors: list[str]) -> None:
    for path, link in iter_graph_links(workflow):
        target, output_index = link
        if target not in {str(key) for key in workflow}:
            errors.append(f"broken graph link at {path}: missing node {target}")
        if output_index < 0:
            errors.append(f"invalid output index at {path}: {output_index}")


def validate_required(
    workflow: Mapping[str, Any],
    plan: Mapping[str, Any],
    errors: list[str],
    checks: dict[str, Any],
) -> None:
    classes = plan.get("require_classes", {})
    if not isinstance(classes, Mapping):
        errors.append("plan.require_classes must be an object")
        classes = {}
    class_results: dict[str, Any] = {}
    for node_id, expected in classes.items():
        actual = workflow.get(str(node_id), {}).get("class_type") if isinstance(workflow.get(str(node_id)), Mapping) else None
        passed = actual == expected
        class_results[str(node_id)] = {"expected": expected, "actual": actual, "passed": passed}
        if not passed:
            errors.append(f"node {node_id} class_type {actual!r} != {expected!r}")
    checks["classes"] = class_results

    values = plan.get("require_values", {})
    if not isinstance(values, Mapping):
        errors.append("plan.require_values must be an object")
        values = {}
    value_results: dict[str, Any] = {}
    for dotted_path, expected in values.items():
        try:
            actual = get_path(workflow, str(dotted_path))
            passed = actual == expected
            value_results[str(dotted_path)] = {"expected": expected, "actual": actual, "passed": passed}
        except KeyError:
            passed = False
            value_results[str(dotted_path)] = {"expected": expected, "actual": None, "passed": False}
        if not passed:
            errors.append(f"required value mismatch at {dotted_path}: {value_results[str(dotted_path)]['actual']!r} != {expected!r}")
    checks["values"] = value_results

    links = plan.get("require_links", {})
    if not isinstance(links, Mapping):
        errors.append("plan.require_links must be an object")
        links = {}
    link_results: dict[str, Any] = {}
    for dotted_path, expected in links.items():
        try:
            actual = get_path(workflow, str(dotted_path))
            passed = actual == expected
            link_results[str(dotted_path)] = {"expected": expected, "actual": actual, "passed": passed}
        except KeyError:
            passed = False
            link_results[str(dotted_path)] = {"expected": expected, "actual": None, "passed": False}
        if not passed:
            errors.append(f"required link mismatch at {dotted_path}: {link_results[str(dotted_path)]['actual']!r} != {expected!r}")
    checks["links"] = link_results

    forbidden = plan.get("forbid_classes", [])
    if not isinstance(forbidden, list):
        errors.append("plan.forbid_classes must be a list")
        forbidden = []
    forbidden_found = sorted(
        {str(node.get("class_type")) for node in workflow.values() if isinstance(node, Mapping) and node.get("class_type") in forbidden}
    )
    checks["forbidden_classes_found"] = forbidden_found
    if forbidden_found:
        errors.append(f"forbidden class types present: {forbidden_found}")


def validate_geometry(plan: Mapping[str, Any], errors: list[str]) -> dict[str, Any] | None:
    geometry = plan.get("geometry")
    if geometry is None:
        return None
    if not isinstance(geometry, Mapping):
        errors.append("plan.geometry must be an object")
        return None
    required = ("source_width", "source_height", "output_scale", "max_megapixels", "expected_width", "expected_height")
    missing = [key for key in required if key not in geometry]
    if missing:
        errors.append(f"plan.geometry missing: {', '.join(missing)}")
        return None
    try:
        source_width = int(geometry["source_width"])
        source_height = int(geometry["source_height"])
        output_scale = float(geometry["output_scale"])
        max_megapixels = float(geometry["max_megapixels"])
        expected_width = int(geometry["expected_width"])
        expected_height = int(geometry["expected_height"])
    except (TypeError, ValueError) as exc:
        errors.append(f"plan.geometry contains invalid numeric values: {exc}")
        return None
    if source_width <= 0 or source_height <= 0 or output_scale <= 0 or max_megapixels <= 0:
        errors.append("plan.geometry source and scale values must be positive")
        return None
    scale = min(output_scale, math.sqrt(max_megapixels * 1_000_000 / (source_width * source_height)))
    actual_width = max(32, int(source_width * scale) // 32 * 32)
    actual_height = max(32, int(source_height * scale) // 32 * 32)
    passed = (actual_width, actual_height) == (expected_width, expected_height)
    result = {
        "source": [source_width, source_height],
        "output_scale": output_scale,
        "max_megapixels": max_megapixels,
        "effective_scale": scale,
        "actual": [actual_width, actual_height],
        "expected": [expected_width, expected_height],
        "passed": passed,
    }
    if not passed:
        errors.append(f"geometry mismatch: actual {actual_width}x{actual_height}, expected {expected_width}x{expected_height}")
    return result


def validate_references(plan: Mapping[str, Any], plan_path: Path, errors: list[str]) -> list[dict[str, Any]]:
    references = plan.get("reference_files", [])
    if not isinstance(references, list):
        errors.append("plan.reference_files must be a list")
        return []
    results: list[dict[str, Any]] = []
    for index, item in enumerate(references):
        if not isinstance(item, Mapping) or not item.get("path"):
            errors.append(f"reference_files[{index}] must contain a path")
            continue
        raw_path = Path(str(item["path"])).expanduser()
        path = raw_path if raw_path.is_absolute() else (plan_path.parent / raw_path).resolve()
        expected = str(item.get("sha256") or "").lower() or None
        exists = path.is_file()
        actual = sha256_file(path) if exists else None
        passed = exists and (expected is None or actual == expected)
        results.append({"path": str(path), "exists": exists, "expected_sha256": expected, "actual_sha256": actual, "passed": passed})
        if not exists:
            errors.append(f"reference file not found: {path}")
        elif expected and actual != expected:
            errors.append(f"reference SHA mismatch for {path}: {actual} != {expected}")
    return results


def prepare(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    base_path = Path(args.base).expanduser().resolve()
    plan_path = Path(args.plan).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if output_path == base_path:
        errors.append("output must not overwrite the base workflow")
    if output_path.exists() and not args.overwrite:
        errors.append(f"output already exists: {output_path}; pass --overwrite to replace it")
    try:
        base = load_json(base_path)
        plan = load_json(plan_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        report: dict[str, Any] = {
            "status": "failed",
            "base": str(base_path),
            "plan": str(plan_path),
            "output": str(output_path),
            "errors": [str(exc)],
            "warnings": warnings,
        }
        if args.report:
            report_path = Path(args.report).expanduser().resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report["report_path"] = str(report_path)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report, 1

    candidate, apply_errors = apply_plan(base, plan)
    errors.extend(apply_errors)
    changed = changed_nodes(base, candidate)
    allowed_raw = plan.get("allow_changed_nodes", [])
    if not isinstance(allowed_raw, list):
        errors.append("plan.allow_changed_nodes must be a list")
        allowed_raw = []
    allowed = sorted({str(item) for item in allowed_raw}, key=natural_node_key)
    unexpected = [node_id for node_id in changed if node_id not in allowed]
    if unexpected:
        errors.append(f"unexpected changed nodes: {unexpected}")

    validate_links(candidate, errors)
    checks: dict[str, Any] = {}
    validate_required(candidate, plan, errors, checks)
    geometry = validate_geometry(plan, errors)
    references = validate_references(plan, plan_path, errors)
    if not changed and allowed:
        warnings.append("no nodes changed; verify the plan values are intentional")

    status = "passed" if not errors else "failed"
    report: dict[str, Any] = {
        "status": status,
        "base": str(base_path),
        "base_sha256": sha256_file(base_path),
        "plan": str(plan_path),
        "plan_sha256": sha256_file(plan_path),
        "output": str(output_path),
        "node_count": len(candidate),
        "changed_nodes": changed,
        "allowed_changed_nodes": allowed,
        "unexpected_changed_nodes": unexpected,
        "geometry": geometry,
        "references": references,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }
    if status == "passed":
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["output_sha256"] = sha256_file(output_path)
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report["report_path"] = str(report_path)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report, 0 if status == "passed" else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args(argv)
    try:
        report, code = prepare(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"status": "failed", "errors": [str(exc)], "warnings": []}
        code = 1
    if report["status"] == "passed":
        print(f"Regional workflow: PASS | changed nodes {report['changed_nodes']}")
        print(f"output: {report['output']}")
        if report.get("report_path"):
            print(f"report: {report['report_path']}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
