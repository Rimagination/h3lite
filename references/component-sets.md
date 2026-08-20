# H3 Lite component sets

## Preferred package download

For a new installation, download one complete package from the maintained
Baidu Netdisk shares before assembling files from multiple upstream sources.

| Set | Default match | Share link | Code |
| --- | --- | --- | --- |
| A | About 8 GB VRAM, low-VRAM fast route | <https://pan.baidu.com/s/1IBlH0VY7tWGvxqMtniraow> | `4hri` |
| B | 16 GB-class VRAM, FP8 compatibility route | <https://pan.baidu.com/s/1x5GGuJv0h8chApgVoDgIaQ> | `1hjx` |

Each package contains its exclusive model files, the shared VAE and ClipProj
files, the matching custom nodes, workflows, and a component manifest. Do not
mix the two packages. If a user cannot use Baidu Netdisk, fall back to the
upstream sources below while preserving the exact filenames, sizes, and hashes.

The bundled multi-image Ref2VA graphs reuse the selected set's W4A8 diffusion,
4B text encoder, ClipProj, dual VAEs, and Turbo LoRA. Ref2VA therefore has no
separate checkpoint download; verify that the native
`MiniMaxH3ReferenceToVideo` node and the resident ClipProj image path are
available before adding new files.

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
Chunk Feed Forward, and H3 T8 Block Cache node classes are loaded. Use the matching
`*_compat_api.json` template otherwise. The same component set supports the
native `MiniMaxH3ImageToVideo` first/last-frame inputs; the I2V templates do
not require a separate model download.

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

## Experimental quality route

`minimax_h3_turbo_v4_step600_ema.safetensors` is an opt-in quality candidate for
the compatibility graph only. H3 Lite rejects this LoRA when the workflow also
contains Sage/Sol/Chunk/T8 acceleration nodes: local fast-path tests showed
severe ghosting, motion trails, and color artifacts. Record v4 as a separate
quality variant and use a `*_compat_api.json` workflow. For the 4-step fast route,
use the registered LightX2V/Turbo LoRA instead.

## Runtime compatibility record

For W4A8 native quantized kernels, record all of the following together:

- NVIDIA driver version;
- Python executable actually used by ComfyUI;
- Python version;
- PyTorch version and `torch.version.cuda`;
- `comfy_kitchen` version and module path;
- ComfyUI commit/version and relevant custom-node commits;
- selected component-set ID and workflow template.

`torch 2.13.0+cu130` with CUDA 13.0 is a known-good combination on the two
reported machines. It is evidence for a validated set, not a universal rule
detached from driver, wheel, extension ABI, and node versions.

## Download integrity

Download each target through a unique `.part` file and a per-target lock. Only
rename it after size or SHA-256 validation. Never allow two downloader
processes to append to the same destination. Store source URL, expected and
actual bytes, hash when available, and completion time in the component
manifest.
