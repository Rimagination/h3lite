# H3 Lite component sets

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

Use `h3_w4a8_t2v_api.json` only when the Sol Attention and H3 T8 Block Cache
node classes are available. Use `h3_w4a8_t2v_compat_api.json` otherwise.

## Set B — portable 16 GB candidate

This combination completed a real RTX 4060 Ti 16 GB installation and video
generation, but it is a separate route rather than an automatic replacement
for Set A.

| Role | File | Source / expected bytes |
| --- | --- | --- |
| W4A8 diffusion | `minimax_h3_fl2va_pruned_w4a8_mixed.safetensors` | `Kijai/MiniMax-H3-experimental`; 12,540,858,008 |
| Text encoder | `qwen3vl_4b_fp8_scaled.safetensors` | `Comfy-Org/Krea-2`; 5,242,467,968 |
| ClipProj | `mmh3-4b-ClipProj-celeb-mlp.safetensors` | `NicoLab28/ClipProj-MiniMax-H3`; verify repository metadata |
| Turbo LoRA | `minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_resized_avg_rank_21_bf16.safetensors` | `drbaph/MiniMax-H3-Turbo-Lora-ComfyUI`; verify repository metadata |
| Video VAE | `minimax_h3_video_vae_fp16.safetensors` | `Comfy-Org/MiniMax-H3`; 5,207,808,496 |
| Audio VAE | `minimax_h3_audio_vae_fp32.safetensors` | `Comfy-Org/MiniMax-H3`; verify repository metadata |

Pin the exact workflow and node revisions used by this set in its environment
manifest. Do not silently select it through a loose filename match.

## Experimental quality route

`minimax_h3_turbo_v4_step600_ema.safetensors` is an opt-in quality candidate.
Record it as a separate timing and quality variant. Do not make it the global
default until a same-machine comparison confirms action adherence, coherent
frames, native audio, and acceptable time.

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
