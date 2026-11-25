#!/usr/bin/env python3
"""Verify and manifest the Set C asset package or an installed ComfyUI tree.

Set C is an overlay on Set B, not a third standalone base. This tool checks the
four Set C model files, the core/ref2va package layout, workflows, licenses and
SHA manifests, then writes component_manifest.json.

Usage:
  python h3_setc_assets.py --package F:/H3lite_SetC_Baidu/staging
  python h3_setc_assets.py --comfyui E:/MiniMax-H3/ComfyUI
  python h3_setc_assets.py --package ... --comfyui ... --quick --json
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

SHARE_URL = "https://pan.quark.cn/s/6f8f5ce9f8a6"
SHARE_CODE = "/~67293cXj30~:/"

EXPECTED_FILES: list[dict[str, Any]] = [
    {
        "role": "sol_vae_int8",
        "package": "core",
        "path": "models/vae/minimax_h3_sol_vae_int8_convrot.safetensors",
        "target": "models/vae/minimax_h3_sol_vae_int8_convrot.safetensors",
        "bytes": 1_988_306_504,
        "sha256": "a742069ba173bc3aba64cf8d8289d073e0818f2753f2fc2768f0342645089682",
    },
    {
        "role": "pika_fl2va_lora",
        "package": "core",
        "path": "models/loras/pika_h3_flex_turbo_4step_fl2va_lite_r32.safetensors",
        "target": "models/loras/pika_h3_flex_turbo_4step_fl2va_lite_r32.safetensors",
        "bytes": 310_189_392,
        "sha256": "7c60a2ff31f7f56c1f59020c2441fa0532c7b3fd8a510fbd0f806327021f5367",
    },
    {
        "role": "ref2va_diffusion_base",
        "package": "ref2va",
        "path": "models/diffusion_models/minimax_h3_ref2va_pruned_w4a8_mixed.safetensors",
        "target": "models/diffusion_models/minimax_h3_ref2va_pruned_w4a8_mixed.safetensors",
        "bytes": 11_770_657_048,
        "sha256": "de2c6c29c4ee702b45e48e40daae3834aeee58ab681c732d9152589a87c89910",
    },
    {
        "role": "pika_ref2va_lora",
        "package": "ref2va",
        "path": "models/loras/pika_h3_flex_turbo_4step_ref2va_lite_r32.safetensors",
        "target": "models/loras/pika_h3_flex_turbo_4step_ref2va_lite_r32.safetensors",
        "bytes": 310_189_392,
        "sha256": "c9482ccfffd2580b57a0b994035a94379afa97bc97dc0b05b5753e8ab906b9bd",
    },
]

WORKFLOWS = [
    "h3_c_speed640_api.json",
    "h3_c_t2va768_api.json",
    "h3_c_quality864_api.json",
    "h3_c_i2va768_api.json",
    "h3_c_fl2va768_api.json",
    "h3_c_ref2va768_api.json",
]
LICENSES = [
    "SOURCE_AND_LICENSE.txt",
    "ComfyUI-sol-attn-LICENSE",
    "MiniMax-H3-Community-License.txt",
    "ComfyUI-ClipProj-LICENSE",
]
PACKAGES = ["core", "ref2va"]
SIDECARS = ["NOTICE.txt", "README_安装说明.md", "SHA256SUMS.txt"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_file(path: Path, expected_bytes: int, expected_sha: str, *, quick: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "expected_bytes": expected_bytes,
        "expected_sha256": expected_sha,
        "size_ok": False,
        "sha256_ok": None,
        "actual_bytes": None,
        "actual_sha256": None,
    }
    if not path.is_file():
        return result
    actual_bytes = path.stat().st_size
    result["actual_bytes"] = actual_bytes
    result["size_ok"] = actual_bytes == expected_bytes
    if quick:
        return result
    if not result["size_ok"]:
        return result
    actual_sha = _sha256(path)
    result["actual_sha256"] = actual_sha
    result["sha256_ok"] = actual_sha == expected_sha
    return result


def _check_package(package_root: Path, *, quick: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "root": str(package_root),
        "exists": package_root.is_dir(),
        "packages": {},
        "files": [],
        "errors": [],
        "warnings": [],
    }
    if not package_root.is_dir():
        report["errors"].append(f"package root does not exist: {package_root}")
        return report

    for package in PACKAGES:
        base = package_root / package
        entry: dict[str, Any] = {
            "path": str(base),
            "exists": base.is_dir(),
            "workflows": [],
            "licenses": [],
            "sidecars": [],
        }
        report["packages"][package] = entry
        if not base.is_dir():
            report["errors"].append(f"missing package folder: {base}")
            continue
        for name in WORKFLOWS:
            path = base / "workflows" / name
            entry["workflows"].append({"name": name, "exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else None})
            if not path.is_file():
                report["errors"].append(f"missing workflow: {path}")
        for name in LICENSES:
            path = base / "licenses" / name
            entry["licenses"].append({"name": name, "exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else None})
            if not path.is_file():
                report["errors"].append(f"missing license: {path}")
        for name in SIDECARS:
            path = base / name
            entry["sidecars"].append({"name": name, "exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else None})
            if not path.is_file():
                report["errors"].append(f"missing sidecar: {path}")

    for expected in EXPECTED_FILES:
        path = package_root / expected["package"] / expected["path"]
        check = _check_file(path, expected["bytes"], expected["sha256"], quick=quick)
        check.update({"role": expected["role"], "package": expected["package"], "target": expected["target"]})
        report["files"].append(check)
        if not check["exists"]:
            report["errors"].append(f"missing model: {path}")
        elif not check["size_ok"]:
            report["errors"].append(f"size mismatch: {path} ({check['actual_bytes']} != {expected['bytes']})")
        elif check["sha256_ok"] is False:
            report["errors"].append(f"sha256 mismatch: {path}")
        elif check["sha256_ok"] is None:
            report["warnings"].append(f"size-only checked (--quick): {path}")
    return report


def _check_comfyui(comfyui: Path, *, quick: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "root": str(comfyui),
        "exists": comfyui.is_dir(),
        "files": [],
        "errors": [],
        "warnings": [],
    }
    if not comfyui.is_dir():
        report["errors"].append(f"ComfyUI root does not exist: {comfyui}")
        return report
    for expected in EXPECTED_FILES:
        path = comfyui / expected["target"]
        check = _check_file(path, expected["bytes"], expected["sha256"], quick=quick)
        check.update({"role": expected["role"], "target": expected["target"]})
        report["files"].append(check)
        if not check["exists"]:
            report["errors"].append(f"missing installed model: {path}")
        elif not check["size_ok"]:
            report["errors"].append(f"installed size mismatch: {path} ({check['actual_bytes']} != {expected['bytes']})")
        elif check["sha256_ok"] is False:
            report["errors"].append(f"installed sha256 mismatch: {path}")
        elif check["sha256_ok"] is None:
            report["warnings"].append(f"installed size-only checked (--quick): {path}")
    return report


def _manifest(package_report: dict[str, Any] | None, comfy_report: dict[str, Any] | None, *, quick: bool) -> dict[str, Any]:
    files = []
    source = package_report or {}
    by_role = {item.get("role"): item for item in source.get("files", []) if isinstance(item, dict)}
    for expected in EXPECTED_FILES:
        check = by_role.get(expected["role"], {})
        verified = bool(check.get("size_ok") and (check.get("sha256_ok") is True or quick))
        files.append(
            {
                "role": expected["role"],
                "package": expected["package"],
                "source_path": f'{expected["package"]}/{expected["path"]}',
                "target_path": expected["target"],
                "bytes": expected["bytes"],
                "sha256": expected["sha256"],
                "verified": verified,
                "actual_bytes": check.get("actual_bytes"),
                "actual_sha256": check.get("actual_sha256"),
            }
        )
    return {
        "schema_version": 1,
        "component_set": "set-c-2026-11-19",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "share": {"url": SHARE_URL, "code": SHARE_CODE},
        "install_order": [
            "Install Set B first.",
            "Merge core/models/* into <ComfyUI>/models/*.",
            "Add ref2va/models/* only when the Ref2VA route is used.",
            "Keep each package's workflows/, licenses/, NOTICE.txt and SHA256SUMS.txt.",
        ],
        "packages": {
            "core": {
                "bytes": 2_298_495_896,
                "files": 15,
                "roles": ["sol_vae_int8", "pika_fl2va_lora"],
                "routes": ["speed640", "quality864", "t2va768", "i2va768", "fl2va768"],
            },
            "ref2va": {
                "bytes": 12_080_846_440,
                "files": 15,
                "roles": ["ref2va_diffusion_base", "pika_ref2va_lora"],
                "routes": ["ref2va768"],
            },
        },
        "files": files,
        "workflows": WORKFLOWS,
        "licenses": LICENSES,
        "verification": {
            "quick": quick,
            "package": package_report is not None,
            "comfyui": comfy_report is not None,
            "package_errors": (package_report or {}).get("errors", []),
            "comfyui_errors": (comfy_report or {}).get("errors", []),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", help="Set C package root containing core/ and ref2va/")
    parser.add_argument("--comfyui", help="ComfyUI root with models/vae, models/loras and models/diffusion_models")
    parser.add_argument("--manifest", help="write component_manifest.json here; defaults to <package>/component_manifest.json")
    parser.add_argument("--no-manifest", action="store_true", help="do not write a manifest")
    parser.add_argument("--quick", action="store_true", help="check size only; skip sha256 hashing")
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = parse_args()
    if not args.package and not args.comfyui:
        print("ERROR: give --package and/or --comfyui", file=sys.stderr)
        return 2
    package_root = Path(args.package).expanduser().resolve() if args.package else None
    comfyui = Path(args.comfyui).expanduser().resolve() if args.comfyui else None
    package_report = _check_package(package_root, quick=args.quick) if package_root else None
    comfy_report = _check_comfyui(comfyui, quick=args.quick) if comfyui else None
    errors = []
    warnings = []
    if package_report:
        errors.extend(package_report["errors"])
        warnings.extend(package_report["warnings"])
    if comfy_report:
        errors.extend(comfy_report["errors"])
        warnings.extend(comfy_report["warnings"])
    manifest_path = None
    if package_root and not args.no_manifest:
        manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else (package_root / "component_manifest.json")
        manifest = _manifest(package_report, comfy_report, quick=args.quick)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = manifest_path.with_name(manifest_path.name + ".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, manifest_path)
    summary = {
        "ok": not errors,
        "package": str(package_root) if package_root else None,
        "comfyui": str(comfyui) if comfyui else None,
        "manifest": str(manifest_path) if manifest_path else None,
        "errors": errors,
        "warnings": warnings,
        "package_report": package_report,
        "comfyui_report": comfy_report,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Set C assets: {'PASS' if not errors else 'FAIL'}")
        if package_root:
            print(f"package: {package_root}")
        if comfyui:
            print(f"comfyui: {comfyui}")
        if manifest_path:
            print(f"manifest: {manifest_path}")
        for warning in warnings:
            print(f"WARN: {warning}")
        for error in errors:
            print(f"ERROR: {error}")
        if not errors:
            print("4 model files verified" if not args.quick else "4 model sizes verified (--quick)")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
