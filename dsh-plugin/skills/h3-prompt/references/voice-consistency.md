# 人物声音一致性：H3 原生台词

适用：`h3-director` 选角与声音圣经、`h3-prompt` 写法、`h3-generate` 参考音频路线、`h3-post` 验收。
硬规则不变：**台词进 H3 原生整体生成，不做后期 TTS、不叠第二遍人声。** 一致性靠选角 + 提示词 + 路线 + 可测量验收，不靠补录。

一句话结论：声音一致性不是"多写几个音色形容词"。它是三件事——**每个角色一份逐字复用的声音圣经、角色之间可听辨的声学距离、交付前可复核的数字**。参考音频能帮忙，但官方与社区都有已知坑，先读第 7 节再决定要不要接。

---

## 1. 三层责任，先分清再动手

| 层 | 能做什么 | 成本 | 何时用 |
|---|---|---|---|
| 提示词层 | VOICE 块、说话人 ID、声学距离、轮次与时长预算、人数锁 | 零 | 所有路线，默认先做满 |
| 路线层 | Ref2VA + `ref_audios` 音色参考、正典样本、链式 latent | 换图/换路线 | 提示词层做满仍漂，且用户同意换路线 |
| 后期/QA 层 | 测量、门限判定、有限音高/共振峰修正 | 中 | 只测量与判定；修正需用户明确批准 |

本机 Set C 的 I2VA / FL2VA 图只有 `LoadImage → MiniMaxH3ImageToVideo`，**没有音频参考输入**。在这两条路线上写 `<Audio 1>` 是悬空标签：不会生效，还可能把模型推向串台词（见第 7 节）。声音一致性在这两条路线上只能靠提示词层 + 验收。

## 2. 声音圣经：每个角色一行，全片逐字复用

开写分镜前先定这张表，之后每镜复制同一行，不换同义词。

| 角色 | 语言 | F0 目标带 | 质地 | 语速 | 咬字/口音 | 情绪基线 | 正典样本 |
|---|---|---|---|---|---|---|---|
| 老年男 A | 日语 | 95–110 Hz | 干涩、沙哑、气声少 | 慢，句尾下沉 | 标准语，齿音轻 | 平静到疲惫 | `voice_A_dry.wav` |
| 青年男 B | 日语 | 140–160 Hz | 清亮、靠前 | 偏快 | 轻口音 | 紧张 | `voice_B_dry.wav` |
| 青年女 C | 日语 | 210–260 Hz | 柔、 breathy 尾 | 中 | 标准语 | 压抑 | `voice_C_dry.wav` |

规则：

- "苍老"换成"低沉"、"沙哑"换成"粗粝"都算改描述，会漂。**逐字一致**，和身份块同一纪律。
- 声音描述与外貌描述分开成块（见第 4 节），不要混在身份块里让模型每帧重新解释。
- 底床声（念经、雨、房间底噪、磁带嗡鸣）也要有正典来源：全片用同一条样本或同一段生成，不要每镜各自生成。本项目实测念经底床 F0 从 93 Hz 漂到 161.6 Hz（约 9 个半音），听起来像换了个人在念。
- 样本要求：单人、干声、无环境底噪、5–8 s、与目标同语言同情绪。从成片里截的带环境声样本会把环境声和原台词一起带进来（第 7 节 #95）。

## 3. 选角声学距离：这是硬规则，不是建议

社区大样本实测的机制判断：**模型主要靠粗声学特征（音高、共振峰、声道长度）区分说话人，而不是靠提示词里的"参考音频↔角色"绑定关系。**（MiniMax-H3 issue #17，lihuiran135）

由此得到可执行的选角约束：

- 同性别 + 同年龄段 + F0 中位数差小于约 20 Hz（约 3 个半音）→ 高概率合并成同一个声音。原话："Same-gender speakers do not work. With two men (or three) the voices collapse into one."
- 同场两个男声（或两个女声）目标 **F0 中位数差 ≥ 25–30 Hz（约 4 个半音）**，并且质地不同（沙哑 vs 清亮、气声 vs 实声）。
- 一条生成里 **≤2 个说话人最稳**；3 个以上同性别说话人默认高风险，拆条或改选角。
- 距离不够时的正确顺序：改音色描述拉开音高带 → 换更轻口音/更中性的参考样本（vm8net 实测：自己的音色单人没问题，多角色 20/20 失败，换轻口音样本后分离恢复）→ 拆条 → 换角色性别/年龄设定。**不要靠堆形容词。**
- 本项目实测反例：田村 123 Hz 与新租客 130 Hz 同镜，差 7 Hz，听感几乎同一个人；这就是选角距离不足，不是提示词不够详细。

半音换算：`semitones = 12 * log2(f2 / f1)`。12% 的频率差约等于 2 个半音。

## 4. VOICE 块写法（基础三字段路线，本机默认）

身份块只写外貌，VOICE 块单独一段只写声音，两者都逐字复用：

```text
Subject A is a 72-year-old man, thin grey hair, deep wrinkles, faded brown cardigan.
His face, hair and clothing remain identical in all shots.

VOICE A (S1): Japanese, elderly male, fundamental pitch around 100 Hz, dry gravelly
timbre with little breath, slow deliberate pace, falling sentence endings, close-miked
and quiet. This voice quality is identical in every shot.

Subject B is a 22-year-old man, short black hair, plain white shirt.
VOICE B (S2): Japanese, young male, fundamental pitch around 150 Hz, bright forward
timbre, quicker pace, light regional accent, slightly nervous breath.

Visible actors in this shot: A, B.
Preserve the established screen-side positions and spacing.
Do not swap, duplicate, or add cast members.

(S1) says the line once and nothing else: "<日语台词>"
(S2) listens with lips at rest, jaw closed, his breath lifting his chest.
```

要点：

- **写可听辨的物理事实**：音高带、质地、气声量、语速、句尾走向、麦克风距离。"苍老的声音"不是事实，"around 100 Hz, dry gravelly, slow, falling endings"是。
- **说话人 ID 全片固定**：`(S1)`/`(S2)` 按实际发声顺序分配一次，之后所有镜头复用同一编号。官方全参考格式同此规则。
- **台词只说一次**：`says the line once and nothing else`；官方 schema 用 `<d>[Japanese] ...</d>`，每个 `<d>` 块只说一次、按书写顺序。
- **非说话者给正向静止事实**，画外声明 `off-screen` 且可见人物嘴唇闭合。
- ** incidental 发声必须格式化或删除**：轻笑、叹气、"嗯"、"sharing a small chuckle" 这类裸写会被当成台词并打乱说话人路由。oliacym 在 issue #17 实测：删掉一句未格式化的 "sharing a small chuckle" 后所有声音恢复正常。要么写进 `<d>`/引号当正式台词，要么删掉，要么写成纯环境音。
- **人数与站位锁**：`Do not swap, duplicate, or add cast members.` 这条同时治"背景多出一个人"的穿帮（本项目 Shot 06 前景 giant hands + 背景完整老人，就是没有这条锁）。
- 可复用的纪律句（社区数千镜头验证过的写法，nonsense2025）：

```text
(S1) is <Subject 1> BILL. <Audio 1> is only this character voice timbre; do not copy its words.
Keep the supplied voice identities separate.
Only words inside <d>...</d> are spoken.
Speak each <d> block exactly once, in written order. Camera cuts never restart dialogue.
```

`<Audio 1>` 只在真的接了参考音频时写；I2VA/FL2VA 路线删掉这一句。

## 5. 官方 Ref2VA 音频绑定（六字段路线）

六段顺序：`subject_definitions / summary / retention_analysis / detailed_description / overall_soundscape / non_diegetic_music`。

标签：`<Subject N>` `<Picture N>` `<Video N>` `<Audio N>`，各自独立编号。音频关系标记四选一：

| 标记 | 含义 | 声音一致性用法 |
|---|---|---|
| `fully_copy` | 整条源信号成为最终音轨 | 不用于音色参考 |
| `partially_copy` | 复用部分层或时间段 | 底床复用 |
| `reference` | 只跟随音色/节奏/风格/演绎 | **音色参考用这个** |
| `weak_reference` | 只保留宽泛相似 | 风格氛围 |

官方绑定句（可直接复用）：

```text
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2>: reference - the target audio references the male voice timbre from <Audio 2>
to generate <Subject 1>'s spoken dialogue.
```

硬规则（官方 ref-en.txt）：**只参考音色、节奏、情绪或演绎时，不要把参考音频里的原台词带进目标视频。** 补一句显式约束：

```text
<Audio 1> is only this character voice timbre; do not copy its words.
```

**A→B→A 的槽位技巧**（maramoscabral 实测）：写 `S1/S2/S1` 会失败；正确做法是给第三次发声一个新的音频槽，`Audio 3 = Speaker A voice again (same file as Audio 1)`，第三句写 `S3 using Audio 3`。说话人编号与音频槽编号是两套东西，不要复用槽位去表达"同一个人又说话了"。

上限（官方文档 + 本机 `object_info` 实测一致）：

| 输入 | 上限 | 备注 |
|---|---|---|
| `ref_images` | 9 | 每张一个角色，`ref_image_size=match` |
| `ref_videos` | 3 | 每条 2–15 s，总 ≤15 s，24 fps 帧序列 |
| `ref_audios` | 3 | 每条 2–15 s，总 ≤15 s，独立音频 |
| `ref_video_audios` | 3 | 同编号参考视频自带的音轨 |
| 混合文件总数 | 12 | 官方限制 |

- **音频不能是唯一输入**，必须伴随图像或视频。
- 输出 4–15 s、24 fps、32 kHz 立体声，默认短边 768。
- `audio_vae` 必须接上。本机节点 tooltip 原文："Without it reference audio only conditions the text encoder." 只接 `vae` 不接 `audio_vae`，参考音频不会真正进入音频分支。
- 提交命令与接线见 `h3-generate` SKILL.md 的"参考音频"一节。

## 6. 时长与轮次预算（社区大样本经验值）

来自 nonsense2025（数千镜头、RTX 5090、FL2VA pruned INT8 ConvRot、16 步）的公开复盘，**是经验值不是模型合同**：

- **约 0.36 s / 词**。他对比 .34/.35/.36/.37/.38 后选定 .36。日语按拍（モーラ）估，先试听校准再用。
- **一条 ≤6 个对白轮次**。超了就拆条，不要指望模型自己分配时间。
- **时长敏感**：同一提示词 12.5 s 失败、14 s 成功。重试时**只改时长 ±1–2 s**，seed/步数/提示词/参考全部锁死。
- **保留跑通的配置**：一旦某条成功，把 seed、时长、步数、提示词、参考样本原样记录成基线；不要"顺手优化"其中一个变量。
- 自报成功率 60–70%。这不是可靠修复，是概率改善；验收仍按第 9 节的数字。

## 7. 已知坑：不要当提示词问题去 debug

| 症状 | 证据 | 对策 |
|---|---|---|
| 接了独立参考音频后开头抢话、台词重复、首音节被切 | MiniMax-H3 issue #95（VDiva）：样本是从成片截的、带环境声（3.2 s 单声道 / 约 2.333 s 立体声，32 kHz） | 换干净干声样本；仍不行就断开参考音频。原帖实用结论："Disabling reference audio has been the practical workaround in my project, although this makes voice consistency harder." |
| 续接视频自带音轨 + 独立音色参考 → 直接崩 | ComfyUI issue #16289：`RuntimeError: shape mismatch: value tensor of shape [938, 32] cannot be broadcast to indexing result of shape [1010, 32]`，位置 `comfy/ldm/minimax/model.py:711`；两者单独都正常；master c75d8c9 仍未修 | 二选一：要么续接视频（音轨走 `ref_video_audios`），要么独立音色参考。不要同时接 |
| 两个男声合并成一个 | issue #17 lihuiran135 | 第 3 节声学距离；拆条 |
| A→B→A 第三句错人 | issue #17 maramoscabral | 第 5 节新槽位技巧 |
| 一句轻笑/叹气后所有声音乱掉 | issue #17 oliacym | 第 4 节：格式化或删除 incidental 发声 |
| 多角色 20/20 失败，单人正常 | issue #17 vm8net | 换轻口音/中性样本；拉开声学距离 |
| 写了 `<Audio 1>` 但图里没有音频输入 | 本机 Set C I2VA/FL2VA 图结构 | 删掉悬空标签；#95 的 C 组对照证明悬空标签本身也会改变结果 |

**#95 的 A/B/C 复现法**（值得照抄的诊断纪律）：A 接 `ref_audios`；B 同提示词同 seed 但断开音频；C 在 B 基础上再删掉悬空的 `<Audio 1>` 文本。三组对比才能分清"参考音频的作用"与"标签文本的作用"。原帖基线：seed 666、`res_multistep`、`simple`、20 步、0.4 MP 16:9、328 帧。

## 8. 链式与跨镜一致

- 同角色沿用同一 VOICE 块、同一参考样本、同一语言。**上一镜尾帧作下一镜首帧只锁画面，不锁声音。**
- 底床声用正典样本贯穿全片；不要每镜重新生成念经/雨/嗡鸣。
- 社区线索（**未取用原文，只作方向**）：缓存每条的视频与音频 latent 喂给下一条，能更久保持质量；相关节点 `LatentAVMaskedExtender`、`H3 Motion Context Chain`。本机未实测，不要当已验证路线写进分镜。
- 长提示词比短提示词稳：每条都写完整的身份 + VOICE + 声音底床，不要因为"上一条写过"就省略。

## 9. 验收：可测量，不靠"听起来还行"

工具：`h3-post/scripts/h3_voice_audit.py`。按角色窗口测 F0 中位数、p10–p90、周期性（HNR 代理）、频谱质心、HF>2 kHz 占比、RMS dBFS。

门限（本项目实测校准，可按片调整）：

| 指标 | 门限 | 超标含义 |
|---|---|---|
| 同一角色跨镜 F0 中位数极差 | ≤2 个半音（约 12%） | 音色漂了，听起来换人 |
| 同一角色频谱质心极差 | ≤约 25% | 明暗/年龄感漂了 |
| 同场两个角色 F0 中位数差 | ≥3 个半音 | 低于此值有合并风险 |
| 周期性（voiced 帧自相关峰） | 与正典样本同量级 | 气声/沙哑程度变了 |

流程：

1. 先测正典样本，得到每个角色的基线数字；
2. 每镜生成后测对应窗口，与基线比；
3. 超标**先回提示词/路线重跑**（改 VOICE 块、拉开声学距离、换样本、只改时长 ±1–2 s）；
4. 只有用户明确批准，才做有限后期修正：窗口化 rubberband 音高/共振峰匹配（`pitch=X:tempo=1.0:formant=shifted:pitchq=quality:detector=soft:channels=together`），40 ms 等功率交叉淡化，时长漂移 ≤0.05 s，视频流 `-c:v copy`；
5. **任何情况下都不加第二遍人声、不做 TTS 补录。** 修正只改已有原生人声的音高/共振峰，不新增语音内容。

本项目实测漂移（作为门限校准依据）：田村 F0 106.7 / 118.5–128 / 123.1+145.5 / 122.6 Hz，质心 722–1153 Hz；念经底床 93→161.6 Hz；讲述人 112–116 vs 98–118 Hz；真希 250 / 222 / 281 Hz。

## 10. 提交前声音检查（8 问）

1. 每个角色有声音圣经行吗？本镜是否逐字复制？
2. 同场说话人 F0 目标带差 ≥25–30 Hz 且质地不同吗？说话人 ≤2 吗？
3. VOICE 块与身份块分开吗？写的是物理事实还是形容词？
4. 说话人 ID 全片固定吗？A→B→A 用了新音频槽吗？
5. 每句台词只说一次吗？非说话者有正向嘴部静止事实吗？画外声明了吗？
6. 有 incidental 发声吗？格式化了还是删了？
7. 台词词数 × 0.36 s 加停顿，落在请求时长内吗？轮次 ≤6 吗？
8. 接了参考音频吗？样本干净吗？`audio_vae` 接了吗？有没有同时接续接视频音轨（#16289）？图里真的有音频输入吗？

---

## 来源

官方（已取用全文）：

- MiniMax-H3 官方 README（中文，Ref2VA 规格与音色参考案例）：<https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/README.zh-CN.md>
- 官方全参考提示词指南 ref-en.txt（六字段、`<Audio N>`、`(Sx)`、`<d>`）：<https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/skills/h3-prompt-writing/references/ref-en.txt>
- comfy.org 官方 R2V 工作流页（节点与常见问答）：<https://comfy.org/zh-CN/hub/workflows/minimax-h3-reference-to-video-46a303cbccf9/>

社区实测（已取用全文）：

- MiniMax-H3 issue #17 多说话人音色串味：<https://github.com/MiniMax-AI/MiniMax-H3/issues/17>
- issue #17 的六条评论（lihuiran135 / oliacym / maramoscabral / nonsense2025 / vm8net）：<https://api.github.com/repos/MiniMax-AI/MiniMax-H3/issues/17/comments>
- MiniMax-H3 issue #95（VDiva，独立参考音频串台词 + A/B/C 复现）：<https://github.com/MiniMax-AI/MiniMax-H3/issues/95>
- ComfyUI issue #16289（续接视频 + 音色参考 shape mismatch）：<https://github.com/Comfy-Org/ComfyUI/issues/16289>
- Runware《Sound and voice》：<https://runware.ai/docs/models/minimax-h3/guides/sound-and-voice>
- Runware《Reference-driven consistency》：<https://runware.ai/docs/models/minimax-h3/guides/reference-driven-consistency>
- DomoAI《MiniMax H3 Character Consistency Guide》：<https://www.domoai.app/blog/minimax-h3-character-consistency-guide>

线索（**未取用原文，不作为结论依据**）：

- Reddit 无缝链式 / latent 缓存：<https://www.reddit.com/r/StableDiffusion/comments/1vj3zi3/a_technique_for_creating_seamless_continuous/>
- Reddit latent prepend/extend 节点：<https://www.reddit.com/r/StableDiffusion/comments/1vujhwo/yet_another_minimax_h3_latent_prependextend_nodes/>
- Reddit H3 Motion Context Chain：<https://www.reddit.com/r/StableDiffusion/comments/1w5bt7j/h3_motion_context_050_no_more_bypassing_the/>
- Reddit 长片讨论：<https://www.reddit.com/r/StableDiffusion/comments/1wrodxx/long_minimaxh3_videos_situation_lets_talk/>
- 抓取失败或未取用：Reddit 1w6hwd5 / 1vxpbo1、HuggingFace joeygambino 多镜链式包、知乎、morphic、astorie。

本机证据：Set C I2VA/FL2VA/Ref2VA API 图结构、`MiniMaxH3ReferenceToVideo` 与 `LoadAudio` 的 `object_info` 实测（2026-11）、《隔壁的念经声》Ep01 全片 `voice_audit` 测量。