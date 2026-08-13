# H3 Lite

H3 Lite is a Codex skill for configuring and operating a local MiniMax H3
text-to-video workflow through ComfyUI. It is designed for NVIDIA laptops and
other constrained local machines, with the validated low-VRAM W4A8/4B fast
route as the default.

It combines:

- hardware-aware profile, resolution, path, and time-budget planning;
- cached environment checks with a lightweight runtime preflight;
- an API-format ComfyUI workflow for the fast route;
- official H3-style prompt structuring, including motion, camera, audio, and
  timing cues;
- compact status output, bounded monitoring, output verification, and empirical
  timing calibration.

H3 Lite does not include MiniMax model weights or a full ComfyUI installation.
Those remain separate local assets because they are large, machine-specific,
and may have their own licenses.

## Install for Codex

Clone this repository into the Codex skills directory:

```powershell
git clone https://github.com/Rimagination/h3lite.git "$env:CODEX_HOME\skills\h3lite"
```

If `CODEX_HOME` is not set, use the configured Codex skills directory directly,
for example `D:\CodexHome\skills\h3lite`. Restart or refresh Codex skill
discovery, then invoke it with `$h3lite`.

The skill can reuse an existing ComfyUI installation or configure an isolated
installation under a user-selected folder. It keeps models, custom nodes,
runtime manifests, and generated output under the selected ComfyUI root.

## Typical request

```text
请使用 $h3lite，生成一只柯基在雨夜窗边打哈欠，镜头慢慢推近，写实电影感，5 秒，分辨率为 864×480，不要对白。
```

“不要对白” means dialogue is absent; it does not imply silent output. Unless
the user explicitly requests complete silence, H3 Lite keeps the native audio
path and verifies that the resulting video contains an audio stream.

## Requirements

- Windows is the primary supported local deployment target.
- An NVIDIA GPU with CUDA support is required for the local route.
- ComfyUI, the required H3 custom nodes, and compatible W4A8/4B model assets
  must be installed or made available to the agent.
- Python and FFmpeg should be available to the ComfyUI environment.

An 8 GB laptop can use the fast low-VRAM route, but actual speed and success
depend on the driver, PyTorch/CUDA build, available RAM/pagefile, background GPU
use, and the installed model/node versions. H3 Lite measures the machine before
making a plan and records successful timings for later estimates.

## Repository layout

```text
SKILL.md                         Codex skill instructions
agents/openai.yaml               Codex display metadata
scripts/                         diagnosis, planning, generation, and QA tools
assets/h3_w4a8_t2v_api.json       bundled API-format fast workflow
references/                      deployment and prompt-writing guidance
tests/                            offline contract and safety tests
```

## Development checks

From the repository root:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m py_compile scripts/h3_doctor.py scripts/h3_preflight.py scripts/h3_plan.py scripts/h3_generate.py scripts/h3_status.py
```

## Upstream references

- [MiniMax H3 ComfyUI tutorial](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 repository](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)

## License

The H3 Lite skill code and documentation are released under the MIT License.
Third-party models, ComfyUI, custom nodes, and upstream documentation remain
subject to their respective licenses.
