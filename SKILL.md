---
name: h3lite
description: Use when configuring, repairing, planning, or running MiniMax H3 locally on Windows with an NVIDIA laptop, especially when resolution, generation-time budget, installation path, low-VRAM risk, or H3 prompt mode must be chosen from hardware and user requirements.
---

# MiniMax H3 Local Video

Use this skill to turn a user's local NVIDIA computer into a reproducible MiniMax H3 audio-video workstation and to generate short clips through ComfyUI. Treat path selection, hardware-aware planning, prompt writing, execution, timing, and verification as one workflow. The default is the validated fast route; other modes must be chosen explicitly or justified by a time budget.

## Operating rules

- Inspect before changing anything. Run `scripts/h3_doctor.py --json` and locate the target ComfyUI directory before installing packages, nodes, or weights.
- Prefer an isolated ComfyUI directory when no installation is supplied. Never overwrite an existing installation or silently replace model files.
- Keep the deployment path configurable. Do not copy paths from another computer into scripts or workflows.
- Report required disk space before large downloads. Use resumable downloads and verify file size or hash when a source provides one.
- Do not redistribute model weights by default. Respect each model and node repository's license; let the user download weights from the selected source.
- Prefer the ComfyUI HTTP API with an API-format workflow JSON. Use browser/CDP capture only as a recovery path when no reusable workflow JSON exists.
- Check `http://127.0.0.1:8188/system_stats` before starting anything. If ComfyUI is already healthy, reuse it and do not restart it or rediscover its workflow history.
- Preserve MiniMax H3's audio path and flow/sigma-shift handling when the user wants native audio. Do not remove audio VAE, audio conditioning, or the H3 sampling node merely to make a graph look simpler.
- Run the read-only planner before a non-trivial generation. It must report selected mode, resolution, steps, cache policy, paths, and an estimated time range. Do not present an estimate as a guarantee.
- Run the read-only preflight after the doctor and planner. Treat low available RAM/VRAM as a caution, but stop when the pagefile is critically low, required assets are missing, or the doctor recommends an alternative backend.
- Do not perform a full recursive doctor scan for every prompt. Cache the environment report under `<ComfyUI>/user/h3lite_runs/_environment/`; reuse it for a normal session (normally no older than 30 minutes), invalidate it after ComfyUI/model/node/driver changes or a failed run, and use `h3_preflight.py --refresh-runtime` for volatile resource fields.
- Treat every submission as an auditable run: save the effective prompt, mutated API workflow, configuration fingerprint, queue ID, actual execution time, and verified output in the run manifest.
- Keep agent-facing status compact: omit ComfyUI's full history graph by default; use verbose history only when diagnosing a failure.
- Never submit an identical configuration while its manifest is `submitting`, `queued`, or `running`. Return the existing prompt ID instead; use `--allow-duplicate` only when the user explicitly asks for a second identical run.
- Treat low-VRAM timing as an empirical estimate. The first run can be much slower because kernels compile and weights move between system RAM and VRAM.

## Installation target contract

Before installing, downloading, or moving any component, establish one explicit
deployment target and state it to the user:

```text
Install mode: reuse-existing | current-project | dedicated-folder
ComfyUI: <absolute path>
Models: <ComfyUI>\models
Custom nodes: <ComfyUI>\custom_nodes
Output: <ComfyUI>\output
```

Use these rules:

- `reuse-existing`: use the exact existing ComfyUI path supplied by the user or discovered and confirmed by the user. Do not clone, reinstall, or create a second model directory.
- `current-project`: keep everything under the active workspace in `<workspace>\.h3lite\ComfyUI` so the project-scoped choice is unambiguous and does not scatter models across the repository.
- `dedicated-folder`: use the user's absolute path, preferably a non-repository path such as `D:\AI\MiniMax-H3\ComfyUI` or `F:\MiniMax-H3\ComfyUI`. Put the venv, custom nodes, models, user data, and output under this ComfyUI root.
- If no existing installation and no target path are available, recommend `dedicated-folder` and ask the user to confirm the absolute path before downloading large files. Never silently choose a drive or install into the current project root.
- If the user says “当前项目” without naming the workspace, resolve and display the active workspace path before proceeding. If the user gives a path ending in `ComfyUI`, use it directly; if they give a parent install folder, append `ComfyUI` and display the resulting path for confirmation.

After the target is selected, read `references/deployment-matrix.md` and present
the component checklist, exact destination folders, estimated disk budget, and
the launch command. Install or repair in this order: runtime prerequisites,
ComfyUI, required custom nodes, model files, doctor verification, then launch.
Do not start a generation while any required node class or model asset is
missing.

## Adaptive planning contract

Before generation, separate the user's requirements into four independent
choices:

- **Intent:** `fast` (default), `balanced`, or `quality`.
- **Wall-clock budget:** maximum expected generation time, such as “within 10
  minutes”; this is different from the requested clip duration.
- **Canvas:** `auto`, landscape/`16:9`, portrait/`9:16`, square/`1:1`, or an
  explicit `WIDTHxHEIGHT`.
- **Target path:** `reuse-existing`, `current-project`, or `dedicated-folder`.

Run the planner after the doctor scan. It is read-only and does not create
folders:

```powershell
python scripts/h3_plan.py `
  --root <hardware-or-disk-root> `
  --comfyui <ComfyUI-path> `
  --install-mode reuse-existing `
  --mode auto `
  --target-minutes 10 `
  --aspect landscape `
  --video-seconds 5 `
  --json
```

Use the planner result as the source of truth for `--profile`, `--resolution`,
`--steps`, `--length`, and `--fps`. If no quality or time requirement is
given, `auto` selects `fast` and preserves the validated 640x352, 4-step,
Block-Cache route. On an 8 GB laptop, `balanced` keeps 640x352 and increases
steps while bypassing T8 Block Cache; `quality` does the same with 8 steps.
Only the mid/high-VRAM plan promotes balanced/quality to 864x480 by default.

When the user supplies an explicit resolution, treat that canvas choice as
already confirmed: issue one concise OOM/time warning, then continue unless
preflight is `blocked`. Do not ask the same resolution question again. If a
separate wall-clock budget conflicts with the explicit canvas, state the
conflict once and keep the user's explicit canvas. Never silently trade away
the audio path or change the installation target to make the estimate fit.

## Fast path for ordinary text-to-video

Use this path for a text-only H3 request on a machine that passes the low-VRAM
doctor check. It is the default route for a short clip:

Hot-path contract: after the environment has been validated, prompt-to-queue is
`/system_stats` -> cached plan -> lightweight runtime refresh -> template
submission. Do not rerun the recursive model/node doctor, inspect old history,
or ask nonessential setup questions for every prompt. Full diagnosis is only a
cold-start, install/update, or failure-recovery action.

1. Reuse a healthy local ComfyUI server; start it only when `/system_stats` is unavailable.
2. Reuse the cached environment report when it is fresh and the installation has not changed. On a first run, after an install/update, or after a failure, run the full doctor and save `<ComfyUI>/user/h3lite_runs/_environment/doctor.json`; generate a plan JSON from that report, then run the lightweight preflight with `--refresh-runtime`. The planner automatically reuses `<ComfyUI>/user/h3lite_runs/_environment/timing.json` when present. If preflight is `blocked`, stop before queueing; if it is `caution`, report the exact resource risk and continue only when the selected plan remains reasonable. An explicit user-supplied resolution does not require a second confirmation.
3. If the W4A8/4B assets and required nodes are present and the plan is `fast`, use `assets/h3_w4a8_t2v_api.json` directly. Do not inspect `/history`, search old output folders, or capture a UI workflow first.
4. Write the official T2VA prompt to a run-local UTF-8 file and submit with `h3_generate.py --workflow-template h3_w4a8_t2v --queue-only --run-root <ComfyUI>/user/h3lite_runs`. The helper records a configuration fingerprint and skips an identical active run.
5. Poll with `h3_status.py --prompt-id <id> --output-dir <ComfyUI>/output --run-root <ComfyUI>/user/h3lite_runs --require-audio --dynamic-check --compact --json` every 20-30 seconds, or use `--watch --watch-interval 20 --compact --json` when the caller can keep one bounded monitor alive. Pending status is `ok:false, complete:false`; this is normal and is not a generation failure. Omit `--require-audio` only for an explicit complete-silence request; omit `--dynamic-check` only when a deliberately static result is requested.
6. Return the output only after MP4 existence, video stream, duration, frame count, FPS, audio policy, and (when requested) dynamic QA are confirmed. Do not submit the same request again while it is `running`.

Use the history/object-info/browser fallback only when the bundled template is
incompatible, a custom reference mode is needed, or the queue reports a
missing node/model. This keeps a normal request from paying workflow discovery
cost on every run.

## Workflow

### 1. Diagnose the computer

Run:

```powershell
$environment = '<ComfyUI>\user\h3lite_runs\_environment'
python scripts/h3_doctor.py `
  --json `
  --report-file "$environment\doctor.json" `
  --root <chosen-root> `
  --comfyui <ComfyUI-path>
```

Record GPU name and VRAM, system RAM, free disk, Python, CUDA/PyTorch visibility, ComfyUI location, model presence, and custom-node presence. If there is no NVIDIA CUDA device, do not promise this local CUDA route; explain the limitation and offer API/cloud or another backend as an alternative.

The doctor also records available physical RAM, available Windows pagefile, and
GPU compute processes. Low available RAM or VRAM is a warning because the
validated 8 GB route can still finish with offload. A nearly exhausted
pagefile is different: it previously caused `hostbuf_file_reader_read failed`
and system-level paging failures, so `h3_preflight.py` blocks that run.

Use `references/deployment-matrix.md` to choose a profile. For an 8 GB laptop, start with the tested W4A8 profile, not the larger official INT8/32B profile.

If the user asked for installation or repair, report the selected installation
target before the doctor result. The doctor is read-only; it does not install
ComfyUI, nodes, Python packages, or model weights.

### 2. Select a profile

- **Fast (default):** W4A8 H3 main model, Qwen3-VL 4B INT4 text encoder, 4B ClipProj, FP16 video VAE, FP32 audio VAE, LightX2V 4-step LoRA, `--lowvram`, 640x352, 124 frames, 4 steps, and Block Cache on. This is the success-rate baseline.
- **Balanced:** keep the low-VRAM canvas on an 8 GB laptop, use 6 steps, and bypass Block Cache. On a mid/high-VRAM machine, the planner may select 864x480.
- **Quality:** use 8 steps and bypass Block Cache. On an 8 GB laptop, keep 640x352 and warn that W4A8/4B remains a quality ceiling; on a mid/high-VRAM machine, the planner may select 864x480.
- **Below 8 GB or insufficient RAM/disk:** stop before downloading or queueing. Explain the missing capacity and propose a hosted/API or alternative model.

Do not infer that a smaller file or INT8 label is automatically faster. On low-VRAM systems, CPU offload, RAM bandwidth, kernel compatibility, and first-run compilation often dominate.

The planner's `--target-minutes` option chooses the highest-quality mode whose
conservative upper estimate fits the budget. Without that option, `auto`
always selects fast. The estimate must include a cold-start warning and the
final report must include ComfyUI's actual execution time.

### 3. Install or repair the environment

Use the official ComfyUI H3 tutorial and the component list in
`references/deployment-matrix.md`. Create or reuse the selected ComfyUI root
and place every component below that root. Pin or record the ComfyUI and
custom-node commits used for a successful run. Install only the nodes required
by the selected profile, typically:

- `ComfyUI-KJNodes`
- `ComfyUI-ClipProj`
- `ComfyUI-MiniMax-H3-Turbo`
- `ComfyUI-sol-attn`
- `comfyui-minimax-h3-blockcache-T8`

Keep optional INT8 loaders and experimental cache nodes disabled until the baseline works. Start ComfyUI with a profile-appropriate command; the low-VRAM baseline commonly uses `--lowvram`, `--fast-disk`, and `--use-sage-attention` when the installed build supports them.

After installation, rerun the doctor and stop if any required model or node is missing. Do not start a long generation while the graph contains unresolved node classes.

Before queueing, run:

```powershell
python scripts/h3_plan.py `
  --doctor-json <ComfyUI>\user\h3lite_runs\_environment\doctor.json `
  --install-mode reuse-existing `
  --comfyui <ComfyUI-path> `
  --mode auto `
  --aspect landscape `
  --video-seconds 5 `
  --report-file <ComfyUI>\user\h3lite_runs\_environment\plan.json `
  --json

python scripts/h3_preflight.py `
  --doctor-json <ComfyUI>\user\h3lite_runs\_environment\doctor.json `
  --plan-json <ComfyUI>\user\h3lite_runs\_environment\plan.json `
  --refresh-runtime `
  --require-audio `
  --json
```

`ready` means no observed risk, `caution` means the run may proceed with an
explicit warning, and `blocked` means fix the environment or use another
backend first. The preflight ignores the Python process used by ComfyUI and
zero-memory desktop helpers; it warns only for meaningful external GPU
competitors. This is a runtime gate, not a promise of success.

### 4. Rewrite the user's request into an H3 prompt

Identify the generation mode before writing:

- text only → `T2VA`
- one first-frame image → `I2VA`
- first and last images → `FL2VA`
- last-frame image → `L2VA`
- reusable images/video/audio references → `Ref2VA`

Read `references/prompt-writing.md` when composing or revising a prompt. Use the exact field names and ordering required by that mode. For native base modes, the core order is:

```text
integrated_multimodal_description: ...
overall_soundscape: ...
non_diegetic_music: ...
```

For full-reference mode, use the six-section structure in the reference. Write the rewritten description in English, but preserve user-provided dialogue, lyrics, and visible scene text in the original language.

Make the prompt operational:

- establish style, framing, subjects, environment, lighting, and initial state in Shot 1;
- describe observable actions and state changes in playback order;
- use later shot cut times only when a real cut introduces new information;
- write camera motion as a natural sentence with motion type, amplitude, and speed when useful;
- describe dialogue, singing, and diegetic sound in the timeline body;
- describe ambient/physical sound in `overall_soundscape` and audience-only music in `non_diegetic_music`;
- Resolve the audio policy before submission: `auto`/ordinary prompts require the native H3 audio path; “no dialogue” does not disable sound. Only explicit complete-silence wording may remove the `CreateVideo` audio input.
- Interpret `不要对白` / `无对白` / `no dialogue` as a dialogue-only constraint: keep native ambience, sound effects, animal or action sounds, and the audio stream. Disable all audio only when the user explicitly requests `完全静音`, `无任何声音`, or `no audio`.
- use stable speaker IDs and exact text for dialogue;
- use `N/A` for music only when no non-diegetic music is desired, and use `overall_soundscape: N/A` only for explicitly complete silence.

If the selected ComfyUI graph uses a ClipProj/krea2 or another custom prompt schema, inspect its example workflow first. Adapt the official semantic structure to the node's accepted field while preserving the graph's required fields; do not blindly paste a T2VA prompt into a Ref2VA input or vice versa.

### 5. Generate through ComfyUI

For the low-VRAM text-only fast path, use the bundled API workflow and return
the queue ID immediately:

```powershell
python scripts/h3_generate.py `
  --base-url http://127.0.0.1:8188 `
  --workflow-template h3_w4a8_t2v `
  --prompt-file prompts/current.txt `
  --filename-prefix video/H3Lite_my_clip `
  --run-root <ComfyUI>\user\h3lite_runs `
  --audio-policy auto `
  --profile fast `
  --resolution 640x352 `
  --seed 20260813 `
  --queue-only `
  --json
```

Then check the queue with a short one-shot command:

```powershell
python scripts/h3_status.py `
  --base-url http://127.0.0.1:8188 `
  --prompt-id <prompt-id> `
  --output-dir <ComfyUI>\output `
  --run-root <ComfyUI>\user\h3lite_runs `
  --require-audio `
  --dynamic-check `
  --compact `
  --json
```

The JSON result is compact by default; use `--verbose` only when a failed run
needs the full ComfyUI history graph. For a bounded foreground monitor, add
`--watch --watch-interval 20 --watch-timeout 3600`. A pending response has
`ok: false` and `complete: false`; only a completed, verified media response
has `ok: true`.

The bundled template already contains the prompt node, W4A8 model path, 4B
ClipProj, dual VAE, LightX2V, H3 sigma shifts, Sage/Sol/T8 patches, native
audio, 124 frames, 640x352, and 4 steps. Override `--seed`, `--width`,
`--height`, `--length`, `--steps`, `--fps`, `--profile`, or `--resolution` only
when needed. `fast` keeps Block Cache; `balanced` uses 6 steps and bypasses
Block Cache; `quality` uses 8 steps and bypasses Block Cache. For a custom API
workflow, pass `--workflow <file>`; the prompt field can still be discovered or
selected with `--prompt-node` and `--prompt-field`.

Do not use the synchronous wait mode from a terminal command with a short
timeout. `--queue-only` plus one-shot status polling prevents a terminal timeout
from hiding a still-running ComfyUI job.

For the low-VRAM baseline, use 124 frames at 24 fps (about 5 seconds), 4 steps, `res_multistep`, and `simple`. Use 640x352 for the normal fast output; run 864x480 only when the planner approves the hardware/time trade-off.

### 6. Verify and report

Do not report success from a queue ID alone. Confirm:

- the job completed without an execution error;
- an MP4 or other intended video file exists;
- the file has a video stream and, for native H3 output, an audio stream;
- duration, frame count, and FPS are close to the requested values;
- the first/middle/last samples are not black or flat; suspicious block/mosaic output still requires visual inspection, and when the user asked for an action, dynamic QA must classify the clip as `dynamic`;
- the output path and elapsed time are reported.
- the plan's estimated range is compared with the actual ComfyUI execution time;
- the configuration fingerprint and run manifest are recorded so a retry can be distinguished from an accidental duplicate;
- the selected ComfyUI, models, custom_nodes, and output paths are recorded.

When diagnosing failures, use this order:

1. critically low pagefile, unavailable RAM, or another GPU process;
2. missing model or custom node;
3. wrong model folder or filename;
4. CUDA/PyTorch/custom-kernel incompatibility;
5. out-of-memory or excessive CPU offload;
6. invalid H3 flow/audio graph;
7. prompt or reference alignment problem.

For black/mosaic output, restore the official H3 flow/sigma-shift node and simplify optional attention/cache patches. For distorted audio at 4 steps, check the H3 audio/video schedules and use the compatible H3 Turbo sampler on older ComfyUI builds.

## Bundled resources

- `references/deployment-matrix.md`: tested low-VRAM profile, official fallback profile, model folders, node roles, launch flags, and failure triage.
- `references/prompt-writing.md`: concise operational digest of MiniMax's official H3 prompt guide and prompt-writing skill.
- `assets/h3_w4a8_t2v_api.json`: reusable low-VRAM T2VA API graph based on the validated W4A8/4B/audio route.
- `scripts/h3_doctor.py`: dependency-free hardware, disk, model, and node diagnosis.
- `scripts/h3_plan.py`: read-only hardware, resolution, time-budget, aspect-ratio, profile, and installation-path planner.
- `scripts/h3_preflight.py`: read-only pagefile/RAM/VRAM/process/model/node gate before queueing.
- `scripts/h3_generate.py`: fast template-based or custom-workflow submission with profile, resolution, prompt/settings overrides, and queue-only mode.
- `scripts/h3_status.py`: compact one-shot or bounded watch status, actual execution-time, media metadata verification, optional first/middle/last dynamic QA, and empirical timing-cache updates.

## Sources

- Official H3 prompt guide: <https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md>
- Official H3 prompt-writing skill: <https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing>
- Official ComfyUI H3 tutorial: <https://docs.comfy.org/tutorials/video/minimax/minimax-h3>
- H3 Turbo ComfyUI nodes: <https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo>
