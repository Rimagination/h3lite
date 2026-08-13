# H3 Lite

<p align="center">
  <video controls autoplay loop muted playsinline width="100%" poster="assets/h3-lite-hero-poster.png" aria-label="H3 Lite — MiniMax H3 skill for ComfyUI local deployment">
    <source src="https://raw.githubusercontent.com/Rimagination/h3lite/main/assets/h3-lite-hero.mp4" type="video/mp4">
  </video>
</p>

<p align="center">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-1F5E4A?style=for-the-badge">
  <img alt="Hosts Codex" src="https://img.shields.io/badge/Hosts-Codex-4B6B8A?style=for-the-badge">
  <img alt="Route Low VRAM Fast" src="https://img.shields.io/badge/Route-Low--VRAM%20Fast-D9A441?style=for-the-badge">
</p>

<p align="center">
  <a href="#zh-cn">中文</a> | <a href="#english">English</a> | <a href="#references--参考资料">References / 参考资料</a>
</p>

<a id="zh-cn"></a>
## 中文

`H3 Lite` 是一个给 Codex/WorkBuddy 等 Agent 使用的 MiniMax H3 本地视频生成 skill。你只需要用自然语言描述想看的画面，它会根据电脑配置选择 ComfyUI 路线，准备必要组件，生成短视频并验证结果。

### 路线选择

| 路线 | 输入 | 适合场景 |
|---|---|---|
| T2VA | 文字提示 | 文生视频，保留 H3 原生声音 |
| I2VA | 一张首帧图片 + 文字提示 | 从指定画面开始生成视频 |
| FL2VA | 首帧图片 + 尾帧图片 + 文字提示 | 约束视频的起点和终点 |
| L2VA | 一张尾帧图片 + 文字提示 | 让视频收束到指定画面 |
| Ref2VA | 参考图片、视频或音频 | 需要自定义参考素材的工作流 |

I2VA、FL2VA 和 L2VA 通过 fastpath 的首帧/尾帧参数自动选择对应工作流；T2VA 直接使用文字提示。

### 一分钟开始

把下面这句话发给 Codex，Codex 会根据你的电脑准备环境并开始本地生成：

```text
请帮我安装这个 skill，并根据我的电脑配置准备本地 MiniMax H3 视频生成环境：
https://github.com/Rimagination/h3lite
```

安装位置也可以直接写进需求：

```text
请把 ComfyUI 放在 F:\MiniMax-H3\ComfyUI；如果那里已经是健康的安装，就直接复用。
```

项目内安装：

```text
请把安装放在当前项目中。
```

手动安装：打开 [H3 Lite repository](https://github.com/Rimagination/h3lite)，选择 **Code → Download ZIP**，解压后把 `h3lite` 文件夹放入 Codex 的 skills 文件夹，再重新打开 Codex。

### 快速验证

**案例 1 · 红球弹跳**

安装完成后，先用这个简单案例验证视频与声音生成：

```text
请使用 H3 Lite，生成一个 5 秒横屏视频：一颗小型哑光红色橡胶球，在灰色混凝土地面上弹跳两次，然后向右滚出画面。低机位固定镜头，阴冷的多云日光，浅景深、35mm 电影质感；保留两次撞击地面的声音和滚动声，不配音乐。
```

▶️ [播放 / 下载生成视频](assets/examples/h3lite-red-ball-and-plant.mp4)

**动作时间轴示例 · 金毛幼犬醒来**：[播放 / 下载](assets/examples/h3lite-golden-retriever-puppy.mp4)

### 以规范的提示词生成视频

下面三个想法化用自 MiniMax H3 的[可复现 768p 案例](https://github.com/MiniMax-AI/MiniMax-H3#reproducible-768p-cases)。直接把自然语言提示词交给 H3 Lite 即可；实际分辨率会根据电脑配置和你的明确要求决定。

#### 三段式提示案例

规范的短视频提示词可以按三段式来写：

1. **画面与氛围**：主体在哪里，光线、景别和风格是什么。
2. **动作与镜头**：主体发生什么变化，镜头怎样运动。
3. **声音**：环境声、动作声、音乐或对白；对白是可选项，环境声和动作声可以独立保留。

**星舰跃迁（T2VA，8 秒）**

```text
请使用 H3 Lite，生成一个 8 秒 16:9 视频：昏暗而宽阔的星舰舰桥内，一位短发女舰长背对镜头站在弧形观察窗前，窗外的深紫色星云中排列着庞大的黑色舰队。镜头先缓慢推近，舰队尾部的蓝色引擎逐渐增强；约 3.5 秒时切到舰长面部特写，舰队突然跃迁，强烈白光淹没舰桥，冲击使镜头剧烈震动，舰长踉跄后重新站稳。白光消退，窗外只剩空旷星云，她缓缓闭上眼睛。保留舰桥低沉嗡鸣、引擎蓄能声、跃迁爆响和金属震动声，配以逐渐增强的太空歌剧管弦乐。
```

▶️ [播放 / 下载生成视频](assets/examples/h3lite-starship-jump.mp4)

#### 图生视频

**拉面与家宴（I2VA，8 秒）**

先下载或直接附上 H3 Lite 的[拉面示例首帧](assets/examples/h3lite-i2va-ramen-first-frame.jpg)，明确将它指定为视频第一帧，然后发送。这张图片采用较轻量的 1280×704 画布，宽高均为 32 的倍数，比 1920×1080 官方原图更适合本地 I2VA 快速尝试。

![H3 Lite I2VA 拉面示例首帧](assets/examples/h3lite-i2va-ramen-first-frame.jpg)

```text
请使用 H3 Lite，将我在这条消息中附上的图片作为视频 0 秒的第一帧，生成一个 8 秒视频，并保持图片中的人物、拉面、餐桌和房间构图。镜头全程固定：开始时让前景的青花瓷拉面碗、叉烧、葱花和升腾的热气清晰可见，背景中的家人保持柔和虚化；随后平稳地把焦点从拉面转移到家人，拉面逐渐虚化，家人的笑容、夹菜和轻微交谈动作变得清晰，热气始终在前景飘动。保留汤汁轻微沸腾声、碗筷碰撞声和温暖的室内环境声，加入轻柔的原声吉他与古筝音乐，不要清晰对白。
```

#### 视频与声音参考

**粉色西装与黑羊（Ref2VA，5 秒）**

先下载 MiniMax 官方案例的[参考视频](assets/examples/minimax-official-ref2va-pink-suit-black-lamb.mp4)和[男声音色参考](assets/examples/minimax-official-ref2va-voice-reference.mp3)，再在同一条消息中附上这两份素材。参考视频已经包含原有背景音乐和环境声，单独的音频只用于参考男声音色。然后发送：

```text
请使用 H3 Lite，根据我在这条消息中附上的参考视频和男声音频生成一个 5 秒视频：以参考视频作为画面、动作和背景音轨基础，保留金发男子、亮粉色西装、怀中的黑色小羊、夕阳草地、远处白羊以及原有镜头构图；只参考单独男声音频的音色来生成新对白。男子看向镜头自然说：“跟着风，自由生活。”说完后露出轻松的微笑，望向远处，并轻轻抚摸黑羊的毛，镜头缓慢推近。人物口型与中文对白同步，其余画面保持写实自然。
```

以上创意和 Ref2VA 素材来自 MiniMax H3 官方可复现案例；拉面首帧使用 H3 Lite 的本地示例版本。素材来源与校验值记录在 [`assets/examples/sources.json`](assets/examples/sources.json)。

### 已验证配置与路线

默认使用已经验证过的低显存 W4A8/4B fast 路线，优先保证笔记本上的成功率和速度。

本仓库中的红球、金毛幼犬和星舰视频已在下面这台 8 GB 笔记本上实际生成；Set B 也已在一台 16 GB 台式机上跑通：

| 电脑 | GPU | CPU / 内存 | 已验证路线 |
|---|---|---|---|
| 机械革命翼龙 15 Pro 笔记本 | RTX 4070 Laptop，8 GB | Ryzen 7 8845H / 32 GB | Set A/Set B，`LOW_VRAM`，W4A8/4B，4 步，T2VA/I2VA，原生声音 |
| Windows 10 台式机 | RTX 4060 Ti，16 GB | i5-13400F / 32 GB | Set B，`NORMAL_VRAM`，W4A8/4B，4 步，T2VA/I2VA，原生声音 |

同一套 Set B 模型、工作流、提示词、seed 和 640×352 / 124 帧 / 4 步参数下，4060 Ti 16 GB 用时 77.08 秒，4070 Laptop 8 GB 用时 591.22 秒。约 7.7 倍差距主要来自 16 GB 能让模型保持 `NORMAL_VRAM`，而 8 GB 需要动态加载和内存卸载；这不是纯 GPU 算力排名，因为两台电脑的桌面/笔记本形态和运行时也不同。

其他硬件按显存档位选择路线：

| 电脑情况 | 默认建议 |
|---|---|
| NVIDIA 笔记本，约 8 GB 显存 | W4A8/4B fast，默认 640×352；更大画布交给 planner 评估 |
| 10–16 GB 显存 | fast 或 balanced；默认不加 `--lowvram`，可尝试更大画布 |
| 16 GB 以上显存 | balanced 或 quality，按驱动与已安装组件选择 |

模型权重、ComfyUI 和第三方 custom nodes 由各自项目提供；H3 Lite 负责按组件集把它们接入对应工作流。

#### 组件集

H3 Lite 提供两套完整组件集：运行时通过 `--component-set A`
或 `--component-set B` 选择一套完整组合。Set B 的兼容工作流已经实测验证，自动路线会使用它；尚未升为默认的只是 Set B 的可选 Sage/Sol/Chunk/T8 加速图。Set A 在加速节点齐全时使用 fast 工作流。

Set B 曾出现“文件大小正确但内容损坏”的 W4A8 主模型，结果是彩色马赛克。H3 Lite 会在首次使用或文件变化后校验已登记的 SHA-256，并缓存结果；正常复跑不会重复计算大文件哈希。

<a id="english"></a>
## English

`H3 Lite` is an Agent skill for Codex, WorkBuddy, and similar tools for local MiniMax H3 video generation. Describe the video you want in plain English, and it chooses a ComfyUI route from your hardware, prepares the required components, generates the clip, and verifies the result.

### Choose a route

| Route | Input | Best for |
|---|---|---|
| T2VA | Text prompt | Text-to-video with native H3 audio |
| I2VA | One first-frame image + text prompt | Starting from a specified image |
| FL2VA | First-frame and last-frame images + text prompt | Constraining both ends of a clip |
| L2VA | One last-frame image + text prompt | Ending on a specified image |
| Ref2VA | Reference image, video, or audio | Custom reference workflows |

Fastpath selects T2VA, I2VA, FL2VA, or L2VA from the supplied first/last-frame arguments. Ref2VA uses a matching custom workflow and reference assets.

### One-minute start

Start by sending this to Codex. It will prepare the environment for your computer and begin local generation:

```text
Please install this skill and prepare a local MiniMax H3 video-generation environment for my computer:
https://github.com/Rimagination/h3lite
```

Choose the installation location in the same request:

```text
Put ComfyUI at F:\MiniMax-H3\ComfyUI. Reuse it if it is already healthy.
```

### Quick validation

**Example 1 · Bouncing red ball**

After installation, start with this simple prompt to quickly validate video and audio generation:

```text
Use H3 Lite to generate a 5-second landscape video. A small matte red rubber ball bounces twice on grey concrete, then rolls out of frame to the right. Use a locked-off low-angle camera, cold overcast daylight, shallow depth of field, and a 35mm cinematic look. Keep the sounds of the ball striking the ground twice and rolling across the concrete. No music.
```

▶️ [Play / download the generated video](assets/examples/h3lite-red-ball-and-plant.mp4)

**Timeline example · Golden retriever puppy wakes up**: [Play / download](assets/examples/h3lite-golden-retriever-puppy.mp4)

### Generate video with structured prompts

These prompts are adapted from MiniMax H3's [reproducible 768p cases](https://github.com/MiniMax-AI/MiniMax-H3#reproducible-768p-cases). H3 Lite chooses the actual resolution from the machine and any explicit canvas request.

#### Three-part prompt example

Use a simple three-part structure:

1. **Scene and atmosphere**: subject, setting, lighting, framing, and style.
2. **Action and camera**: what changes and how the camera moves.
3. **Sound**: ambience, action sounds, music, or dialogue; dialogue is optional and ambience can remain active on its own.

**Starship jump (T2VA, 8 seconds)**

```text
Use H3 Lite to generate an 8-second 16:9 video. On the vast, dim bridge of a starship, a short-haired female captain stands with her back to the camera before a curved observation window. A massive dark fleet waits against a deep-purple nebula. The camera slowly pushes in as the fleet's blue engines intensify. At about 3.5 seconds, cut to a close-up of the captain. The fleet suddenly jumps to hyperspace; a white flash floods the bridge, the camera shakes violently, and the captain staggers before bracing herself. As the light fades, only the empty nebula remains and she slowly closes her eyes. Keep the low bridge hum, rising engine whine, hyperspace boom, and metallic vibration, with a swelling space-opera orchestral score.
```

▶️ [Play / download the generated video](assets/examples/h3lite-starship-jump.mp4)

#### Image to video

**Ramen family dinner (I2VA, 8 seconds)**

Download or directly attach H3 Lite's [ramen example first frame](assets/examples/h3lite-i2va-ramen-first-frame.jpg), designate it as the video's first frame, and then send. Its lighter 1280×704 canvas uses dimensions divisible by 32 and is better suited to quick local I2VA trials than the official 1920×1080 source.

![H3 Lite I2VA ramen example first frame](assets/examples/h3lite-i2va-ramen-first-frame.jpg)

```text
Use H3 Lite to treat the image attached to this message as the first frame at 0 seconds and generate an 8-second video while preserving its people, ramen, table, room, and composition. Keep the camera static. Begin with the blue-and-white ramen bowl, chashu, scallions, and rising steam in crisp foreground focus while the family remains softly blurred. Smoothly rack focus from the ramen to the family: the bowl softens, their smiles and small dining gestures become clear, and steam continues drifting through the foreground. Keep the quiet broth simmer, ceramic and chopstick clinks, and warm room tone. Add gentle acoustic guitar and koto music, with no intelligible dialogue.
```

#### Video and audio reference

**Pink suit and black lamb (Ref2VA, 5 seconds)**

Download MiniMax's official [reference video](assets/examples/minimax-official-ref2va-pink-suit-black-lamb.mp4) and [male voice reference](assets/examples/minimax-official-ref2va-voice-reference.mp3), then attach both in the same message. The reference video already contains its original music and ambient audio; the separate audio file is used only as a male voice-timbre reference. Then send:

```text
Use H3 Lite to generate a 5-second video from the reference video and male voice sample attached to this message. Use the reference video as the visual, motion, and background-audio foundation, preserving the blond man, bright pink suit, black lamb in his arms, golden-hour pasture, distant white lambs, and original camera composition. Use only the separate male voice sample's timbre to generate new dialogue. Looking toward the camera, he naturally says, “Follow the wind, live free.” He then smiles peacefully, looks toward the horizon, and gently strokes the lamb as the camera slowly pushes in. Keep realistic motion and synchronize his lips to the English dialogue.
```

The ideas and Ref2VA assets come from MiniMax H3's official reproducible cases; the ramen first frame is H3 Lite's local example version. Asset provenance and checksums are recorded in [`assets/examples/sources.json`](assets/examples/sources.json).

### Validated hardware and profiles

The default is the validated low-VRAM W4A8/4B fast route, prioritizing a reliable and reasonably fast result on laptops.

The red-ball, golden-retriever, and starship videos were generated on the validated 8 GB laptop below. Set B was also validated on a 16 GB desktop:

| Machine | GPU | CPU / RAM | Validated route |
|---|---|---|---|
| MECHREVO Yilong15Pro laptop | RTX 4070 Laptop, 8 GB | Ryzen 7 8845H / 32 GB | Set A/Set B, `LOW_VRAM`, W4A8/4B, 4 steps, T2VA/I2VA, native audio |
| Windows 10 desktop | RTX 4060 Ti, 16 GB | i5-13400F / 32 GB | Set B, `NORMAL_VRAM`, W4A8/4B, 4 steps, T2VA/I2VA, native audio |

With the same Set B models, workflow, prompt, seed, and 640×352 / 124-frame / 4-step settings, the RTX 4060 Ti 16 GB run took 77.08 seconds and the RTX 4070 Laptop 8 GB run took 591.22 seconds. The observed 7.7× gap is mainly explained by `NORMAL_VRAM` versus dynamic loading and offload under `LOW_VRAM`; it is not a pure GPU benchmark because the machines and runtimes also differ.

Select the route by VRAM:

| Machine | Default recommendation |
|---|---|
| NVIDIA laptop with about 8 GB VRAM | W4A8/4B fast, default 640×352; the planner selects larger canvases when appropriate |
| 10–16 GB VRAM | Fast or balanced; omit `--lowvram` by default and test larger canvases gradually |
| More than 16 GB VRAM | Balanced or quality, using the installed driver and components |

Model weights, ComfyUI, and third-party custom nodes come from their respective projects; H3 Lite integrates them into the selected workflow.

#### Component sets

H3 Lite provides two complete component sets. Select one with `--component-set A` or `--component-set B`. Set B's compatibility workflow is validated and selected automatically; only its optional Sage/Sol/Chunk/T8 acceleration graph is not yet the default. Set A uses the fast workflow when its acceleration nodes are loaded.

A Set B W4A8 checkpoint once had the correct byte size but corrupted contents and produced colored mosaic frames. H3 Lite verifies registered SHA-256 values on first use or after a file changes, then caches the result so normal reruns do not rehash large files.

<a id="references--参考资料"></a>
## References / 参考资料

- [MiniMax H3 ComfyUI tutorial](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 repository](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
- [Good Story README structure](https://github.com/Rimagination/good-story)
- [THU Digitizer user-first installation flow](https://github.com/Rimagination/thu-digitizer)

## License

H3 Lite is released under the MIT License. MiniMax model weights, ComfyUI, third-party custom nodes, and upstream documentation remain subject to their respective licenses.
