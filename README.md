# H3 Lite

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

`H3 Lite` 是一个给 Codex 使用的 MiniMax H3 本地视频生成 skill。它会根据你的 NVIDIA 显卡、内存、磁盘和视频要求，自动选择合适的 ComfyUI 路线，准备组件，生成短视频并检查结果。

一句话说：**你只需要用自然语言描述想看的画面，H3 Lite 会替你处理本地部署、分辨率、提示词、生成和验证。**

它默认使用已经验证过的低显存 W4A8/4B fast 路线，优先保证在笔记本上的成功率和速度；如果你的电脑和需求允许，也可以选择更高质量的路线。

### 先看这里

| 你现在想做什么 | 直接去这里 |
|---|---|
| 安装这个 skill | [一分钟开始](#一分钟开始) |
| 直接生成第一个视频 | [一句话使用](#一句话使用) |
| 只想改提示词，不想学参数 | [怎么描述视频](#怎么描述视频) |
| 了解声音和对白 | [声音规则](#声音规则) |
| 了解它会自动处理什么 | [它会替你做什么](#它会替你做什么) |
| 手动排查失败 | [常见边界](#常见边界) |

### 一分钟开始

你不需要打开命令行，也不需要先学会安装 Python、ComfyUI 或模型。把下面这句话发给 Codex：

```text
Please install this skill and help me set up a local MiniMax H3 video-generation environment:
https://github.com/Rimagination/h3lite
```

安装完成后，Codex 会检查你的电脑，并在必要时询问 ComfyUI 应该放在哪里。你可以直接用自然语言回答，例如：

```text
Use a dedicated folder at F:\MiniMax-H3\ComfyUI. Reuse it if it is already healthy.
```

如果你不想使用独立文件夹，也可以说：

```text
Keep the installation inside the current project.
```

如果你更喜欢手动安装，可以打开 [H3 Lite repository](https://github.com/Rimagination/h3lite)，选择 **Code → Download ZIP**，解压后把整个 `h3lite` 文件夹放进 Codex 的 skills 文件夹，再重新打开 Codex。

### 一句话使用

安装完成后，直接把一个英文视频提示词发给 Codex：

```text
Use H3 Lite to generate a 5-second landscape video of an orange cat yawning beside a rainy window at night. The camera slowly pushes in. Photorealistic cinematic style. No dialogue.
```

也可以直接使用这个更完整的例子：

```text
Use H3 Lite to generate a 5-second landscape video. On a wooden table beside a rainy window at night, an open vintage picture book remains still. During the first second, a breeze gently turns one page. From 1 to 3 seconds, paper streets, houses, and a miniature tram unfold layer by layer into a three-dimensional paper city with foreground, middle ground, and background. From 3 to 5 seconds, the windows light up one by one, the miniature tram moves slowly, and the camera makes a subtle push-in. Show paper fibers, creases, cut edges, layered shadows, and a miniature photography look. Delicate paper stop-motion style. No dialogue, no subtitles, and no readable text. Keep the rain, page-turning, paper mechanism clicks, and a distant miniature tram bell.
```

你不需要自己写出模型名称、节点名称、采样步数或 ComfyUI 工作流。H3 Lite 会根据电脑和要求决定这些细节。

### 怎么描述视频

最简单的提示词只要包含四件事：主体、动作、镜头和时长。下面的模板可以直接复制后替换方括号内容：

```text
Use H3 Lite to generate a [duration]-second [landscape/portrait/square] video of [subject] [action]. [Camera movement]. [Visual style].
```

如果你想让动作更稳定，可以按照时间顺序写：

```text
Use H3 Lite to generate a 5-second video. From 0 to 2 seconds, [first action]. From 2 to 4 seconds, [second action]. During the final second, [ending action]. The camera [camera movement]. [Visual style].
```

建议优先写清楚：

- **主体**：one orange cat, a red ball, a seedling, a miniature paper city
- **动作**：yawns, rolls slowly, sprouts two leaves, unfolds layer by layer
- **镜头**：slow push-in, locked-off shot, gentle pan, overhead view
- **画面**：photorealistic, cinematic, paper stop-motion, soft morning light
- **时间**：first second, from 1 to 3 seconds, during the final second
- **声音**：rain, page turns, footsteps, room tone, distant bells

分辨率可以直接写在提示词中：

```text
Use H3 Lite to generate a 5-second landscape video at 864x480 of a corgi yawning beside a rainy window at night. The camera slowly pushes in. Photorealistic cinematic style. No dialogue.
```

### 声音规则

`No dialogue` 只表示不要对白，不表示完全静音。默认情况下，H3 Lite 会保留自然环境声，并检查视频是否包含音轨。

```text
No dialogue or spoken words. Keep natural rain and room tone.
```

如果你确实需要完全静音，请明确写出来：

```text
Complete silence: no dialogue, no music, and no ambient sound.
```

如果你只是不想要文字和对白，但希望保留声音，可以这样写：

```text
No dialogue, no subtitles, and no readable text. Keep the natural environmental sounds.
```

### 它会替你做什么

H3 Lite 会把一次视频请求当成完整任务处理：

1. 检查 NVIDIA GPU、显存、内存、分页文件和磁盘空间。
2. 根据电脑配置和目标时长选择 fast、balanced 或 quality 路线。
3. 根据画幅和显存选择分辨率；你明确指定的分辨率会被保留，只提示一次风险。
4. 复用健康的 ComfyUI 和已安装组件，不重复扫描或重复提交同一个任务。
5. 按 H3 的结构整理主体、动作、镜头、时间顺序、风格和声音。
6. 生成完成后检查 MP4、画面尺寸、时长、帧数、帧率和音轨。
7. 记录实际生成耗时，让下一次预计时间更接近你的电脑真实速度。

### 默认路线和电脑要求

| 电脑情况 | 默认建议 |
|---|---|
| NVIDIA 笔记本，约 8 GB 显存 | 低显存 W4A8/4B fast，优先 640×352；明确指定大画布时会提示风险 |
| 10–16 GB 显存 | fast 或 balanced，可尝试更大画布 |
| 16 GB 以上显存 | 可以尝试 balanced 或 quality，但仍以实际组件和驱动为准 |
| 没有 NVIDIA CUDA GPU | 不承诺本地 H3 路线，改用远程 API 或其他后端 |

模型权重、ComfyUI 和第三方 custom nodes 不包含在这个仓库里。它们体积较大，并且各自有版本和许可要求；缺少组件时，Codex 会告诉你需要准备什么。

### 常见边界

- 第一次运行可能比后续运行慢，因为模型加载、CUDA 编译和低显存 CPU offload 需要额外时间。
- 低显存设备上的 864×480 仍可能较慢或触发 OOM；明确指定后 H3 Lite 不会偷偷换成更小的画布。
- 生成时间是估计范围，不是承诺；成功运行后会自动用实际耗时校准。
- 如果输出失败，先查看紧凑状态结果；只有需要排查时才让 Codex读取完整 ComfyUI history。
- H3 Lite 负责本地路线和验证，不包含 MiniMax 模型权重的再分发。

### 项目结构

```text
h3lite/
  SKILL.md                         Codex 主流程
  README.md                        中英文用户入口
  agents/openai.yaml               Codex 显示信息
  assets/h3_w4a8_t2v_api.json      fast 路线的 API 工作流
  scripts/                         诊断、规划、生成和验证脚本
  references/                      部署与提示词参考
  tests/                            离线契约与安全测试
```

`SKILL.md` 是给 agent 的主流程；普通用户只需要阅读本 README 并发送一句英文提示词。

<a id="english"></a>
## English

`H3 Lite` is a Codex skill for local MiniMax H3 video generation. It inspects your NVIDIA GPU, memory, disk, and video request, then chooses a suitable ComfyUI route, prepares the required local components, generates the clip, and verifies the output.

In one sentence: **describe the video you want in plain English, and H3 Lite handles the local setup, resolution, prompt structure, generation, and verification.**

The default is the validated low-VRAM W4A8/4B fast route. It prioritizes a reliable and reasonably fast first result on laptops; balanced and quality routes are available when the machine and time budget allow them.

### Start here

| What you want to do | Go here |
|---|---|
| Install the skill | [One-minute start](#one-minute-start) |
| Generate your first video | [One-sentence use](#one-sentence-use) |
| Write a prompt without learning parameters | [How to describe a video](#how-to-describe-a-video) |
| Understand dialogue and sound | [Audio rules](#audio-rules) |
| See what the skill handles | [What it does for you](#what-it-does-for-you) |
| Diagnose a failed run | [Boundaries](#boundaries) |

### One-minute start

You do not need to open a terminal or learn how to install Python, ComfyUI, or model files. Send this sentence to Codex:

```text
Please install this skill and help me set up a local MiniMax H3 video-generation environment:
https://github.com/Rimagination/h3lite
```

After installation, Codex will inspect your computer and ask where ComfyUI should live if a path decision is needed. For example:

```text
Use a dedicated folder at F:\MiniMax-H3\ComfyUI. Reuse it if it is already healthy.
```

Or:

```text
Keep the installation inside the current project.
```

For a manual fallback, open the [H3 Lite repository](https://github.com/Rimagination/h3lite), choose **Code → Download ZIP**, extract the `h3lite` folder into your Codex skills folder, and reopen Codex.

### One-sentence use

After installation, send one English video prompt:

```text
Use H3 Lite to generate a 5-second landscape video of an orange cat yawning beside a rainy window at night. The camera slowly pushes in. Photorealistic cinematic style. No dialogue.
```

You can also use a more detailed prompt:

```text
Use H3 Lite to generate a 5-second landscape video. On a wooden table beside a rainy window at night, an open vintage picture book remains still. During the first second, a breeze gently turns one page. From 1 to 3 seconds, paper streets, houses, and a miniature tram unfold layer by layer into a three-dimensional paper city with foreground, middle ground, and background. From 3 to 5 seconds, the windows light up one by one, the miniature tram moves slowly, and the camera makes a subtle push-in. Show paper fibers, creases, cut edges, layered shadows, and a miniature photography look. Delicate paper stop-motion style. No dialogue, no subtitles, and no readable text. Keep the rain, page-turning, paper mechanism clicks, and a distant miniature tram bell.
```

You do not need to name the model, nodes, sampler steps, or ComfyUI workflow. H3 Lite chooses those details from the machine and the request.

### How to describe a video

The shortest useful prompt contains four things: subject, action, camera, and duration.

```text
Use H3 Lite to generate a [duration]-second [landscape/portrait/square] video of [subject] [action]. [Camera movement]. [Visual style].
```

For more stable motion, describe the clip in time order:

```text
Use H3 Lite to generate a 5-second video. From 0 to 2 seconds, [first action]. From 2 to 4 seconds, [second action]. During the final second, [ending action]. The camera [camera movement]. [Visual style].
```

Useful prompt ingredients:

- **Subject:** one orange cat, a red ball, a seedling, a miniature paper city
- **Action:** yawns, rolls slowly, sprouts two leaves, unfolds layer by layer
- **Camera:** slow push-in, locked-off shot, gentle pan, overhead view
- **Look:** photorealistic, cinematic, paper stop-motion, soft morning light
- **Timing:** first second, from 1 to 3 seconds, during the final second
- **Sound:** rain, page turns, footsteps, room tone, distant bells

You can specify the canvas directly:

```text
Use H3 Lite to generate a 5-second landscape video at 864x480 of a corgi yawning beside a rainy window at night. The camera slowly pushes in. Photorealistic cinematic style. No dialogue.
```

### Audio rules

`No dialogue` means no spoken dialogue; it does not mean silence. By default, H3 Lite keeps natural environmental sound and verifies that the output contains an audio stream.

```text
No dialogue or spoken words. Keep natural rain and room tone.
```

For complete silence, say so explicitly:

```text
Complete silence: no dialogue, no music, and no ambient sound.
```

If you want sound but no words or on-screen text:

```text
No dialogue, no subtitles, and no readable text. Keep the natural environmental sounds.
```

### What it does for you

H3 Lite treats a video request as one complete task:

1. It checks the NVIDIA GPU, VRAM, RAM, pagefile, and disk space.
2. It chooses fast, balanced, or quality from the hardware and time budget.
3. It chooses a suitable resolution; an explicit resolution is preserved with one concise risk warning.
4. It reuses a healthy ComfyUI installation and skips redundant scans or duplicate submissions.
5. It structures the H3 prompt around subject, action, camera, timing, style, and sound.
6. It verifies the MP4, dimensions, duration, frame count, FPS, and audio stream.
7. It records actual generation time so future estimates fit the local machine better.

### Default route and hardware

| Machine | Default recommendation |
|---|---|
| NVIDIA laptop with about 8 GB VRAM | Low-VRAM W4A8/4B fast, usually 640×352; an explicit larger canvas triggers a risk warning |
| 10–16 GB VRAM | Fast or balanced; larger canvases may be practical |
| More than 16 GB VRAM | Balanced or quality can be tested, subject to the installed components and driver |
| No NVIDIA CUDA GPU | The local CUDA route is not promised; use a remote API or another backend |

Model weights, ComfyUI, and third-party custom nodes are not bundled. They are large, version-sensitive, and subject to their own licenses. If something is missing, Codex will explain what needs to be prepared.

### Boundaries

- The first run can be slower because models load, CUDA kernels compile, and low-VRAM CPU offload may occur.
- 864×480 can still be slow or cause OOM on low-VRAM devices; H3 Lite will not silently replace an explicit canvas with a smaller one.
- Generation time is an estimate, not a promise; successful runs update the empirical timing cache.
- For a failed run, start with the compact status result. Ask for the full ComfyUI history only when diagnosing the failure.
- H3 Lite handles the local route and verification; it does not redistribute MiniMax model weights.

### Repository layout

```text
h3lite/
  SKILL.md                         Main Codex workflow
  README.md                        Bilingual user entry point
  agents/openai.yaml               Codex display metadata
  assets/h3_w4a8_t2v_api.json      API workflow for the fast route
  scripts/                         Diagnosis, planning, generation, and QA
  references/                      Deployment and prompt-writing guidance
  tests/                            Offline contract and safety tests
```

`SKILL.md` is the agent-facing workflow. Most users only need this README and one English video prompt.

<a id="references--参考资料"></a>
## References / 参考资料

- [MiniMax H3 ComfyUI tutorial](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 repository](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
- [Good Story README structure](https://github.com/Rimagination/good-story)
- [THU Digitizer user-first installation flow](https://github.com/Rimagination/thu-digitizer)

## License

H3 Lite is released under the MIT License. MiniMax model weights, ComfyUI, third-party custom nodes, and upstream documentation remain subject to their respective licenses.
