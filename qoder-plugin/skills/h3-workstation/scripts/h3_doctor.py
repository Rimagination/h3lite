#!/usr/bin/env python3
"""Dependency-light diagnosis for a local MiniMax H3 / ComfyUI install.

The script deliberately reads state only. It does not install packages, download
models, start ComfyUI, or change files. Use --json when an agent needs a stable
machine-readable report.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import hashlib
from typing import Any, Iterable

from h3_paths import (
    default_config_path,
    find_comfyui,
    is_comfyui_root,
    normalize_windows_path,
    save_config,
)


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_command(command: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except (FileNotFoundError, OSError) as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return 124, stdout.strip(), stderr.strip() or "command timed out"


def parse_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except (AttributeError, ValueError):
        return None


def nvidia_gpus() -> list[dict[str, Any]]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free,driver_version",
        "--format=csv,noheader,nounits",
    ]
    code, stdout, stderr = run_command(command)
    if code != 0:
        return [{"error": "nvidia-smi unavailable", "detail": stderr or stdout}]

    gpus: list[dict[str, Any]] = []
    for row in csv.reader(stdout.splitlines()):
        if not row:
            continue
        values = [item.strip() for item in row]
        while len(values) < 4:
            values.append("")
        total_mb = parse_float(values[1])
        free_mb = parse_float(values[2])
        gpus.append(
            {
                "name": values[0],
                "vram_total_mb": total_mb,
                "vram_free_mb": free_mb,
                "vram_total_gb": round(total_mb / 1024, 2) if total_mb is not None else None,
                "vram_free_gb": round(free_mb / 1024, 2) if free_mb is not None else None,
                "driver_version": values[3],
            }
        )
    return gpus or [{"error": "nvidia-smi returned no GPUs", "detail": stdout}]


def nvidia_processes() -> list[dict[str, Any]]:
    """List compute processes that can steal VRAM from a low-VRAM run."""
    command = [
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_gpu_memory",
        "--format=csv,noheader,nounits",
    ]
    code, stdout, _ = run_command(command)
    if code != 0:
        return []
    processes: list[dict[str, Any]] = []
    for row in csv.reader(stdout.splitlines()):
        if not row:
            continue
        values = [item.strip() for item in row]
        while len(values) < 3:
            values.append("")
        processes.append({"pid": values[0], "process_name": values[1], "used_gpu_memory_mb": parse_float(values[2])})
    return processes


def system_memory() -> dict[str, Any]:
    if os.name == "nt":
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return {
                "total_gb": round(status.ullTotalPhys / 1024**3, 2),
                "available_gb": round(status.ullAvailPhys / 1024**3, 2),
                "page_file_total_gb": round(status.ullTotalPageFile / 1024**3, 2),
                "page_file_available_gb": round(status.ullAvailPageFile / 1024**3, 2),
                "load_percent": int(status.dwMemoryLoad),
            }

    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        values: dict[str, int] = {}
        for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                values[parts[0].rstrip(":")] = int(parts[1]) * 1024
        total = values.get("MemTotal")
        available = values.get("MemAvailable", values.get("MemFree"))
        if total:
            return {
                "total_gb": round(total / 1024**3, 2),
                "available_gb": round(available / 1024**3, 2) if available else None,
                "page_file_total_gb": round(values.get("SwapTotal", 0) / 1024**3, 2),
                "page_file_available_gb": round(values.get("SwapFree", 0) / 1024**3, 2),
                "load_percent": round((1 - available / total) * 100, 1) if available else None,
            }
    return {"error": "system memory information unavailable"}


def candidate_python_paths(comfyui: Path | None) -> list[Path]:
    paths: list[Path] = []
    if comfyui:
        paths.extend(
            [
                comfyui / "venv" / "Scripts" / "python.exe",
                comfyui / ".venv" / "Scripts" / "python.exe",
                comfyui / "python_embeded" / "python.exe",
                comfyui.parent / "python_embeded" / "python.exe",
                comfyui / "venv" / "bin" / "python",
                comfyui / ".venv" / "bin" / "python",
            ]
        )
    # Probe the interpreter that actually owns ComfyUI. A system Python which
    # cannot import ComfyUI-only packages is not evidence that the running
    # installation is broken.
    if not any(path.exists() for path in paths):
        paths.append(Path(sys.executable))
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen and path.exists():
            seen.add(key)
            unique.append(path)
    return unique


def python_probe(path: Path) -> dict[str, Any]:
    code = (
        "import json,sys; r={'python':sys.version.split()[0]}; "
        "\ntry:\n import torch\n r.update({'torch':torch.__version__,'cuda_available':bool(torch.cuda.is_available()),'torch_cuda':torch.version.cuda})\n "
        "\n if torch.cuda.is_available():\n  r['torch_arch_list']=list(torch.cuda.get_arch_list()) if hasattr(torch.cuda,'get_arch_list') else []\n  r['torch_devices']=[]\n  for i in range(torch.cuda.device_count()):\n   r['torch_devices'].append({'name':torch.cuda.get_device_name(i),'capability':list(torch.cuda.get_device_capability(i))})\n "
        "\nexcept Exception as e: r.update({'torch_error':type(e).__name__+': '+str(e)})\n"
        "\ntry:\n import comfy_kitchen\n r.update({'comfy_kitchen':getattr(comfy_kitchen,'__version__','unknown'),'comfy_kitchen_path':getattr(comfy_kitchen,'__file__',None)})\n "
        "\nexcept Exception as e: r.update({'comfy_kitchen_error':type(e).__name__+': '+str(e)})\n"
        # Optional acceleration runtimes. A custom node can be registered in
        # object_info while its backend still fails to import, so class
        # presence alone is not evidence that the fast graph can execute.
        "\ntry:\n import triton\n r.update({'triton':getattr(triton,'__version__','unknown')})\n "
        "\nexcept Exception as e: r.update({'triton_error':type(e).__name__+': '+str(e)})\n"
        "\ntry:\n import sageattention\n r.update({'sageattention':getattr(sageattention,'__version__','unknown')})\n "
        "\nexcept Exception as e: r.update({'sageattention_error':type(e).__name__+': '+str(e)})\n"
        "print(json.dumps(r, ensure_ascii=False))"
    )
    return_code, stdout, stderr = run_command([str(path), "-c", code], timeout=30)
    result: dict[str, Any] = {"path": str(path), "returncode": return_code}
    if stdout:
        try:
            result.update(json.loads(stdout.splitlines()[-1]))
        except json.JSONDecodeError:
            result["stdout"] = stdout[-500:]
    if stderr:
        result["stderr"] = stderr[-500:]
    return result


def path_disk(path: Path) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
        return {
            "path": str(path),
            "total_gb": round(usage.total / 1024**3, 2),
            "free_gb": round(usage.free / 1024**3, 2),
            "used_percent": round((usage.used / usage.total) * 100, 1) if usage.total else None,
        }
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


MODEL_MANIFEST: dict[str, dict[str, Any]] = {
    "low_vram_diffusion": {
        "role": "low-VRAM W4A8 diffusion",
        "folders": ["models/diffusion_models"],
        "patterns": [r"minimax_h3.*w4a8.*\.safetensors$"],
    },
    "native_diffusion": {
        "role": "native INT8 diffusion",
        "folders": ["models/diffusion_models"],
        "patterns": [r"minimax_h3.*int8.*\.safetensors$"],
    },
    "low_vram_text_encoder": {
        "role": "Qwen3-VL 4B low-VRAM text encoder",
        "folders": ["models/text_encoders", "models/text_encoder"],
        "patterns": [r"qwen3vl.*4b.*(int4|4bit|fp8).*\.safetensors$"],
    },
    "native_text_encoder": {
        "role": "Qwen3-VL 32B native text encoder",
        "folders": ["models/text_encoders", "models/text_encoder"],
        "patterns": [r"qwen3vl.*32b.*\.safetensors$"],
    },
    "video_vae_fp16": {
        "role": "FP16 video VAE",
        "folders": ["models/vae"],
        "patterns": [r"minimax_h3.*video_vae.*fp16.*\.safetensors$"],
    },
    "audio_vae_fp32": {
        "role": "FP32 audio VAE",
        "folders": ["models/vae"],
        "patterns": [r"minimax_h3.*audio_vae.*fp32.*\.safetensors$"],
    },
    "clipproj": {
        "role": "H3 4B ClipProj",
        "folders": ["models", "custom_nodes"],
        "patterns": [r".*clipproj.*\.safetensors$"],
    },
    "lightx2v_lora": {
        "role": "4-step H3 Turbo/LightX2V LoRA",
        "folders": ["models/loras", "models/lora"],
        "patterns": [r".*lightx2v.*\.safetensors$", r"minimax_h3.*turbo.*step.*\.safetensors$"],
    },
}


NODE_REQUIREMENTS = {
    "kj_nodes": ["ComfyUI-KJNodes", "KJNodes"],
    "clipproj_node": ["ComfyUI-ClipProj", "ClipProj"],
    "h3_turbo": ["ComfyUI-MiniMax-H3-Turbo", "MiniMax-H3-Turbo"],
    "sol_attention": ["ComfyUI-sol-attn", "sol-attn"],
    "sage_attention": ["ComfyUI_NVIDIA_RTX_Nodes", "NVIDIA_RTX_Nodes", "SageAttention", "sage-attn"],
    "block_cache": ["comfyui-minimax-h3-blockcache-T8", "blockcache-T8", "blockcache"],
}


def matching_files(comfyui: Path, entry: dict[str, Any]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    patterns = [re.compile(pattern, re.IGNORECASE) for pattern in entry["patterns"]]
    seen: set[str] = set()
    for relative_folder in entry["folders"]:
        folder = comfyui / relative_folder
        if not folder.exists():
            continue
        try:
            candidates: Iterable[Path] = folder.rglob("*")
            for path in candidates:
                if not path.is_file() or str(path) in seen:
                    continue
                if any(pattern.search(path.name) for pattern in patterns):
                    seen.add(str(path))
                    try:
                        size = path.stat().st_size
                    except OSError:
                        size = None
                    matches.append({"path": str(path), "size_bytes": size, "size": human_size(size) if size is not None else None})
        except OSError:
            continue
    return matches


def model_report(comfyui: Path | None) -> dict[str, Any]:
    if not comfyui or not comfyui.exists():
        return {"available": False, "reason": "ComfyUI path not found", "assets": {}}
    assets: dict[str, Any] = {}
    for key, entry in MODEL_MANIFEST.items():
        found = matching_files(comfyui, entry)
        assets[key] = {"role": entry["role"], "found": found, "present": bool(found)}
    return {"available": True, "root": str(comfyui), "assets": assets}


QUANTIZED_DIT_RE = re.compile(r"(w4a8|w6a8|int8|convrot)", re.IGNORECASE)
FP8_DIT_RE = re.compile(r"fp8(_scaled)?", re.IGNORECASE)
BLACKWELL_NAME_RE = re.compile(r"RTX\s*50\d0|B[12]00|Blackwell", re.IGNORECASE)


def blackwell_devices(report: dict[str, Any]) -> list[str]:
    """Return Blackwell GPU names seen through nvidia-smi or a Torch probe."""
    names: list[str] = []
    for gpu in report.get("gpus", []):
        if not isinstance(gpu, dict):
            continue
        name = str(gpu.get("name") or "")
        if BLACKWELL_NAME_RE.search(name):
            names.append(name)
    for probe in report.get("python_probes", []):
        if not isinstance(probe, dict):
            continue
        for device in probe.get("torch_devices", []) or []:
            if not isinstance(device, dict):
                continue
            capability = device.get("capability")
            name = str(device.get("name") or "")
            if (isinstance(capability, list) and capability[:2] in ([12, 0], [12, 1])) or BLACKWELL_NAME_RE.search(name):
                names.append(name or "Blackwell GPU")
    return sorted(set(item for item in names if item))


def blackwell_quantized_risk(report: dict[str, Any]) -> dict[str, Any]:
    """Flag the upstream sm_120 + W4A8/INT8 convrot failure before GPU time.

    RTX 50-series cards can load and sample quantized H3 checkpoints while
    ignoring text conditioning or producing a fixed texture. The failure is in
    comfy-kitchen's convrot kernel path, not in H3Lite's workflows, so this is
    a warning plus a single-variable workaround rather than a hard block.
    """
    devices = blackwell_devices(report)
    if not devices:
        return {"status": "not-applicable", "devices": [], "checkpoints": []}

    models = report.get("models") if isinstance(report.get("models"), dict) else {}
    assets = models.get("assets") if isinstance(models.get("assets"), dict) else {}
    if not assets:
        return {"status": "unknown", "devices": devices, "checkpoints": [], "reason": "model scan disabled"}

    checkpoints: list[str] = []
    fp8_candidates: list[str] = []
    for role in ("low_vram_diffusion", "native_diffusion"):
        asset = assets.get(role)
        if not isinstance(asset, dict):
            continue
        for found in asset.get("found", []):
            if not isinstance(found, dict):
                continue
            name = Path(str(found.get("path", ""))).name
            if QUANTIZED_DIT_RE.search(name):
                checkpoints.append(name)
            elif FP8_DIT_RE.search(name):
                fp8_candidates.append(name)
    if not checkpoints:
        return {"status": "clear", "devices": devices, "checkpoints": [], "fp8_checkpoints": sorted(set(fp8_candidates))}

    message = (
        "Blackwell GPU detected ("
        + ", ".join(devices)
        + ") together with quantized H3 DiT checkpoint(s): "
        + ", ".join(sorted(set(checkpoints)))
        + ". Upstream reports fixed woven texture, identical output for different prompts, "
        "and numerical blowup on RTX 5060 Ti 16 GB with the int8/convrot kernel path "
        "(Comfy-Org/comfy-kitchen#163, #120; Comfy-Org/ComfyUI#17098; 0.2.38 did not fix it, "
        "RTX 5090 did not reproduce). Before committing a long render, run a 640x352 4-step "
        "text-influence check with two different prompts. If text has zero effect, switch ONLY "
        "the DiT/UNETLoader to minimax_h3_fl2va_pruned_fp8_scaled.safetensors and keep the "
        "text encoder, LoRA and VAE unchanged; do not treat Set C/W4A8 as validated on sm_120 yet."
    )
    return {
        "status": "risk",
        "devices": devices,
        "checkpoints": sorted(set(checkpoints)),
        "fp8_checkpoints": sorted(set(fp8_candidates)),
        "message": message,
        "references": [
            "https://github.com/Comfy-Org/comfy-kitchen/issues/163",
            "https://github.com/Comfy-Org/comfy-kitchen/issues/120",
            "https://github.com/Comfy-Org/ComfyUI/issues/17098",
        ],
    }


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def node_report(comfyui: Path | None) -> dict[str, Any]:
    if not comfyui:
        return {"available": False, "reason": "ComfyUI path not supplied", "nodes": {}}
    node_dir = comfyui / "custom_nodes"
    if not node_dir.exists():
        return {"available": False, "reason": "custom_nodes directory not found", "nodes": {}}
    installed = [path.name for path in node_dir.iterdir() if path.is_dir()]
    installed_normalized = [(name, normalized(name)) for name in installed]
    nodes: dict[str, Any] = {}
    for key, aliases in NODE_REQUIREMENTS.items():
        matches = []
        for name, normalized_name in installed_normalized:
            if any(normalized(alias) in normalized_name or normalized_name in normalized(alias) for alias in aliases):
                matches.append(name)
        nodes[key] = {"aliases": aliases, "present": bool(matches), "matches": sorted(set(matches))}
    return {"available": True, "root": str(node_dir), "installed": sorted(installed), "nodes": nodes}


def environment_fingerprint(report: dict[str, Any], comfyui: Path | None) -> str:
    """Fingerprint cheap-to-check environment identity for cache reuse."""
    entries: list[str] = []
    for gpu in report.get("gpus", []):
        if isinstance(gpu, dict):
            entries.append(f"gpu:{gpu.get('name')}:{gpu.get('vram_total_gb')}:{gpu.get('driver_version')}")
    if comfyui:
        main_py = comfyui / "main.py"
        try:
            stat = main_py.stat()
            entries.append(f"comfyui:{comfyui.resolve()}:{stat.st_size}:{stat.st_mtime_ns}")
        except OSError:
            entries.append(f"comfyui:{comfyui.resolve()}:missing")
    models = report.get("models", {}).get("assets", {}) if isinstance(report.get("models"), dict) else {}
    for asset in models.values():
        if not isinstance(asset, dict):
            continue
        for found in asset.get("found", []):
            if not isinstance(found, dict):
                continue
            path = Path(str(found.get("path", "")))
            try:
                stat = path.stat()
                entries.append(f"model:{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}")
            except OSError:
                entries.append(f"model:{path}:missing")
    nodes = report.get("custom_nodes", {}).get("installed", []) if isinstance(report.get("custom_nodes"), dict) else []
    entries.extend(f"node:{name}" for name in nodes)
    return hashlib.sha256("\n".join(sorted(entries)).encode("utf-8")).hexdigest()


def runtime_compatibility(report: dict[str, Any]) -> dict[str, Any]:
    """Expose import failures before a large model download or generation."""
    errors: list[str] = []
    warnings: list[str] = []
    for probe in report.get("python_probes", []):
        if not isinstance(probe, dict):
            continue
        if probe.get("torch_error"):
            errors.append(f"Torch import failed in {probe.get('path')}: {probe['torch_error']}")
        if probe.get("comfy_kitchen_error"):
            message = f"comfy-kitchen import failed in {probe.get('path')}: {probe['comfy_kitchen_error']}"
            errors.append(message + "; repair the ComfyUI/comfy-kitchen/Torch/extension ABI set before using W4A8")
        if probe.get("torch") and not probe.get("torch_error"):
            # Optional acceleration backends. The node classes can be loaded
            # while these imports fail, which turns the fast graph into a
            # runtime error instead of a faster render.
            if probe.get("triton_error"):
                warnings.append(
                    f"Triton is unavailable in {probe.get('path')}: {probe['triton_error']}; "
                    "the ComfyUI-sol-attn Triton nodes (MemoryEfficientSol, ScheduledSol, FusedModulation) "
                    "raise at execute time. Use the native BlockSparseAttention Set C graphs, "
                    "a *_compat graph, or install Triton in the ComfyUI interpreter."
                )
            if probe.get("sageattention_error"):
                warnings.append(
                    f"sageattention is unavailable in {probe.get('path')}: {probe['sageattention_error']}; "
                    "MiniMaxH3MemoryEfficientSageAttentionPatch raises at execute time. "
                    "Use a *_compat graph or install sageattention in the ComfyUI interpreter."
                )
        arch_list = {str(item) for item in probe.get("torch_arch_list", []) if item}
        if arch_list and isinstance(probe.get("torch_devices"), list):
            for device in probe["torch_devices"]:
                capability = device.get("capability") if isinstance(device, dict) else None
                if isinstance(capability, list) and capability[:2] == [12, 0] and not any(
                    item.startswith("sm_120") for item in arch_list
                ):
                    warnings.append(
                        f"{device.get('name', 'Blackwell GPU')} requires a Torch build containing sm_120; "
                        "update the ComfyUI environment before using the RTX 50-series acceleration path."
                    )
    risk = report.get("blackwell_quantized")
    if isinstance(risk, dict) and risk.get("status") == "risk" and risk.get("message"):
        warnings.append(str(risk["message"]))
    return {"status": "error" if errors else ("caution" if warnings else "ready"), "errors": errors, "warnings": warnings}


def choose_profile(gpus: list[dict[str, Any]], memory: dict[str, Any], disk: dict[str, Any]) -> dict[str, Any]:
    usable_vram = max(
        (gpu.get("vram_total_gb") or 0 for gpu in gpus if isinstance(gpu, dict) and gpu.get("vram_total_gb") is not None),
        default=0,
    )
    ram = memory.get("total_gb") or 0
    free_disk = disk.get("free_gb") or 0
    if usable_vram <= 0:
        return {"name": "no-nvidia-cuda", "confidence": "high", "reasons": ["No NVIDIA GPU was reported by nvidia-smi."]}
    blockers: list[str] = []
    if usable_vram < 5.5:
        blockers.append(f"reported VRAM is only {usable_vram:.2f} GB")
    if ram and ram < 16:
        blockers.append(f"system RAM is {ram:.2f} GB")
    if free_disk and free_disk < 12:
        blockers.append(f"free disk is {free_disk:.2f} GB")
    if blockers:
        return {"name": "blocked-or-alternative", "confidence": "medium", "reasons": blockers}
    if usable_vram < 7.5:
        reasons = [
            "6 GB-class H3 runs have been reported with aggressive system-RAM offload; treat this as experimental, not the validated W4A8 baseline.",
            "Start at 608x352 with 4 steps and expect long, hardware-dependent wall time.",
        ]
        if ram and ram < 31:
            reasons.append(f"Only {ram:.2f} GB system RAM was reported; 32 GB is the community-tested 6 GB reference point.")
        return {"name": "experimental-6gb", "confidence": "low", "reasons": reasons}
    if usable_vram < 10:
        reasons = ["Use the tested W4A8/4B/4-step profile first."]
        confidence = "high"
        if ram and ram < 24:
            confidence = "medium"
            reasons.append("16 GB system RAM is validated only with the RTX 3060 Ti 8 GB floor case; 32 GB is recommended for other 8 GB GPUs.")
        return {"name": "low-vram-w4a8", "confidence": confidence, "reasons": reasons}
    if usable_vram < 16:
        return {"name": "w4a8-mid", "confidence": "medium", "reasons": ["Keep W4A8 as the reproducible baseline; scale only after a smoke test."]}
    reasons = ["Use a validated W4A8 component set first; 16 GB VRAM alone does not prove that the native route fits system RAM or its quantized kernels."]
    if ram and ram < 48:
        reasons.append(f"System RAM is {ram:.2f} GB, so keep the native INT8/32B route opt-in until a short official-workflow smoke test passes.")
    return {"name": "w4a8-high", "confidence": "high", "reasons": reasons}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = normalize_windows_path(args.root).resolve() if args.root else Path.cwd().resolve()
    comfyui, comfyui_source = find_comfyui(args.comfyui, root)
    if comfyui is not None:
        comfyui = comfyui.resolve()
        if not args.root:
            # The disk that matters for models, cache and output is the
            # ComfyUI drive, not whichever task workspace happened to start
            # the doctor. Keep an explicit --root authoritative.
            root = comfyui

    gpus = nvidia_gpus()
    gpu_processes = nvidia_processes()
    memory = system_memory()
    disk = path_disk(root)
    pythons = [python_probe(path) for path in candidate_python_paths(comfyui)]
    report: dict[str, Any] = {
        "schema_version": 1,
        "read_only": True,
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "runtime": {"invoked_python": sys.version.split()[0], "cwd": str(Path.cwd().resolve())},
        "root": str(root),
        "comfyui": {
            "path": str(comfyui) if comfyui else None,
            "exists": bool(comfyui and comfyui.exists()),
            "main_py": bool(comfyui and (comfyui / "main.py").exists()),
            "source": comfyui_source,
            "config": str(default_config_path()),
        },
        "gpus": gpus,
        "gpu_processes": gpu_processes,
        "system_memory": memory,
        "disk": disk,
        "python_probes": pythons,
        "models": {} if args.no_model_scan else model_report(comfyui),
        "custom_nodes": {} if args.no_node_scan else node_report(comfyui),
    }
    report["recommendation"] = choose_profile(gpus, memory, disk)
    report["environment_fingerprint"] = environment_fingerprint(report, comfyui)
    report["blackwell_quantized"] = blackwell_quantized_risk(report)
    report["runtime_compatibility"] = runtime_compatibility(report)
    return report


def print_human(report: dict[str, Any]) -> None:
    recommendation = report["recommendation"]
    print(f"Recommended profile: {recommendation['name']} ({recommendation['confidence']} confidence)")
    for reason in recommendation.get("reasons", []):
        print(f"- {reason}")
    print(f"Root: {report['root']}")
    comfyui = report["comfyui"]
    print(f"ComfyUI: {comfyui.get('path') or 'not found'} (source: {comfyui.get('source', 'unknown')})")
    print(f"Config: {comfyui.get('config')}")
    risk = report.get("blackwell_quantized")
    if isinstance(risk, dict) and risk.get("status") == "risk":
        print("WARNING: " + str(risk.get("message")))
    for gpu in report["gpus"]:
        if "error" in gpu:
            print(f"GPU: {gpu['error']} ({gpu.get('detail', '')})")
        else:
            print(f"GPU: {gpu['name']} | VRAM {gpu.get('vram_total_gb')} GB total, {gpu.get('vram_free_gb')} GB free | driver {gpu.get('driver_version')}")
    memory = report["system_memory"]
    print(f"RAM: {memory.get('total_gb', 'unknown')} GB total, {memory.get('available_gb', 'unknown')} GB available | pagefile {memory.get('page_file_available_gb', 'unknown')} GB available")
    if report.get("gpu_processes"):
        print(f"GPU compute processes: {len(report['gpu_processes'])}")
    disk = report["disk"]
    print(f"Disk: {disk.get('free_gb', 'unknown')} GB free at {disk.get('path')}")
    for probe in report["python_probes"]:
        print(f"Python: {probe.get('path')} | {probe.get('python', '?')} | torch {probe.get('torch', 'not found')} | CUDA available: {probe.get('cuda_available', 'unknown')}")
    if report.get("models", {}).get("available"):
        missing = [item["role"] for item in report["models"]["assets"].values() if not item["present"]]
        print(f"Model scan: {len(report['models']['assets']) - len(missing)}/{len(report['models']['assets'])} roles found")
        if missing:
            print("Missing roles: " + "; ".join(missing))
    if report.get("custom_nodes", {}).get("available"):
        missing_nodes = [key for key, item in report["custom_nodes"]["nodes"].items() if not item["present"]]
        print(f"Custom nodes: {len(report['custom_nodes']['nodes']) - len(missing_nodes)}/{len(report['custom_nodes']['nodes'])} expected roles found")
        if missing_nodes:
            print("Missing node roles: " + "; ".join(missing_nodes))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print a machine-readable JSON report")
    parser.add_argument("--report-file", help="also save the JSON report for planner/preflight reuse")
    parser.add_argument("--root", help="project or disk root used for free-space reporting")
    parser.add_argument("--comfyui", help="explicit ComfyUI directory")
    parser.add_argument("--no-model-scan", action="store_true", help="skip recursive model filename scan")
    parser.add_argument("--no-node-scan", action="store_true", help="skip custom_nodes scan")
    parser.add_argument(
        "--write-config",
        action="store_true",
        help="persist the resolved ComfyUI path to ~/.h3lite/config.json so new tasks do not lose it",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    if args.write_config:
        resolved = report.get("comfyui", {}).get("path")
        if not resolved or not is_comfyui_root(Path(str(resolved))):
            print(
                "ERROR: cannot write config: no valid ComfyUI root (need main.py and models/). "
                "Pass --comfyui <ComfyUI> or set H3LITE_COMFYUI.",
                file=sys.stderr,
            )
            return 2
        target = save_config({"comfyui": str(resolved)})
        report["config_written"] = {"path": str(target), "comfyui": str(resolved)}
        if not args.json:
            print(f"Wrote {target}: comfyui={resolved}")
    if args.report_file:
        report_path = Path(args.report_file).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = report_path.with_name(report_path.name + ".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(report_path)
    if args.json:
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        try:
            print(payload)
        except UnicodeEncodeError:
            print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
