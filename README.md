# H3 Lite

<p align="center">
  <img src="assets/h3-lite-hero.png" alt="H3 Lite — MiniMax H3 skill for ComfyUI local deployment" width="100%">
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

`H3 Lite` 是一个给 Codex 使用的 MiniMax H3 本地视频生成 skill。你只需要用自然语言描述想看的画面，它会根据电脑配置选择 ComfyUI 路线，准备必要组件，生成短视频并验证结果。

### 一分钟开始

不需要打开命令行，也不需要先学习 Python、ComfyUI 或模型安装。把下面这句话发给 Codex：

```text
请帮我安装这个 skill，并根据我的电脑配置准备本地 MiniMax H3 视频生成环境：
https://github.com/Rimagination/h3lite
```

如果需要指定安装位置，可以继续说：

```text
请把 ComfyUI 放在 F:\MiniMax-H3\ComfyUI；如果那里已经是健康的安装，就直接复用。
```

也可以说：

```text
请把安装放在当前项目中。
```

不想使用 agent 时，可以打开 [H3 Lite repository](https://github.com/Rimagination/h3lite)，选择 **Code → Download ZIP**，解压后把 `h3lite` 文件夹放入 Codex 的 skills 文件夹，再重新打开 Codex。

### 生成一个 5s 的视频

安装完成后，直接发送这句中文提示词：

```text
请使用 H3 Lite，生成一个 5 秒横屏视频：雨夜窗边，一只橘猫轻轻打哈欠，镜头慢慢推近，写实电影感。不要对白，但保留雨声和室内环境声。
```

你也可以指定画布：

```text
请使用 H3 Lite，生成一个 5 秒横屏视频，分辨率为 864×480：雨夜窗边，一只柯基轻轻打哈欠，镜头慢慢推近，写实电影感。不要对白，但保留雨声。
```

不需要自己填写模型名称、节点名称、采样步数或 ComfyUI 工作流。`H3 Lite` 会根据电脑和要求决定这些细节。

### 默认路线和电脑要求

默认使用已经验证过的低显存 W4A8/4B fast 路线，优先保证笔记本上的成功率和速度。

| 电脑情况 | 默认建议 |
|---|---|
| NVIDIA 笔记本，约 8 GB 显存 | W4A8/4B fast，通常选择 640×352；明确指定更大画布时会提示风险 |
| 10–16 GB 显存 | fast 或 balanced，可尝试更大画布 |
| 16 GB 以上显存 | 可以尝试 balanced 或 quality，仍以实际驱动和组件为准 |
| 没有 NVIDIA CUDA GPU | 不承诺本地 H3 路线，改用远程 API 或其他后端 |

模型权重、ComfyUI 和第三方 custom nodes 不包含在仓库中。它们体积较大，并且各自有版本与许可要求；缺少组件时，Codex 会告诉你需要准备什么。

### 常见问题

**需要懂代码吗？**

不需要。普通用户只需安装 skill，然后用自然语言描述视频。

**“不要对白”是不是完全静音？**

不是。`不要对白` 只表示没有 spoken dialogue；默认仍保留雨声、脚步声、室内环境声等自然音效。需要完全静音时，请明确说“完全静音，不要对白、音乐和环境声”。

**可以自己指定分辨率吗？**

可以。H3 Lite 会提示 OOM 或耗时风险，但不会偷偷替换你明确指定的画布。

**第一次为什么可能比较慢？**

第一次运行可能需要加载模型、编译 CUDA 内核或进行低显存 CPU offload。成功运行后，H3 Lite 会记录实际耗时，用于改进下一次估计。

**没有 NVIDIA 显卡可以用吗？**

本地 CUDA 路线不承诺支持；可以改用远程 API 或其他视频生成后端。

<a id="english"></a>
## English

`H3 Lite` is a Codex skill for local MiniMax H3 video generation. Describe the video you want in plain English, and it chooses a ComfyUI route from your hardware, prepares the required components, generates the clip, and verifies the result.

### One-minute start

You do not need to open a terminal or learn Python, ComfyUI, or model installation. Send this to Codex:

```text
Please install this skill and prepare a local MiniMax H3 video-generation environment for my computer:
https://github.com/Rimagination/h3lite
```

To choose the installation location, say:

```text
Put ComfyUI at F:\MiniMax-H3\ComfyUI. Reuse it if it is already healthy.
```

### Generate a 5-second video

```text
Use H3 Lite to generate a 5-second landscape video of an orange cat yawning beside a rainy window at night. The camera slowly pushes in. Photorealistic cinematic style. No dialogue, but keep the rain and indoor room tone.
```

### Default route and hardware

The default is the validated low-VRAM W4A8/4B fast route, prioritizing a reliable and reasonably fast result on laptops.

| Machine | Default recommendation |
|---|---|
| NVIDIA laptop with about 8 GB VRAM | W4A8/4B fast, usually 640×352; an explicit larger canvas triggers a risk warning |
| 10–16 GB VRAM | Fast or balanced; larger canvases may be practical |
| More than 16 GB VRAM | Balanced or quality can be tested, subject to the driver and installed components |
| No NVIDIA CUDA GPU | Use a remote API or another backend instead of the local CUDA route |

Model weights, ComfyUI, and third-party custom nodes are not bundled. They are large, version-sensitive, and subject to their own licenses.

### FAQ

**Do I need to know how to code?**

No. Install the skill and describe the video in plain language.

**Does “No dialogue” mean complete silence?**

No. It removes spoken dialogue but keeps natural environmental sound by default. Ask for complete silence if you want no dialogue, music, or ambient sound.

**Can I specify a resolution?**

Yes. H3 Lite keeps an explicit canvas and gives one concise OOM or time warning.

**Why can the first run be slower?**

Models may need to load, CUDA kernels may compile, and low-VRAM CPU offload may occur. Successful runs update the empirical timing estimate.

<a id="references--参考资料"></a>
## References / 参考资料

- [MiniMax H3 ComfyUI tutorial](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 repository](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
- [Good Story README structure](https://github.com/Rimagination/good-story)
- [THU Digitizer user-first installation flow](https://github.com/Rimagination/thu-digitizer)

## License

H3 Lite is released under the MIT License. MiniMax model weights, ComfyUI, third-party custom nodes, and upstream documentation remain subject to their respective licenses.
