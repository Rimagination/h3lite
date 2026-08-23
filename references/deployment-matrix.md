# MiniMax H3 deployment matrix

This reference is for a Windows workstation running ComfyUI with an NVIDIA GPU. It is a decision aid, not a promise that every GPU can run every H3 graph. Measure the installed machine first and keep the exact model, node, ComfyUI, PyTorch, and CUDA versions in the handoff record.

## Backend and architecture compatibility

- The validated low-VRAM route is **Windows + NVIDIA CUDA**. VRAM capacity and backend compatibility are separate gates.
- AMD GPUs such as the RX 7900 XT may have enough VRAM in theory, but the current H3 Lite component sets and acceleration nodes are not an AMD/ROCm-validated route. Report this as experimental or offer another backend; do not promise local success from the VRAM number alone.
- RTX 50-series cards need a current Torch/CUDA build containing the matching Blackwell architecture (for example `sm_120`) before optional acceleration nodes are enabled. The doctor performs this check without loading the video model.
- These checks run during doctor/preflight only. They must not add nodes, sampling steps, model passes, or generation-time work to an otherwise valid graph.

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

1. **Runtime:** current NVIDIA driver, Python 3.11, Git, and FFmpeg. Use the ComfyUI virtual/embedded environment for PyTorch and custom-node packages; do not infer compatibility from an unrelated system Python. Record the actual ComfyUI interpreter, PyTorch version, `torch.version.cuda`, `comfy_kitchen` module path/version, driver, and native extension ABI together.
2. **ComfyUI:** clone or update the official ComfyUI repository into `<ComfyUI>`, then record its commit. Do not install ComfyUI beside a second copy of `main.py`.
3. **Custom nodes:** clone each required repository directly under `<ComfyUI>\custom_nodes\<repository>` and install only its documented dependencies in `<ComfyUI>\venv`.
4. **Models:** download each checkpoint into the exact role folder in the tables below. Preserve the filename expected by the loader; do not rename a model to make it appear present. If an upstream filename is unavailable, do not guess: use `h3_generate.py --resolve-models` only when the local role match is unique, and record the replacement in the run manifest.
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
| `experimental-6gb` | About 6 GB VRAM, preferably 32 GB system RAM, SSD and healthy pagefile | Begin with the official H3-compatible INT8/NVFP4 route when its exact files are available, or another explicitly validated 6 GB graph; use aggressive offload | 608x352, about 4-5 seconds, 4 steps | Community reports show successful 3060 6 GB laptop runs, but this is not the bundled W4A8 graph's validated floor. Expect high variance and long CPU/RAM offload. |
| `low-vram-w4a8` | 8 GB VRAM; **16 GB system RAM is validated on RTX 3060 Ti**, 32 GB recommended; SSD | One registered W4A8 + Qwen3-VL 4B + Turbo LoRA component set; 4B ClipProj; dual VAEs; `--lowvram`/offload flags | 640x352 fast default; 608x352 smoke test; 864x480 only after validation | Use `component-sets.md`; do not mix files across sets. The 16 GB floor is hardware-specific evidence, not a blanket claim for every 8 GB GPU. |
| `w4a8-mid` | 10-<16 GB VRAM, 32 GB+ RAM | Same W4A8 family, normally without `--lowvram`; keep the same audio and flow/sigma-shift path | 864x480; 124 frames; 4-8 steps | A reproducible baseline is more important than using the largest checkpoint. |
| `w4a8-high` | 16 GB+ VRAM with 32 GB-class system RAM | Keep a registered W4A8 set as the first reproducible route; normal VRAM launch by default | 864x480 after the fast baseline | VRAM alone does not prove that the native 32B route fits system RAM or its kernels. |
| `native-int8` | More VRAM/RAM and a compatible current ComfyUI build | Official native H3 INT8 diffusion/text encoder/VAE set; optional Turbo LoRA and Sage Attention | Official H3 canvas, then a short comparison | Opt in only after the official workflow and runtime kernel set pass a smoke test. |
| `blocked-or-alternative` | Less than about 6 GB VRAM, a 6 GB GPU with clearly insufficient system RAM/pagefile, less than 16 GB RAM generally, or insufficient SSD headroom | Do not download a large H3 model yet | N/A | Use a hosted/API backend, a smaller video model, or upgrade storage/RAM. |

The thresholds are operational heuristics. VRAM is not the only constraint: system RAM, disk speed, CUDA kernel support, and model offload behavior can dominate the elapsed time.

The project's current lower-bound evidence is an RTX 3060 Ti with 8 GB VRAM
and 16 GB system RAM completing the W4A8 route. No timing sample is attached to
that validation, so the planner must keep it on the 640x352/4-step fast baseline
and report a caution. Do not generalize this result to an arbitrary 8 GB GPU.

### Controlled Set B timing evidence

The same Set B models, compatibility workflow, prompt, seed, 640x352 canvas,
124 frames, and four steps were run on two validated machines:

| Hardware | Memory mode | ComfyUI execution time | Result |
| --- | --- | ---: | --- |
| RTX 4060 Ti 16 GB desktop, i5-13400F, 32 GB RAM | `NORMAL_VRAM` | 77.08 s | coherent video and native audio |
| RTX 4070 Laptop 8 GB, Ryzen 7 8845H, 32 GB RAM | `LOW_VRAM` with dynamic loading/offload | 591.22 s | coherent video and native audio |

The same RTX 4070 Laptop machine also completed the bundled experimental
multi-image Ref2VA graph with two references at `640x352`, 124 frames, and four
steps in **472.11 s**. The output had native audio and passed technical media
checks; identity and wardrobe continuity still require manual review. This is
an observed local run, not a guarantee for every 8 GB GPU or reference count.

The 7.7x observed gap is primarily consistent with model residency versus
dynamic loading/offload. Do not attribute it to output caching or optional
acceleration nodes: both runs performed real sampling with the compatibility
graph. This remains a cross-machine comparison, not a pure GPU-compute
benchmark, because desktop/laptop power limits and attention runtimes differ.
Use it to choose the memory profile and estimate time, not to rank GPUs.

### Community low-VRAM timing evidence

Keep these observations as planning anchors, not guarantees. They came from different posters, model quantizations, workflows, software versions, and thermal/power conditions:

| Hardware/workflow | Canvas and duration | Reported time | Interpretation |
| --- | --- | --- | --- |
| RTX 3060 Laptop 6 GB + 32 GB RAM, I2V | 608x352, 4 seconds | 345 s; 303 s after an acceleration node | Confirms feasibility; the reported acceleration gain is modest and workflow-specific. |
| RTX 3060 Laptop 6 GB + 32 GB RAM, I2V | 864x480, 5 seconds | 441 s | A useful upper-canvas data point, not a safe first-run default. |
| RTX 3060 6 GB-class laptop, T2V/default-style run | 640x480, 5 seconds | about 13.7 min | Demonstrates that nominally similar hardware can be much slower. |
| RTX 3060 Laptop 6 GB + 32 GB RAM, Ref2VA with three images | 864x480, 5 seconds | about 18 min | Reference generation is materially heavier than I2V/T2V; do not estimate it from the text-only fast route. |
| RTX 4080 Super 16 GB + 128 GB RAM, single-reference accelerated workflow | 0.4 resolution scale, 6 seconds | about 110 s | Scale labels are workflow-relative and cannot be converted to exact pixels without the source graph. |
| Same 4080 Super system | 1.5 resolution scale, 6 seconds | about 10 min accelerated versus 19 min before | Pixel workload and offload/cache behavior can dominate GPU class. |
| RTX 5060 Ti 16 GB + 32 GB RAM | 0.7 resolution scale, 7 seconds | about 9 min | Another reminder that workflow-relative scales are not portable canvas specifications. |

When exact local timing exists in `timing.json`, prefer it over this table. Separate T2V, I2V, FL2VA, and Ref2VA estimates; reference count and resolution must be part of any future timing key before automating those modes.

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

## Hot-path vs cold-path cost policy

Do not make every prompt pay installation costs.

| Path | Trigger | Allowed checks | Forbidden during this path |
| --- | --- | --- | --- |
| Hot generation | Existing validated ComfyUI, unchanged models/nodes, normal prompt | cached doctor/component report, `/system_stats`, refreshed RAM/VRAM/pagefile/process fields, one compact status watch, media verification | Git remote checks, browser workflow discovery, full recursive model scans, hash verification of large files, package upgrades, large downloads |
| Cold installation/repair | New computer, new target folder, missing file/node, failed import, changed model set, previous run failed with loader/model/runtime error | download source validation, resumable transfer, size/hash check, model-role mapping, runtime import probes, small recorded compatibility patches, smoke test when requested or needed | silent model substitution, unbounded parallel downloads, starting a long generation with unresolved assets |

The hot path should usually enter queue submission after prompt rewrite and a
small runtime preflight. The cold path may spend extra time because it prevents
hour-scale failures, but it must write its findings under
`user/h3lite_runs/_environment/` so the next generation can reuse them.

## Adaptive planning contract

Run `scripts/h3_plan.py` after the read-only doctor scan and before a long
generation. It combines the reported VRAM/RAM/disk, the requested visual
intent, the clip duration, an optional wall-clock budget, and the selected
installation target. It does not create directories or install anything.

| User intent | Low-VRAM W4A8 default | Higher-VRAM W4A8 option | Acceleration | Purpose |
| --- | --- | --- | --- | --- |
| `fast` (default) | 640x352, 4 steps | 640x352, 4 steps | T8 Block Cache on | Highest success rate and shortest expected time |
| `balanced` | 640x352, 6 steps | 16:9 0.4MP bucket = 864x480, 6 steps | T8 Block Cache off | Better detail within a moderate time budget |
| `quality` | 640x352, 8 steps | 16:9 0.5MP bucket = 960x544, 8 steps | T8 Block Cache off | Detail-first trial; still W4A8/4B, not native high precision |

The bundled template is intentionally 640x352. The older 608x352 value is a
smoke-test option, not the normal fast output. ComfyUI's native H3 template
uses `ResolutionSelector` rather than a hardcoded canvas: aspect ratio + target
megapixels + a 32-pixel multiple. Its common `16:9`, `0.4 MP`, `multiple=32`
choice resolves to `864x480`. Treat that as the official-style normal canvas,
not as the low-VRAM fast default.

The fast/accelerated row is for the registered LightX2V/Turbo 4-step LoRA.
`minimax_h3_turbo_v4_step600_ema.safetensors` is compatibility-only in H3 Lite:
the v4-plus-Sage/Sol/Chunk/T8 combination produced severe ghosting, motion trails,
and color artifacts in local validation. Use the compatibility graph for v4, or
use the LightX2V/Turbo 4-step LoRA for a fast render. The generator rejects the
disallowed pairing before it can be queued.

Common 16:9 buckets with ComfyUI's 32-pixel alignment:

| Target megapixels | Aligned canvas |
| --- | --- |
| 0.20 MP | 608x352 |
| 0.25 MP | 672x384 |
| 0.30 MP | 736x416 |
| 0.40 MP | 864x480 |
| 0.50 MP | 960x544 |
| 0.75 MP | 1184x672 |
| 1.00 MP | 1376x768 |

Treat 736x416 as an experimental action-adherence bucket, not a new default.
In Hugging Face community reports, complex Ref2VA/keyframe prompts sometimes
follow composition and action order better at 352p-416p than at 768p. Validate
this with the same prompt, seed, model, LoRA, steps, and acceleration graph;
resolution must be the only changed variable. Raising steps can improve visual
coherence without restoring omitted actions.

Local same-seed T2VA testing on the H3 Lite W4A8 graph found mixed adherence:
736x416 completed the key-in-cup and lid-closing interaction more clearly than
640x352, while 640x352 showed the final wave more clearly. Runtime was within
normal variance (328 s versus 340 s). Keep 736x416 available for object-heavy
ordered actions, but do not promote it over 640x352 globally.

The LightX2V v1.0 768p 4-step ComfyUI LoRA with video shift 6 was also tested
at 736x416, strength 1.0, with Block Cache disabled. It produced sharper,
stable frames but introduced an extra blue container and did not improve the
full action sequence; runtime increased to 536 s. Retain it as an experimental
detail-oriented option. Keep the validated v0.1 LoRA as the default fast route.

The official workflow-template note describes H3's native canvas as a
768-pixel short edge capped at `768x1344`, rounded to a multiple of 32. For an
exact native 16:9 canvas, use about `0.98 MP`, which resolves to `1344x768`.
This belongs to the official/native or high-VRAM path after the 0.4MP preview
succeeds, not to the low-VRAM fast default.

Keep the user's explicit pixel size in the ComfyUI graph parameters. In the H3
prompt, describe framing and composition instead: landscape composition,
medium-wide shot, close-up, macro detail, slow push-in, locked-off camera, and
similar visual language.

`--target-minutes` means maximum wall-clock generation time, not the duration
of the resulting clip. `--video-seconds` controls the clip length. Estimates
are broad ranges: cold start, CUDA compilation, CPU offload, RAM pressure, and
disk speed can push a run beyond the upper bound. After completion, report the
actual ComfyUI execution time and use it to refine future expectations.

Supported aspect intents are `landscape`/`16:9`, `portrait`/`9:16`, and
`square`/`1:1`. `--megapixels` selects a ComfyUI ResolutionSelector-style
canvas for that aspect. Explicit `WIDTHxHEIGHT` values are accepted, rounded
down to the model's 32-pixel alignment, and carry one concise OOM warning when
they exceed the hardware recommendation. An explicit user-supplied canvas is
already a confirmation; do not ask the same resolution question again unless
preflight is `blocked`.

## Registered component sets

Read `component-sets.md` for the authoritative combinations and exact known byte
sizes. A role-level filename match is useful for diagnosis but does not prove
that independently sourced files are graph-compatible.

## Tested low-VRAM roles

Use configurable paths; the names below are the expected role and common filename, not a license to overwrite a user's files.

| Role | Expected low-VRAM asset | ComfyUI folder |
| --- | --- | --- |
| H3 diffusion | `minimax_h3_fl2va_pruned_w4a8_mixed*.safetensors` | `models/diffusion_models` |
| Text encoder | Registered Qwen3-VL 4B INT4 or FP8 file from the selected component set | `models/text_encoders` |
| ClipProj | `mmh3-4b-ClipProj-celeb-mlp.safetensors` | The folder required by the ClipProj node, commonly `models/clip_projections`; confirm with the node version |
| Video VAE | `minimax_h3_video_vae_fp16.safetensors` | `models/vae` |
| Audio VAE | `minimax_h3_audio_vae_fp32.safetensors` | `models/vae` |
| 4-step acceleration | Registered LightX2V/Turbo LoRA from the selected component set | `models/loras` |

The exact ClipProj folder can vary with the custom node version. Inspect its example workflow and node documentation instead of guessing.

The bundled multi-image Ref2VA graphs reuse every role in this table; they do
not introduce a separate Ref2VA checkpoint. The additional requirements are the
native `MiniMaxH3ReferenceToVideo` node and a ClipProj `resident` image path,
which changes VRAM residency rather than the disk component set.

The bundled `assets/h3_w4a8_t2v_api.json` and `assets/h3_w4a8_i2v_api.json` are
pinned to the validated
`minimax_h3_fl2va_pruned_w4a8_mixed_ax1y2jp.safetensors` variant and the
validated `lightx2v_v0.1`-style filename. These are reproducibility anchors,
not download promises. The I2V graph adds only a native `LoadImage` input and
uses the same diffusion, encoder, VAE, and Turbo component set. If a new
machine has only another W4A8, ClipProj, or
LightX2V filename, inspect the local loader choices and use the explicit
resolver; never silently edit the public template or submit unresolved model
names.

Do not approve a replacement W4A8 diffusion checkpoint merely because ComfyUI
loads it and writes an MP4. A failed compatibility trial with the ModelScope
`AI-ModelScope/MiniMax-H3-w4a8` raw file
`minimax_h3_fl2va_pruned_w4a8_mixed.safetensors` produced valid MP4/AAC output
but only blocky color-noise frames in the H3 Lite graph, both with the
validated `lightx2v_v0.1` LoRA and with the newer v4 turbo LoRA. Under the same
512x288, 56-frame, native-audio smoke prompt, the pinned `_ax1y2jp` W4A8 file
produced a coherent red-ball scene. On 2026-08-13, the ModelScope repository
file API listed only the no-suffix FL2VA file and the Ref2VA file; the
validated `_ax1y2jp` filename was not available there. Treat ModelScope as a
useful download source, not as automatic proof of graph compatibility. A
replacement passes only when it clears media verification and visual/dynamic QA
against a pinned control run.

## Torch and comfy-kitchen compatibility

Run the doctor before downloading large assets. It probes Torch and
`comfy-kitchen` imports in the ComfyUI Python environment and stores the result
in `runtime_compatibility`. A failed import is a preflight blocker or warning,
not something to discover after a 20 GB download. Keep ComfyUI, Torch,
frontend package, and comfy-kitchen versions from one known-good installation;
do not upgrade comfy-kitchen independently when its annotations require a
newer Torch than the installed ComfyUI supports.

Prefer a minimal, recorded compatibility patch over a large Torch reinstall
when the failure is only a Python typing annotation mismatch, such as
`list[int]` vs `List[int]`. The patch must be exact, idempotent, and recorded in
the environment report. Do not apply broad source rewrites and do not upgrade
or downgrade Torch during a normal generation.

## Download policy

Use direct resumable downloads for mirrors whose Hugging Face API compatibility
is incomplete; `hf_hub_download` may fail against such mirrors even when raw
file URLs work. Download to a temporary `.part` file, then validate size or
hash before renaming into the model folder. Store URL, destination, expected
size/hash when available, actual size, and completion time in the component
manifest.

ModelScope can be a faster domestic source when it hosts the required filename,
but classify the result by behavior, not by repository title. Record the
ModelScope repository, raw URL, linked etag or hash when exposed, exact
filename, and file size. If the hash does not match a pinned checkpoint, run a
small compatibility smoke test plus a pinned-control comparison before using it
as a default route.

When public internet is the only source, run a small source probe before
starting a multi-GB checkpoint:

1. Build candidate raw URLs for the official Hugging Face file, configured
   mirror raw file, and any user-provided proxy endpoint.
2. Test each candidate with a short ranged request or a small resumed partial
   transfer, then estimate the full-file time from measured throughput.
3. If all candidates are below roughly 2 MB/s for a 10 GB+ file, state that the
   bottleneck is the network route and ask for a proxy, alternate mirror, or
   permission to keep a long resumable download running.
4. Use `aria2c -c` with conservative per-file connections only when the source
   supports ranges and the probe improves speed. Otherwise use
   `curl.exe -L -C -` for maximum compatibility.
5. Never delete a `.part` file just to switch tools. Resume from the existing
   partial file when possible; restart from byte zero only after size/hash
   validation proves the partial file is unrecoverable.

Default to one or two downloads; use three-way parallelism only after
confirming the mirror, disk, and network can sustain it. Do not launch many
model downloads in parallel on a slow line; it often lowers reliability more
than it improves total time. Never repeat this download validation during hot
generation unless the recorded file metadata no longer matches the local file
or a run failed with a relevant loader/model error.

Use these rough estimates when explaining expectations for a 12.5 GB W4A8
diffusion checkpoint:

| Measured speed | Approximate download time |
| --- | --- |
| 1.5 MB/s | about 2 hours 20 minutes |
| 4 MB/s | about 55 minutes |
| 10 MB/s | about 21 minutes |
| 30 MB/s | about 7 minutes |

## Official native fallback

The official ComfyUI tutorial currently documents a native H3 path with these roles:

- diffusion model in `models/diffusion_models`, for example `minimax_h3_fl2va_pruned_int8_convrot.safetensors`;
- Qwen3-VL 32B NVFP4/AWQ text encoder in `models/text_encoders`;
- FP16 video VAE and FP32 audio VAE in `models/vae`.

The official workflow uses native stereo audio, `MiniMaxH3ImageToVideo` /
`MiniMaxH3ReferenceToVideo` nodes with 32-pixel width/height steps, and frame
counts at 24 fps that snap to H3's `17k+5` grid (`124` frames is about 5
seconds). Treat the official workflow as the source of truth for node names,
model revisions, and canvas constraints. The W4A8/4B route is a practical
low-VRAM adaptation and should not be described as the same memory envelope as
the native 32B workflow.

## Node roles

The low-VRAM route commonly needs these repositories or equivalents:

- `ComfyUI-KJNodes`: utility, attention, and workflow support nodes;
- `ComfyUI-ClipProj`: H3 4B ClipProj loading/conditioning;
- `ComfyUI-MiniMax-H3-Turbo`: Turbo LoRA and sampler support;
- `ComfyUI-sol-attn`: optional attention acceleration;
- `comfyui-minimax-h3-blockcache-T8`: optional block-cache acceleration.

The accelerated bundled graph also requires the loaded classes
`MiniMaxH3MemoryEfficientSageAttentionPatch`,
`MiniMaxH3MemoryEfficientSolAttentionPatch`,
`MiniMaxH3ChunkFeedForward`, and `MiniMaxH3BlockCacheT8`. A custom-node folder
being present is not proof that its import succeeded; fastpath checks
`/object_info` when available and otherwise falls back conservatively.

Start with the official graph plus the minimum required nodes. Add attention and cache patches one at a time. If output becomes black, blocky, or unstable, restore the official H3 flow/sigma-shift path and remove optional patches before changing the prompt.

ComfyUI merged its native MiniMax H3 audio scheduling fix on 2026-08-06. The
API class remains `MiniMaxH3SigmaShift`, while `/object_info` displays
`ModelSamplingMiniMaxH3`; internally current builds use `ModelSamplingAV` with
separate video/audio shifts. Check for that implementation before installing a
third-party dual-clock sampler. The current H3 Lite machine already contains
this fix, so its existing shift node is the native path rather than a legacy
custom workaround.

Prefer acceleration in this order: first the correct 4-step/Turbo graph, then a compatible H3-optimized Sage Attention implementation, then a specifically validated H3 block cache. Do not install KJ Nodes merely because a tutorial names it; install it only when the chosen workflow contains a required KJ node. Keep Easy Cache and generic cache nodes disabled by default because community reports describe blurred or damaged output. A reported change such as 345 seconds to 303 seconds is useful evidence of possible benefit, not enough reason to alter every user's baseline.

### OOM recovery

After a CUDA OOM or host-buffer/pagefile failure, do not immediately queue a
second long job into the same process. Mark the environment cache stale, stop
the affected ComfyUI process through its normal launcher/terminal, restart it
with the recorded launch profile, and wait until `/system_stats` responds.
Refresh runtime RAM/VRAM/pagefile values before retrying with a smaller canvas,
shorter duration, compatibility workflow, or fewer optional patches. Never
assume that a still-visible process is healthy after an OOM.

## Launch profile

A typical low-VRAM Windows launch uses a dedicated virtual environment and an explicit ComfyUI directory, for example:

```powershell
New-Item -ItemType Directory -Force -Path .\user\h3lite_logs | Out-Null
python main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch --disable-api-nodes --lowvram --fast-disk *> .\user\h3lite_logs\comfyui.log
```

Add `--use-sage-attention` only when Sage Attention and the installed PyTorch/CUDA build are compatible. Do not copy a launch line from another GPU without checking the local build. Keep the API bound to localhost unless the user explicitly needs network access and understands the security implications.

When an agent starts ComfyUI in the background on Windows, give both native
streams persistent file handles rather than leaving them attached to a
temporary task pipe. Use separate files with `Start-Process`:

```powershell
$comfyui = '<ComfyUI>'
$logRoot = Join-Path $comfyui 'user\h3lite_logs'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
Start-Process -FilePath '<python.exe>' `
  -ArgumentList 'main.py','--listen','127.0.0.1','--port','8188','--disable-auto-launch','--disable-api-nodes','--lowvram','--fast-disk' `
  -WorkingDirectory $comfyui `
  -RedirectStandardOutput (Join-Path $logRoot 'comfyui.stdout.log') `
  -RedirectStandardError (Join-Path $logRoot 'comfyui.stderr.log') `
  -WindowStyle Hidden
```

If a long-lived process later fails inside `tqdm/std.py` or `app/logger.py`
with `OSError: [Errno 22] Invalid argument`, treat an invalid detached output
handle as the leading diagnosis. Restart with persistent redirection and retry
the same job. This failure does not by itself justify model downloads,
dependency repair, or a full environment rescan. Keep logs outside timestamped
run directories and rotate or archive them during maintenance so they do not
grow without bound.

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
- 640x352 for the current fast template; use 608x352 only as a smoke test and the official-style 0.4MP bucket (`864x480` for 16:9) after the planner approves it;
- native audio path enabled.

The first run can be slower because kernels compile and weights are moved between RAM and VRAM. Report warm-up and steady-state timings separately. Four-step output is a speed baseline, not a universal quality setting. Balanced and quality modes bypass the optional T8 Block Cache before increasing steps.

A faster warm run does not mean ComfyUI returned a cached finished video.
Weights may remain resident and unchanged loader/encoder/VAE nodes may report
cache hits; changing the prompt or seed still reruns sampling and creates a new
result. Describe cold and warm timings separately and do not compare them as if
they were the same condition.

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
`ok:true`. The automated check catches black/flat output and samples RGB color
statistics for abrupt saturated block patterns. A `suspected_mosaic` result is
a failed verification, not a successful render; inspect its sampled frames and
validate the selected component set before retrying. Use `--verbose` only for
failure diagnosis and use `--watch` only with a bounded timeout.

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
