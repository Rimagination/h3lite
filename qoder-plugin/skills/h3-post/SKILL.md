---
name: h3-post
description: 后期与交付：多镜拼接、剪辑决策、动作片验收、声音设计、人物声音一致性审计（F0/频谱质心门限）、字幕烧录、响度标准化、放大、QA 与交付。当用户要求拼接、剪辑、动作片检查、加字幕、调音量、检查角色声音是否一致、放大或交付成片时使用。
---

# H3 后期与交付

处理对象是**已生成并验证过的镜头**。任何一镜生成失败，先回 `h3-generate`，不要用后期掩盖。

## 默认交付

- 成片默认交付到 `%USERPROFILE%\Downloads`（当前用户下载目录），除非用户当次指定别处。有 `show.json` 时以 `deliverable` / `post` 为准，不重新猜目录、命名、字幕、封面或响度目标。
- 文件名语义化：`主题_版本_时长_画幅.mp4`，例如 `JOJO风_断罪硬币_三镜版_9s_竖屏.mp4`；不覆盖已有文件，必要时加 `_v2`。
- 中间文件留在项目目录；交付的是可播放成片，不是散镜头。
- 报告：路径、时长、分辨率、帧率、音轨、响度、字幕语言、QA 结论。

## 单次生成多镜

源文件本身是一条 H3 生成（例如 FL2VA 3–4 拍）时，不要按“每镜独立处理”拆开：

- 不做逐镜裁切、逐镜变速、逐镜 loudnorm；这些会重新制造接缝。
- 视频流 `-c:v copy`；只对整条音轨做一次 loudnorm，再编码 AAC 48 kHz。
- 只核对提示词请求的切点附近（±0.5 s），不做全片阈值扫；请求切点变成一次连续运镜、但仍有清楚视觉段，不算失败。
- 244→260 这类自然补帧不裁尾、不重跑；以实际时长交付。

## 专业剪辑与声音

剪辑先服从情绪和故事，再服从节奏，最后才是画面空间的技术连续性。Walter Murch 的 Rule of Six 可当作排序：Emotion 51、Story 23、Rhythm 10、Eye-trace 7、2D plane 5、3D space 4。百分比是经验权重，不是公式；不要为了完美 180° 牺牲一个真实反应。

- 切在动作中段、眨眼/听完/说完之后；台词落地留 0.3–0.5 秒，不要切在第一个音节。
- match cut 用形状/动作/声音做锚点；J/L cut 让声音提前或延后 2–4 帧；环境底床用 sound bridge 跨接缝。
- 一个情绪事件不要碎成很多角度；快切之间留一个静止反应拍；全片都在切等于没有节奏。
- 单条多镜 H3 的切点已经烧在画面里：只修剪头尾、验证切点和声音，不重新拆 coverage。
- 声音四层：对白、SFX、环境、BGM；一个动作一个主 SFX，环境 2–3 个元素，整条一条 master track。
- 每个地点铺 room tone；接缝 20–50 ms 交叉淡化，不用静音补洞；对白优先，BGM 不盖人声。
- 分批生成先统一黑白、白平衡、饱和和肤色；调色用于统一，不用于掩盖身份漂移。
- 任何表演/动作/身份失败，回 `h3-generate`；剪辑不补救坏镜头。

完整优先级、切点语法、声音层与调色清单见 `references/professional-edit-sound.md`。

## 动作片：不伪造速度

- `h3_status.py --dynamic-check` 只抽首/中/末 3 帧；它报 `dynamic` 不代表打斗不慢。动作片另抽 8–12 帧或接触表，数主要动作事件并统计近静止比例。
- 5 秒动作段至少 5 个主要动作事件；有 >0.5 秒对峙/定格，或近静止（帧间 MAD < 1.0）超过 20%，判慢放，回 `h3-generate`/`h3-prompt` 重做。
- 不用帧插值、光流、变速或“快剪碎片”去掩盖慢打斗。动作因果补不回来，快剪只会把同一条慢动作切成更多小段。
- 用户明确要求风格化速度 ramp 时才做；保留原速母版，并在回执里写清“变速/插帧”及倍率，不把它说成生成质量。
- 单条动作生成不逐镜变速、不重新拆 coverage；不为凑时长硬裁自然补帧。详细判据见 [`../h3-director/references/action-combat.md`](../h3-director/references/action-combat.md)。

## 拼接

先确认所有镜头分辨率、帧率、像素格式一致；不一致先统一转码。

**硬切（快切短剧默认）** 用 concat demuxer：

```text
file 'shot01.mp4'
file 'shot02.mp4'
file 'shot03.mp4'
```

```bash
ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4
```

`-c copy` 失败（时间戳/参数不一致）时改用重编码 `-c:v libx264 -c:a aac`。

**叠化** 用 `xfade` + `acrossfade`，累计偏移：

```text
offset_1 = d1 - T
offset_k = offset_{k-1} + d_k - T
```

`T` 为转场时长。xfade 的 `transition` 名以本机 ffmpeg 支持为准；`smoothstep` 不可用时改用 `fade`，不要硬报错重来。音频必须都有流才能 `acrossfade`，否则先补静音轨或改用硬切。

**不硬修时长**：73 帧就是 3.042 s，124 帧就是 5.167 s，244 帧参数的 Set C FL2VA 实测 260 帧 / 10.833 s；几十毫秒到十几帧的自然偏差是正常的，不要为了凑整裁尾或重跑。切点落在自然动作边界，不落在半帧上。详见 `references/assembly.md`。

## 字幕

本机默认审美（用户当次要求优先）：

- 纯白、衬线字体、字号偏大、**不带标点**；不要彩色描边、装饰线或色块。
- 双语：日语在上、字号略小；中文在下、字号更大。
- 一行说完一个语义单元；最多两行；每条时长不短于 0.4 s。
- 时间轴按**实测语音**对齐，不按字数估算；先出 SRT/ASS，再抽帧核对同步。
- 用 `subtitles=` 滤镜烧录，或按用户要求输出软字幕。烧录后必须重验时长、音轨与可读性。

完整样式与 ASS 模板见 `references/subtitles.md`。

## 音频

- **整条成片只做一次 loudnorm**：单次多镜和逐镜拼接都一样，拼接后再统一处理；禁止逐镜归一。
- 验收目标 `I=-14 LUFS, TP=-1.5 dBTP, LRA=11`；编码时用 `I=-13.7, TP=-1.8` 给 AAC 预留过冲，编码后实测成片再核对。
- **不要用 `alimiter` 代替响度归一**：本机实测会把峰值压坏、听感发闷。
- 层级参考（以对白为 0 dB）：环境 −3～−6，拟音 −1～+1，音乐 −2～−4，强调音效 +1～+3；对白永远最清楚。
- 用户没要求音乐就不加 BGM；BGM 不得盖过台词。原生台词镜头不要再叠一层 TTS 或第二遍人声。
- 详见 `references/audio.md`。

## 声音一致性审计

跨镜"同一个人一会儿年轻一会儿苍老"是可测量的，不要只靠听感下结论。工具：`scripts/h3_voice_audit.py`。

```bash
python scripts/h3_voice_audit.py --plan qa/voice_windows.json --json qa/voice_audit.json
```

- 计划 JSON 按角色给窗口：`[{"character":"A","file":"video/shot05.mp4","start":3.95,"end":7.05,"band":[70,220],"note":"line1"}]`；`band` 是该角色的 F0 搜索带。
- 输出每窗 F0 中位数 / p10–p90 / 周期性 / 频谱质心 / HF 比 / dBFS，并按角色汇总极差与半音差。
- 门限：同一角色跨镜 **F0 中位数极差 ≤2 个半音（约 12%）**、质心极差 ≤约 25%；同场两个角色 F0 中位数差 **≥3 个半音**，否则有合并风险。
- 先测正典样本拿基线，再逐镜比。超标**先回 `h3-prompt`/`h3-generate` 重跑**（改 VOICE 块、拉开声学距离、换干净样本、只改时长 ±1–2 s）。
- 只有用户明确批准才做有限后期修正：窗口化 rubberband 音高/共振峰匹配 + 40 ms 等功率交叉淡化，时长漂移 ≤0.05 s，视频流 `-c:v copy`。**任何情况下都不加第二遍人声、不做 TTS 补录。**
- 底床声（念经、雨、嗡鸣）同样审计：全片应来自同一正典源。本项目实测念经底床 F0 93→161.6 Hz（约 9 个半音），就是每镜各自生成的后果。
- 方法、门限依据与已知坑见 [`../h3-prompt/references/voice-consistency.md`](../h3-prompt/references/voice-consistency.md)。

## 放大

超分是后处理，不是第二次生成：不改生成图、不加采样步数。

- 主路线 Topaz Video AI（本机已装，GUI 选择模型与倍率）；记录导出设置。
- 脚本化备选 FlashVSR：tiled 参数用 `--tile_size 256 --tile_overlap 64`，旧 128/24 会留网格；输出可能丢音轨，需重封装。
- ComfyUI + 4x-UltraSharp 和纯 ffmpeg 依次回退。
- 导出后必须核对 `nb_frames` 与输入一致；截断（如 100/479 帧）是坏跑，不是质量结论。已带 `videoai=Enhanced` 的文件不要二次放大。
- 详见 `references/video-upscale.md`。

## 修脸（FaceRefine）：实验性，不是默认

FaceRefine / 贴回式修脸只在用户明确要求、单镜、且问题只是清晰度时考虑；身份、脸型、画风、动作或运镜不对时回 `h3-generate` 重生成，不用贴回。

- **没有一个参数组合达到完美**；技术清晰度/稳定性 PASS ≠ 身份、画风、几何通过。
- 禁止全片自动套、跨镜批量套、没有原片/A/B 就套。
- 已知 bug、历史接线、wobble/接缝指标与止损条件见 [`references/face-refine.md`](references/face-refine.md)。
- 正确生脸不要叠 FlowLock/freq_sep；它们可能把正确五官拉回错误几何。
- 用户否决脸就停，不要继续调 mask/feather 试图“修对”。

## 分级验收

- 技术 PASS、低清身份 PASS、生产分辨率可见内容 PASS 是不同等级，不能互相外推。
- 没拍到的角度必须标为 `not exercised`；例如角色始终背向/侧向时，正脸和眼镜细节不算验收通过。
- grid 检查的 `residual` 不能改写成 `clean`；低于阈值且叠加图无可见网格时，按实际 residual 记录。
- 双角色复刻的验收证据至少包括完整解码、source/guide/map/output 接触表、A/B crop、转身/停步段、尾段持续双人、全分辨率关键帧和 changed-node 报告。
- 诊断片即使达到生产画布，也不能替代最终整片原音轨组装、连续性和交付 QA。

## QA

交付前逐项：

1. `ffprobe`：时长、分辨率、帧率、视频流 + 音频流；
2. 抽首/中/末帧：非黑、非纯色、人物比例与身份没有突变；
3. 镜头顺序与分镜表一致；
4. 字幕逐条核对措辞、语言与同步；
5. 响度与真峰值达标，对白可懂；带台词的另跑声音一致性审计（同一角色跨镜 F0 中位数极差 ≤2 个半音、同场角色间距 ≥3 个半音）；
6. 单次多镜/拼接片：报告实际视觉段数与切点；确认整条只做了一次 loudnorm；
7. 动作片：报告主要事件数、近静止比例、是否有 >0.5 秒定格；确认没有用变速/插帧掩盖慢动作；
8. 固定网格/接缝：跑 `scripts/h3_grid_check.py --video <mp4> --comfyui <ComfyUI> --json`；`suspected` 时按 `component-sets.md` 做 fp16 VAE 单变量 A/B，不用模糊/降噪遮盖；`residual` 按实际记录，不升级成 clean；
9. 双角色/角色替换：确认身份与配饰隔离、双人持续可见、guide/map 无残留、原演员身份无泄漏；未出现的角度标 `not exercised`；
10. 整片从头到尾看一遍——技术指标合格不等于内容可用。

任何一项失败：报告具体失败项与已完成部分，不把它标记为完成视频。

## 资源

- `references/professional-edit-sound.md`：Murch Rule of Six、切点语法、声音四层、room tone、统一调色。
- `references/assembly.md`：硬切/叠化、累计偏移、常见失败。
- `references/subtitles.md`：白字无标点样式、双语版式、ASS 烧录、对齐方法。
- `references/audio.md`：loudnorm、层级、BGM、禁用项。
- `references/delivery.md`：交付目录、命名、回执格式。
- [`../h3-generate/references/show-contract.md`](../h3-generate/references/show-contract.md)：交付规格、QA 门禁与失败返工规则。
- `references/video-upscale.md`：Topaz / FlashVSR / 4x / ffmpeg 路线与问题表。
- `references/face-refine.md`：FaceRefine / 贴回式修脸的实验记录、已知 bug、指标口径与止损线；不是默认后期。
- `scripts/h3_voice_audit.py`：按角色窗口测 F0/质心/周期性/RMS，输出半音差与门限判定。
- `scripts/h3_grid_check.py`：原生分辨率测 128px 固定网格/接缝，输出 profile、overlay、JSON 与 clean/residual/suspected 判定。
- [`../h3-prompt/references/voice-consistency.md`](../h3-prompt/references/voice-consistency.md)：声音一致性方法、选角声学距离、已知坑与修正边界。
- [`../h3-generate/references/dual-character-remake.md`](../h3-generate/references/dual-character-remake.md)：双角色复刻的分级验收、接触表/crop、未 exercised 角度与生产画布边界。

## 来源

- Walter Murch, *In the Blink of an Eye*（Rule of Six 的原始论述）.
- PremiumBeat, Cutting on the Blink: Editing Tips From Walter Murch: https://www.premiumbeat.com/blog/cutting-on-the-blink-editing-tips-from-walter-murch/
- StudioBinder, 180-degree rule: https://www.studiobinder.com/blog/what-is-the-180-degree-rule/
- OSideMedia, higgsfield-ai-prompt-skill: https://github.com/OSideMedia/higgsfield-ai-prompt-skill
- 公开剪辑与声音写法参考（非运行时依赖）：https://github.com/higgsfield-ai/skills
