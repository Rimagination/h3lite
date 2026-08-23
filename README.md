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

## 从需求到成片：四步工作流

复杂视频先按“**意图路由 → 参考图锚点 → 提示词增强 → 生成与验收**”处理。这个工作流借鉴了公开 Agent Skill 的组织方式，但 H3 Lite 仍然只使用本地 ComfyUI，不调用 Higgsfield、MCP 或云端模型。

| 你的目标 | 优先路线 | 关键做法 |
|---|---|---|
| 纯文字描述完整视频 | `T2VA` | 先写开场状态，再按时间顺序写动作、镜头和声音。 |
| 指定视频第一帧 | `I2VA` | 把参考图锁定在 `0.00s`，只描述后续变化。 |
| 指定首尾画面 | `FL2VA` | 描述两个锚点之间连续、可见的变化。 |
| 多张图/视频/音频参考 | `Ref2VA` | 先定义每份素材的角色、保留项和可变项，再写分镜。 |

人物或多镜头任务会先建立“锚点卡”：角色、服装、发型/花纹、道具、场景、光线、必须保持的内容、允许变化的内容，以及禁止漂移的内容。每个参考素材使用稳定名称（如 `Subject A`、`Picture 1`），并在提示词、输出文件夹和运行记录中保持一致。若 Ref2VA 的模型、文本编码器或工作流没有实际安装，Agent 不会把“有节点”当成“路线可用”，而是回退到分镜化 I2VA 或明确标记实验路线。

运行时会把这张锚点卡保存为每次任务目录中的 `anchors.json`，并在 `manifest.json` 记录其路径和摘要。生成完成后，`h3_status.py` 会在存在参考图或多镜头锚点时记录 `anchor_qa`：比较首/中/尾帧与参考图的像素连续性，并标记需要人工复核的身份、服饰和构图一致性。它是提示漂移的早期信号，不是人脸识别，也不会因为像素相似度偏低而代替人工判断或自动否定已通过的媒体技术验收。

提示词内部按五遍增强：意图一句话 → 可观察的角色/场景锁定 → 按播放顺序的动作与分镜 → 物理运镜和声音 → 少量防漂移约束。最终仍转换为 H3 所需的 `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music` 字段；不要求用户自己填写 schema，也不会用堆砌“电影感”形容词代替具体动作。

当描述比较模糊（例如“更电影感”“做一个好看的 3D 动画”）时，Agent 可选读取 [`references/prompt-assist.md`](references/prompt-assist.md)，参考 Higgsfield 公开模板把需求拆成稳定的风格/角色锁定、`SCENE`、`MOTION`、`AUDIO` 和少量 `NEGATIVE` 约束，再翻译回 H3 字段。它只是提示词写作辅助，不调用 Higgsfield，不复制其模型参数，也不会改变本地 Windows 低显存路线；如果联网不可用，就使用本地 H3 提示词参考继续工作。

## 你能用它做什么

| 路线 | 输入 | 适合场景 |
|---|---|---|
| T2VA | 文字提示 | 文生视频，保留 H3 原生声音 |
| I2VA | 首帧图片 + 文字提示 | 从指定画面开始生成 |
| FL2VA | 首帧 + 尾帧图片 + 文字提示 | 约束视频起点和终点 |
| L2VA | 尾帧图片 + 文字提示 | 让视频收束到指定画面 |
| Ref2VA | 多张图片、视频或音频参考 | 复用人物、风格、动作、镜头或声音；当前 fastpath 先提供实验性多图工作流 |

T2VA、I2VA、FL2VA 和 L2VA 可由 fastpath 根据首帧、尾帧参数自动选择。当前 fastpath 也支持重复 `--ref-image` 自动选择实验性的 Ref2VA 工作流；实际运行前仍必须确认 `MiniMaxH3ReferenceToVideo`、匹配的 ClipProj/文本编码器和工作流已经加载。

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

**Ref2VA 不需要单独的模型包。** bundled 多图 Ref2VA 工作流复用所选组件集中的 W4A8 扩散模型、4B 文本编码器、ClipProj、双 VAE 和 Turbo LoRA；只新增工作流入口和参考图绑定。若这些组件已经存在，Agent 应先复用并检查原生 `MiniMaxH3ReferenceToVideo` 节点，不要重复下载所谓的“Ref2VA checkpoint”。

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

### 模糊需求的提示词辅助

如果用户只给出风格词或一句松散想法，先补齐“观众最终要看到什么”，再确定一个可观察动作和一个主要运镜。例如“两个男生在海边，真实、电影感、镜头绕过去”可以明确为：两位人物的正/三分之四朝向、服饰和海岸线保持不变，镜头在平视高度缓慢顺时针环绕约 20°，保留海浪与风声，不凭空添加对白。参考网站的结构是为了减少歧义，不是让提示词堆更多形容词；完整模板和边界见 [`references/prompt-assist.md`](references/prompt-assist.md)。

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

### Ref2VA：多张图片参考

把图片按提示词中的顺序重复附加为 `Picture 1`、`Picture 2`、`Picture 3`。建议一张主图负责人物身份，其余图片分别负责场景、服装/道具或姿势；不要让每张图片都要求“完整复制”。对应的命令形式是：

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

当前 Ref2VA 模板要求 ClipProj 编码器使用 `resident` 模式。它比 I2VA 更占显存，8 GB 显卡可能需要先用一张参考图或直接由 preflight 阻止；通过后再逐步增加参考图数量。完整的六段式提示词和角色分配见 [`references/prompt-writing.md`](references/prompt-writing.md) 与 [`references/agent-workflow.md`](references/agent-workflow.md)。

底层 `MiniMaxH3ReferenceToVideo` 节点还支持参考视频和音频；本次 bundled fastpath 先把最稳定、最容易验收的多图入口做成 `--ref-image`，视频/音频素材仍可通过原生工作流接入。

## 不打开网页也能看进度

Windows 上运行 fastpath 时，H3 Lite 默认会弹出一个原生进度窗口：

- 显示排队、采样、解码、写入视频等阶段；
- 直接读取 ComfyUI 原生 WebSocket 的步骤和节点进度；
- 同时显示已用时间、预计剩余时间、显存、内存和 pagefile；
- 生成完成后显示视频路径，可直接打开输出文件夹。

新版 ComfyUI 会通过 `progress_state` 提供工作流节点状态，窗口会显示已完成节点、当前节点步骤和当前节点监测时长；轨道也按节点分段。默认窗口为 `760×620`，内容区带垂直滚动条，较小屏幕也能看到全部按钮。节点完成度是工作流结构进度，不等于耗时百分比；预计剩余时间使用经验耗时估计。没有可量化事件时，进度条保持静态并显示等待原因，不用动画伪装进展。这个本地窗口直接连接 ComfyUI，不需要浏览器或 MCP 中转。需要终端-only 运行时，加上 `--no-monitor-gui`。

它不需要打开浏览器，关闭窗口也不会中断生成。也可以独立打开窗口，让它自动寻找当前新任务：

```powershell
python scripts/h3_monitor_gui.py `
  --comfyui F:\MiniMax-H3\ComfyUI
```

没有正在运行的任务时，窗口会显示等待状态；几天前遗留的 `running` 清单不会被当成当前任务。`--once --no-websocket` 可用于诊断 ComfyUI 和运行清单是否可读。

## 组件完整性与故障排查

H3 Lite 把扩散模型、文本编码器、ClipProj、Turbo LoRA、双 VAE、工作流和节点版本视为一套组件，不会按文件名随意混搭。Set B 曾出现过“文件大小正确、内容损坏”的 W4A8 主模型，结果是彩色马赛克；首次使用或文件变化后会校验已登记的 SHA-256，并缓存结果。

遇到问题时，按这个顺序检查：磁盘/pagefile 和可用内存 → 模型或节点是否缺失 → 模型目录/文件名 → CUDA、PyTorch 和 custom node 兼容性 → OOM/CPU 卸载 → H3 音视频流程 → 提示词或参考素材对齐。灰屏或马赛克时，优先检查权重来源、VAE、sigma-shift 和可选注意力/缓存补丁。

### 同机其他 CUDA 程序抢占显存

ComfyUI 队列清空后仍可能让模型常驻显存；Windows WDDM 驱动下 `nvidia-smi --query-compute-apps` 查不到单进程占用，CUDA 会在“看似 8 GB 空闲”时连几 MiB 的分配都失败，甚至直接访问违例（退出码 0xC0000005）而不是报 OOM。诊断用 `python scripts/h3_vram.py --json` 查看每个进程的真实专用显存（读 WDDM 计数器，`nvidia-smi` 总量只有全局值），`--check-free-gb 5` 作门禁；确认对方的队列空闲后才能停止它，空队列不等于模型已释放。详见 [references/gpu-contention.md](references/gpu-contention.md)（含 ComfyUI 常驻 9.8 GB 拖垮 Topaz Video AI 导出的实测案例与处理顺序）。

## 视频超分（后处理，Topaz 主推）

本地 H3 画布上限约 0.5 MP，要 1080p/4K 时不要把“放大”交给重新生成——超分是明确的、用户主动请求的后处理步骤，不改变生成图。主推路线是已装的 Topaz Video AI：打开视频 → 选 Starlight/Astra Fast（或 Proteus/Rhea）→ 选输出倍率（实测常见 1.125x→1296x720、2x→2304x1280）→ 导出；音频由顶层封装（cleanupPass）原样保留。导出前用 `scripts/h3_vram.py --json` 确认显存空闲（停止 ComfyUI 前先确认 `/queue` 为空），注意 Astra HQ/Astra Sharp/Starlight Mini 本机未安装，以及 0 字节权重陷阱——文件名对不代表文件完整。导出后看 `videoai=Enhanced using ...` 元数据，不要对已增强视频再次超分。

备选（可脚本化、离线）：首选本机已装的 FlashVSR CLI（`E:\FlashVSR`，含自带 Python 环境与 FlashVSR-v1.1 模型包）。旧 `run_flashvsr.bat` 内置 `--tiled_dit --tiled_vae --tile_size 128`（overlap 默认 24）——这是本机实测网格伪影的根源；修正是 `run_flashvsr_best.bat` 的 256/64 组合（`--tile_size 256 --tile_overlap 64 --frame_chunk_size 50 --keep_models_on_cpu`）：8 帧切片实测 2:58 完成且抽帧无网格；稳定态 0.14 fps（约 7 秒/帧），479 帧全片约 55-60 分钟，速度与旧 128/24 基本相当但无网格；"非 tiled 全帧"路径实测 >4 分钟/帧不可用；输出不含音轨，需 ffmpeg 从源复制。其次 ComfyUI venv + 4x-UltraSharp（已下载至 `models/upscale_models/4x-UltraSharp.pth`，66,961,958 字节，SHA-256 `a5812231fc936b42af08a5edba784195495d303d5b3248c24489ef0c4021fe01`，spandrel 实测可加载）；纯 ffmpeg `lanczos + unsharp` 仅作快速预览。用 FlashVSR 跑完必须用 ffprobe 校验 `nb_frames` 等于输入帧数（实测曾出现 479 帧输入只输出 100 帧的截断）。详见 [references/video-upscale.md](references/video-upscale.md)。

## 参考资料

- [MiniMax H3 ComfyUI 教程](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [MiniMax-H3 官方仓库](https://github.com/MiniMax-AI/MiniMax-H3)
- [H3 prompt-writing skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
- [Agent 工作流参考：路由、锚点、提示词增强与验收](references/agent-workflow.md)
- [Higgsfield 公开 Agent Skills（仅作设计参考，不是运行依赖）](https://github.com/higgsfield-ai/skills)
- [Higgsfield 提示词模板与生成器（仅作模糊需求的写作辅助）](references/prompt-assist.md)
- [社区 Mac/Metal MLX 移植实录（参考，不代表 H3 Lite 已支持）](https://zhuanlan.zhihu.com/p/2069479566171812707)
- [社区 Apple Silicon 本地部署排错实录（参考，不代表 Windows 资源来源）](https://mp.weixin.qq.com/s/hN60KLN7Pkpqb0pbk-r4WQ)
- [完整组件集与校验值](references/component-sets.md)
- [硬件、分辨率与部署矩阵](references/deployment-matrix.md)

## License

H3 Lite 使用 MIT License。MiniMax 模型权重、ComfyUI、第三方 custom nodes 和上游资料分别遵循各自许可证。
