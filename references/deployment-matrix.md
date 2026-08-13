# MiniMax H3 deployment matrix

This reference is for a Windows workstation running ComfyUI with an NVIDIA GPU. It is a decision aid, not a promise that every GPU can run every H3 graph. Measure the installed machine first and keep the exact model, node, ComfyUI, PyTorch, and CUDA versions in the handoff record.

## Installation target and directory layout

Select the target before downloading anything. The agent must show the
absolute paths it will use:

```text
<ComfyUI>/
  main.py
  venv/                         # isolated Python environment
  custom_nodes/                 # git repositories and their dependencies
  models/
    diffusion_models/           # H3 W4A8 or native diffusion model
    text_encoders/              # Qwen3-VL 4B or native encoder
    clip_projections/            # H3 4B ClipProj
    vae/                        # video VAE and audio VAE
    loras/                      # LightX2V/Turbo LoRA
  output/                       # generated MP4 files
  user/h3lite_runs/             # prompt/workflow/config manifests per run
```

Use `<workspace>\.h3lite\ComfyUI` only when the user explicitly chooses a
current-project installation. Prefer a dedicated absolute folder such as
`D:\AI\MiniMax-H3\ComfyUI` for large model files. Do not put models in the
Skill directory, the active source repository, or an unrelated existing
ComfyUI directory. If a healthy existing ComfyUI path is selected, reuse its
own `models`, `custom_nodes`, `user`, and `output` folders together.

## Required component checklist

For the tested `low-vram-w4a8` route, guide the user through this order:

1. **Runtime:** current NVIDIA driver, Python 3.11, Git, and FFmpeg. Use the ComfyUI virtual environment for PyTorch and custom-node packages; do not mix a second Python environment into the same root.
2. **ComfyUI:** clone or update the official ComfyUI repository into `<ComfyUI>`, then record its commit. Do not install ComfyUI beside a second copy of `main.py`.
3. **Custom nodes:** clone each required repository directly under `<ComfyUI>\custom_nodes\<repository>` and install only its documented dependencies in `<ComfyUI>\venv`.
4. **Models:** download each checkpoint into the exact role folder in the tables below. Preserve the filename expected by the loader; do not rename a model to make it appear present.
5. **Verification:** rerun `h3_doctor.py`, query `/object_info` for required node classes, then launch ComfyUI from `<ComfyUI>` and verify `/system_stats`.

The low-VRAM graph is not ready until all of these roles are present: W4A8
diffusion, Qwen3-VL 4B INT4, 4B ClipProj, FP16 video VAE, FP32 audio VAE, and
the 4-step LightX2V LoRA. Native audio requires both VAE paths and the H3
flow/sigma-shift node.

## Component source addresses

Use official or pinned sources and record the selected commit/revision in the
handoff. The common repositories for the tested graph are:

| Component | Source | Install destination |
| --- | --- | --- |
| ComfyUI | https://github.com/Comfy-Org/ComfyUI | `<ComfyUI>` |
| KJNodes | https://github.com/kijai/ComfyUI-KJNodes | `<ComfyUI>\custom_nodes\ComfyUI-KJNodes` |
| ClipProj | https://github.com/NicoLab28/ComfyUI-ClipProj | `<ComfyUI>\custom_nodes\ComfyUI-ClipProj` |
| H3 Turbo | https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo | `<ComfyUI>\custom_nodes\ComfyUI-MiniMax-H3-Turbo` |
| Sage/attention | https://github.com/Saganaki22/ComfyUI-sol-attn | `<ComfyUI>\custom_nodes\ComfyUI-sol-attn` |
| T8 block cache | https://github.com/T8mars/comfyui-minimax-h3-blockcache-T8 | `<ComfyUI>\custom_nodes\comfyui-minimax-h3-blockcache-T8` |
| H3 model collection | https://huggingface.co/Comfy-Org/MiniMax-H3 | role-specific `models` folders |

Treat node repositories as versioned dependencies. If a repository changes its
install instructions or node class names, stop and adapt the graph instead of
blindly copying an old command.

## Profiles

| Profile | Typical hardware | Model and graph | Starting output | Use when |
| --- | --- | --- | --- | --- |
| `low-vram-w4a8` | 8 GB VRAM, 32 GB system RAM, SSD | H3 W4A8 diffusion model; Qwen3-VL 4B INT4 text encoder; 4B ClipProj; FP16 video VAE; FP32 audio VAE; LightX2V 4-step LoRA; low-VRAM/offload flags | 640x352 fast default; 608x352 smoke test; 864x480 only after validation | The default local laptop route. This is the validated RTX 4070 Laptop-class route in the accompanying project notes. |
| `w4a8-mid` | 10-16 GB VRAM, 32 GB+ RAM | Same W4A8 family, with fewer offload constraints; keep the same audio and flow/sigma-shift path | 864x480; 124 frames; 4-8 steps | A reproducible baseline is more important than using the largest checkpoint. |
| `native-int8` | More VRAM/RAM and a compatible current ComfyUI build | Official native H3 INT8 diffusion/text encoder/VAE set; optional Turbo LoRA and Sage Attention | Official H3 canvas, then a short Turbo comparison | The machine passes a smoke test without excessive CPU offload or custom-kernel errors. |
| `blocked-or-alternative` | Less than about 8 GB VRAM, less than 24-32 GB RAM, or insufficient SSD headroom | Do not download a large H3 model yet | N/A | Use a hosted/API backend, a smaller video model, or upgrade storage/RAM. |

The thresholds are operational heuristics. VRAM is not the only constraint: system RAM, disk speed, CUDA kernel support, and model offload behavior can dominate the elapsed time.

## Runtime preflight gate

`h3_doctor.py` records total and available RAM, available Windows pagefile,
free VRAM, GPU compute processes, model roles, and custom-node roles. Save that
report under `user/h3lite_runs/_environment/doctor.json` and reuse it for later
prompts while the installation is unchanged. Run `h3_preflight.py` after
`h3_plan.py` and before queueing; `--refresh-runtime` updates only volatile
RAM/VRAM/pagefile/process fields and avoids another recursive model scan:

```powershell
python scripts/h3_preflight.py --doctor-json <doctor.json> --plan-json <plan.json> --refresh-runtime --require-audio --json
```

Interpret the result as follows:

| Status | Meaning | Action |
| --- | --- | --- |
| `ready` | No observed runtime risk | Queue the selected plan |
| `caution` | Low available RAM/VRAM, pagefile headroom, or competing GPU process | Tell the user the risk; continue only with a conservative plan |
| `blocked` | Pagefile nearly exhausted, unsupported hardware, insufficient disk/RAM, or missing required asset/node | Stop before a long run |

Do not treat low available RAM alone as an automatic failure. The validated
8 GB route can finish with CPU offload. The preflight ignores the Python
process used by ComfyUI and zero-memory desktop helpers, and warns only for a
meaningful external GPU competitor. Treat a nearly exhausted pagefile as a
different class of failure: it has caused `hostbuf_file_reader_read failed` and
system-level paging exhaustion in real runs.

## Adaptive planning contract

Run `scripts/h3_plan.py` after the read-only doctor scan and before a long
generation. It combines the reported VRAM/RAM/disk, the requested visual
intent, the clip duration, an optional wall-clock budget, and the selected
installation target. It does not create directories or install anything.

| User intent | Low-VRAM W4A8 default | Higher-VRAM W4A8 option | Acceleration | Purpose |
| --- | --- | --- | --- | --- |
| `fast` (default) | 640x352, 4 steps | 640x352, 4 steps | T8 Block Cache on | Highest success rate and shortest expected time |
| `balanced` | 640x352, 6 steps | 864x480, 6 steps | T8 Block Cache off | Better detail within a moderate time budget |
| `quality` | 640x352, 8 steps | 864x480, 8 steps | T8 Block Cache off | Detail-first trial; still W4A8/4B, not native high precision |

The bundled template is intentionally 640x352. The older 608x352 value is a
smoke-test option, not the normal fast output. `864x480` is a post-smoke-test
option and must remain a warning-level choice on an 8 GB laptop.

`--target-minutes` means maximum wall-clock generation time, not the duration
of the resulting clip. `--video-seconds` controls the clip length. Estimates
are broad ranges: cold start, CUDA compilation, CPU offload, RAM pressure, and
disk speed can push a run beyond the upper bound. After completion, report the
actual ComfyUI execution time and use it to refine future expectations.

Supported aspect intents are `landscape`/`16:9`, `portrait`/`9:16`, and
`square`/`1:1`. Explicit `WIDTHxHEIGHT` values are accepted, rounded down to
the model's 32-pixel alignment, and carry one concise OOM warning when they
exceed the hardware recommendation. An explicit user-supplied canvas is
already a confirmation; do not ask the same resolution question again unless
preflight is `blocked`.

## Tested low-VRAM component set

Use configurable paths; the names below are the expected role and common filename, not a license to overwrite a user's files.

| Role | Expected low-VRAM asset | ComfyUI folder |
| --- | --- | --- |
| H3 diffusion | `minimax_h3_fl2va_pruned_w4a8_mixed*.safetensors` | `models/diffusion_models` |
| Text encoder | `qwen3vl_4b_int4_convrot.safetensors` | `models/text_encoders` |
| ClipProj | `mmh3-4b-ClipProj-celeb-mlp.safetensors` | The folder required by the ClipProj node, commonly `models/clip_projections`; confirm with the node version |
| Video VAE | `minimax_h3_video_vae_fp16.safetensors` | `models/vae` |
| Audio VAE | `minimax_h3_audio_vae_fp32.safetensors` | `models/vae` |
| 4-step acceleration | `minimax_h3_fl2v_lightx2v_turbo_4step*.safetensors` | `models/loras` |

The exact ClipProj folder can vary with the custom node version. Inspect its example workflow and node documentation instead of guessing.

The bundled `assets/h3_w4a8_t2v_api.json` is pinned to the validated
`minimax_h3_fl2va_pruned_w4a8_mixed_ax1y2jp.safetensors` variant. If a new
machine has only another W4A8 filename, use the custom workflow path or inspect
the local loader choices before changing the asset; do not submit a graph with
a guessed model name.

## Official native fallback

The official ComfyUI tutorial currently documents a native H3 path with these roles:

- diffusion model in `models/diffusion_models`, for example `minimax_h3_fl2va_pruned_int8_convrot.safetensors`;
- Qwen3-VL 32B NVFP4/AWQ text encoder in `models/text_encoders`;
- FP16 video VAE and FP32 audio VAE in `models/vae`.

The official workflow uses native stereo audio and a 768-pixel short edge. Treat the official workflow as the source of truth for node names, model revisions, and canvas constraints. The W4A8/4B route is a practical low-VRAM adaptation and should not be described as the same memory envelope as the native 32B workflow.

## Node roles

The low-VRAM route commonly needs these repositories or equivalents:

- `ComfyUI-KJNodes`: utility, attention, and workflow support nodes;
- `ComfyUI-ClipProj`: H3 4B ClipProj loading/conditioning;
- `ComfyUI-MiniMax-H3-Turbo`: Turbo LoRA and sampler support;
- `ComfyUI-sol-attn`: optional attention acceleration;
- `comfyui-minimax-h3-blockcache-T8`: optional block-cache acceleration.

Start with the official graph plus the minimum required nodes. Add attention and cache patches one at a time. If output becomes black, blocky, or unstable, restore the official H3 flow/sigma-shift path and remove optional patches before changing the prompt.

## Launch profile

A typical low-VRAM Windows launch uses a dedicated virtual environment and an explicit ComfyUI directory, for example:

```text
python main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch --disable-api-nodes --lowvram --fast-disk
```

Add `--use-sage-attention` only when Sage Attention and the installed PyTorch/CUDA build are compatible. Do not copy a launch line from another GPU without checking the local build. Keep the API bound to localhost unless the user explicitly needs network access and understands the security implications.

## Preflight and disk budget

Before downloading, estimate the selected asset set and leave room for temporary files, model caches, ComfyUI outputs, and a second copy during upgrades:

- low-VRAM W4A8 set: roughly 22-30 GB for the named assets and working headroom; prefer at least 40-50 GB free on the target SSD;
- native INT8/32B set: roughly 42-50 GB for the named assets and working headroom; prefer at least 65-80 GB free.

The doctor script reports actual files and free space. Never report an install as ready merely because one large diffusion file exists.

## Fast-generation baseline

Keep the first comparison fixed:

- 124 frames at 24 fps (about 5 seconds);
- 4 sampling steps with a Turbo-compatible sampler;
- `res_multistep` flow/sigma handling and `simple` scheduler when required by the selected workflow;
- 640x352 for the current fast template; use 608x352 only as a smoke test and 864x480 after the planner approves it;
- native audio path enabled.

The first run can be slower because kernels compile and weights are moved between RAM and VRAM. Report warm-up and steady-state timings separately. Four-step output is a speed baseline, not a universal quality setting. Balanced and quality modes bypass the optional T8 Block Cache before increasing steps.

After a verified success, save a compact empirical timing sample in
`user/h3lite_runs/_environment/timing.json`. The planner automatically uses a
matching profile/resolution/frame/FPS/step sample on later requests; its
`estimate.source` becomes `empirical` instead of the broad heuristic range.

Every queued run should create a manifest under `user/h3lite_runs/<run-id>/`:

- `prompt.txt`: exact UTF-8 prompt sent to the graph;
- `workflow.api.json`: effective in-memory API graph, including model names and patches;
- `manifest.json`: profile, resolution, frames, steps, FPS, audio policy, seed, configuration fingerprint, prompt ID, timing, and output verification.

The submission helper uses the fingerprint to skip an identical configuration
while it is still `submitting`, `queued`, or `running`. A second identical run
requires an explicit `--allow-duplicate`.

For a requested action, status verification should use
`--require-audio --dynamic-check --compact`. The result must confirm an MP4,
video stream, expected duration/frame count/FPS, the requested audio policy,
and a first/middle/last frame classification of `dynamic`. Pending status is
`ok:false, complete:false`; only a completed verified media response is
`ok:true`. The automated check catches black/flat output; inspect suspicious
block/mosaic frames visually. Use `--verbose` only for failure diagnosis and
use `--watch` only with a bounded timeout.

## Triage order

1. Check pagefile/RAM headroom and competing GPU processes.
2. Check the ComfyUI version and unresolved node classes.
3. Check model folder, exact filename, and loader type.
4. Check CUDA, PyTorch, custom attention, and kernel compatibility.
5. Check VRAM/RAM pressure and CPU offload time.
6. Check the H3 audio VAE, flow/sigma-shift, and Turbo sampler path.
7. Check prompt mode, reference alignment, frame count, dynamic QA, and output muxing.

## Sources

- Official ComfyUI H3 tutorial: https://docs.comfy.org/tutorials/video/minimax/minimax-h3
- MiniMax H3 repository: https://github.com/MiniMax-AI/MiniMax-H3
- H3 Turbo custom nodes: https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo
