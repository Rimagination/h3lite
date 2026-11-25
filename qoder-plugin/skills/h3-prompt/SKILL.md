---
name: h3-prompt
description: 撰写、改写、诊断 MiniMax H3 提示词（基础模式三字段 T2VA/I2VA/FL2VA，Ref2VA 六字段）；应用身份-运动分离、场面调度、构图布光、情绪拆解、完成态、正向约束与防漂移措辞；处理人物声音一致性（VOICE 块、说话人 ID、选角声学距离、参考音频绑定）。当用户要求写提示词、改提示词、分析人物/动作失真，或反映角色声音不一致、音色漂移、两个角色声音合并时使用。
---

# H3 提示词：写法与诊断

输出物：一段可直接提交的 H3 提示词 + 建议路线/分辨率/帧数 + 预检结论。**不提交任务**；需要渲染时交给 `h3-generate`。

## 先读开拍合同

写任何提示词前，先读 `show.json` 的镜头卡和 `canon.json` 的身份块/VOICE 块：

- `show.json` 决定这一镜的 mode、template、length、seed、参考图槽位和验收条件；不要重新猜路线或时长。
- 身份块、VOICE 块、底床声从 `canon.json` **逐字复制**；不要在同义词上“润色”，那会重新解释这张脸/这个声音。
- 提示词落成 `prompts/<shot-id>.txt`，与 show.json 的 `prompt` 路径一致；提交前跑 `h3-generate/scripts/h3_show_validate.py`。
- 合同与字段见 [`../h3-generate/references/show-contract.md`](../h3-generate/references/show-contract.md)；不要用聊天记录代替镜头卡。

## 先定模式

| 用户输入 | 模式 | 核心 |
|---|---|---|
| 只有文字 | `T2VA` | 从首帧开始写完整视听时间线 |
| 一张首帧图 | `I2VA` | 图锚定在 0.00 s，只写向前的发展 |
| 首帧 + 尾帧 | `FL2VA` | 两个锚点之间写一条物理连续的路径；可在中途写 1–3 个硬切拍点 |
| 只有尾帧 | `L2VA` | 从尾帧倒推前文与汇聚 |
| 多图/视频/音频参考 | `Ref2VA` | 先定义参考角色与保留项，再写时间线 |

不要把 T2VA 提示词直接粘进参考图工作流；每个图接受自己的 schema。

## 字段顺序

基础模式严格三字段：

```text
integrated_multimodal_description: <画面时间线、动作、镜头、台词、画内音>
overall_soundscape: <环境音与物理音，1–4 句>
non_diegetic_music: <只给观众听的配乐，或 N/A>
```

参考锚句：

```text
I2VA: For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
FL2VA: At 0.00 seconds, <Picture 1> (from [Shot 1]) is fully referenced. At <final timestamp>, <Picture 2> (from the final shot) is fully referenced.
L2VA: At <final timestamp>, <Picture 1> (from the final shot) is fully referenced.
```

Ref2VA 六段：

```text
subject_definitions / summary / retention_analysis / detailed_description /
overall_soundscape / non_diegetic_music
```

先定义再引用；`<Picture 1/2/3>` 顺序与提交时的 `--ref-image` 顺序一致，一张图只承担一个角色（身份/场景/服装道具/姿势/风格），并写清保留项。

## 单次多镜（FL2VA）

一条约 10 秒的 FL2VA 可以包含 3–4 个镜头，不需要逐镜生成再拼；这是文戏/叙事默认。动作戏先看下一节的事件密度，不够就拆 2 × 5 秒。写法：

```text
integrated_multimodal_description: At 0.00 seconds, <Picture 1> (from [Shot 1]) is fully referenced. At 10.17 seconds, <Picture 2> (from the final shot) is fully referenced.

Subject A is an adult woman ... [static identity block]. Her face, hair, coat and body proportions remain identical in all shots.

[Shot 1] 0.00-2.60 seconds: <opening framing and action>.
[Shot 2] At 2.60 seconds, the camera cuts to <new shot size/angle>. This is a hard cut. <action>.
[Shot 3] At 5.20 seconds, the camera cuts to <new shot>. This is a hard cut. <action>.
[Shot 4] At 7.60 seconds, the camera cuts to <new shot>. This is a hard cut. <action reaching Picture 2>.
overall_soundscape: <one continuous bed for the whole clip>
non_diegetic_music: <one cue, or N/A>
```

规则：

- 切点严格递增、落在请求时长内；最后一个锚点用目标总时长，不按实际补帧后的时长反推。
- 每个切点写 `This is a hard cut.`，切后重述景别、机位、朝向和关键道具状态。
- `overall_soundscape` 写整条的声音底床，不按镜头分段，不写“每镜重新起雨声”。
- 3–4 拍是目标；模型可能把相邻两拍合成一次运镜。只要仍有清楚的新构图/新机位，不把“少一个硬切”当失败，也不为凑数加无意义切点。
- 文戏单拍只放一个主动作；动作戏按因果链放 1–2 招（见下节）；4 拍不要塞 4 个故事。
- 这是提示词层的切点，不是后期拼接；成片仍是一条 H3 生成、一条音轨。

## 动作与战斗提示词

动作戏先读 [`../h3-director/references/action-combat.md`](../h3-director/references/action-combat.md)。它和文戏的差别不是“多写几个动词”，而是事件密度、因果链和接触预算。

- **默认 5 秒一个动作单元**：5–7 个主要动作事件、1–3 个视觉段。10 秒需要 9–13 个事件；15 秒需要 13–18 个。事件 = 攻击、格挡/闪避、命中反馈、明显位移、武器/道具状态变化、环境碰撞。
- **一镜一条因果动作链**：`attack → trajectory → hit/block/miss → reaction → displacement → next attack`。这不是“一拳一镜”；一条 5 秒里可以有 1–2 招相接。不要每次攻击后复位、站定、对视。
- **写具体招式与向量**：谁先动、打哪里、从哪边、用什么挡、命中后身体怎么反应、脚退到哪。不要只写 `two people fighting` 或 `they exchange blows`。
- **写实时速度**：`full real-time 1.0x speed`、`full-weight impacts`、`the next attack begins before the previous recoil ends`。H3 在事件不足时默认往慢动作/停顿跑；只写 `fast` 不够。
- **一句只承载一个动作阶段**：不要把“起手 + 命中 + 受击 + 反击 + 落地”塞进同一句。按因果顺序分成 5–7 句，每句一个可见变化。
- **接触预算**：默认两人交手、一次一对接触点；快速连击要简化、缩短或拉开距离。多人同时抓扯、手指锁、复杂兵器缠绕拆成插入镜头或画外结果。
- **动作与台词分开**：先完成击打和受击，再让说话者开口；更稳的是把台词放到单独一段。打斗中同时说话容易退回底模慢动作，嘴部也容易被动作吃掉。
- **时间码可选**：公开动作模板多数只写 `[Shot N]` 和招式顺序，不写每一拳的微时间码。需要硬切或首尾锁定时才写时间；不要给 0.3–0.5 秒的微节拍，H3 更容易把它变成停顿。
- **不要用多张动作相位关键帧 + Add Guide 去“插动作”**：本机 E1 已证明它会钉帧并产生硬切/定格。动作连续靠因果链、参考视频/动作 LoRA 和采样，不靠密集锚点。

可复用骨架（身份块保持静态，动作块只写动作）：

```text
[Subject A and B static identity blocks]

The fight is already in progress at 0.00 seconds. A steps in with a right straight to B's jaw.
B slips outside, parries with his left forearm, and immediately counters with a left hook to A's ribs.
A's torso folds; his rear foot skids half a step, then he drives forward with a right knee.
Every recoil flows directly into the next attack; the exchange stays at full real-time 1.0x speed from the first frame to the last.

[Shot 2] At 2.60 seconds, the camera cuts to a wider side angle. This is a hard cut. ...
```

加载 Wushu 动作 LoRA 时，可按其模板把 `wushu_action` 放开头，并使用 `无慢动作，无停顿`；没有加载 LoRA 时不要把这些触发词当万能加速符。

## 写作顺序

1. **开场状态与 look block**：主体、地点、时间、画风、景别、光线、初始声音；用一句 look block 固定 capture base、镜头倾向、光色和表演基调。
2. **动作时间线**：按播放顺序写可见状态变化，一个变化一句；
3. **摄影机**：景别 + 有动机的运动；单次多镜要明确写切点和 `This is a hard cut.`，切后重述机位；
4. **声音**：台词/动作音随因果写入主体时间线；
5. **音乐政策**：观众专属配乐写 `non_diegetic_music`，没有就 `N/A`；
6. **约束**：时长、画幅、参考保留、文字保真，仅在图暴露这些控制时写。

## 专业场面调度

把摄影/构图/灯光/表演写成可见证据；H3 没有真实镜头元数据，焦段、光圈、光比只是写作提示。

- **一段 look block**：整条只写一次介质、焦段倾向、主光方向/软硬/光比、主色 + 强调色、材质、表演基调、声音视角。不要每拍重复。
- **景别按目的选**：建立用 WS/MS，关系用 MS/two-shot，对话用 MCU，决定用 CU，信息用 insert/ECU；相邻拍换景别，不连续同景别同机位。
- **构图有视线路径**：三分/中心、头顶空间、视线空间、负空间、框中之框、引导线、前中后景；竖屏把脸放上三分之一，下半部留给手和道具。
- **光有来源**：写方向、软硬、光比、色温和 practical；切镜后主光方向不要无故改变；光变一次对应一个转折。
- **色彩有物理来源**：一个主色 + 一个强调色；不要默认青橙/蓝灰/雾气；肤色是锚点。
- **表演写动作**：把 sad/angry 换成眼、眉、下颌、呼吸、手和重心的事实；一个 beat 一次情绪转化；听者也要演；角色按成年人写，服装完整。
- **一镜一主运镜**：写振幅、速度、持续时间、距离和终点构图；微动写厘米；插入/紧特写锁焦；不要同时推拉摇移。
- **声音四层**：对白、SFX、环境、BGM；一个动作一个主 SFX，环境 2–3 个元素，写透视和画外声，不要堆音效名。

完整表格、反模板检查和可复用骨架见 `references/professional-mise-en-scene.md`。

## 十条硬纪律

1. **身份块与运动块分开**：外貌（发色、瞳色、服装、体型、皮肤）集中成静态描述；运镜/动作另起段落，不复述外貌。两者混写会让模型每帧重新解释这张脸。
2. **文戏一镜一主动作；动作戏一镜一条因果动作链**：文戏最多再加 1–2 个次级动作（呼吸、衣角、雨）；动作戏允许 1–2 招相接，但每一招都要有受力、命中和反应，不是无因果的连挥。
3. **一个主运镜**：推/拉/摇/移只选一个主导；复合运镜分时段写（"rises 0–3 s, holds, then pushes in 4–6 s"）。微动要写距离（"pushes in only 15 centimeters over the full 3 seconds"）。
4. **写完成态**：文戏每个短镜头结尾写一个可见事实（"her hand has closed fully around the coin and stays closed"）；动作戏写命中结果、位移或新劣势（"his head snaps back and his rear foot skids half a step"），不要回到起手式。
5. **情绪拆开写**：不写 sad/angry/surprised，写眉、眼、下颌、呼吸、手与皮肤的具体变化；主导情绪在脸上，底层情绪在呼吸/姿态，破绽在眼睛。
6. **非说话者的嘴要有正向静止事实**：`lips at rest, jaw closed, his breath lifting his chest`。不要只写"没说话"。
7. **朝向单独写**：地点/活动不决定脸是否可见。明确正脸、四分之三、侧脸或背对，以及眼睛是否必须可见；切镜后重述。
8. **正向约束，不写否定清单**：没有独立 negative 输入。把必须避免的事写成一个成立的事实；景深两种写法——全画面清晰 `sharp focus throughout, deep depth of field`，主体实背景虚 `subject in sharp focus, background falling into soft bokeh`。
9. **删空话**：beautiful / stunning / epic / cinematic / 8k 不改变渲染。换成具名参照（导演、布光、镜头规格）和物理后果。
10. **台词逐字保留**：说话人用稳定 ID（S1/S2），台词放引号内；保留用户语言，不翻译、不改写。画外人说话要说明"off screen"，可见人物嘴唇闭合。

## 对话与声音政策

- `不要对白` / `no dialogue` 只约束台词：保留环境音、动作音与音频流。
- 只有 `完全静音` / `no audio` 才关闭全部音频。
- `non_diegetic_music: N/A` 只表示没有观众配乐，不表示没有画内声。
- 简短台词要给出窗口任务：扩展台词、写一个环境/动作事件，或把镜头剪短到台词长度；不要让空白窗口留给模型即兴。
- 说话者：`says the line once and nothing else: "<台词>"`。

## 声音一致性（跨镜音色）

完整方法、官方绑定句、社区实测与已知坑见 [`references/voice-consistency.md`](references/voice-consistency.md)。写任何带台词的提示词前先过这六条：

1. **声音圣经逐字复用**：每个角色一行（语言 / F0 目标带 / 质地 / 语速 / 咬字 / 情绪基线 / 正典样本），每镜复制同一行。"苍老"改"低沉"就算改描述，会漂。
2. **VOICE 块与身份块分开**：身份块只写外貌，VOICE 块只写声音的物理事实（`fundamental pitch around 100 Hz, dry gravelly timbre, slow pace, falling sentence endings, close-miked`）。不写"苍老的声音"这类形容词。
3. **选角声学距离是硬规则**：模型靠音高/共振峰/声道长度区分说话人，不靠提示词里的绑定关系。同场两个同性别说话人 F0 目标带差 **≥25–30 Hz（约 4 个半音）**且质地不同；一条里 ≤2 个说话人最稳。距离不够就改音色描述、换轻口音样本或拆条，不要堆形容词。
4. **说话人 ID 全片固定**：`(S1)`/`(S2)` 按实际发声顺序分配一次后复用。A→B→A 在 Ref2VA 里要给第三次发声**新的音频槽**（`Audio 3` = 与 `Audio 1` 同一文件）并写 `S3`，不要写 `S1/S2/S1`。
5. ** incidental 发声必须格式化或删除**：裸写 `sharing a small chuckle`、叹气、"嗯"会被当成台词并打乱说话人路由（社区实测：删掉后所有声音恢复正常）。要么进 `<d>`/引号当正式台词，要么删掉。
6. **人数与站位锁**：`Visible actors in this shot: A, B.` + `Preserve the established screen-side positions and spacing. Do not swap, duplicate, or add cast members.` 这条同时治"背景多出一个人"的穿帮。

台词预算：约 **0.36 s/词**（社区数千镜头经验值，日语按拍校准），一条 **≤6 个对白轮次**；时长敏感时重试**只改 ±1–2 s**，seed/步数/提示词/参考全锁。

路线边界：本机 Set C 的 I2VA/FL2VA 图**没有音频参考输入**，写 `<Audio 1>` 是悬空标签，不生效还可能引入串台词——这两条路线只能靠 VOICE 块 + 声学距离。音色参考要走 Ref2VA（`--ref-audio`），接线与上限见 `h3-generate`。

## 中文提示词与时长

- 中文不要只写一两个名词：H3 的长多模态序列会让极短中文被种子主导。至少写清主体特征、环境、景别、光线、动作，约 30–50 字起，再用低成本预览验证。
- 切点时间必须严格递增且落在请求时长内；I2VA/FL2VA/L2VA 的尾帧时间等于目标时长。H3 可能自然补 16 帧，不要用补帧后的时长改提示词。
- 124 帧 @ 24 fps ≈ 5 s；72 帧 ≈ 3 s。提示词里不要写像素尺寸，画幅交给工作流参数。

## 简体图与官方 schema

本机常用简体 ClipProj 图只接受自然语言，不认官方 `<d>`、`<scenetrans>`、`<cutoff>` 等标记。先看所选工作流的示例；官方标记只在图接受官方 prompt schema 时使用。Ref2VA 的身份锚句用 `<Picture 1>`，不要换成别名后再改口。

## 面部与身份

- 第一镜只保留一个人；正脸或四分之三，眼睛、鼻子、嘴、发际线清晰；先验证无对白稳定性，再加对白或口型。
- 身份一致性优先走 `Ref2VA`（Set C，`ref_image_size=match`）；需要精确首尾构图或严格运镜时用 `FL2VA` 双关键帧。动作戏只用首帧或首 + 尾两帧锁构图，不要生成多张动作相位关键帧；连续运动靠提示词和路线，不靠 Add Guide 插值。
- W4A8 路线不要写 `natural skin texture / freckles / stubble`，会变砂纸。用 `smooth refined skin, fine delicate pores, soft highlight roll-off`，避免 `heavy grain / waxy plastic / oily sheen`。
- 社区逐帧换脸/修复器（FaceDetailer、CodeFormer/GFPGAN）不作为默认后处理：会闪烁、加显存、改变身份。

## 提交前检查

对照 `references/failure-modes.md` 过一遍：filler-babble、动作截断、假操作、多手、滑步、多运镜、跨镜身份漂移、打戏拼接、打斗慢放/定格、情绪空泛、整帧糊化、跨镜音色漂移、同性别说话人合并、参考音频串台词、A→B→A 错人。动作戏另查事件密度、因果链、实时速度、是否误用多锚点、是否把台词塞进交手。带台词的另过 `references/voice-consistency.md` 的 8 问。检查结果附在输出里：

```text
Route: FL2VA / Ref2VA / ...
Canvas & length: ...
Shots: <单条 3–4 拍 / 逐镜 N 条>
Action: <5s 5–7 events / N/A；real-time；有无 standoff/reset>
Prompt: <三字段或六字段>
Voice: <说话人数 / F0 目标带与间距 / 轮次 / 词数×0.36s / 参考音频有无>
Risks: <仍存在的具体风险>
```

## 资源

- `references/prompt-writing.md`：官方三字段/六字段、锚句、镜头与声音规则的操作摘要。
- `references/prompt-assist.md`：模糊创意 → 有界提示词的模板与 H3 映射。
- `references/cinematic-prompting.md`：电影决策卡、构图压力、光学语法。
- `references/professional-mise-en-scene.md`：look block、景别/构图/灯光/色彩、表演、运镜、声音与反模板检查。
- `references/official-h3-insights.md`：Context-IR、参考角色、保留分析与官方能力边界。
- `references/failure-modes.md`：症状—机制—正向改法目录。
- `references/voice-consistency.md`：声音圣经、选角声学距离、VOICE 块、官方 `<Audio N>` 绑定、时长/轮次预算、已知坑与验收门限。
- [`../h3-generate/references/show-contract.md`](../h3-generate/references/show-contract.md)：开拍前合同、镜头卡字段与 show 校验门禁。
- [`../h3-director/references/action-combat.md`](../h3-director/references/action-combat.md)：动作密度、因果链、实时速度、动作路线与慢放诊断。

## 来源

- 官方 H3 prompt guide：https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md
- 官方 h3-prompt-writing：https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing
- StudioBinder, rules of shot composition: https://www.studiobinder.com/blog/rules-of-shot-composition-in-film/
- StudioBinder, film blocking: https://www.studiobinder.com/filmmaking-techniques-film-blocking/
- OSideMedia, higgsfield-ai-prompt-skill: https://github.com/OSideMedia/higgsfield-ai-prompt-skill
- 公开提示词模式参考（只作写法，不是运行时依赖）：https://github.com/higgsfield-ai/skills
- Combat Base V2 模型卡：https://huggingface.co/JOKER141/MiniMax-H3-Combat-Base-V2
- General Motion Continuity Repair：https://huggingface.co/JOKER141/MiniMax-H3-General-Motion-Continuity-Repair
- Wushu Action v7：https://huggingface.co/Jojocodex/wushu-action-v7-minimax-h3-fl2va-ref2va-lora
