# H3 Lite component sets

## Preferred package download

For a new installation, download one complete package from the maintained
Baidu Netdisk shares before assembling files from multiple upstream sources.

| Set | Default match | Share link | Code |
| --- | --- | --- | --- |
| A | About 8 GB VRAM, low-VRAM fast route | <https://pan.baidu.com/s/1IBlH0VY7tWGvxqMtniraow> | `4hri` |
| B | 16 GB-class VRAM, FP8 compatibility route | <https://pan.baidu.com/s/1x5GGuJv0h8chApgVoDgIaQ> | `1hjx` |
| C | 16 GB Set B + Set C overlay (core 2.14 GiB; ref2va 11.25 GiB) | <https://pan.quark.cn/s/6f8f5ce9f8a6> | Quark share code `/~67293cXj30~:/` |

Each package contains its exclusive model files, the shared VAE and ClipProj
files, the matching custom nodes, workflows, and a component manifest. Do not
mix the two packages. If a user cannot use Baidu Netdisk, fall back to the
upstream sources below while preserving the exact filenames, sizes, and hashes.

Set C is an overlay, not a third standalone base. Install Set B first, merge
`H3lite_SetC_0.1.1/core/` into the ComfyUI tree, and add `ref2va/` only when
the Ref2VA route is used. The Quark share contains both folders, six workflows
and four license files in each, and a `SHA256SUMS.txt` per package; verify the
four model files before use.

The bundled multi-image Ref2VA graphs reuse the selected set's W4A8 diffusion
only when that base actually carries Ref2VA weights. This holds for Set A's
hybrid base (`..._ax1y2jp`). Set B's pure FL2VA base
(`minimax_h3_fl2va_pruned_w4a8_mixed.safetensors`) does NOT: upstream ships
FL2VA and Ref2VA as two separate transformer checkpoints, and the validated
Ref2VA route (2026-11-19, see Set C) uses the dedicated
`minimax_h3_ref2va_pruned_w4a8_mixed.safetensors` base with a Ref2VA-specific
Turbo LoRA. Verify that the native `MiniMaxH3ReferenceToVideo` node and the
resident ClipProj image path are available before adding new files, and never
assume a Ref2VA LoRA loads correctly onto an FL2VA base.

Treat each row as a versioned set. Do not freely mix a diffusion checkpoint,
text encoder, Turbo LoRA, node revision, and workflow merely because each file
loads independently. A set is validated only after it produces coherent moving
frames and the requested native audio, not merely a playable MP4.

## Set A — validated low-VRAM acceleration route

This is the current RTX 4070 Laptop 8 GB baseline and remains the default for
an already working installation.

| Role | File | Exact bytes when known |
| --- | --- | ---: |
| W4A8 diffusion | `minimax_h3_fl2va_pruned_w4a8_mixed_ax1y2jp.safetensors` | 12,540,884,878 |
| Text encoder | `qwen3vl_4b_int4_convrot.safetensors` | 2,814,694,400 |
| ClipProj | `mmh3-4b-ClipProj-celeb-mlp.safetensors` | 304,213,176 |
| Turbo LoRA | `minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors` | 314,878,200 |
| Video VAE | `minimax_h3_video_vae_fp16.safetensors` | 5,207,808,496 |
| Audio VAE | `minimax_h3_audio_vae_fp32.safetensors` | 605,254,808 |

Use `h3_w4a8_t2v_api.json` or `h3_w4a8_i2v_api.json` only when the Sage, Sol,
Chunk Feed Forward, and H3 T8 Block Cache node classes are loaded **and** their
runtime backends import in the ComfyUI interpreter: Sol attention and fused
modulation need `triton`, the KJ Sage patch needs `sageattention`. Registered
node classes alone are not sufficient. On this machine (2026-11-21) both now
import (`triton` 3.6.0 via the consented `triton-windows` install;
`sageattention` 2.2.0 via a consented community wheel, see runtime record), so
the fast templates are *runnable* — but the step-5 A/B below measured them
**slower** than Set C at the 768 production canvas, so they stay opt-in
experiments rather than the default. `h3_doctor.py` probes both imports and
`h3_fastpath.py` gates explicit fast-template requests on them; a missing
backend fails fast with the remedy. Prefer a self-pinned `h3_c_*` Set C graph
(native `BlockSparseAttention` needs no Triton/Sage) for production. Fastpath
promotes Set C automatically on a 16 GB GPU when the route, canvas, and all
assets/nodes match (0.1.1); the A/B resolver policy itself is unchanged —
`auto`/A/B stay on the validated `*_compat` graph (`COMPONENT_SET_ACCELERATION_POLICY`
after the step-5 measurement). The same
component set supports the native `MiniMaxH3ImageToVideo` first/last-frame
inputs; the I2V templates do not require a separate model download.

The command-line ID is `validated-low-vram-a` (short alias `A`).

## Set B — validated portable W4A8 route

This combination produced coherent video with native audio on both an RTX
4060 Ti 16 GB desktop in `NORMAL_VRAM` mode and an RTX 4070 Laptop 8 GB system
in `LOW_VRAM` mode. The compatibility workflow is validated; this remains a
separate route rather than an automatic replacement for Set A.

| Role | File | Source / expected bytes |
| --- | --- | --- |
| W4A8 diffusion | `minimax_h3_fl2va_pruned_w4a8_mixed.safetensors` | `Kijai/MiniMax-H3-experimental`; 12,540,858,008 |
| Text encoder | `qwen3vl_4b_fp8_scaled.safetensors` | `Comfy-Org/Krea-2`; 5,242,467,968; SHA-256 `54bd5144df0bbc25dd6ccadfcb826b521445a1b06ae5a42570bdd2974ca87094` |
| ClipProj | `mmh3-4b-ClipProj-celeb-mlp.safetensors` | `NicoLab28/ClipProj-MiniMax-H3`; 304,213,176; SHA-256 `275b389991276532d969dbb32f91ce67e170549873e61819cfec52a770660699` |
| Turbo LoRA | `minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_resized_avg_rank_21_bf16.safetensors` | `drbaph/MiniMax-H3-Turbo-Lora-ComfyUI`; 298,177,224; SHA-256 `1b85da614014024a0c9507f12558917dcc69b6adb564e716324594f401723115` |
| Video VAE | `minimax_h3_video_vae_fp16.safetensors` | `Comfy-Org/MiniMax-H3`; 5,207,808,496 |
| Audio VAE | `minimax_h3_audio_vae_fp32.safetensors` | `Comfy-Org/MiniMax-H3`; 605,254,808; SHA-256 `8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48` |

Pin the exact workflow and node revisions used by this set in its environment
manifest. Do not silently select it through a loose filename match.

The command-line ID remains `portable-16gb-b` (short alias `B`) for backward
compatibility; the word `portable` does not mean unvalidated. In `auto` mode,
H3 Lite keeps this validated set on its validated compatibility workflow until
a pinned accelerated run records the full Sage/Sol/Chunk/T8 chain. Use
`--acceleration fast` only for an intentional comparison. If both Set A and
Set B are installed, pass `--component-set A` or `--component-set B`; do not
let a filename heuristic choose between them.

The Set B diffusion checkpoint must be exactly 12,540,858,008 bytes with
SHA-256 `01aa7b92c007c599890461c325f9b7e3c96fb06c36f242f95b62f7f20e538dec`.
A historical same-size local copy was corrupted by two downloaders writing the
same destination and produced colored mosaic output. Never accept size alone.
`h3_generate.py` verifies registered Set B components on first use and stores a
path/size/mtime-bound cache under `user/h3lite_runs/_environment/`. Rehash only
when the file changes, the cache is absent, or failure recovery invalidates it.

## Set C — validated 16 GB acceleration and quality overlay (2026-11-19)

Set C is not a replacement base set; it is an overlay on top of Set B's
diffusion checkpoint, text encoder, ClipProj, and audio VAE, validated on the
RTX 4060 Ti 16 GB desktop with ComfyUI v0.46.0. It changes the video VAE, adds
two optional Turbo LoRA variants and a dedicated Ref2VA base, and pins launch
flags plus a BlockSparseAttention configuration. All numbers below come from
same-prompt controlled runs recorded in
`user/h3lite_runs/_environment/timing.json`.

| Role | File | Source / exact bytes |
| --- | --- | ---: |
| Video VAE (replaces fp16) | `minimax_h3_sol_vae_int8_convrot.safetensors` | Sol INT8 convrot; 1,988,306,504 |
| FL2VA Turbo LoRA (quality tier, replaces v1.0) | `pika_h3_flex_turbo_4step_fl2va_lite_r32.safetensors` | Pika Flex × lightx2v exact rank-concat fusion; 310,189,392 |
| Ref2VA Turbo LoRA | `pika_h3_flex_turbo_4step_ref2va_lite_r32.safetensors` | same fusion, Ref2VA variant; 310,189,392 |
| Ref2VA diffusion base (Ref2VA route only) | `minimax_h3_ref2va_pruned_w4a8_mixed.safetensors` | `Kijai/MiniMax-H3-experimental` via ModelScope; 11,770,657,048 |

Unchanged from Set B: `minimax_h3_fl2va_pruned_w4a8_mixed.safetensors`
(FL2VA routes), `qwen3vl_4b_fp8_scaled.safetensors`,
`mmh3-4b-ClipProj-celeb-mlp.safetensors`, `minimax_h3_audio_vae_fp32.safetensors`.

**RTX 50-series caveat (2026-11-25):** Set C is validated on the RTX 4060 Ti
16 GB (Ada, sm_89), not on Blackwell (sm_120). Upstream reports on RTX 5060 Ti
16 GB show W4A8/INT8 convrot H3 graphs running without errors but ignoring text
and emitting a fixed texture; comfy-kitchen 0.2.38 did not fix it, and an RTX
5090 did not reproduce it. The W4A8 bases above are therefore **unvalidated on
sm_120**. Run a two-prompt 640x352/4-step text-influence test before a final
render; if text has no effect, switch only the DiT to
`minimax_h3_fl2va_pruned_fp8_scaled.safetensors` and keep TE/ClipProj/LoRA/VAE
unchanged. Do not use the Sol fp16 VAE as the fix for this symptom; that is the
separate 128px seam issue. The doctor/preflight/generator now surface this risk
as `blackwell_quantized`. See `deployment-matrix.md` for links and procedure.

### Set C asset package (2026-11-25, Quark)

- Share: <https://pan.quark.cn/s/6f8f5ce9f8a6> (permanent; 43 entries, 13.4 GB)
- Quark share code: `/~67293cXj30~:/`
- `core/`: 15 files, 2.14 GiB — Sol INT8 VAE, Pika FL2VA LoRA, six
  `h3_c_*_api.json` workflows, license files, `SHA256SUMS.txt`.
- `ref2va/`: 15 files, 11.25 GiB — Ref2VA diffusion base, Ref2VA Pika LoRA,
  six workflows, license files, `SHA256SUMS.txt`.
- Install order: Set B first, merge `H3lite_SetC_0.1.1/core/models/*` into
  `<ComfyUI>/models/*`; add `ref2va/models/*` only when the Ref2VA route is
  used. Workflows stay in `h3-generate/assets/` (or copy the package
  `workflows/` files there). Keep `licenses/`, `NOTICE.txt`, and
  `SHA256SUMS.txt`.
- Verify each package with `sha256sum -c SHA256SUMS.txt`; the four model sizes
  are pinned in the role table above. The MiniMax community license and
  third-party licenses are included; redistribution must keep them.
- Machine check: `python scripts/h3_setc_assets.py --package <pkg> --comfyui <ComfyUI>`
  hashes the four models and writes `component_manifest.json` (share URL/code,
  roles, bytes, SHA-256, install order). `--quick` checks size only. The
  2026-11-25 staging package passed full SHA-256 verification against this table.

Pinned runtime configuration:

- Launch flags: `--fast fp16_accumulation fp8_matrix_mult cublas_ops autotune`
  (keep them on every restart; autotune pays a one-time per-shape tuning cost
  on the first run of each new resolution/length, then reuses the cache).
- ClipProjLoader: `mode=dynamic`, `type=krea2`, device `cuda:0`.
- BlockSparseAttention node: `selection=sol-attn`, `selection.tau=1.0`,
  `min_tokens=4096`, `extra_tokens=256`,
  `sink_conditioning=exact_kv_and_rows`, `dense_blocks=""`.
- Sparse `start_percent` rule: 640×352 → `0.2` (start 0.0 measured +2.8 s with
  no visible gain); 864×480 and 1344×768 → `0.0`.
- SigmaShift rule (`shift_audio=3.0` always): lightx2v turbo v1.0 graphs →
  `shift_video=12.0`; Pika FL2VA lite → `6.0`; Pika Ref2VA lite → `12.0`.
- Sampler: `res_multistep`, scheduler `simple`, 4 steps, denoise 1.0, CFG 1
  (BasicGuider). Pika lite LoRAs REPLACE the turbo LoRA at strength 1.0; never
  stack them on top of another turbo LoRA. Audio is weak below ~6 steps — this
  is inherent to the 4-step lite route, not a wiring error.
- Ref2VA node: `ref_image_size=match` (scales the reference to the generation
  pixel area; +6.1 % time vs FL2VA at 768p). `max` (2048 px short edge) is
  untested and several times slower; do not default to it. Reference images
  bind through the autogrow dotted key `"ref_images.ref_image_0": ["<node>",0]`
  and the prompt addresses them as `<Picture 1>`.

Measured ladder (124 frames @ 24 fps, seed-controlled, verified with audio):

| Tier | Config | Total seconds |
| --- | --- | ---: |
| 640×352 speed | turbo v1.0, stock fp16 VAE, no sparse | 52.68 |
| 640×352 speed | + sol-attn sparse (start 0.2) | 37.71 |
| 640×352 speed | + Sol INT8 VAE | 26.22 |
| 640×352 speed | + autotune launch flags | 22.91 |
| 864×480 quality | Pika FL2VA lite, sparse start 0.0, autotune | 42.31 |
| 1344×768 T2VA | turbo v1.0, sparse start 0.0, Sol INT8 VAE, autotune | 128.84 |
| 1344×768 I2VA | 1 first frame, Pika lite, sparse start 0.0, autotune | 145.1 (project median, n=15) |
| 1344×768 FL2VA | dual keyframe, Pika lite, autotune | 151.97 |
| 1344×768 Ref2VA | 1 reference, match, Pika lite, autotune | 161.23 |

The I2VA row is the same graph as FL2VA minus the `last_frame` anchor; it is
registered as `h3_c_i2va768`. Re-verified through the plugin template on
2026-11-21 at 768×1344 / 124 frames / seed 20261122: 159.43 s, 124 frames /
5.167 s / 24 fps, video+audio present, first-frame similarity 0.995. The
low-VRAM `h3_w4a8_i2v_compat` graph measured 369.45 s on the same canvas and
frame count because it has no sparse attention and decodes with the stock fp16
VAE — use the Set C I2VA template for 768p single-first-frame work.

T2VA 768p (`h3_c_t2va768`): the speed640 stack (turbo v1.0 LoRA,
Sol INT8 VAE, native sparse) at 1344×768 / 124 f / 4 steps measured 128.84 s,
verified 124 f / 24 fps / audio. Sparse must start at 0.0 at this canvas: reusing
speed640's `start_percent=0.2` leaves the first 768p step dense and measured
198.35 s. The bundled `h3_w4a8_t2v` (Sage+Sol+Chunk+T8 resolved to set B, same
4 steps, same prompt/seed) measured 185.14 s and its BlockCache recorded zero
skips at 4 steps, so the Set C template is ~30% faster without Triton/Sage and is
the 768p T2VA recommendation; `h3_w4a8_t2v` stays as the low-VRAM `_compat`
fallback and cross-check. QA strip of the 0.0 run is clean (no ghosting or trails);
cross-route MAD is real output difference from the different LoRA, not a defect.

VAEDecode alone at 864×480 dropped from 23.3 s (stock fp16 VAE) to 3.4 s
(Sol INT8). The Sol VAE is the single largest free-quality/speed win; adopt it
before touching samplers or step counts.

Template and resolver policy: Set C workflows are SELF-PINNED assets
(`h3_c_speed640_api.json`, `h3_c_t2va768_api.json`, `h3_c_quality864_api.json`,
`h3_c_i2va768_api.json`,
`h3_c_fl2va768_api.json`, `h3_c_ref2va768_api.json`). They are deliberately NOT
registered in `COMPONENT_SETS`, because on a machine with B and C files both
present, `auto` substitution would become ambiguous and an explicit
`--component-set A/B` would rewrite unet/clip/lora and silently break the Pika
or Ref2VA pairing. Run Set C templates with `auto` (all configured files exist,
so the resolver returns no overrides) or without `--resolve-models`. Never
pass `--component-set B` to a Set C graph.

Automatic 16 GB routing (0.1.1): `h3_fastpath.py` now promotes Set C ahead of
A/B without an explicit `--workflow-template`, but only inside the measured
matrix and only when every dependency is present. Conditions: detected VRAM
≥15.5 GB, `--component-set auto` (default), `--workflow-template auto`
(default), and acceleration not pinned to `compat`; `/object_info` must list
the required node classes and the model names must exist in the ComfyUI model
folders. Matching canvases (portrait equivalents included):

| Route | Canvas | Auto template |
| --- | --- | --- |
| T2VA | 640×352 | `h3_c_speed640` |
| T2VA | 864×480 | `h3_c_quality864` |
| T2VA | 1344×768 | `h3_c_t2va768` |
| I2VA | 1344×768 | `h3_c_i2va768` |
| FL2VA | 1344×768 | `h3_c_fl2va768` |
| Ref2VA | 1344×768 | `h3_c_ref2va768` |

Everything else falls back to the registered A/B resolver: L2VA, unmeasured
canvases (for example 960×544 or 864×480 I2VA), a missing file/node, an 8 GB
GPU, an explicit `--component-set A/B`, an explicit `--workflow-template`, or
`--acceleration compat`. The fastpath plan records `workflow_template_selection`
(`set-c-auto` / `registered-set` / `explicit`) and a `set_c_auto` decision with
the reason, so `--dry-run` shows exactly why C was or was not chosen. Auto
routing never downloads assets and never writes a different component set into
the template; `h3_c_*` templates still submit with `component_set=auto`.

## Pitfalls recorded during Set C validation

- ComfyUI V3 autogrow inputs MUST use dotted, group-prefixed keys
  (`ref_images.ref_image_0`). A flat `ref_image_0` passes prompt validation but
  raises `TypeError: ... unexpected keyword argument 'ref_image_0'` at execute
  time; the job fails before sampling, so check `/history` `status.executed`
  rather than assuming GPU time was spent.
- FL2VA and Ref2VA are separate transformer bases upstream. A Ref2VA LoRA on
  an FL2VA base is not a validated combination; the Set A hybrid base is the
  only exception where one checkpoint serves both routes.
- `h3_status.py` can transiently report failure right after a run finishes
  (output-file race). Re-verify via `/history` and direct
  `verify_outputs`/`dynamic_video_quality` before declaring a run failed.
- SaveVideo with prefix `video/H3Lite` may write to the output ROOT on some
  builds; locate outputs by filename pattern, not only by the prefix folder.
- Pika lite LoRAs are exact rank-concat fusions of Pika Flex and lightx2v
  turbo. Treat each as a complete replacement at strength 1.0; stacking or
  partial strength reintroduces the artifacts the fusion was built to avoid.
- Autotune first-run cost is per shape. Budget one warm-up run per new
  resolution before recording steady-state timings; the timing ledger entries
  for Set C are steady-state values.
- Lengths beyond the trained range can DEADLOCK, not merely degrade. A
  481-frame (20 s) 1344×768 FL2VA run with BlockSparse sol-attn spun a kernel
  forever: GPU 100% at ~48 W, memory-controller util ~1%, no websocket
  `progress` events, server CPU delta 0 over 8 s. Real sampling on this card
  draws ~140-165 W — low power at 100% util is the spin-stall signature.
  `/interrupt` cannot break a kernel-internal deadlock; restart the server.
  Keep `--length` within 124-362 (`h3_generate.py` rejects >362). For ~20 s
  films chain two 243-frame segments (validated 2026-11-19: 436.8 s first run
  at the new shape, 427.2 s second) and xfade 0.5 s; native dialogue written
  into each segment's prompt timeline keeps speech joint with video.
- Server restarts must use the ComfyUI venv python. The system python lacks
  `yaml`, so `main.py` dies at `from app import governance` before binding.

### Sol VAE 128-pixel seams (2026-11-25)

The Sol INT8 video VAE can leave a fixed spatial grid in the decoded frames.
Measured on a 1344×768 / 124-frame Set C Ref2VA run:

- x=128n luma-step ratio 1.369×, y=128n 1.643×; x exceeded the threshold in
  124/124 frames, y in 123/124. v2/v3 with the same VAE showed the same period.
- The decoder uses 16×16-token local windows with a half-window shift; this
  maps to the observed 128 px main grid and 64 px half-shift. It is not tiled
  VAEDecode and not the player/H.264 geometry.
- ComfyUI #17429 reports the same VAE/coordinates; Sol fp16 has the same seam,
  so switching to Sol fp16 is not a fix. Native sparse attention is a secondary
  suspect, not the primary cause.
- Single-variable fix: keep prompt, references, seed, canvas, frames, steps,
  LoRA, shifts, sparse attention and audio VAE fixed; change only the video VAE
  to `minimax_h3_video_vae_fp16.safetensors`. Measured x −13.5%, y −27.2%,
  y thin-line 1.359× → 0.996×.

Policy: treat Sol INT8 as the speed/preview VAE. For final delivery on smooth
backgrounds, large color fields or stage-like sets, run
`h3-post/scripts/h3_grid_check.py`; if `suspected`, do the one-variable fp16 VAE
A/B. Use `h3_generate.py --video-vae minimax_h3_video_vae_fp16.safetensors`
instead of hand-editing the API graph.

## Experimental quality route

`minimax_h3_turbo_v4_step600_ema.safetensors` is an opt-in quality candidate.
H3 Lite rejects this LoRA on accelerated graphs (Sage/Sol/Chunk/T8 **and native
`BlockSparseAttention`**) **below 6 steps**: local A/B on 2026-11-21 (same prompt,
seed and first frame, 768x1344 x 124f) showed severe ghosting, motion trails and
color artifacts at 4 steps on both the sparse and the dense graph, while 6 and 8
steps were clean on both. The ghosting is a 4-step distillation mismatch, not an
inherent v4 incompatibility, so the guard is keyed on step count: at >= 6 steps
the pairing is allowed (measured 175.32 s sparse-6, 227.96 s sparse-8, 454.82 s
dense-6; sparse is ~2.6x faster than dense at equal steps). At 4 steps use a
`*_compat_api.json` workflow for v4, or the registered LightX2V/Turbo LoRA for the
fast route. The >= 6-step allowance is measured on native BlockSparseAttention
and dense attention. Triton is now installed (see runtime record), but the
Triton-dependent Sage/Sol kernels paired with v4 at >= 6 steps remain unverified
on this machine; ScheduledSol was only A/B'd at 4 steps on the 640 canvas.

## Runtime compatibility record

For W4A8 native quantized kernels, record all of the following together:

- NVIDIA driver version;
- Python executable actually used by ComfyUI;
- Python version;
- PyTorch version and `torch.version.cuda`;
- `comfy_kitchen` version and module path;
- whether `triton` and `sageattention` import in that interpreter (Sol / fused
  modulation and the KJ Sage patch raise at execute time without them);
- ComfyUI commit/version and relevant custom-node commits;
- selected component-set ID and workflow template.

`torch 2.13.0+cu130` with CUDA 13.0 is a known-good combination on the two
reported machines. It is evidence for a validated set, not a universal rule
detached from driver, wheel, extension ABI, and node versions.

Measured 2026-11-21 on the RTX 4060 Ti 16 GB desktop, in two states:

1. Before the Triton install the ComfyUI venv (`venv\Scripts\python.exe`,
   Python 3.12.4, torch 2.13.0+cu130) had **neither `triton` nor
   `sageattention`**. `MiniMaxH3FusedModulation` and
   `MiniMaxH3ScheduledSolAttentionPatch` raised `RuntimeError: ... requires the
   installed Triton runtime` / `requires Triton; the Sol Triton backend failed to
   import`, and the KJ Sage patch raised `sageattention is not new enough version or
   could not determine CUDA architecture`.
2. After installing `triton-windows 3.6.0.post26` (triton 3.6.0, matching
   sol-attn's verified version) with user consent, both Sol nodes execute.
   `sageattention` was still absent at that point, so the bundled `h3_w4a8_*`
   fast templates (which contain Sage **and** Sol nodes) still resolved to
   `*_compat` under `auto`, and an explicit fast request still failed fast with
   the missing-backend message.
3. After installing `sageattention 2.2.0` (community Windows wheel
   `sageattention-2.2.0+cu130torch2.10.0andhigher.post6-cp310-abi3-win_amd64.whl`,
   woct0rdho/SageAttention release `v2.2.0-windows.post6`, sha256
   `1635283f5c01ec3cda58a784d0d7eabbcaffaf9511d1b263db4750e1ed7958bb`, same author
   as the installed triton-windows) with user consent, the KJ Sage gate passes
   (`get_cuda_arch_versions()` -> `sm89`, a real `sageattn` call returns finite
   fp16). `h3_doctor.py` now reports `runtime_compatibility: ready` with zero
   warnings. The fast templates become runnable, but the step-5 A/B below shows
   they are slower than Set C at the production canvas, so they remain opt-in.
   `auto` is unchanged: `COMPONENT_SET_ACCELERATION_POLICY` pins auto/A/B to
   `compat` (step-5 guard), so installing the backends cannot flip auto onto the
   slower chain; Set C is reached via explicit `h3_c_*` templates or the
   measured-canvas 16 GB auto-router added in 0.1.1.

The only acceleration used in production remains native `BlockSparseAttention`
(comfy-kitchen) + Sol INT8 VAE + the
`--fast fp16_accumulation fp8_matrix_mult cublas_ops autotune` launch flags;
`MiniMaxH3ChunkFeedForward` and `MiniMaxH3BlockCacheT8` are pure torch and need no
Triton.

### Triton-route A/B findings (2026-11-21, 640x352x124f, 4 steps)

Full evidence table and strips: workspace `accel_ab/RESULTS_triton_ab.md`.

- **FusedModulation gives no steady-state gain at the 640 canvas, ~10% at the
  768 production canvas.** Per-step tqdm times (step 2 onward) at 640x352x124f
  are ~3.9-4.9 s/step with and without it. At 1344x768x124f I2VA with the v4
  LoRA at 6 steps: base steady 30.81 s/step vs fused warm 27.85 s/step
  (~9.6% sampling gain, ~17.8 s over 6 steps; wall 228.26 s -> 188.45 s, the
  remainder of the wall gap is load/init noise). Wall-clock differences of 10+ s
  between runs at 640 are model-load / first-step init noise, not fusion gain;
  always compare steady per-step times, never manifest `elapsed_seconds`, when
  judging an attention/modulation patch. Because the gain is modest and the
  node needs the local compat shim below plus a per-session Triton JIT cold
  tax, FusedModulation is an **opt-in experimental component, not part of any
  bundled template**: a bundled graph containing it would TypeError on
  machines without the shim.
- **ScheduledSol (tau 1.30->0.80 cosine, dense first 20%) is 1.3-1.9x slower**
  than native BlockSparseAttention here (sampling compute 23-34 s vs 17.5-18.4 s)
  with comparable clean quality. Do not adopt it as the default sparse backend
  on 16 GB Ada at these token counts; its memory-efficiency value shows up only
  at much larger sequences or tighter VRAM.
- **The native sparse kernel is nondeterministic run-to-run.** Same seed, same
  graph, fresh server instances, autotune OFF: base-vs-base mean frame MAD
  ~11.8 (high-frequency texture only; composition and motion identical).
  Therefore same-seed pixel equality is NOT a valid correctness criterion on
  the native sparse route. Prove patch exactness on a deterministic attention
  route instead: on ScheduledSol, fused vs non-fused was pixel-identical
  (MAD 0.0000 over all 124 frames).
- **Local third-party compat shim required for fused + native sparse.** Core
  0.46 passes an `attention` override into the block forward only when a
  `dit/double_block` replace wrapper exists (`comfy/ldm/minimax/model.py:315,663`),
  which is exactly what `BlockSparseAttention` registers
  (`comfy_extras/nodes_sparse_attention.py:317,345`). sol-attn v0.6.1/v0.6.2's
  fused forward lacks that parameter and raises `TypeError: ... unexpected
  keyword argument 'attention'`. The local shim adds `attention=None`, uses
  `block.attn if attention is None else attention`, and forwards the override
  into both fallback calls. Ignoring the parameter instead of using it would
  silently drop the sparse override and run dense. Backup of the unpatched
  file: workspace `accel_ab/sol_minimax_v061_original.py`; revert by restoring
  it and restarting ComfyUI. Upstream main has no fix for this signature.
- **A/B cache trap.** ComfyUI v0.46 caches nodes by upstream output content;
  renaming a downstream node id (e.g. BasicScheduler 9->90) does NOT force the
  sampler to recompute (same-session repeat returned in ~2 s). Force a fresh
  compute by restarting the server between runs or by changing a semantic
  input; a "repeat" that returns in seconds is a cache hit, not a measurement.

### Sageattention install + bundled-fast vs Set C A/B (2026-11-21, 768x1344x124f)

Full evidence table and strips: workspace `accel_ab/RESULTS_triton_ab.md` (§4);
runner `accel_ab/run_ab_sage.sh`, QA `accel_ab/qa_sage.py`, steady parse
`accel_ab/parse_steady.py`. Canvas 768x1344 (WIDTHxHEIGHT, portrait to match the
JOJO first frame), 124 f, seed 20261121, identical first frame + prompt.

| Run | Route | Steps | Steady s/it (step 2+) | Wall s |
| --- | --- | --- | --- | --- |
| fast6 | bundled `h3_w4a8_i2v` (Sage+Sol+ChunkFF+BlockCache, v4 LoRA, fp16 VAE, shift 12) | 6 | 35.40 | 280.53 |
| setC6 | Set C `h3_c_i2va768` (native sparse, pika LoRA, Sol INT8 VAE, shift 6) | 6 | 28.80 | 225.99 |
| setC4 | Set C `h3_c_i2va768` production default | 4 | 28.00 | 141.50 |

- **The bundled fast route is ~23% slower per step than Set C at the production
  canvas** (35.40 vs 28.80 s/it at equal 6 steps), and ~2x slower in wall time
  than Set C's 4-step default (280.53 vs 141.50 s). The v4 guard forces the fast
  graph to >=6 steps, so it cannot use the cheaper 4-step schedule.
- **BlockCache never skipped a step** on this content: every step logged
  `Block Cache - refresh` with video_diff 0.22-0.45, above the 0.12 threshold, so
  its skip benefit did not materialize at 6 steps; the Sol-Triton + Sage overhead
  outweighs it. Consistent with step 3 (Sol-Triton slower than native sparse).
- **Quality is a wash.** Contact sheets for all three runs are clean (consistent
  characters, coherent action, no ghosting). Cross-route frame MAD fast6-vs-setC6
  is ~40.7, but that reflects genuinely different LoRA/attention/shift outputs,
  not kernel noise; it is not a defect signal. Judge quality visually here.
- **Verdict: keep Set C (native `BlockSparseAttention` + Sol INT8 VAE) as the
  production default; do NOT promote the bundled `h3_w4a8_*` fast graphs.**
  sageattention 2.2.0 is now installed as an optional enabler (fast graphs become
  runnable for experimentation or other canvases), not as a speed win on this
  card at this canvas. `auto` remains on the validated compat graph: after this
  measurement `COMPONENT_SET_ACCELERATION_POLICY` pins auto/A/B to `compat`, so
  installing the backends cannot flip auto onto the slower chain; the fast graphs
  are opt-in via `--acceleration fast` or an explicit `h3_w4a8_*` template, and
  Set C is reached via explicit `h3_c_*` templates or the 0.1.1 auto-router
  (measured canvases on a 16 GB GPU only).
- **Methodology traps hit and fixed.** (a) `--resolution` is WIDTHxHEIGHT; the
  JOJO first frame is portrait 768x1344, so a landscape override distorts it —
  match the canvas orientation to the reference frame. (b) `--output-dir` must be
  the ComfyUI output root: h3_generate verifies at `<output-dir>/video/...` and
  does not copy from ComfyUI's own output dir, so pointing it elsewhere yields
  `exists=false / audio_ok=false / verification_failed` even when the render on
  disk is correct (portrait, 124 f, audio present). Verify such runs by probing
  the ComfyUI output mp4 directly.

## Download integrity

Download each target through a unique `.part` file and a per-target lock. Only
rename it after size or SHA-256 validation. Never allow two downloader
processes to append to the same destination. Store source URL, expected and
actual bytes, hash when available, and completion time in the component
manifest.
