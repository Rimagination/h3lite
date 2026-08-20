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

`H3 Lite` is a MiniMax H3 local video-generation skill for AI agents such as Codex and WorkBuddy. Describe the clip you want, and the agent selects a ComfyUI route, prepares the components, generates native video and audio, and verifies the result.

## Hand it to an agent in one minute

Send this to Codex or WorkBuddy:

```text
Please install H3 Lite and prepare a local MiniMax H3 video-generation environment for my computer:
https://github.com/Rimagination/h3lite
```

Initial setup time depends on model size, network, and storage speed.

Choose a non-system drive in the same request when needed:

```text
Install MiniMax H3 and ComfyUI under F:\MiniMax-H3. Reuse the environment if it is already healthy.
```

## Validated computers and default route

The primary route is Windows + NVIDIA + ComfyUI. GPU model, VRAM, system RAM, pagefile, storage, and laptop power limits affect speed. The lowest validated W4A8 configuration is an RTX 3060 Ti with 8 GB VRAM and 16 GB system RAM; 32 GB remains the recommended target.

| Validated computer | GPU | CPU / RAM | Route and memory mode |
|---|---|---|---|
| MECHREVO Yilong15Pro laptop | RTX 4070 Laptop, 8 GB | Ryzen 7 8845H / 32 GB | `LOW_VRAM`; Set A validated for T2VA/I2VA and Set B compatibility graph validated for T2VA; native audio |
| Windows 10 desktop | RTX 4060 Ti, 16 GB | i5-13400F / 32 GB | Set B; `NORMAL_VRAM`; T2VA/I2VA; native audio |

With the same Set B models, compatibility workflow, prompt, seed, and `640×352 / 124 frames / 4 steps`:

| GPU | ComfyUI execution time | Result |
|---|---:|---|
| RTX 4060 Ti 16 GB | 77.08 seconds | coherent video and native audio |
| RTX 4070 Laptop 8 GB | 591.22 seconds | coherent video and native audio |

The difference mainly comes from resident VRAM versus dynamic system-memory offload. The agent also considers RAM, storage, canvas, and time budget.

Start with `fast`: four steps, native audio, and 640×352. Use `balanced` for six steps or `quality` for eight steps.

### Set A route comparison

These six clips use the same prompt, Set A components, and `640×352 / 4 steps / native audio`; only the acceleration-node combination changes. Click a poster to open the player.

<table>
  <tr>
    <td align="center" width="33%">
      <a href="https://rimagination.github.io/h3lite/?video=seta-lightx2v-compat">
        <img src="docs/gallery/seta-lightx2v-compat.jpg" width="280" alt="Set A LightX2V compatibility baseline">
      </a><br>
      <strong>Compatibility baseline</strong><br>
      640×352 · 5 sec · native audio
    </td>
    <td align="center" width="33%">
      <a href="https://rimagination.github.io/h3lite/?video=seta-lightx2v-sage">
        <img src="docs/gallery/seta-lightx2v-sage.jpg" width="280" alt="Set A LightX2V Sage">
      </a><br>
      <strong>Sage only</strong><br>
      640×352 · 5 sec · native audio
    </td>
    <td align="center" width="33%">
      <a href="https://rimagination.github.io/h3lite/?video=seta-lightx2v-ffn">
        <img src="docs/gallery/seta-lightx2v-ffn.jpg" width="280" alt="Set A LightX2V FFN">
      </a><br>
      <strong>FFN only</strong><br>
      640×352 · 5 sec · native audio
    </td>
  </tr>
  <tr>
    <td align="center" width="33%">
      <a href="https://rimagination.github.io/h3lite/?video=seta-lightx2v-blockcache">
        <img src="docs/gallery/seta-lightx2v-blockcache.jpg" width="280" alt="Set A LightX2V Block Cache">
      </a><br>
      <strong>Block Cache only</strong><br>
      640×352 · 5 sec · native audio
    </td>
    <td align="center" width="33%">
      <a href="https://rimagination.github.io/h3lite/?video=seta-lightx2v-sol">
        <img src="docs/gallery/seta-lightx2v-sol.jpg" width="280" alt="Set A LightX2V Sol">
      </a><br>
      <strong>Sol only</strong><br>
      640×352 · 5 sec · native audio
    </td>
    <td align="center" width="33%">
      <a href="https://rimagination.github.io/h3lite/?video=seta-lightx2v-all-accel">
        <img src="docs/gallery/seta-lightx2v-all-accel.jpg" width="280" alt="Set A LightX2V full acceleration">
      </a><br>
      <strong>Full acceleration</strong><br>
      Sage + Sol + FFN + Block Cache
    </td>
  </tr>
</table>

The player uses GitHub Pages, MP4 files under `docs/videos/`, and repository posters. The `assets` Release remains available as a download backup.

## From brief to verified clip

For complex requests, H3 Lite follows: **intent route → reference/identity anchors → prompt enhancement → generation and verification**.

| Goal or input | Preferred route | Key decision |
|---|---|---|
| Text describes the whole clip | `T2VA` | Establish the opening state, then write the audiovisual timeline. |
| A specific opening image is supplied | `I2VA` | Anchor it at `0.00s` and describe forward motion only. |
| Both endpoints are supplied | `FL2VA` | Describe a physically continuous path between the anchors. |
| Several image/video/audio references are supplied | `Ref2VA` | Define each reference role, retention, allowed change, and forbidden drift first. |

For characters or multi-shot work, the agent builds an anchor sheet for subjects, wardrobe, props, scene, lighting, and permitted changes. The same labels are reused in the prompt and run manifest. Incomplete Ref2VA components route the task to I2VA or an experimental workflow.

The sheet is saved as `anchors.json`; `manifest.json` stores its path. `anchor_qa` compares first/middle/last frames with the references for continuity review.

Prompt enhancement follows: intent → identity and scene → ordered action → camera and sound → drift constraints. The result is translated into H3's required fields.

For vague briefs, use [`references/prompt-assist.md`](references/prompt-assist.md) to fill in scene, action, camera, and sound.

## Quick validation: bouncing red ball

After installation, use a simple five-second action with clear sound to verify the full pipeline:

```text
Use H3 Lite to generate a 5-second landscape video. A small matte red rubber ball bounces twice on grey concrete, then rolls out of frame to the right. Use a locked-off low-angle camera, cold overcast daylight, shallow depth of field, and a 35mm cinematic look. Keep the sounds of the ball striking the ground twice and rolling across the concrete. No music.
```

[![H3 Lite bouncing red-ball video poster](docs/gallery/case-red-ball.jpg)](https://rimagination.github.io/h3lite/?video=case-red-ball)

Click the poster to open the player.

This checks action count, motion direction, video muxing, and native audio.

## Generate with structured prompts

Organize a short-video prompt into three parts:

1. **Scene and atmosphere**: subject, environment, lighting, framing, and style.
2. **Action and camera**: actions in playback order and camera movement.
3. **Sound**: ambience, physical sound, music, or dialogue.

“No dialogue” keeps ambience and sound effects; “complete silence” disables audio.

### Optional assist for vague briefs

For a loose brief, define the visible result, one action, one camera move, and the sound bed. See [`references/prompt-assist.md`](references/prompt-assist.md).

### Timeline prompt: golden retriever wakes up

```text
Use H3 Lite to generate a 5-second video:

[0s-2s] A golden retriever puppy sleeps curled up on a sunlit wooden floor, morning light streaming through a window, dust motes floating in the air.

[2s-5s] The puppy slowly wakes up, stretches its front paws forward, yawns with a tiny squeak, then sits up and looks around with bright curious eyes as its tail starts wagging.
```

[![H3 Lite golden-retriever video poster](docs/gallery/case-golden-retriever.jpg)](https://rimagination.github.io/h3lite/?video=case-golden-retriever)

Click the poster to open the player.

Timeline segments are easier to follow than packing many ordered actions into one sentence.

### Text to video: starship jump

This eight-second T2VA example is adapted from MiniMax H3's reproducible cases:

```text
Use H3 Lite to generate an 8-second 16:9 video. On the vast, dim bridge of a starship, a short-haired female captain stands with her back to the camera before a curved observation window. A massive dark fleet waits against a deep-purple nebula. The camera slowly pushes in as the fleet's blue engines intensify. At about 3.5 seconds, cut to a close-up of the captain. The fleet suddenly jumps to hyperspace; a white flash floods the bridge, the camera shakes violently, and the captain staggers before bracing herself. As the light fades, only the empty nebula remains and she slowly closes her eyes. Keep the low bridge hum, rising engine whine, hyperspace boom, and metallic vibration, with a swelling space-opera orchestral score.
```

[![H3 Lite starship-jump video poster](docs/gallery/case-starship-jump.jpg)](https://rimagination.github.io/h3lite/?video=case-starship-jump)

Click the poster to open the player.

### Image to video: sitcom living-room channel change

Download or attach the [example first frame](assets/examples/h3lite-i2va-familyguy-first-frame.png) and designate it as the first video frame. This example uses original characters and an original setting with bold outlines, flat cel colors, and exaggerated American adult-animation expressions. It demonstrates how I2VA can preserve the cast, wardrobe, and living-room composition while advancing a continuous action.

![H3 Lite I2VA sitcom living-room example first frame](assets/examples/h3lite-i2va-familyguy-first-frame.png)

Current example: `864×480 · 5 sec · 8 steps · Set A compatibility route · native audio`.

```text
Use H3 Lite to treat the image attached to this message as the first frame at 0 seconds and generate a 5-second landscape video. Preserve the original American adult-animation look, the four family members, their clothing, the living-room layout, the television position, the bold dark outlines, the flat cel colors, and the locked medium-wide composition. The father suddenly leans forward and points the remote at the television to change the channel; the mother crosses her arms and rolls her eyes; the son and daughter turn toward the father with exaggerated annoyed expressions. The TV glow flickers slightly and the popcorn bowl jiggles; end with the father proudly pointing at the screen while everyone else stares at him. Keep the television room tone, remote clicks, couch rustle, a small popcorn-bowl rattle, and brief nonverbal reactions, with light playful sitcom music and no intelligible dialogue.
```

[![H3 Lite 8-step sitcom living-room video poster](assets/examples/h3lite-i2va-familyguy-first-frame.png)](https://rimagination.github.io/h3lite/?video=case-familyguy)

Click the poster to open the player.

### Video and audio reference: pink suit and black lamb

Download MiniMax's official [reference video](assets/examples/minimax-official-ref2va-pink-suit-black-lamb.mp4) and [male voice reference](assets/examples/minimax-official-ref2va-voice-reference.mp3), then attach both in the same message:

```text
Use H3 Lite to generate a 5-second video from the reference video and male voice sample attached to this message. Use the reference video as the visual, motion, and background-audio foundation, preserving the blond man, bright pink suit, black lamb in his arms, golden-hour pasture, distant white lambs, and original camera composition. Use only the separate male voice sample's timbre to generate new dialogue. Looking toward the camera, he naturally says, “Follow the wind, live free.” He then smiles peacefully, looks toward the horizon, and gently strokes the lamb as the camera slowly pushes in. Keep realistic motion and synchronize his lips to the English dialogue.
```

Asset provenance and checksums are recorded in [`assets/examples/sources.json`](assets/examples/sources.json).

### Ref2VA: multiple image references

Repeat `--ref-image` in the same order used by the prompt's `Picture 1`,
`Picture 2`, and `Picture 3` labels. A practical arrangement is one master
identity image plus separate scene, wardrobe/prop, or pose references. Do not
ask every image to be copied in full:

```powershell
python scripts/h3_fastpath.py `
  --comfyui F:\MiniMax-H3\ComfyUI `
  --prompt-file prompts/ref2va.txt `
  --ref-image identity.png `
  --ref-image scene.png `
  --ref-image wardrobe.png `
  --mode ref2va `
  --resolution 640x352 `
  --profile fast `
  --json
```

The bundled Ref2VA graph keeps the ClipProj encoder in `resident` mode and uses
more VRAM than I2VA. Start with one reference image on an 8 GB GPU.

The native `MiniMaxH3ReferenceToVideo` node also accepts reference video and
audio through a native ComfyUI workflow.

## Installation target and component downloads

### Choose the installation target first

| Mode | Location | Best for |
|---|---|---|
| Reuse existing | Your existing `<ComfyUI>` | Preserving an installed environment |
| Dedicated folder | For example `F:\MiniMax-H3\ComfyUI` | Recommended; keeps large files off the system drive and outside projects |
| Current project | `<project>\.h3lite\ComfyUI` | Keeping the environment with one project |

Choose the ComfyUI, model, custom-node, and output directories before downloading.

### Choose one component set

Choose one complete set. Each Baidu package contains matching models, nodes, workflows, and manifest:

| Set | Validated starting point | Link | Code |
|---|---|---|---|
| Set A | RTX 4070 Laptop 8 GB + 32 GB RAM, low-VRAM fast route | [Baidu Netdisk](https://pan.baidu.com/s/1IBlH0VY7tWGvxqMtniraow) | `4hri` |
| Set B | RTX 4060 Ti 16 GB + 32 GB RAM, FP8 compatibility route; T2VA also validated on RTX 4070 Laptop 8 GB | [Baidu Netdisk](https://pan.baidu.com/s/1x5GGuJv0h8chApgVoDgIaQ) | `1hjx` |

Merge `models` and `custom_nodes` into `<ComfyUI>`, import the workflow JSON, and keep `component-manifest.json`. Upstream filenames and hashes are in [`references/component-sets.md`](references/component-sets.md).

**Ref2VA uses the selected component set.** Its graph reuses the W4A8 model,
text encoder, ClipProj, dual VAEs, and Turbo LoRA.

### Manual skill installation

Without agent installation, open the repository page and choose **Code → Download ZIP**. Extract it, place the `h3lite` folder in the Codex skills folder, and reopen Codex.

## Watch progress without a browser

On Windows, fastpath opens the native progress window by default. Use `--no-monitor-gui` for terminal-only runs. It reads ComfyUI's WebSocket progress channel and shows queueing, sampling, decoding, video writing, time, VRAM, RAM, pagefile, and output path.

The window connects directly to ComfyUI and can also be opened independently:

```powershell
python scripts/h3_monitor_gui.py `
  --comfyui F:\MiniMax-H3\ComfyUI
```

The monitor understands `progress_state`, separates completed/active/pending nodes, and shows node time and ETA. Default size is `760x620` with a scrollbar. Use `--once --no-websocket` for diagnostics.

## Component integrity

H3 Lite manages the diffusion model, text encoder, ClipProj, Turbo LoRA, dual VAEs, workflow, and node versions as one component set. Registered Set B files receive a SHA-256 check on first use or after a change; the result is cached.

## References

- [MiniMax H3 ComfyUI tutorial](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 official repository](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
- [Agent workflow reference: routing, anchors, prompt enhancement, and verification](references/agent-workflow.md)
- [Higgsfield public agent skills (design reference)](https://github.com/higgsfield-ai/skills)
- [Higgsfield prompt templates and generator (writing aid)](references/prompt-assist.md)
- [Complete component sets and checksums](references/component-sets.md)
- [Hardware, resolution, and deployment matrix](references/deployment-matrix.md)

## License

H3 Lite is released under the MIT License. MiniMax model weights, ComfyUI, third-party custom nodes, and upstream documentation remain subject to their respective licenses.

## Community Support

- [Linux.do](https://linux.do/)
