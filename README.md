# H3 Lite

<p align="center">
  <img src="assets/h3-lite-hero.gif" alt="H3 Lite — MiniMax H3 本地部署与视频生成 Skill" width="100%">
</p>

<p align="center">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-1F5E4A?style=for-the-badge">
  <img alt="Hosts Codex" src="https://img.shields.io/badge/Hosts-Codex-4B6B8A?style=for-the-badge">
  <img alt="Route Low VRAM Fast" src="https://img.shields.io/badge/Route-Low--VRAM%20Fast-D9A441?style=for-the-badge">
</p>

<p align="center">中文 | <a href="README.en.md">English</a> | <a href="#参考资料">参考资料</a></p>

`H3 Lite` 是给 Codex、WorkBuddy 等 AI Agent 使用的 MiniMax H3 本地视频生成 Skill。你只需要描述想看的画面，Agent 就会根据电脑配置选择 ComfyUI 路线、准备组件、生成带原生声音的视频并检查结果。

它面向第一次接触本地视频生成的用户：不必先学习 ComfyUI 节点，也不必自己判断模型、文本编码器、LoRA、双 VAE 和低显存参数怎样组合。

## 模型定位与适用范围

H3 Lite 主要面向 Windows 低显存 NVIDIA 显卡。默认使用经过剪枝与量化、并针对低显存适配的组件集，而不是需要大容量显存/统一内存的完整高配模型。典型 Set A 是 W4A8 剪枝扩散模型加 4B INT4 文本编码器，Set B 使用 4B FP8 文本编码器；目标是在消费级显卡上稳定生成，而不是追求满血模型的最高画质。

当前已验证的主路线是 **Windows + NVIDIA + ComfyUI**：

| 平台 | 支持状态 | 指导 |
|---|---|---|
| Windows + NVIDIA | 主支持路线 | 使用本仓库的 ComfyUI、doctor、planner 和 fastpath。 |
| macOS Apple Silicon | 社区替代路线 | 可参考 MLX/Metal 的 `mmh3turbo`，但不是本 Skill 已验证的 ComfyUI 后端。 |
| macOS Intel | 不建议 | 不承诺本地运行，建议使用托管/API 或其他后端。 |
| Linux + NVIDIA | 实验性 | Windows 路径、节点包和耗时数据不能直接套用。 |

Mac 用户不会被引导安装 CUDA 或 Windows 虚拟环境。若明确选择 Mac 社区路线，可参考[社区权重包](https://huggingface.co/yunfengwang/mmh3turbo-bundles)和 `uvx mmh3turbo`；其权重、许可证、更新和性能数据独立于 H3 Lite，不能与 ComfyUI 模型混用。

## 你能用它做什么

| 路线 | 输入 | 适合场景 |
|---|---|---|
| T2VA | 文字提示 | 文生视频，保留 H3 原生声音 |
| I2VA | 首帧图片 + 文字提示 | 从指定画面开始生成 |
| FL2VA | 首帧 + 尾帧图片 + 文字提示 | 约束视频起点和终点 |
| L2VA | 尾帧图片 + 文字提示 | 让视频收束到指定画面 |
| Ref2VA | 图片、视频或音频参考 | 复用人物、风格、动作、镜头或声音 |

T2VA、I2VA、FL2VA 和 L2VA 可由 fastpath 根据首帧、尾帧参数自动选择。Ref2VA 需要匹配的参考工作流，并且必须确认对应模型和节点已经安装。

## 快速开始

把下面这句话发给 Codex 或 WorkBuddy：

```text
请帮我安装 H3 Lite，并根据我的电脑配置准备本地 MiniMax H3 视频生成环境：
https://github.com/Rimagination/h3lite
```

如果不想占用系统盘，把目标位置写进同一条消息：

```text
请把 MiniMax H3 和 ComfyUI 安装到 F:\MiniMax-H3；如果那里已经有健康环境就直接复用。
```

“一分钟”只指把任务和安装位置交给 Agent；模型文件较大，首次下载时间取决于网络、硬盘和电脑配置。

## 基本配置

当前默认支持 **Windows + NVIDIA CUDA** 的本地低显存路线。已实测验证的下限是 **RTX 3060 Ti 8 GB 显存 + 16 GB 系统内存**；这只代表当前 W4A8 快速路线可以运行，不代表所有 8 GB 显卡都能得到相同结果。仍建议配 32 GB 系统内存和 SSD；12–16 GB 显存会更宽裕。

6 GB 显存属于社区实验路线，建议配 32 GB 系统内存；低于 6 GB 显存或低于 16 GB 系统内存时，不建议下载和部署这套工作流。AMD/ROCm、RTX 50 系列新架构和原生 BF16 H3 不在当前默认验证范围内，Agent 会先做兼容性判断，不会仅凭显存容量承诺“能跑”。

## 硬件与路线选择

GPU 型号、显存、笔记本功耗、系统内存、pagefile 和磁盘都会影响结果；“8 GB 显存”本身不是充分条件。

| 已验证电脑 | GPU | 内存 | 路线 |
|---|---|---|---|
| 机械革命翼龙 15 Pro | RTX 4070 Laptop 8 GB | Ryzen 7 8845H / 32 GB | `LOW_VRAM`；Set A T2VA/I2VA，Set B 兼容 T2VA |
| Windows 10 台式机 | RTX 4060 Ti 16 GB | i5-13400F / 32 GB | Set B；`NORMAL_VRAM`；T2VA/I2VA |

同一套 Set B、兼容工作流、提示词、seed 和 `640×352 / 124 帧 / 4 步` 参数下，RTX 4060 Ti 16 GB 纯生成约 77.08 秒，RTX 4070 Laptop 8 GB 约 591.22 秒。这不是芯片跑分，而是常驻显存与动态卸载差异造成的实测参考。

默认从成功率最高的 `fast` 路线开始：4 步、原生音频、短视频和较小画布。基线跑通后，再提高分辨率、时长或采样步数。

### 常见视频分辨率

社区推荐使用 **32 的倍数**。VAE 的空间压缩和 DiT patch 对齐都需要这个约束；“720p”“1080p”只是便于理解的预设名称。不指定分辨率时，本 Skill 默认使用 **640×352**。

| 预设用途 | 实际分辨率 | MP |
|---|---:|---:|
| 6 GB/8 GB 低显存预览 | 608×352 | 0.21 |
| H3 Lite 默认快速路线 | 640×352 | 0.23 |
| 复杂动作实验档 | 736×416 | 0.31 |
| 约 480p、16:9 | 864×480 | 0.41 |
| 约 704p、16:9 | 1216×704 | 0.86 |
| 约 720p、16:9 | 1280×704 | 0.90 |
| 约 768p、16:9 | 1376×768 | 1.06 |
| 约 1080p、16:9 | 1920×1056 | 2.03 |

MP 为宽×高÷1,000,000，保留两位小数。高分辨率或多镜头任务建议先用低分辨率完整预览，确认构图、动作和提示词后再正式生成。

## 安装与组件

### 先确定安装位置

| 方式 | 位置 | 适合情况 |
|---|---|---|
| 复用现有环境 | 已有 `<ComfyUI>` | 保留现有模型和节点 |
| 独立目录 | 如 `F:\MiniMax-H3\ComfyUI` | 推荐，避免占用系统盘或污染项目 |
| 当前项目 | `<项目>\.h3lite\ComfyUI` | 环境随项目保存 |

Agent 在下载大文件前应明确显示 ComfyUI、模型、节点和输出目录。

### 只选择一套组件

不要混用 Set A 与 Set B。百度网盘包已整理对应模型、节点、工作流和清单：

| 组件集 | 已验证起点 | 分享链接 | 提取码 |
|---|---|---|---|
| Set A | RTX 4070 Laptop 8 GB + 32 GB，低显存快速路线 | [百度网盘](https://pan.baidu.com/s/1IBlH0VY7tWGvxqMtniraow) | `4hri` |
| Set B | RTX 4060 Ti 16 GB + 32 GB，FP8 兼容路线；T2VA 也在 RTX 4070 Laptop 8 GB 上验证 | [百度网盘](https://pan.baidu.com/s/1x5GGuJv0h8chApgVoDgIaQ) | `1hjx` |

下载一个完整方案即可。将包内 `models` 和 `custom_nodes` 合并到 `<ComfyUI>`，导入工作流 JSON，并保留 `component-manifest.json`。百度网盘不可用时，按 [`references/component-sets.md`](references/component-sets.md) 的文件名、大小和哈希从上游来源下载。

### 手动安装 Skill

打开仓库页面，选择 **Code → Download ZIP**。解压后把 `h3lite` 文件夹放入 Codex 的 skills 文件夹，再重新打开 Codex。

## 第一次验证

安装完成后，先用动作简单、声音明确的 5 秒视频检查整条链路：

```text
请使用 H3 Lite，生成一个 5 秒横屏视频：一颗小型哑光红色橡胶球，在灰色混凝土地面上弹跳两次，然后向右滚出画面。低机位固定镜头，阴冷的多云日光，浅景深、35mm 电影质感；保留两次撞击地面的声音和滚动声，不配音乐。
```

▶️ [播放 / 下载红球验证视频](assets/examples/h3lite-red-ball-and-plant.mp4)

成功标准是：视频文件存在、画面有运动、动作次数大致正确、封装正常并包含原生声音。通过后再进入人物、复杂动作和更大画布。

## 提示词与案例

短视频提示词可以按三部分组织：

1. **画面与氛围**：主体、环境、光线、景别和风格。
2. **动作与镜头**：按播放顺序描述动作和运镜。
3. **声音**：环境声、动作声、音乐或对白。

“不要对白”只表示不说话；只有明确要求“完全静音”时才关闭音频。中文提示词不要只写一个很短的名词，建议补充主体特征、环境、景别、光线和动作，先以约 30–50 个汉字作为起点，再用低分辨率预览检查。

### 分段提示：金毛幼犬醒来

```text
请使用 H3 Lite 生成一个 5 秒视频：

[0s-2s] 一只金毛幼犬蜷缩着睡在洒满阳光的木地板上，晨光透过窗户倾泻而入，尘埃微粒在空气中漂浮。

[2s-5s] 幼犬慢慢醒来，前爪向前伸展，打了个带着细小吱声的哈欠，然后坐起身，用明亮好奇的眼睛环顾四周，尾巴开始摇晃。
```

▶️ [播放 / 下载金毛幼犬视频](assets/examples/h3lite-golden-retriever-puppy.mp4)

### 文生视频：星舰跃迁

这个 8 秒 T2VA 案例化用自 MiniMax H3 官方可复现案例，适合观察复杂时序、转场和声音设计：

```text
请使用 H3 Lite，生成一个 8 秒 16:9 视频：昏暗而宽阔的星舰舰桥内，一位短发女舰长背对镜头站在弧形观察窗前，窗外的深紫色星云中排列着庞大的黑色舰队。镜头先缓慢推近，舰队尾部的蓝色引擎逐渐增强；约 3.5 秒时切到舰长面部特写，舰队突然跃迁，强烈白光淹没舰桥，冲击使镜头剧烈震动，舰长踉跄后重新站稳。白光消退，窗外只剩空旷星云，她缓缓闭上眼睛。保留舰桥低沉嗡鸣、引擎蓄能声、跃迁爆响和金属震动声，配以逐渐增强的太空歌剧管弦乐。
```

▶️ [播放 / 下载星舰跃迁视频](assets/examples/h3lite-starship-jump.mp4)

### 图生视频：拉面与家宴

下载或直接附上[拉面示例首帧](assets/examples/h3lite-i2va-ramen-first-frame.jpg)，并明确指定它为视频第一帧。

![H3 Lite I2VA 拉面示例首帧](assets/examples/h3lite-i2va-ramen-first-frame.jpg)

```text
请使用 H3 Lite，将我在这条消息中附上的图片作为视频 0 秒的第一帧，生成一个 8 秒视频，并保持图片中的人物、拉面、餐桌和房间构图。镜头全程固定：开始时让前景的青花瓷拉面碗、叉烧、葱花和升腾的热气清晰可见，背景中的家人保持柔和虚化；随后平稳地把焦点从拉面转移到家人，拉面逐渐虚化，家人的笑容、夹菜和轻微交谈动作变得清晰，热气始终在前景飘动。保留汤汁轻微沸腾声、碗筷碰撞声和温暖的室内环境声，加入轻柔的原声吉他与古筝音乐，不要清晰对白。
```

### Ref2VA：视频与声音参考

下载 MiniMax 官方案例的[参考视频](assets/examples/minimax-official-ref2va-pink-suit-black-lamb.mp4)和[男声音色参考](assets/examples/minimax-official-ref2va-voice-reference.mp3)，再明确说明画面、动作、声音和对白分别参考哪份素材。Ref2VA 需要对应模型和工作流，不能只因为节点存在就认为路线可用。

对于多镜头任务，先用最小可用画布跑完整分镜，再提升目标分辨率。长任务保留每个镜头的完整日志，并在磁盘或 pagefile 不足时提前停止；不要把被 `grep` 过滤掉的输出当作成功。

## 不打开网页也能看进度

Windows 交互式运行时，在 fastpath 命令后加上 `--monitor-gui`，H3 Lite 会弹出一个原生进度窗口：

- 显示排队、采样、解码、写入视频等阶段；
- 直接读取 ComfyUI 原生 WebSocket 的步骤和节点进度；
- 同时显示已用时间、预计剩余时间、显存、内存和 pagefile；
- 生成完成后显示视频路径，可直接打开输出文件夹。

新版 ComfyUI 会通过 `progress_state` 提供工作流节点状态，窗口会显示已完成节点、当前节点步骤和当前节点监测时长；轨道也按节点分段。默认窗口为 `760×620`，内容区带垂直滚动条，较小屏幕也能看到全部按钮。节点完成度是工作流结构进度，不等于耗时百分比；预计剩余时间使用经验耗时估计。没有可量化事件时，进度条保持静态并显示等待原因，不用动画伪装进展。这个本地窗口直接连接 ComfyUI，不需要浏览器或 MCP 中转。

它不需要打开浏览器，关闭窗口也不会中断生成。也可以独立打开窗口，让它自动寻找当前新任务：

```powershell
python scripts/h3_monitor_gui.py `
  --comfyui F:\MiniMax-H3\ComfyUI
```

没有正在运行的任务时，窗口会显示等待状态；几天前遗留的 `running` 清单不会被当成当前任务。`--once --no-websocket` 可用于诊断 ComfyUI 和运行清单是否可读。

## 组件完整性与故障排查

H3 Lite 把扩散模型、文本编码器、ClipProj、Turbo LoRA、双 VAE、工作流和节点版本视为一套组件，不会按文件名随意混搭。Set B 曾出现过“文件大小正确、内容损坏”的 W4A8 主模型，结果是彩色马赛克；首次使用或文件变化后会校验已登记的 SHA-256，并缓存结果。

遇到问题时，按这个顺序检查：磁盘/pagefile 和可用内存 → 模型或节点是否缺失 → 模型目录/文件名 → CUDA、PyTorch 和 custom node 兼容性 → OOM/CPU 卸载 → H3 音视频流程 → 提示词或参考素材对齐。灰屏或马赛克时，优先检查权重来源、VAE、sigma-shift 和可选注意力/缓存补丁。

## 参考资料

- [MiniMax H3 ComfyUI 教程](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 官方仓库](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
- [社区 Mac/Metal MLX 移植实录（参考，不代表 H3 Lite 已支持）](https://zhuanlan.zhihu.com/p/2069479566171812707)
- [社区 Apple Silicon 本地部署排错实录（参考，不代表 Windows 资源来源）](https://mp.weixin.qq.com/s/hN60KLN7Pkpqb0pbk-r4WQ)
- [完整组件集与校验值](references/component-sets.md)
- [硬件、分辨率与部署矩阵](references/deployment-matrix.md)

## License

H3 Lite 使用 MIT License。MiniMax 模型权重、ComfyUI、第三方 custom nodes 和上游资料分别遵循各自许可证。
