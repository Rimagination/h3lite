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

H3 performance depends on the complete hardware configuration. GPU model and architecture, VRAM capacity and bandwidth, laptop power limits, system RAM, and storage all affect feasibility and speed; “8 GB VRAM” alone is not a sufficient requirement. The lowest configuration validated for the current W4A8 route is an RTX 3060 Ti with 8 GB VRAM and 16 GB system RAM; 32 GB system RAM remains the recommended target.

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

## From brief to verified clip

For complex requests, H3 Lite follows a four-stage contract: **intent route → reference/identity anchors → prompt enhancement → generation and verification**. This organization is informed by public agent-skill designs, but H3 Lite remains a local ComfyUI workflow; it does not call Higgsfield, MCP, or cloud models.

| Goal or input | Preferred route | Key decision |
|---|---|---|
| Text describes the whole clip | `T2VA` | Establish the opening state, then write the audiovisual timeline. |
| A specific opening image is supplied | `I2VA` | Anchor it at `0.00s` and describe forward motion only. |
| Both endpoints are supplied | `FL2VA` | Describe a physically continuous path between the anchors. |
| Several image/video/audio references are supplied | `Ref2VA` | Define each reference role, retention, allowed change, and forbidden drift first. |

For characters or multi-shot work, the agent builds a compact anchor sheet: stable subject and picture labels, wardrobe and prop locks, scene/light locks, permitted changes, and anti-drift constraints. The same labels are reused in the prompt, output prefix, and run manifest. If the Ref2VA checkpoint, text encoder, or workflow is not actually installed, the agent falls back to shot-based I2VA or clearly marks the route as experimental.

At runtime this sheet is written to `anchors.json` inside the task run directory, while `manifest.json` stores its path and summary. When references or multi-shot anchors exist, `h3_status.py` records advisory `anchor_qa` data by comparing first/middle/last frames with the bound images. This is an early drift signal—not face recognition—and it never replaces manual review of identity, wardrobe, markings, or composition.

Prompt enhancement happens in five passes: one-sentence intent → observable identity and scene locks → ordered actions and shots → physical camera and sound → only the few exclusions that prevent a concrete failure. The final text is translated into H3's required fields; users do not need to write the schema themselves.

When a brief is vague (for example, “make it more cinematic” or “a nice 3D animation”), the agent may read [`references/prompt-assist.md`](references/prompt-assist.md) and use Higgsfield's public prompt organization—stable style/identity locks, `SCENE`, `MOTION`, `AUDIO`, and a short `NEGATIVE` clause—as a writing scaffold. It is only an optional aid: H3 Lite does not call Higgsfield, copy its model parameters, or change the local Windows low-VRAM route. If browsing is unavailable, the agent falls back to the local H3 references.

## Showcase

These six clips use the same prompt, Set A components, LightX2V four-step LoRA, `640×352 / 124 frames / 24 fps`, and native audio. Only the acceleration-node combination changes. They represent a runnable local-generation floor and route comparison, not the final image-quality ceiling; higher resolution, more sampling steps, and LoRA-strength tuning can improve the result. Click a poster to open the native video player.

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

### Existing generated cases

The earlier red-ball, golden-retriever, and starship examples now use the same showcase page for action validation, timeline prompting, and complex temporal design.

<table>
  <tr>
    <td align="center" width="33%">
      <a href="https://rimagination.github.io/h3lite/?video=case-red-ball">
        <img src="docs/gallery/case-red-ball.jpg" width="280" alt="H3 Lite red-ball example">
      </a><br>
      <strong>Bouncing red ball</strong><br>
      Action and audio validation · 5 sec
    </td>
    <td align="center" width="33%">
      <a href="https://rimagination.github.io/h3lite/?video=case-golden-retriever">
        <img src="docs/gallery/case-golden-retriever.jpg" width="280" alt="H3 Lite golden-retriever example">
      </a><br>
      <strong>Golden retriever wakes</strong><br>
      Timeline prompt · 5 sec
    </td>
    <td align="center" width="33%">
      <a href="https://rimagination.github.io/h3lite/?video=case-starship-jump">
        <img src="docs/gallery/case-starship-jump.jpg" width="280" alt="H3 Lite starship-jump example">
      </a><br>
      <strong>Starship jump</strong><br>
      Complex timing and transitions · 8 sec
    </td>
  </tr>
</table>

The MP4 files live in the GitHub Release tagged `assets`; the repository keeps the posters and player page lightweight. Upload the matching filenames and the posters become playable from the showcase.

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

### Optional assist for vague briefs

When a user gives only a style adjective or a loose idea, first define what the audience must see by the end, then choose one observable action and one primary camera move. For example, “two men by the sea, realistic and cinematic, camera slowly circles” becomes an explicit front/three-quarter orientation, stable wardrobe and coastline, a slow eye-level 20-degree clockwise arc, and ocean/wind ambience without invented dialogue. The public website's structure is used to remove ambiguity, not to add adjectives; see [`references/prompt-assist.md`](references/prompt-assist.md) for the full template and boundaries.

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

### Image to video: sitcom living-room channel change

Download or attach the [example first frame](assets/examples/h3lite-i2va-familyguy-first-frame.png) and designate it as the first video frame. This example uses original characters and an original setting with bold outlines, flat cel colors, and exaggerated American adult-animation expressions. It demonstrates how I2VA can preserve the cast, wardrobe, and living-room composition while advancing a continuous action.

![H3 Lite I2VA sitcom living-room example first frame](assets/examples/h3lite-i2va-familyguy-first-frame.png)

Current example: `864×480 · 5 sec · 8 steps · Set A compatibility route · native audio`.

```text
Use H3 Lite to treat the image attached to this message as the first frame at 0 seconds and generate a 5-second landscape video. Preserve the original American adult-animation look, the four family members, their clothing, the living-room layout, the television position, the bold dark outlines, the flat cel colors, and the locked medium-wide composition. The father suddenly leans forward and points the remote at the television to change the channel; the mother crosses her arms and rolls her eyes; the son and daughter turn toward the father with exaggerated annoyed expressions. The TV glow flickers slightly and the popcorn bowl jiggles; end with the father proudly pointing at the screen while everyone else stares at him. Keep the television room tone, remote clicks, couch rustle, a small popcorn-bowl rattle, and brief nonverbal reactions, with light playful sitcom music and no intelligible dialogue.
```

▶️ [Play / download the 8-step sitcom living-room video](assets/examples/h3lite-i2va-familyguy-scene-864x480-8step.mp4)

### Video and audio reference: pink suit and black lamb

Download MiniMax's official [reference video](assets/examples/minimax-official-ref2va-pink-suit-black-lamb.mp4) and [male voice reference](assets/examples/minimax-official-ref2va-voice-reference.mp3), then attach both in the same message:

```text
Use H3 Lite to generate a 5-second video from the reference video and male voice sample attached to this message. Use the reference video as the visual, motion, and background-audio foundation, preserving the blond man, bright pink suit, black lamb in his arms, golden-hour pasture, distant white lambs, and original camera composition. Use only the separate male voice sample's timbre to generate new dialogue. Looking toward the camera, he naturally says, “Follow the wind, live free.” He then smiles peacefully, looks toward the horizon, and gently strokes the lamb as the camera slowly pushes in. Keep realistic motion and synchronize his lips to the English dialogue.
```

The ideas and Ref2VA assets come from MiniMax H3's official reproducible cases. Asset provenance and checksums are recorded in [`assets/examples/sources.json`](assets/examples/sources.json).

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

The bundled Ref2VA graph keeps the ClipProj encoder resident because the
installed image-reference path is not reliable in dynamic mode with the int8
encoder. This can use more VRAM than I2VA; on an 8 GB GPU, start with one
reference image and let preflight decide whether more are safe.

The native `MiniMaxH3ReferenceToVideo` node also accepts reference video and
audio. The bundled fastpath exposes the more predictable, easier-to-verify
multi-image path first; video/audio references remain available through a
native ComfyUI workflow.

## Supported inputs

| Route | Input | Best for |
|---|---|---|
| T2VA | Text prompt | Text-to-video with native H3 audio |
| I2VA | First-frame image + text | Starting from a specified image |
| FL2VA | First and last images + text | Constraining both ends of a clip |
| L2VA | Last-frame image + text | Ending on a specified image |
| Ref2VA | Multiple reference images, video, or audio | Reusing identity, style, motion, camera, or voice; experimental local multi-image graph |

Fastpath selects T2VA, I2VA, FL2VA, or L2VA from supplied first/last-frame arguments, and can select the experimental Ref2VA graph when `--ref-image` is repeated. Ref2VA still requires the matching native node, ClipProj/text encoder, and workflow to be loaded.

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

**Ref2VA does not require a separate model package.** The bundled multi-image
Ref2VA graphs reuse the selected set's W4A8 diffusion model, 4B text encoder,
ClipProj, dual VAEs, and Turbo LoRA; they add a workflow entry and reference
image binding. If those roles are already present, reuse and verify the native
`MiniMaxH3ReferenceToVideo` node instead of downloading a second “Ref2VA
checkpoint.”

### Manual skill installation

Without agent installation, open the repository page and choose **Code → Download ZIP**. Extract it, place the `h3lite` folder in the Codex skills folder, and reopen Codex.

## Watch progress without a browser

On Windows, the fastpath opens the native progress window by default. Use `--no-monitor-gui` for a terminal-only run, or `--monitor-gui` to force it on. The window reads ComfyUI's WebSocket progress channel and shows queueing, sampling, decoding, video writing, elapsed/estimated time, VRAM, RAM, pagefile, and the output path.

It does not require a browser, and closing the window does not interrupt generation. You can also open it independently; it will discover a fresh active H3 manifest:

```powershell
python scripts/h3_monitor_gui.py `
  --comfyui F:\MiniMax-H3\ComfyUI
```

The monitor reuses the manifest's ComfyUI `client_id` and understands the newer `progress_state` node events. Its track is segmented by workflow node: completed, active, and pending nodes remain distinct. The default window is `760x620` with a vertical scrollbar and mouse-wheel support, so all controls remain reachable on smaller displays. It labels node completion as structural workflow progress rather than elapsed-time progress, shows the current node's observed runtime, and keeps ETA on the empirical timing estimate. When ComfyUI has not exposed quantifiable progress, the track stays static and says why; it does not animate a fake percentage. With no active task it shows a waiting state. Stale `running` manifests are ignored during automatic discovery. Use `--once --no-websocket` for a one-shot diagnostic. The local window connects directly to ComfyUI, so an MCP bridge is not required.

## Component integrity

H3 Lite treats the diffusion model, text encoder, ClipProj, Turbo LoRA, dual VAEs, workflow, and node versions as one component set instead of mixing plausible filenames.

A Set B W4A8 checkpoint once had the correct byte size but corrupted contents and produced colored mosaic frames. H3 Lite verifies registered SHA-256 values on first use or after a file changes, then caches the result so normal reruns do not rehash large files.

## References

- [MiniMax H3 ComfyUI tutorial](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 official repository](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
- [Agent workflow reference: routing, anchors, prompt enhancement, and verification](references/agent-workflow.md)
- [Higgsfield public agent skills (design reference only, not a runtime dependency)](https://github.com/higgsfield-ai/skills)
- [Higgsfield prompt templates and generator (optional writing aid for vague briefs)](references/prompt-assist.md)
- [Complete component sets and checksums](references/component-sets.md)
- [Hardware, resolution, and deployment matrix](references/deployment-matrix.md)

## License

H3 Lite is released under the MIT License. MiniMax model weights, ComfyUI, third-party custom nodes, and upstream documentation remain subject to their respective licenses.

## Community Support

- [Linux.do](https://linux.do/)
