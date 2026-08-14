# H3 Lite

<p align="center">
  <img src="assets/h3-lite-hero.gif" alt="H3 Lite — MiniMax H3 skill for local ComfyUI video generation" width="100%">
</p>

<p align="center">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-1F5E4A?style=for-the-badge">
  <img alt="Hosts Codex" src="https://img.shields.io/badge/Hosts-Codex-4B6B8A?style=for-the-badge">
  <img alt="Route Low VRAM Fast" src="https://img.shields.io/badge/Route-Low--VRAM%20Fast-D9A441?style=for-the-badge">
</p>

<p align="center">
  <a href="README.md">中文</a> | English | <a href="#references">References</a>
</p>

`H3 Lite` is a MiniMax H3 local video-generation skill for AI agents such as Codex and WorkBuddy. Describe the clip you want in natural language, and the agent selects a ComfyUI route for your computer, prepares the required components, generates native video and audio, and verifies the result.

It is designed for people new to local video generation. You do not need to learn ComfyUI nodes or manually work out how the diffusion model, text encoder, LoRA, dual VAEs, and low-VRAM settings fit together.

## Hand it to an agent in one minute

Send this to Codex or WorkBuddy:

```text
Please install H3 Lite and prepare a local MiniMax H3 video-generation environment for my computer:
https://github.com/Rimagination/h3lite
```

“One minute” means one minute to hand the task and installation target to the agent. The initial model download and setup take longer depending on the network, storage, and computer.

Choose a non-system drive in the same request when needed:

```text
Install MiniMax H3 and ComfyUI under F:\MiniMax-H3. Reuse the environment if it is already healthy.
```

## Validated computers and default route

H3 performance depends on the complete hardware configuration. GPU model and architecture, VRAM capacity and bandwidth, laptop power limits, system RAM, and storage all affect feasibility and speed; “8 GB VRAM” alone is not a sufficient requirement.

| Validated computer | GPU | CPU / RAM | Route and memory mode |
|---|---|---|---|
| MECHREVO Yilong15Pro laptop | RTX 4070 Laptop, 8 GB | Ryzen 7 8845H / 32 GB | `LOW_VRAM`; Set A validated for T2VA/I2VA and Set B compatibility graph validated for T2VA; native audio |
| Windows 10 desktop | RTX 4060 Ti, 16 GB | i5-13400F / 32 GB | Set B; `NORMAL_VRAM`; T2VA/I2VA; native audio |

With the same Set B models, compatibility workflow, prompt, seed, and `640×352 / 124 frames / 4 steps`:

| GPU | ComfyUI execution time | Result |
|---|---:|---|
| RTX 4060 Ti 16 GB | 77.08 seconds | coherent video and native audio |
| RTX 4070 Laptop 8 GB | 591.22 seconds | coherent video and native audio |

This is not a pure GPU benchmark. The RTX 4060 Ti 16 GB can keep more weights resident in VRAM, while the RTX 4070 Laptop 8 GB relies on dynamic loading and system-memory offload. The agent reads the exact GPU and VRAM, then considers system RAM, storage, target resolution, and time budget when planning a route.

Start with the highest-success `fast` route: four steps, native audio, a short clip, and a smaller canvas. Increase resolution, duration, or steps only after the baseline succeeds.

## Quick validation: bouncing red ball

After installation, use a simple five-second action with clear sound to verify the full pipeline:

```text
Use H3 Lite to generate a 5-second landscape video. A small matte red rubber ball bounces twice on grey concrete, then rolls out of frame to the right. Use a locked-off low-angle camera, cold overcast daylight, shallow depth of field, and a 35mm cinematic look. Keep the sounds of the ball striking the ground twice and rolling across the concrete. No music.
```

▶️ [Play / download the red-ball validation video](assets/examples/h3lite-red-ball-and-plant.mp4)

This checks action count, motion direction, video muxing, and native audio before you move to characters, complex actions, or larger canvases.

## Generate with structured prompts

Organize a short-video prompt into three parts:

1. **Scene and atmosphere**: subject, environment, lighting, framing, and style.
2. **Action and camera**: actions in playback order and camera movement.
3. **Sound**: ambience, physical sound, music, or dialogue.

“No dialogue” only removes speech; rain, footsteps, impacts, and ambience remain. Audio is disabled only when you explicitly request complete silence.

### Timeline prompt: golden retriever wakes up

```text
Use H3 Lite to generate a 5-second video:

[0s-2s] A golden retriever puppy sleeps curled up on a sunlit wooden floor, morning light streaming through a window, dust motes floating in the air.

[2s-5s] The puppy slowly wakes up, stretches its front paws forward, yawns with a tiny squeak, then sits up and looks around with bright curious eyes as its tail starts wagging.
```

▶️ [Play / download the golden-retriever video](assets/examples/h3lite-golden-retriever-puppy.mp4)

Timeline segments are easier to follow than packing many ordered actions into one sentence.

### Text to video: starship jump

This eight-second T2VA example is adapted from MiniMax H3's reproducible cases:

```text
Use H3 Lite to generate an 8-second 16:9 video. On the vast, dim bridge of a starship, a short-haired female captain stands with her back to the camera before a curved observation window. A massive dark fleet waits against a deep-purple nebula. The camera slowly pushes in as the fleet's blue engines intensify. At about 3.5 seconds, cut to a close-up of the captain. The fleet suddenly jumps to hyperspace; a white flash floods the bridge, the camera shakes violently, and the captain staggers before bracing herself. As the light fades, only the empty nebula remains and she slowly closes her eyes. Keep the low bridge hum, rising engine whine, hyperspace boom, and metallic vibration, with a swelling space-opera orchestral score.
```

▶️ [Play / download the starship-jump video](assets/examples/h3lite-starship-jump.mp4)

### Image to video: ramen family dinner

Download or attach H3 Lite's [ramen example first frame](assets/examples/h3lite-i2va-ramen-first-frame.jpg) and designate it as the first video frame.

![H3 Lite I2VA ramen example first frame](assets/examples/h3lite-i2va-ramen-first-frame.jpg)

```text
Use H3 Lite to treat the image attached to this message as the first frame at 0 seconds and generate an 8-second video while preserving its people, ramen, table, room, and composition. Keep the camera static. Begin with the blue-and-white ramen bowl, chashu, scallions, and rising steam in crisp foreground focus while the family remains softly blurred. Smoothly rack focus from the ramen to the family: the bowl softens, their smiles and small dining gestures become clear, and steam continues drifting through the foreground. Keep the quiet broth simmer, ceramic and chopstick clinks, and warm room tone. Add gentle acoustic guitar and koto music, with no intelligible dialogue.
```

### Video and audio reference: pink suit and black lamb

Download MiniMax's official [reference video](assets/examples/minimax-official-ref2va-pink-suit-black-lamb.mp4) and [male voice reference](assets/examples/minimax-official-ref2va-voice-reference.mp3), then attach both in the same message:

```text
Use H3 Lite to generate a 5-second video from the reference video and male voice sample attached to this message. Use the reference video as the visual, motion, and background-audio foundation, preserving the blond man, bright pink suit, black lamb in his arms, golden-hour pasture, distant white lambs, and original camera composition. Use only the separate male voice sample's timbre to generate new dialogue. Looking toward the camera, he naturally says, “Follow the wind, live free.” He then smiles peacefully, looks toward the horizon, and gently strokes the lamb as the camera slowly pushes in. Keep realistic motion and synchronize his lips to the English dialogue.
```

The ideas and Ref2VA assets come from MiniMax H3's official reproducible cases. Asset provenance and checksums are recorded in [`assets/examples/sources.json`](assets/examples/sources.json).

## Supported inputs

| Route | Input | Best for |
|---|---|---|
| T2VA | Text prompt | Text-to-video with native H3 audio |
| I2VA | First-frame image + text | Starting from a specified image |
| FL2VA | First and last images + text | Constraining both ends of a clip |
| L2VA | Last-frame image + text | Ending on a specified image |
| Ref2VA | Reference image, video, or audio | Reusing identity, style, motion, camera, or voice |

Fastpath selects T2VA, I2VA, FL2VA, or L2VA from supplied first/last-frame arguments. Ref2VA uses a workflow matched to the reference assets.

## Installation target and component downloads

### Choose the installation target first

| Mode | Location | Best for |
|---|---|---|
| Reuse existing | Your existing `<ComfyUI>` | Preserving an installed environment |
| Dedicated folder | For example `F:\MiniMax-H3\ComfyUI` | Recommended; keeps large files off the system drive and outside projects |
| Current project | `<project>\.h3lite\ComfyUI` | Keeping the environment with one project |

Before downloading large files, the agent should display the selected ComfyUI, model, custom-node, and output directories.

### Choose one component set

Do not mix Set A and Set B. The Baidu Netdisk packages contain the matching models, nodes, workflows, and manifest:

| Set | Validated starting point | Link | Code |
|---|---|---|---|
| Set A | RTX 4070 Laptop 8 GB + 32 GB RAM, low-VRAM fast route | [Baidu Netdisk](https://pan.baidu.com/s/1IBlH0VY7tWGvxqMtniraow) | `4hri` |
| Set B | RTX 4060 Ti 16 GB + 32 GB RAM, FP8 compatibility route; T2VA also validated on RTX 4070 Laptop 8 GB | [Baidu Netdisk](https://pan.baidu.com/s/1x5GGuJv0h8chApgVoDgIaQ) | `1hjx` |

Download one complete set. Merge its `models` and `custom_nodes` folders into `<ComfyUI>`, import the JSON files from `workflows`, and keep `component-manifest.json`. If Baidu Netdisk is unavailable, use the exact filenames, sizes, and hashes in [`references/component-sets.md`](references/component-sets.md) when downloading from upstream sources.

### Manual skill installation

Without agent installation, open the repository page and choose **Code → Download ZIP**. Extract it, place the `h3lite` folder in the Codex skills folder, and reopen Codex.

## Component integrity

H3 Lite treats the diffusion model, text encoder, ClipProj, Turbo LoRA, dual VAEs, workflow, and node versions as one component set instead of mixing plausible filenames.

A Set B W4A8 checkpoint once had the correct byte size but corrupted contents and produced colored mosaic frames. H3 Lite verifies registered SHA-256 values on first use or after a file changes, then caches the result so normal reruns do not rehash large files.

## References

- [MiniMax H3 ComfyUI tutorial](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 official repository](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
- [Complete component sets and checksums](references/component-sets.md)
- [Hardware, resolution, and deployment matrix](references/deployment-matrix.md)

## License

H3 Lite is released under the MIT License. MiniMax model weights, ComfyUI, third-party custom nodes, and upstream documentation remain subject to their respective licenses.

## Community Support

- [Linux.do](https://linux.do/)
