---
name: h3lite
description: Use when configuring, repairing, planning, or running MiniMax H3 locally on a Windows NVIDIA computer, especially when installation compatibility, component sets, resolution, generation-time budget, path, low-VRAM risk, or H3 prompt mode must be chosen from hardware and user requirements.
---

# MiniMax H3 Local Video

Use this skill to turn a user's local computer into a reproducible MiniMax H3 audio-video workstation and to generate short clips. The validated primary route is Windows + NVIDIA + ComfyUI; macOS Apple Silicon is a community/experimental alternative, not an equivalent tested backend. Treat platform selection, path selection, hardware-aware planning, prompt writing, execution, timing, and verification as one workflow. The default is the validated fast route; other modes must be chosen explicitly or justified by a time budget.

## Platform scope and routing

Detect the operating system and accelerator before giving installation commands or model links. Do not give CUDA, Windows virtual-environment, `.bat`, or Windows path instructions to a macOS user.

| Platform | h3lite status | Guidance |
| --- | --- | --- |
| Windows + NVIDIA CUDA | Primary, locally validated | Use the ComfyUI/H3 Lite fast path and the Windows doctor/planner/preflight scripts. |
| macOS Apple Silicon | Community alternative, not h3lite-equivalent | Explain that the documented ComfyUI route is not validated on Metal. Offer the MLX/`mmh3turbo` route as an optional external alternative, with its own weights, commands, and timing. |
| macOS Intel | Not recommended | Do not promise local H3 generation; suggest a hosted/API or another backend. |
| Linux + NVIDIA | Unverified | The model concepts may transfer, but Windows paths, packaged nodes, and timings do not. Require an explicit experimental choice. |

For a non-Windows user, preserve the useful cross-platform guidance (prompt structure, 32-pixel canvas alignment, low-resolution preview, disk/log/output checks), but label every resource and timing as platform-specific. A community implementation that can run H3 on a Mac is evidence for feasibility, not evidence that this ComfyUI skill supports Metal.

The Mac alternative described in the project notes uses MLX/Metal and a third-party `mmh3turbo` package. If a Mac user explicitly chooses that route, point them to the author's [community bundle](https://huggingface.co/yunfengwang/mmh3turbo-bundles) and package (`uvx mmh3turbo`), and state that these are external resources with independent licensing, updates, and validation. It may reduce the download footprint with GGUF/4-bit bundles, but it is outside this skill's tested component sets. Do not silently install it, mix its weights with ComfyUI models, or present its 30–43 minute 5-second 720p timings as Windows benchmarks.

## Agent production workflow

For complex creative requests, use the compact workflow contract in
[`references/agent-workflow.md`](references/agent-workflow.md):

```text
intent route → reference/identity anchors → prompt enhancement → execute → verify
```

Route from the user's input and acceptance criteria, not from a style adjective.
Use `I2VA` for a specified opening frame, `FL2VA`/`L2VA` for endpoint anchors,
and `Ref2VA` only after its model, text encoder, and workflow are confirmed.
For recurring characters or multi-shot work, define stable subject/reference
labels, what must be retained, what may change, and what drift is forbidden
before writing the timeline. This workflow pattern is local and does not add a
cloud service, MCP dependency, second model, or second inference pass.

When a creative brief is vague (for example, it only says “more cinematic”
or “make it a nice 3D animation”), optionally read
[`references/prompt-assist.md`](references/prompt-assist.md). It adapts the
public Higgsfield prompt structure—stable style/identity lock, one clear scene
action, physical camera motion, audio, and compact anti-drift constraints—to
H3's native fields. Use it as a writing aid only: do not call Higgsfield, copy
model-specific flags or capabilities, or let a web lookup change the local
route, resolution, component set, or verification rules. If a live lookup is
needed, follow the host `web-access` skill and use public pages only.

## Operating rules

- **Hot path first:** for an ordinary text-to-video request on an already validated installation, run `scripts/h3_fastpath.py` once. It combines `/system_stats`, fresh-cache reuse, in-process planning/preflight, queue submission, and one bounded completion watch. Do not issue repeated one-shot status calls, reread the full reference set, run `--help`, or ask nonessential questions during this path. If the command yields a running terminal cell, wait on that cell; do not start another monitor.
- **Keep cold work out of the hot path:** model download manifests, hash or size verification, Torch/custom-node repair, repository checks, browser workflow discovery, and full recursive doctor scans belong to installation, migration, repair, or first-run validation. A normal generation on an unchanged machine must not pay those costs.
- **Cold path can be heavier when it prevents hour-scale waste:** during installation or repair, verify download source, target folder, expected size/hash when available, runtime imports, and model-role mapping before queueing. Store the result so later prompts reuse it instead of repeating it.
- Inspect before changing anything. Run `scripts/h3_doctor.py --json` and locate the target ComfyUI directory before installing packages, nodes, or weights.
- On first contact, run a platform/accelerator check before the Windows doctor. If the machine is not Windows + NVIDIA, stop the CUDA installation branch and route the user using the platform matrix above.
- Prefer an isolated ComfyUI directory when no installation is supplied. Never overwrite an existing installation or silently replace model files.
- Keep the deployment path configurable. Do not copy paths from another computer into scripts or workflows.
- Report required disk space before large downloads. Use resumable downloads and verify file size or hash when a source provides one.
- Before a long generation or multi-shot batch, check free space and pagefile headroom and keep per-shot logs. A pipeline that filters away the process exit code or traceback is not a successful run; preserve the full log and stop on the first failed shot.
- If the user can only download from the public internet, run a cold-path download plan before fetching multi-GB files: test candidate raw URLs with a small ranged download, choose the fastest stable source, estimate wall-clock time, then use resumable `.part` downloads. Do not pretend scripts can beat the user's real bandwidth.
- Before downloading large assets, run the doctor compatibility probe. Stop on a Torch import error; treat a comfy-kitchen/Torch mismatch as a repair decision, not a post-download surprise. Do not silently substitute model files or start unlimited parallel downloads.
- Treat the diffusion checkpoint, text encoder, Turbo LoRA, workflow, and node revisions as one component set. Read `references/component-sets.md` during installation, migration, model replacement, or kernel repair. Never construct an unvalidated set from individually plausible filenames.
- Use `--component-set auto` for one unambiguous installed set, or explicitly select `A`/`validated-low-vram-a` or `B`/`portable-16gb-b` when both sets are installed. Record the selected set in the run manifest; never resolve a partial set role by role.
- Prefer the maintained Baidu package for the registered A/B component sets. Keep the selected set atomic, and respect the licenses of model weights and third-party nodes when using either the package or upstream sources.
- Prefer the ComfyUI HTTP API with an API-format workflow JSON. Use browser/CDP capture only as a recovery path when no reusable workflow JSON exists.
- Check `http://127.0.0.1:8188/system_stats` before starting anything. If ComfyUI is already healthy, reuse it and do not restart it or rediscover its workflow history.
- Preserve MiniMax H3's audio path and flow/sigma-shift handling when the user wants native audio. Do not remove audio VAE, audio conditioning, or the H3 sampling node merely to make a graph look simpler.
- **Zero-inference optimization constraint:** hardware compatibility checks, timing calibration, face routing, and media QA may run before or after generation, but must not add sampling steps, extra generation models, or a second video inference pass. Keep the selected graph unchanged unless the user explicitly requests a different quality profile.
- **Face-quality routing:** if the user needs a recognizable or speaking human face, do not treat low-VRAM W4A8 T2VA at 640x352 as a final-quality route. Prefer I2VA with a clear first-frame reference; prefer Ref2VA when identity must persist across shots. Read `references/face-quality.md`, confirm `MiniMaxH3ReferenceToVideo` through `/object_info`, and confirm the matching reference-capable text encoder/projection and workflow before selecting that route. A registered node alone is not enough; the bundled Ref2VA templates are an experimental local path until a complete run passes media and manual identity QA.
- **Anchor before prompt:** for multi-shot or identity-sensitive requests, first create an internal anchor sheet with stable subject/picture labels, retention rules, allowed changes, and forbidden drift. Use the same labels in the prompt, output prefix, and run manifest; read `references/agent-workflow.md` for the compact contract.
- **Assist vague creative briefs without inventing facts:** when the request lacks a concrete camera, action, sound, or finish, read `references/prompt-assist.md` and use its bounded defaults or ask one targeted question if the omission changes the route or acceptance criteria. A public Higgsfield lookup is optional and pattern-only; fall back to the local references when browsing is unavailable.
- On current ComfyUI builds, the API class `MiniMaxH3SigmaShift` is the native `ModelSamplingMiniMaxH3` node and uses the merged `ModelSamplingAV` video/audio schedule fix. Detect it by `/object_info` or the local source before adding a custom dual-clock sampler; do not duplicate the fix merely because the API class keeps its compatibility name.
- Run the read-only planner before a non-trivial generation. It must report selected mode, resolution, steps, cache policy, paths, and an estimated time range. Do not present an estimate as a guarantee.
- Run the read-only preflight after the doctor and planner. Treat low available RAM/VRAM as a caution, but stop when the pagefile is critically low, required assets are missing, or the doctor recommends an alternative backend.
- Do not perform a full recursive doctor scan for every prompt. Cache the environment report under `<ComfyUI>/user/h3lite_runs/_environment/`; reuse it for a normal session (normally no older than 30 minutes), invalidate it after ComfyUI/model/node/driver changes or a failed run, and use `h3_preflight.py --refresh-runtime` for volatile resource fields.
- Do not revalidate large model files before every prompt. Trust the cached download/component manifest unless the file is missing, has a different size/mtime than recorded, the user changed components, or the previous run failed with a model/node/loader error.
- For registered Set B files, require the recorded SHA-256 on first use or after a size/mtime change. A same-size corrupted W4A8 checkpoint produced colored mosaic frames, so byte count alone is not proof of integrity; reuse the cached integrity result on unchanged files.
- Treat every submission as an auditable run: save the effective prompt, mutated API workflow, configuration fingerprint, queue ID, actual execution time, and verified output in the run manifest.
- For identity-sensitive or multi-shot runs, the runtime also writes `anchors.json` beside `manifest.json` and records advisory `anchor_qa` comparisons; these signals support manual continuity review but are not face recognition.
- Keep agent-facing status compact: omit ComfyUI's full history graph by default; use verbose history only when diagnosing a failure.
- Never submit an identical configuration while its manifest is `submitting`, `queued`, or `running`. Return the existing prompt ID instead; use `--allow-duplicate` only when the user explicitly asks for a second identical run.
- Treat low-VRAM timing as an empirical estimate. The first run can be much slower because kernels compile and weights move between system RAM and VRAM.
- For expensive renders, use a cheap preview pass first: validate the complete prompt/shot list at the smallest supported canvas (for example 256p or the local fast bucket), then promote only approved shots to the requested resolution. This is especially important for multi-shot work; it is a planning optimization, not a second quality-generation pass for a single requested clip.
- Prefer `NORMAL_VRAM` when a validated 16 GB system can keep Set B resident. In a same-model/workflow/prompt/seed 640x352 comparison, an RTX 4060 Ti 16 GB run took 77.08 seconds versus 591.22 seconds on an RTX 4070 Laptop 8 GB using `LOW_VRAM`; treat dynamic loading/offload as the main operational explanation, not as a pure GPU benchmark or a promise.
- When launching ComfyUI as a background process, redirect stdout and stderr to persistent files. A detached pipe can become invalid after the launching session is cleaned up, leaving ComfyUI alive but causing tqdm/logger writes to fail with `OSError: [Errno 22] Invalid argument`. On that signature, restart ComfyUI with persistent logs; do not redownload models or rerun a full doctor unless the restart exposes another error.
- Keep media verification attached to the selected ComfyUI root. The verifier searches system `PATH`, `H3LITE_FFPROBE`, and common locations in or beside `<ComfyUI>` for `ffprobe`; both `h3_generate --watch` and standalone `h3_status` must receive or infer that root. Standalone status may infer the parent only when `--output-dir` points exactly `<ComfyUI>\output`; otherwise pass `--comfyui` explicitly. Treat `ffprobe_not_found` as a missing verifier, not evidence that generation failed, and do not requeue the video until the existing output has been inspected.
- Treat run-history cleanup as explicit maintenance, never hot-path work. Use `scripts/h3_cleanup.py` in dry-run mode first and require `--apply` before deleting eligible run snapshots. Preserve `_environment`, `_hotpath`, `_workflows`, `_experiments`, prompt folders, timing data, and generated output files.

## Preferred component download source

For installation or repair, use the maintained Baidu package before assembling
the set from multiple upstream repositories. Select one complete package after
the hardware check; do not ask the user to download both sets or mix their
exclusive files.

| Default hardware match | Package | Share link | Code |
| --- | --- | --- | --- |
| About 8 GB VRAM, low-VRAM fast route | Set A | [Baidu Netdisk](https://pan.baidu.com/s/1IBlH0VY7tWGvxqMtniraow) | `4hri` |
| 16 GB-class VRAM, FP8 compatibility route | Set B | [Baidu Netdisk](https://pan.baidu.com/s/1x5GGuJv0h8chApgVoDgIaQ) | `1hjx` |

Guide the user to open the matching link, enter the code, and download the
whole package. If the `baidu-drive` skill or a Baidu Drive connector is
available, use it for the download; otherwise give the link and code directly
and continue after the user places the files locally. Merge the package's
`models` and
`custom_nodes` folders into the selected `<ComfyUI>` root, then import or copy
the packaged workflows and keep `component-manifest.json` with the install.
Run the doctor after the merge.

Set A contains the INT4 text encoder and optional low-VRAM acceleration nodes.
Set B contains the FP8 text encoder and validated compatibility workflows. Both
packages include their own shared ClipProj and VAE files, so a user only needs
one link. If the Baidu package is unavailable or the user explicitly requests
upstream downloads, use the exact sources, filenames, sizes, and hashes in
`references/component-sets.md`.

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
  explicit `WIDTHxHEIGHT`. Keep pixel size as a ComfyUI parameter, not as
  prompt prose. The prompt should describe framing such as landscape
  composition, medium close-up, macro shot, or slow push-in.
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
  --megapixels 0.4 `
  --video-seconds 5 `
  --json
```

Use the planner result as the source of truth for `--profile`, `--resolution`,
`--steps`, `--length`, and `--fps`. If no quality or time requirement is
given, `auto` selects `fast` and preserves the validated 640x352, 4-step,
Block-Cache route. On an 8 GB laptop, `balanced` keeps 640x352 and increases
steps while bypassing T8 Block Cache; `quality` does the same with 8 steps.
Only the mid/high-VRAM plan promotes balanced/quality to an official-style
ComfyUI bucket by default.

ComfyUI's native H3 templates commonly use `ResolutionSelector`: aspect ratio
+ target megapixels + a 32-pixel multiple. For example, `16:9`, `0.4 MP`,
`multiple=32` gives `864x480`. Treat that as the normal official-style H3
canvas, while H3 Lite's `640x352` remains the low-VRAM fast baseline. If the
user asks for "official template size", "normal quality", or "0.4MP", use
`--megapixels 0.4` unless hardware/time preflight blocks it.

The 32-pixel alignment is a practical model/decoder constraint: the VAE's
16-pixel spatial reduction and the DiT's 2-pixel patching must both align. Do
not advertise consumer labels such as "720p" as exact model sizes when the
nearest legal canvas is different; report the actual canvas (for example
`1280x704`) and keep the requested label as a human-friendly preset name.

For a prompt with several ordered actions, prioritize adherence before pixels.
Use the fast 640x352 baseline first; 736x416 is an experimental adherence
bucket between the fast canvas and 0.4 MP. Do not assume 768p follows complex
shot structure better: community reports describe stronger Ref2VA/keyframe
adherence around 352p-416p, while extra steps mainly improve coherence and
detail. Promote 736x416 only after a same-prompt comparison succeeds locally.

When the user supplies an explicit resolution, treat that canvas choice as
already confirmed: issue one concise OOM/time warning, then continue unless
preflight is `blocked`. Do not ask the same resolution question again. If a
separate wall-clock budget conflicts with the explicit canvas, state the
conflict once and keep the user's explicit canvas. Never silently trade away
the audio path or change the installation target to make the estimate fit.

## Fast path for ordinary text-to-video

Use this path for a short H3 clip on a machine that passes the low-VRAM doctor
check. With no frame arguments it is T2VA; adding `--first-frame` or
`--last-frame` selects the native reference route automatically:

```powershell
python scripts/h3_fastpath.py `
  --comfyui <ComfyUI-path> `
  --prompt-text "<rewritten H3 prompt>" `
  --resolution 640x352 `
  --video-seconds 5 `
  --filename-prefix video/H3Lite_my_clip `
  --json
```

For image-to-video, pass the reference image directly. The helper stages an
external image into `<ComfyUI>/input` using a content-addressed filename, then
connects it to the native `MiniMaxH3ImageToVideo` node. No extra I2V node or
manual JSON editing is required:

```powershell
python scripts/h3_fastpath.py `
  --comfyui <ComfyUI-path> `
  --mode i2va `
  --first-frame <path-to-first-frame.png> `
  --prompt-text "<rewritten I2VA prompt>" `
  --resolution 640x352 `
  --video-seconds 5 `
  --filename-prefix video/H3Lite_i2va `
  --json
```

Use `--mode fl2va --first-frame <first> --last-frame <last>` for fixed first
and last images, or `--mode l2va --last-frame <last>` for a last-frame route;
the helper removes the I2V template's first-frame placeholder automatically in
the latter case.
When `--mode auto` is left in place, the mode is inferred from the supplied
frame arguments. The low-VRAM baseline remains 640x352, 124 frames, 4 steps,
and native H3 audio. A validated RTX 4070 Laptop 8 GB I2VA run at that
baseline took about 12 minutes; treat that as local empirical timing, not a
guarantee.

已配置环境的复跑路径就是这一条命令；不要再分别调用 doctor、plan、preflight、generate 和 status。Windows/Git Bash 路径请写 `F:/MiniMax-H3/ComfyUI`，不要写 `/f/MiniMax-H3/ComfyUI`。

The helper reuses `<ComfyUI>/user/h3lite_runs/_environment/doctor.json` for 30
minutes, invalidating it only for a cold start, explicit `--force-doctor`, an
installation change, or failure recovery. It writes the plan and prompt into
the run root, keeps the native audio path unless the prompt explicitly asks
for complete silence, and waits with one compact `--watch` monitor. An
explicit resolution is already confirmed; continue after one concise risk
warning unless preflight is `blocked`. `--dynamic-check` is on by default;
use `--skip-dynamic-check` only for an intentionally static clip.

Hot-path budget rule: spend only the time needed to rewrite the prompt, refresh
volatile runtime status, submit, watch, and verify. Do not check Git remotes,
download pages, model hashes, dependency versions, or official docs during a
normal generation unless the previous command returns a concrete error pointing
there. If cache is valid, proceed directly to generation.

### Native Windows progress window

On Windows, the fastpath opens the native monitor by default, so every normal
desktop generation has a visible progress window without an extra flag. Use
`--no-monitor-gui` for a run that must stay terminal-only; `--monitor-gui`
explicitly forces it on. The window discovers the fresh H3 run manifest
automatically. It uses a native Windows Tkinter window, reuses the manifest's
ComfyUI `client_id`, and listens to the native `/ws`
channel, including the newer `progress_state` node events, while HTTP polling
supplies queue state, elapsed/estimated time, GPU memory, RAM, pagefile, output
path, and failure state. It is monitor-only: closing it does not interrupt
generation.
The node count is structural workflow progress, not elapsed-time progress: H3
nodes have very different runtimes. The window therefore shows node completion
separately, displays the current node's observed runtime, and keeps ETA on the
empirical timing estimate instead of treating `4/5` as `80%` of the time. The
track is segmented by workflow node so completed, active, and pending nodes
remain visually distinct.
The default window is `760x620`; its content area has a vertical scrollbar and
mouse-wheel support for smaller displays or larger system scaling.
The monitor JSON marks these semantics as `progress_basis` (`node_completion`
or `sampling_steps`) and `eta_basis` (`empirical` or `live_progress`) so an
Agent can report them without inventing a time percentage.
When available, elapsed time comes from the run manifest's measured execution
time; the wall-clock timestamp is only the fallback before that field exists.
Old `running` manifests are ignored during automatic discovery; pass
`--prompt-id` to inspect a specific historical run.

To open the monitor independently:

```powershell
python scripts/h3_monitor_gui.py `
  --comfyui <ComfyUI-path>
```

Use `--once --no-websocket` for a one-shot JSON diagnostic. If the optional
WebSocket client is unavailable, the window remains usable through HTTP
polling, but the progress track stays static and explicitly reports that live
quantifiable progress is unavailable. It never substitutes an animated bar
for a measured percentage. An MCP wrapper is unnecessary for this local GUI;
an Agent can query the same monitor JSON separately when it needs status.

Use the lower-level `h3_doctor.py`, `h3_plan.py`, `h3_preflight.py`,
`h3_generate.py`, and `h3_status.py` commands only for installation, recovery,
custom workflows, or diagnosis. Never replace the fastpath with repeated
one-shot status commands during a normal generation.

Use the history/object-info/browser fallback only when the bundled template is
incompatible, a Ref2VA/custom graph is needed, or the queue reports a missing
node/model. T2VA, I2VA, FL2VA, and L2VA are now first-class bundled routes.

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

- **Fast (default):** a registered W4A8/4B/Turbo component set, 4B ClipProj, FP16 video VAE, FP32 audio VAE, 640x352, 124 frames, and 4 steps. The launch profile uses `--lowvram` for the very-low/8 GB tiers; 10–16 GB systems use normal VRAM mode unless preflight or a prior OOM justifies offload. Use Block Cache only when its classes are actually loaded; otherwise use the compatibility workflow. This is the success-rate baseline.
- **Balanced:** keep the low-VRAM canvas on an 8 GB laptop, use 6 steps, and bypass Block Cache. On a mid/high-VRAM machine, the planner may select 864x480.
- **Quality:** use 8 steps and bypass Block Cache. On an 8 GB laptop, keep 640x352 and warn that W4A8/4B remains a quality ceiling; on a mid/high-VRAM machine, the planner may select 864x480.

The accelerated fast graph is paired with the registered LightX2V/Turbo 4-step
LoRA. `minimax_h3_turbo_v4_step600_ema.safetensors` is a compatibility-workflow
quality variant: H3 Lite rejects it when Sage/Sol/Chunk/T8 acceleration nodes are
present, because that combination produced severe ghosting and color artifacts in
local validation. Use a `*_compat_api.json` workflow for v4, or use the registered
LightX2V/Turbo 4-step LoRA for the fast route.

- **6 GB experimental:** when the machine has roughly 6 GB VRAM, 32 GB system RAM, an SSD, and sufficient pagefile headroom, permit a cautious first run at 608x352, 4 steps, and low-VRAM offload. Treat community timings as orientation only: reported I2V runs include about 345 seconds at 608x352/4 seconds and 441 seconds at 864x480/5 seconds, while another 640x480/5-second report took about 13.7 minutes. These used different official/community model and workflow combinations, so do not transfer the numbers to the bundled W4A8 graph as a promise.
- **Below roughly 6 GB or insufficient RAM/disk:** stop before downloading or queueing. Explain the missing capacity and propose a hosted/API or alternative model.

Do not infer that a smaller file or INT8 label is automatically faster. On low-VRAM systems, CPU offload, RAM bandwidth, kernel compatibility, and first-run compilation often dominate.

The planner's `--target-minutes` option chooses the highest-quality mode whose
conservative upper estimate fits the budget. Without that option, `auto`
always selects fast. The estimate must include a cold-start warning and the
final report must include ComfyUI's actual execution time.

### 3. Install or repair the environment

Use the official ComfyUI H3 tutorial and the component list in
`references/deployment-matrix.md`. Create or reuse the selected ComfyUI root
and place every component below that root. Pin or record the ComfyUI and
custom-node commits used for a successful run. Install only nodes referenced by
the selected workflow. The baseline requires `ComfyUI-ClipProj` or a compatible
implementation. KJNodes, H3 Turbo helper nodes, Sol Attention, and T8 Block
Cache are optional unless the selected accelerated graph explicitly uses them.

`h3_fastpath.py --workflow-template auto` is the default. It queries
`/object_info` when available and uses the accelerated T2V or I2V graph only
when the Sage, Sol, Chunk Feed Forward, and T8 classes are actually loaded.
Pass `--component-set A` or `--component-set B` when both complete sets are
installed. Set B is validated with the compatibility graph on RTX 4060 Ti
16 GB and RTX 4070 Laptop 8 GB systems, so `auto` selects that graph. Its full
Sage/Sol/Chunk/T8 acceleration chain is not yet the validated default; use
`--acceleration fast` only for an intentional trial. Use `--acceleration
compat` to force the validated compatibility graph.
Both graphs preserve the H3 sampler, native audio, ClipProj, LoRA, dual VAEs,
and native first/last-frame inputs without optional patches.

The bundled multi-image Ref2VA graphs reuse this same registered component set:
there is no separate Ref2VA checkpoint to download. They add the native
`MiniMaxH3ReferenceToVideo` route and bind repeated reference images through the
resident ClipProj path. Before downloading anything, reuse the local W4A8,
4B encoder, ClipProj, dual VAE, and Turbo LoRA files when their manifest and
loader checks pass.

Keep optional INT8 loaders and experimental cache nodes disabled until the baseline works. Start ComfyUI with a profile-appropriate command; the very-low/8 GB launch profile commonly uses `--lowvram` and `--fast-disk`, while 10–16 GB systems normally omit `--lowvram` unless preflight or an earlier OOM justifies it. Add Sage Attention only after its PyTorch/CUDA compatibility is confirmed. Treat Easy Cache and generic cache nodes as opt-in experiments: community reports and local experience show that some settings can blur or damage motion/detail. Never enable a cache solely from a speed claim; compare a short output against the uncached baseline first.

After installation, rerun the doctor and stop if any required model or node is missing. Do not start a long generation while the graph contains unresolved node classes.

Cold-path validation is deliberately allowed to spend extra seconds or minutes:
record component URLs, selected replacement filenames, file sizes or hashes,
local loader choices, Python import probes, and any small compatibility patch
that was applied. This is cheaper than discovering a wrong 20 GB model or a
Torch/custom-node mismatch after queueing. Once the baseline succeeds, write or
refresh the cached environment/component report and return to the hot path for
future prompts.

When public internet is the only source for a large model such as the W4A8
diffusion checkpoint, do not start a blind long transfer. First probe the
official raw URL, configured mirror raw URL, and any user-provided proxy URL
with a small resumable/ranged request. Report the fastest measured speed,
estimated time, and selected command. Prefer `aria2c` with conservative
connections when available and the server supports ranges; otherwise use
`curl.exe -L -C -`. Keep partially downloaded files as `.part` and resume them;
do not delete progress or restart from byte zero unless the size/hash proves
the file is unrecoverable.

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

Read `references/prompt-writing.md` when composing or revising a prompt. For
multi-shot, identity-sensitive, or reference-heavy requests, also read
`references/agent-workflow.md` and build the route/anchor sheet before writing.
For an underspecified creative request, also read
`references/prompt-assist.md`: it supplies the optional
`STYLE/IDENTITY LOCK → SCENE → MOTION → AUDIO → NEGATIVE` scaffold and the
rules for translating it back to H3. Ask only for information that materially
changes the route or acceptance criteria; otherwise state the bounded default
and continue. Never make a website lookup a runtime dependency.
Use the exact field names and ordering required by the selected mode. For
native base modes, the core order is:

```text
integrated_multimodal_description: ...
overall_soundscape: ...
non_diegetic_music: ...
```

For user-facing 5-second quick-start examples, teach the same idea as a memorable three-part structure: **scene and atmosphere → action and camera → sound**. Present it as one natural-language prompt that can be copied directly; do not require users to write schema labels. Treat this as an explanation aid, then translate it internally into the workflow's required prompt schema.

For full-reference mode, use the six-section structure in the reference. Write the rewritten description in English, but preserve user-provided dialogue, lyrics, and visible scene text in the original language.

Make the prompt operational:

- establish style, framing, subjects, environment, lighting, and initial state in Shot 1;
- make each important person's orientation relative to the camera explicit when identity or facial visibility matters; “watching the sunset” alone often implies a back view. State front-facing, three-quarter, profile, or back-facing, and say whether the face and eyes must remain visible;
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
- For a face-quality attempt, constrain the first shot to one face, a front or three-quarter orientation, visible eyes, stable hair/clothing anchors, and static or small-amplitude motion. Treat dialogue as a second-stage stressor. A valid MP4 with dynamic/color/audio checks can still have unusable faces; visually inspect face consistency at first/middle/last frames.
- For Chinese prompts, avoid an extremely short noun-only description. H3's long multimodal sequence can make a one- or two-token Chinese prompt easy for the seed to dominate. Add concrete subject traits, setting, framing, lighting, and motion; as a practical starting point, use roughly 30–50 Chinese characters or an equivalent amount of structured detail, then validate with a cheap preview.
- For a director-level multi-shot sequence (establishing + over-the-shoulder + reverse + reveal) where H3's single-continuous-shot limit blocks real coverage, see `references/director-sequences.md`. It covers splitting the scene into separate I2VA segments, generating consistent first-frame images with ImageGen (watermark crop, reference-image identity inheritance), locking character identity across prompts, W4A8 skin-quality phrasing, and stitching with ffmpeg `xfade`/`acrossfade`.

### 5. Generate through ComfyUI

For installation, recovery, or custom-workflow debugging, the lower-level
helpers remain available. A normal text-only request should use
`h3_fastpath.py` above:

```powershell
python scripts/h3_generate.py `
  --base-url http://127.0.0.1:8188 `
  --workflow-template h3_w4a8_t2v `
  --prompt-file prompts/current.txt `
  --comfyui <ComfyUI-path> `
  --filename-prefix video/H3Lite_my_clip `
  --run-root <ComfyUI>\user\h3lite_runs `
  --component-set auto `
  --resolve-models `
  --audio-policy auto `
  --profile fast `
  --resolution 640x352 `
  --seed 20260813 `
  --watch `
  --watch-interval 20 `
  --watch-timeout 3600 `
  --json
```

For a lower-level I2VA or FL2VA run, use the matching bundled template and
frame flags. `--workflow <file>` remains supported for custom Ref2VA or other
graphs; the same flags will bind any existing `LoadImage` reference input, or
add one when the H3 node has no connection yet:

```powershell
python scripts/h3_generate.py `
  --workflow-template h3_w4a8_i2v `
  --prompt-text "<rewritten I2VA prompt>" `
  --first-frame <path-to-first-frame.png> `
  --comfyui <ComfyUI-path> `
  --output-dir <ComfyUI>\output `
  --resolution 640x352 `
  --length 124 `
  --steps 4 `
  --component-set auto `
  --resolve-models `
  --watch `
  --json
```

This lower-level command now submits and monitors in the same foreground
process. Use `--queue-only` only when another process must own monitoring.

For the bundled multi-image Ref2VA route, repeat `--ref-image` in the order
that the prompt names `<Picture 1>`, `<Picture 2>`, and so on. The native
`MiniMaxH3ReferenceToVideo` node accepts image references in fixed order; do
not combine `--ref-image` with `--first-frame` or `--last-frame`:

```powershell
python scripts/h3_generate.py `
  --workflow-template h3_w4a8_ref2va_compat `
  --prompt-file prompts/ref2va.txt `
  --ref-image <identity.png> `
  --ref-image <scene.png> `
  --ref-image <wardrobe-or-prop.png> `
  --comfyui <ComfyUI-path> `
  --output-dir <ComfyUI>\output `
  --resolution 640x352 `
  --length 124 `
  --steps 4 `
  --component-set A `
  --resolve-models `
  --watch `
  --json
```

The Ref2VA encoder is kept resident because the installed ClipProj node's
dynamic image path is not reliable with the low-VRAM int8 encoder. Resident
mode can consume more VRAM than I2VA; preflight may therefore block an 8 GB
machine or recommend a small preview. Treat `--ref-image` as a real reference
conditioning input, not as a style-only attachment.

The native `MiniMaxH3ReferenceToVideo` node also exposes reference-video and
reference-audio inputs. The bundled fastpath deliberately exposes repeated
`--ref-image` first because that path is the most predictable to bind and
verify; use a native/custom workflow when those other reference types are
required.

```powershell
python scripts/h3_status.py `
  --base-url http://127.0.0.1:8188 `
  --prompt-id <prompt-id> `
  --comfyui <ComfyUI-path> `
  --output-dir <ComfyUI>\output `
  --run-root <ComfyUI>\user\h3lite_runs `
  --require-audio `
  --dynamic-check `
  --anchor-check `
  --compact `
  --json
```

The JSON result is compact by default; use `--verbose` only when a failed run
needs the full ComfyUI history graph. For a bounded foreground monitor, add
`--watch --watch-interval 20 --watch-timeout 3600`. A pending response has
`ok: false` and `complete: false`; only a completed, verified media response
has `ok: true`.

Do not describe a faster second run as a reused result. ComfyUI may retain model weights and reuse unchanged upstream node outputs such as encoder or VAE loading, but a changed prompt or seed still causes the sampler to generate a new video. Explain this distinction when a user asks why later runs are faster.

The accelerated bundled template contains the prompt node, W4A8 model path, 4B
ClipProj, dual VAE, Turbo LoRA, H3 sigma shifts, Sage/Sol/T8 patches, native
audio, 124 frames, 640x352, and 4 steps. The compatibility template removes
the optional Sage/Sol/T8 chain. `--resolve-models` switches the complete
registered A/B component set atomically; use `--component-set B` when both
sets are installed. Override `--seed`, `--width`,
`--height`, `--length`, `--steps`, `--fps`, `--profile`, or `--resolution` only
when needed. Prefer `--megapixels` for ComfyUI ResolutionSelector-style canvas
choices such as `16:9 0.4MP -> 864x480`. `fast` keeps Block Cache; `balanced`
uses 6 steps and bypasses Block Cache; `quality` uses 8 steps and bypasses
Block Cache. For a custom API
workflow, pass `--workflow <file>`; the prompt field can still be discovered or
selected with `--prompt-node` and `--prompt-field`.

Do not use synchronous wait mode from a terminal command with a short timeout.
`h3_fastpath.py` uses `h3_generate.py --watch` so submission and verification
stay in one bounded foreground process; use `--queue-only` only when another
process must own monitoring.

For the low-VRAM baseline, use 124 frames at 24 fps (about 5 seconds), 4 steps, `res_multistep`, and `simple`. Use 640x352 for the normal fast output; use the ComfyUI official-style 0.4MP bucket (`864x480` for 16:9) only when the planner approves the hardware/time trade-off or the user explicitly asks for it.

### 6. Verify and report

Do not report success from a queue ID alone. Confirm:

- the job completed without an execution error;
- an MP4 or other intended video file exists;
- the file has a video stream and, for native H3 output, an audio stream;
- duration, frame count, and FPS are close to the requested values;
- the first/middle/last samples are not black, flat, or classified as `suspected_mosaic`; when the user asked for an action, dynamic QA must classify the clip as `dynamic`;
- when identity, clothing, props, or a reference composition is an acceptance condition, sampled frames preserve the declared anchors and do not silently drift;
- the output path and elapsed time are reported.
- the plan's estimated range is compared with the actual ComfyUI execution time;
- the configuration fingerprint and run manifest are recorded so a retry can be distinguished from an accidental duplicate;
- the selected ComfyUI, models, custom_nodes, and output paths are recorded.

If verification returns `ffprobe_not_found`, keep the generated file and repair
only the verifier path. Set `H3LITE_FFPROBE` to an absolute `ffprobe.exe` when
the executable lives outside the bounded ComfyUI locations; do not rerun the
model merely because metadata inspection was unavailable.

When diagnosing failures, use this order:

1. critically low pagefile, unavailable RAM, or another GPU process;
2. missing model or custom node;
3. wrong model folder or filename;
4. CUDA/PyTorch/custom-kernel incompatibility;
5. out-of-memory or excessive CPU offload;
6. invalid H3 flow/audio graph;
7. prompt or reference alignment problem.

For black/mosaic output, restore the official H3 flow/sigma-shift node and simplify optional attention/cache patches. For distorted audio at 4 steps, check the H3 audio/video schedules and use the compatible H3 Turbo sampler on older ComfyUI builds.

## Video upscale (post-processing)

Super-resolution is post-processing, not another H3 generation pass: it never
changes the generation graph, adds sampling steps, or silently follows a run.
Add it only when the user explicitly asks for a target beyond the local canvas
(roughly 0.5 MP, e.g. 1080p/4K), and never promise pixel-exact consumer labels
("1080p") as model output sizes. Read
[`references/video-upscale.md`](references/video-upscale.md) for the routes,
the measured Topaz command form, model availability, and the problem table.

Rules:

- **Primary route (local machine): Topaz Video AI.** The user selects the
  enhancement model (Starlight/Astra Fast for H3-style clips, Proteus/Rhea for
  general footage), the output scale, and exports from the GUI. The runtime
  runs `neuroserver --once ... --filters [{"model": "astrafast"}]`; the exact
  command form is recorded in logs (`EventTracker: Video Export Started`)
  for diagnosis only — there is no official CLI contract, so do not tell the
  agent to script Topaz.
- **Pre-export checks:** free VRAM and competitors (`scripts/h3_vram.py
  --json`, stop only after an idle `/queue`), model presence (Astra HQ/Sharp
  and Starlight Mini are *not installed*), no stale Topaz worker processes
  before a repair run, and non-recorrupted model zips (SHA-512 vs catalog
  `zipHash`).
- **During export:** do not start another heavy CUDA job (no H3 generation on
  the same card); a 2x Starlight export of a ~210-frame clip takes on the
  order of 20 minutes at 0.3 fps while decoding.
- **After export:** ffprobe must show the expected size, 24 fps, an audio
  stream, and near-original duration; the `videoai=Enhanced using ...`
  metadata tag marks an already-enhanced file — do not upscale it again.
- **Fallbacks (scriptable, offline):** FlashVSR CLI first — a standalone
  install at `E:\FlashVSR` with its own Python env and the FlashVSR-v1.1
  model pack, driven by `cli_main.py` (`--mode tiny|tiny-long|full`,
  `--scale 2|4`, `--frame_chunk_size`, `--tile_size`/`--tile_overlap`,
  `--keep_models_on_cpu`). `run_flashvsr_best.bat` holds the validated
  recipe: `--tiled_dit --tiled_vae --tile_size 256 --tile_overlap 64
  --frame_chunk_size 50 --keep_models_on_cpu` — measured clean (2:58 for an
  8-frame slice; steady state 0.14 fps, ~7 s/frame, so ~55-60 min for a
  479-frame clip — same speed as the gridded old combo), while the old
  bat's 128/24 combo leaves grid seams and the untiled full-frame path
  is impractically slow (>4 min/frame, killed after 25 min on 8 frames). The CLI output is
  video-only (measured: input AAC dropped) — remux the source audio track
  with ffmpeg afterward. Verify `nb_frames`
  equals the input frame count: a truncated output (e.g. 100 of 479 frames)
  is a broken run, not a quality verdict. See the reference for the full
  case. Then the ComfyUI venv + 4x-UltraSharp (weight present with recorded
  SHA-256; tile to control VRAM, remux audio), and plain ffmpeg
  `lanczos + unsharp` for quick previews. Watch the 0-byte weight trap: a
  filename can be right while the file contains nothing.

## GPU memory contention with other heavy CUDA apps

A machine may host several heavy CUDA workloads at once (ComfyUI plus an
independent video tool, game streaming, another generation backend). Windows
WDDM reporting hides per-process VRAM: `nvidia-smi --query-compute-apps`
returns N/A or 0 MiB per process, while PyTorch's free-memory figure stays
optimistically high. Failures then look like CUDA OOM at tiny allocation sizes
("Tried to allocate 28.00 MiB ... 8.91 GiB free") or like a plain access
violation (Windows exit code 0xC0000005) with no OOM text at all.

Rules:

- When preflight flags a meaningful competitor or a fragile job fails at
  allocation, run `python scripts/h3_vram.py --json` to see who holds the
  VRAM; `nvidia-smi` totals alone never identify the hog.
- Confirm the competitor is idle before touching it. For ComfyUI, check
  `http://127.0.0.1:8188/queue` (running + pending empty), and remember an
  empty queue does not release resident models: the process still shows
  several GB until ComfyUI restarts or offloads.
- Never stop a ComfyUI that has queued or running items; losing a run wastes
  the whole generation.
- Gate fragile submissions with `python scripts/h3_vram.py --check-free-gb 5`.
- Read `references/gpu-contention.md` for the measured case (ComfyUI holding
  9,805 MB resident on a 16 GB card while a Topaz Video AI Starlight export
  failed at a 28 MiB VAE allocation) and the diagnostic commands.

## Bundled resources

- `references/deployment-matrix.md`: tested low-VRAM profile, official fallback profile, model folders, node roles, launch flags, and failure triage.
- `references/component-sets.md`: registered model/workflow sets, exact known byte sizes, runtime ABI record, and download-integrity rules.
- `references/prompt-writing.md`: concise operational digest of MiniMax's official H3 prompt guide and prompt-writing skill.
- `references/director-sequences.md`: end-to-end workflow for multi-segment director sequences (divide a scene into separate I2VA shots, generate consistent first frames with ImageGen including watermark crop and reference-image identity inheritance, lock character identity across prompts, W4A8 skin-quality phrasing, and stitch with ffmpeg `xfade`/`acrossfade` using the cumulative-offset formula).
- `references/agent-workflow.md`: intent routing, reference/identity anchors, five-pass prompt enhancement, and local capability boundaries.
- `references/prompt-assist.md`: optional Higgsfield-inspired prompt-pattern lookup for vague creative briefs; maps style/scene/motion/audio/negative cards back to H3 fields without adding a cloud dependency.
- `references/face-quality.md`: face-first routing, official Ref2VA identity controls, low-VRAM trade-offs, and the limits of dynamic/color QA.
- `references/gpu-contention.md`: Windows/WDDM VRAM contention between ComfyUI and other heavy CUDA apps; per-process memory via the GPU Process Memory counter, idle-queue checks, the stop/restart order, and a measured 16 GB case plus a Topaz Video AI repair appendix.
- `references/video-upscale.md`: post-process video upscale routes (Topaz Video AI primary, FlashVSR CLI at `E:\FlashVSR` as the scripted backup — run command, model pack, VRAM tier table, the measured tiled-seam grid case and fix, frame-count truncation check), 4x-UltraSharp via the ComfyUI venv, plain ffmpeg fallback), the measured Topaz export command form and lifecycle, installed/missing model list, and the problem/consequence table for contention, corrupt weights, audio, and frame-rate pitfalls.
- `assets/h3_w4a8_t2v_api.json`: reusable low-VRAM T2VA API graph based on the validated W4A8/4B/audio route.
- `assets/h3_w4a8_t2v_compat_api.json`: core T2VA graph without optional Sol Attention, Chunk Feed Forward, or T8 Block Cache nodes.
- `assets/h3_w4a8_i2v_api.json`: reusable low-VRAM I2VA graph with native first-frame input and optional acceleration patches.
- `assets/h3_w4a8_i2v_compat_api.json`: core I2VA graph with native first-frame input and no optional acceleration patches.
- `assets/h3_w4a8_ref2va_api.json`: experimental multi-image Ref2VA graph with the native `MiniMaxH3ReferenceToVideo` node.
- `assets/h3_w4a8_ref2va_compat_api.json`: compatibility Ref2VA graph without optional Sage/Sol/Chunk/T8 patches.
- `scripts/h3_doctor.py`: dependency-free hardware, disk, model, and node diagnosis.
- `scripts/h3_plan.py`: read-only hardware, resolution, time-budget, aspect-ratio, profile, and installation-path planner.
- `scripts/h3_preflight.py`: read-only pagefile/RAM/VRAM/process/model/node gate before queueing.
- `scripts/h3_generate.py`: fast template-based or custom-workflow submission with profile, resolution, prompt/settings overrides, native first/last-frame binding, atomic A/B component-set selection, and queue-only mode.
- `scripts/h3_anchor.py`: deterministic prompt/reference anchor-card generation and optional JSON declaration loading; it does not add inference or rewrite the prompt.
- `scripts/h3_status.py`: compact one-shot or bounded watch status, actual execution-time, media metadata verification, optional first/middle/last dynamic QA, advisory anchor continuity QA, and empirical timing-cache updates.
- `scripts/h3_fastpath.py`: single-entry T2V/I2V route that reuses the environment cache, probes loaded node classes, routes component sets, and keeps queueing plus bounded verification in one command.
- `scripts/h3_monitor_gui.py`: native Windows Tkinter progress window for live queue/sampling/resource/output visibility; it does not replace ComfyUI or interrupt a run.
- `scripts/h3_paths.py`: Windows path normalization for `F:/...` and Git Bash `/f/...` inputs.
- `scripts/h3_cleanup.py`: dry-run-first maintenance for old timestamped run snapshots; preserves environment state and recent runs.
- `scripts/h3_vram.py`: read-only Windows per-process dedicated-VRAM report (WDDM counter with `--query-compute-apps` fallback) and a free-VRAM gate; optional destructive `--stop <pid>` for a confirmed-idle hog.

## Sources

- Official H3 prompt guide: <https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md>
- Official H3 prompt-writing skill: <https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing>
- Official ComfyUI H3 tutorial: <https://docs.comfy.org/tutorials/video/minimax/minimax-h3>
- H3 Turbo ComfyUI nodes: <https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo>
- Cinema DNA 21:9 × 3: <https://github.com/dacnay816y62-hub/cinema-dna-21x9x3>
- Official H3 repository and prompting guidance: <https://github.com/MiniMax-AI/MiniMax-H3>
- Public agent-workflow design reference (not a runtime dependency): <https://github.com/higgsfield-ai/skills>
- Public prompt-pattern references (optional writing aid, not a runtime dependency): <https://github.com/higgsfield-ai/skills/blob/main/higgsfield-video-explainer/references/prompts.md>, <https://higgsfield.ai/ai-prompt-generator>
- Community Mac/Metal MLX port and operational notes (reference only; not a tested h3lite backend): <https://zhuanlan.zhihu.com/p/2069479566171812707>
- Community Apple Silicon local-deployment troubleshooting (reference only; not a Windows resource source): <https://mp.weixin.qq.com/s/hN60KLN7Pkpqb0pbk-r4WQ>
