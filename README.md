# H3 Lite

<p align="center">
  <img src="assets/h3-lite-hero.gif" alt="H3 Lite — MiniMax H3 本地部署与视频生成 Skill" width="100%">
</p>

<p align="center">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-1F5E4A?style=for-the-badge">
  <img alt="Hosts Codex" src="https://img.shields.io/badge/Hosts-Codex-4B6B8A?style=for-the-badge">
  <img alt="Route Low VRAM Fast" src="https://img.shields.io/badge/Route-Low--VRAM%20Fast-D9A441?style=for-the-badge">
</p>

<p align="center">
  中文 | <a href="README.en.md">English</a> | <a href="#参考资料">参考资料</a>
</p>

`H3 Lite` 是一个给 Codex、WorkBuddy 等 AI Agent 使用的 MiniMax H3 本地视频生成 Skill。你只需要用自然语言描述想看的画面，Agent 就会根据电脑配置选择 ComfyUI 路线、准备必要组件、生成带原生声音的视频并检查结果。

它面向第一次接触本地视频生成的用户：你不必先学习 ComfyUI 节点，也不必自己判断模型、文本编码器、LoRA、双 VAE 和低显存参数怎样组合。

## 一分钟交给 Agent

把下面这句话发给 Codex 或 WorkBuddy：

```text
请帮我安装 H3 Lite，并根据我的电脑配置准备本地 MiniMax H3 视频生成环境：
https://github.com/Rimagination/h3lite
```

这“一分钟”指把任务和安装位置交给 Agent。模型文件较大，首次下载和部署时间取决于网络、硬盘与电脑配置。

如果不想占用系统盘，把目标位置写进同一条消息：

```text
请把 MiniMax H3 和 ComfyUI 安装到 F:\MiniMax-H3；如果那里已经有健康环境就直接复用。
```

## 基本配置

当前默认支持 **Windows + NVIDIA CUDA** 的本地低显存路线。8 GB 显存也可以尝试，但建议配 32 GB 系统内存和 SSD；12–16 GB 会更宽裕。

AMD/ROCm、RTX 50 系列新架构和原生 BF16 H3 不在当前默认验证范围内，Agent 会先做兼容性判断，不会仅凭显存容量承诺“能跑”。详细硬件、组件和分辨率说明见 [`references/deployment-matrix.md`](references/deployment-matrix.md)。

默认从 `fast` 路线开始。质量档位、I2V/Ref2VA、人脸质量和时间预估由 Agent 根据实际环境自动选择；这些判断不会给视频推理图增加额外采样或模型。

## 快速验证：红球弹跳

安装完成后，先用一个动作简单、声音明确的 5 秒视频检查整条链路：

```text
请使用 H3 Lite，生成一个 5 秒横屏视频：一颗小型哑光红色橡胶球，在灰色混凝土地面上弹跳两次，然后向右滚出画面。低机位固定镜头，阴冷的多云日光，浅景深、35mm 电影质感；保留两次撞击地面的声音和滚动声，不配音乐。
```

▶️ [播放 / 下载红球验证视频](assets/examples/h3lite-red-ball-and-plant.mp4)

这个案例同时检查动作次数、运动方向、视频封装和原生声音。成功后再进入人物、复杂动作和更大画布。

## 用规范提示词生成视频

短视频提示词可以按三部分组织：

1. **画面与氛围**：主体、环境、光线、景别和风格。
2. **动作与镜头**：按播放顺序描述动作和运镜。
3. **声音**：环境声、动作声、音乐或对白。

“不要对白”只表示不说话，雨声、脚步声、碰撞声和其他环境音仍会保留；只有明确要求“完全静音”时才关闭音频。

### 分段提示：金毛幼犬醒来

```text
请使用 H3 Lite 生成一个 5 秒视频：

[0s-2s] 一只金毛幼犬蜷缩着睡在洒满阳光的木地板上，晨光透过窗户倾泻而入，尘埃微粒在空气中漂浮。

[2s-5s] 幼犬慢慢醒来，前爪向前伸展，打了个带着细小吱声的哈欠，然后坐起身，用明亮好奇的眼睛环顾四周，尾巴开始摇晃。
```

▶️ [播放 / 下载金毛幼犬视频](assets/examples/h3lite-golden-retriever-puppy.mp4)

分段提示比把多个动作挤在一句话里更容易控制时序。

### 文生视频：星舰跃迁

这个 8 秒 T2VA 案例化用自 MiniMax H3 官方可复现案例：

```text
请使用 H3 Lite，生成一个 8 秒 16:9 视频：昏暗而宽阔的星舰舰桥内，一位短发女舰长背对镜头站在弧形观察窗前，窗外的深紫色星云中排列着庞大的黑色舰队。镜头先缓慢推近，舰队尾部的蓝色引擎逐渐增强；约 3.5 秒时切到舰长面部特写，舰队突然跃迁，强烈白光淹没舰桥，冲击使镜头剧烈震动，舰长踉跄后重新站稳。白光消退，窗外只剩空旷星云，她缓缓闭上眼睛。保留舰桥低沉嗡鸣、引擎蓄能声、跃迁爆响和金属震动声，配以逐渐增强的太空歌剧管弦乐。
```

▶️ [播放 / 下载星舰跃迁视频](assets/examples/h3lite-starship-jump.mp4)

### 图生视频：拉面与家宴

下载或直接附上 H3 Lite 的[拉面示例首帧](assets/examples/h3lite-i2va-ramen-first-frame.jpg)，并明确指定它为视频第一帧。

![H3 Lite I2VA 拉面示例首帧](assets/examples/h3lite-i2va-ramen-first-frame.jpg)

```text
请使用 H3 Lite，将我在这条消息中附上的图片作为视频 0 秒的第一帧，生成一个 8 秒视频，并保持图片中的人物、拉面、餐桌和房间构图。镜头全程固定：开始时让前景的青花瓷拉面碗、叉烧、葱花和升腾的热气清晰可见，背景中的家人保持柔和虚化；随后平稳地把焦点从拉面转移到家人，拉面逐渐虚化，家人的笑容、夹菜和轻微交谈动作变得清晰，热气始终在前景飘动。保留汤汁轻微沸腾声、碗筷碰撞声和温暖的室内环境声，加入轻柔的原声吉他与古筝音乐，不要清晰对白。
```

### 视频与声音参考：粉色西装与黑羊

下载 MiniMax 官方案例的[参考视频](assets/examples/minimax-official-ref2va-pink-suit-black-lamb.mp4)和[男声音色参考](assets/examples/minimax-official-ref2va-voice-reference.mp3)，在同一条消息中附上两份素材：

```text
请使用 H3 Lite，根据我在这条消息中附上的参考视频和男声音频生成一个 5 秒视频：以参考视频作为画面、动作和背景音轨基础，保留金发男子、亮粉色西装、怀中的黑色小羊、夕阳草地、远处白羊以及原有镜头构图；只参考单独男声音频的音色来生成新对白。男子看向镜头自然说：“跟着风，自由生活。”说完后露出轻松的微笑，望向远处，并轻轻抚摸黑羊的毛，镜头缓慢推近。人物口型与中文对白同步，其余画面保持写实自然。
```

以上创意和 Ref2VA 素材来自 MiniMax H3 官方可复现案例；素材来源与校验值记录在 [`assets/examples/sources.json`](assets/examples/sources.json)。

## H3 Lite 支持什么输入

| 路线 | 输入 | 适合场景 |
|---|---|---|
| T2VA | 文字提示 | 文生视频，保留 H3 原生声音 |
| I2VA | 一张首帧图片 + 文字提示 | 从指定画面开始生成 |
| FL2VA | 首帧图片 + 尾帧图片 + 文字提示 | 约束视频起点和终点 |
| L2VA | 一张尾帧图片 + 文字提示 | 让视频收束到指定画面 |
| Ref2VA | 参考图片、视频或音频 | 复用人物、风格、动作、镜头或声音 |

T2VA、I2VA、FL2VA 和 L2VA 可由 fastpath 根据首帧、尾帧参数自动选择。Ref2VA 使用与参考素材匹配的工作流。

## 安装

把仓库交给 Agent，并说明希望复用的 ComfyUI 目录；例如：

```text
请帮我安装 H3 Lite，把 MiniMax H3 和 ComfyUI 放到 F:\MiniMax-H3；如果已有健康环境就直接复用。
```

Agent 会在下载和运行前检查目录、组件、驱动、显存、系统内存和磁盘。组件集、模型角色、校验和修复流程放在 [`references/component-sets.md`](references/component-sets.md) 与 [`references/deployment-matrix.md`](references/deployment-matrix.md)，不需要用户在 README 里手动拼配置。

## 参考资料

- [MiniMax H3 ComfyUI 教程](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 官方仓库](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
- [完整组件集与校验值](references/component-sets.md)
- [硬件、分辨率与部署矩阵](references/deployment-matrix.md)
- [人脸质量与零推理开销策略](references/face-quality.md)

## License

H3 Lite 使用 MIT License。MiniMax 模型权重、ComfyUI、第三方 custom nodes 和上游资料分别遵循各自许可证。

## 友情链接

- [Linux.do](https://linux.do/)
