# 专业场面调度与提示词（H3 适配）

这份文档把摄影、构图、灯光、色彩、表演和声音判断，翻译成 H3 能渲染的可见证据。它不是镜头元数据，也不承诺 H3 具备真实光学系统；焦段、光圈、光比都只是写作提示，最终要靠画面结果验证。

## 1. 先写一句 look block

在身份块和分镜之前，用 1–2 句固定整条的视觉与表演基调。整条只写一次，不要在每个 beat 重复。

| 要素 | 写什么 | 例子 |
|---|---|---|
| capture base | 介质、年代、质感 | live-action feature film, restrained film texture |
| lens/perspective | 焦段倾向 + 可见后果 | 40mm natural perspective, moderate depth |
| lighting doctrine | 主光源、方向、软硬、光比 | soft window light from camera left, 4:1 ratio |
| color thesis | 主色 + 强调色 + 物理来源 | blue-gray concrete with one rust-red coat |
| texture/design | 材质、磨损、年代 | worn wood, wet concrete, practical tungsten |
| acting register | 表演风格 | restrained naturalistic acting, small gestures |
| sound convention | 视角与底床 | close perspective, continuous rain bed |

```text
Live-action feature film, 40mm natural perspective, soft single-source window light from camera left, cool dusk with one warm practical lamp, muted blue-gray palette with a rust-red accent, restrained naturalistic acting.
```

- 这段是视觉约束，不是“电影感”形容词堆。每个词都要能对应到画面里的东西。
- 声音细节最终写进 `overall_soundscape`；look block 只约定视角和底床。
- 不要写 `8k, masterpiece, cinematic, award-winning`；它们不改变画面，只稀释真正的信息。
- W4A8 路线不要写 `heavy grain / freckles / stubble`，会把皮肤变成砂纸；用 `fine delicate pores, soft highlight roll-off`。

## 2. 景别、角度与镜头目的

先决定这一拍要让观众获得什么，再选景别。景别不是装饰，是信息距离。

| 景别 | 主要用途 | 风险 | 竖屏注意 |
|---|---|---|---|
| EWS/WS | 地理、孤立、规模 | 人物太小，表情消失 | 用门框/道路/窗形成纵向层次 |
| MS | 关系、身体语言、两人距离 | 容易变成电视剧站桩 | 腰上中景最适合 9:16 |
| MCU | 对话、表情 + 手部 | 构图太紧会切头发 | 眼睛放上三分之一，留头顶空间 |
| CU | 决定、反应、情绪转折 | 连续特写会压垮节奏 | 不要每拍都切特写 |
| ECU/insert | 关键道具、文字、时间 | 信息太碎，观众迷路 | 让物件占画面中心或三分线 |
| Two-shot | 权力关系、距离、同框 | 两人都小，脸不清楚 | 一前一后或一高一低，不要并排站 |

角度：

- 平视：中性、观察、对话默认。
- 低角度：权力、威胁、压迫；不要每个英雄都仰拍。
- 高角度：脆弱、被审视、命运感；也可以表示地理关系。
- 俯拍：地图感、无处可逃；适合建立空间，不适合长对白。
- Dutch angle：失衡、精神压力；整条用一次就够，不要连续倾斜。

焦段只作为视觉倾向：

- `24–28mm`：环境压力、空间纵深；避免脸贴近广角边缘。
- `35–40mm`：自然观察、关系 blocking；短剧最稳。
- `50mm`：中性人眼距离；对话和中近景。
- `65–85mm`：压缩、监视、隔离；不要把所有背景都虚成奶油。

需要写景深时，写可见结果，不要只写光圈值：

```text
Subject in sharp focus, the far doorway falling into soft bokeh; the key remains legible in her hand.
```

## 3. 构图：让眼睛有路径

写构图前，先用一句话说清视线路径：“眼睛从 A 进入，停在 B，从 C 离开。”说不出来，通常只是元素堆。

| 手法 | 用途 | 可见写法 |
|---|---|---|
| 三分法 | 关系、不平衡、留白 | eyes on the upper third line; subject on the left third |
| 中心/对称 | 秩序、权力、仪式、压迫 | symmetrical centered frame, subject facing the camera |
| 头顶空间 | 尊重、压迫或渺小 | clean headroom above the hairline; excessive headroom for vulnerability |
| 视线空间 | 期待、方向、离开 | negative space on the frame right where she looks |
| 负空间 | 孤立、缺席、等待 | subject small at the edge of a large empty room |
| 框中之框 | 被困、窥视、秘密 | framed by a doorway, window, mirror or gap between shelves |
| 引导线 | 目的地、纵深、命运 | counter edge, road, corridor or table line leading to the key |
| 前中后景 | 空间层次、压力 | blurred shoulder in foreground, subject in midground, lit door in background |
| 地平线 | 稳定或不稳定 | level horizon; intentionally tilted horizon only for unease |

竖屏 9:16 的额外规则：

- 脸放在上三分之一到上半部，不要把额头或下巴切掉。
- 下半部留给手、道具、桌面和身体动作；不要只拍一张大头。
- 用门、窗、走廊、货架形成纵向线条；横向大全景在竖屏里容易空。
- 两人的左右关系在竖屏里更挤，优先一前一后、一高一低，或过肩。
- 不要默认极近特写；竖屏裁切会放大鼻眼比例，腰上中景通常更稳。

前景虚化必须有理由：门框、车窗、路人肩、栏杆、窗帘、反射。没有理由的黑边不是电影感，是遮挡。

## 4. 灯光：先有来源，再有情绪

每一条光都写清五件事：来源、方向、软硬、光比、色温。能写 practical（画内实用光源）就写。

```text
Soft window light from camera left, 4:1 ratio, cool blue dusk; a warm tungsten practical on the far wall separates her shoulder from the dark corridor.
```

| 判断 | 写法 | 效果 |
|---|---|---|
| 方向 | from camera left / right / behind / below | 决定脸部的明暗结构和悬念 |
| 软硬 | soft diffused window light / hard doorway light | 柔和亲密 vs 硬朗压迫 |
| 光比 | 2:1 gentle, 4:1 dramatic, 8:1 noir | 控制隐藏多少信息 |
| 色温 | cool dusk / warm tungsten / green fluorescent | 冷/暖/病态的对比 |
| 背光 | rim light from the doorway | 把人物从背景里分离 |
| 实用光 | desk lamp, refrigerator glow, phone screen | 让光源在画面里成立 |

- 不要无来源的 beauty light、随机轮廓光、满屏柔光。
- 光可以标记转折：对方关灯、窗帘落下、手机屏幕熄灭、门打开。一个 beat 只变一次。
- 切镜后保持同一主光方向；除非有可见原因，不要从左侧光跳到右侧光。
- 高光保护皮肤，不要让额头和鼻梁死白；H3 不保证曝光，抽帧核对。
- 暗部不是纯黑；留一点环境细节，否则压缩后变成块。

## 5. 色彩：一条色彩脚本，不是滤镜

先定三个 beat 的色彩变化，再写进 look block 或分镜备注：

```text
Beat 1: cool gray room, muted clothing.
Beat 2: the key is the only warm brass accent.
Beat 3: the open door adds a cold blue shaft; the brass stays in her closed hand.
```

- 一个主色 + 一个强调色，强调色要有物理来源：衣服、道具、灯、招牌、天空、金属。
- 不要默认青橙、蓝灰、雾气和粒子；这些是最容易被识别的 AI 模板。
- 用美术和光做颜色，不要只靠后期滤镜；后期用于统一，不是重新发明。
- 肤色是锚点：即使环境很冷，脸不能变成灰绿或塑料。
- 压缩会放大高饱和渐变的 banding；大面积纯色和极端渐变要谨慎。

## 6. 表演：写可执行的动作，不写情绪标签

把抽象情绪翻译成身体事实：

| 不要写 | 改写为 |
|---|---|
| she is sad | she reads the message twice, her thumb stops, her jaw tightens, she breathes out slowly |
| he is angry | he sets the cup down harder than needed and keeps his fingers on the rim |
| she is afraid | her eyes go to the door, she stops breathing for a beat, her hand closes on the key |
| he is lying | he answers a half-beat late, looks at her mouth, then back to her eyes |
| she is relieved | her shoulders drop, her grip loosens, she finally blinks |

- 一个 beat 只发生一次情绪转化：从怀疑到决定、从忍耐到开口、从希望到放弃。
- 听也是表演：对方说话时，听者的眼睛、呼吸、手指和重心要有反应；不要只让说话者演。
- 反应镜头是独立镜头，不是附属品；有时一个 2 秒的听完比十句台词更有信息。
- 微表情靠眼、眉、下颌、呼吸和手，不靠大哭大喊；短剧 3 秒里尤其如此。
- 角色按成年人写，服装完整、符合场景；不要把未成年外观或性化处理写进提示词。
- 对白之间留换气；不要让说话者说完立刻切走，除非故意用硬切打断（官方 schema 可用 `<cutoff>`）。

对白写法：

```text
She looks at him, holds the pause for one beat, then says in a quiet voice: "<原语言台词>". He does not answer; his eyes drop to the key in her hand.
```

## 7. 摄影机：一个主运镜，落到明确终点

每个 beat 只选一个主导运动。复合运动必须分时段写，不能同时推、拉、摇、移。

| 运动 | 适合表达 | 写法要点 |
|---|---|---|
| Push in | 靠近、意识到、压迫 | 写距离与时间：15 cm over 3 seconds |
| Pull out | 孤立、事后、离开 | 终点构图要明确，不要越拉越空 |
| Pan | 揭示、跟随、连接 | 写方向、幅度、停在哪 |
| Truck | 伴随、观察、平行 | 保持人物在画面同一侧 |
| Tilt | 规模、权力、上下关系 | 起幅和落幅都要有内容 |
| Arc | 关系变化、绕行 | 写绕多少、速度、是否保持视线 |
| Tracking | 追逐、同行、时间压力 | 写跟谁、保持什么距离 |
| Handheld | 不安、即时、冲突 | 幅度小，不要全片抖 |
| Static | 控制、观察、让表演说话 | 静止也是导演选择 |

- 运动必须有动机：跟随、揭示、压迫、离开、发现。
- 写清振幅、速度、持续时间；微动要写具体距离。
- 运动必须落到你想要的终点构图；写“push in”却要求最后仍是大全景，模型会矛盾。
- 一个镜头里不要同时写“手持晃动 + 快速推近 + 环绕 + 变焦”。
- 插入镜头和紧特写要锁焦：`focus stays on the key, the background falls soft`。
- 摄影机可以不动；静止的中近景常常比无意义的推拉更专业。

## 8. 声音也是场面调度

声音四层：对白、动作音/SFX、环境、BGM。写声音时跟着动作的因果走，不要最后堆一串音效名。

- 一个动作一个主要 SFX；不要给每个脚步、每件衣服都加声音。
- 环境保留 2–3 个元素：雨、远处交通、房间电流、冰箱低鸣；不要十层叠加。
- 写透视：near/far、画内/画外、闷在墙后/隔着玻璃。
- 画外声可以扩大空间，也可以驱动切点：下一场的声音提前 2–4 帧进入。
- 静音是设计：重击或决定前留 0.3–0.8 秒，比加音效更有效。
- `non_diegetic_music` 只写观众能听到的配乐；写乐器、速度、动态，不写“史诗感”。
- 用户没要求就不加 BGM；原生台词镜头不要再叠 TTS 或第二层人声。

## 9. 可复用骨架

```text
integrated_multimodal_description: At 0.00 seconds, <Picture 1> (from [Shot 1]) is fully referenced. [One look block: capture base, lens tendency, light, color, texture, acting register.]

Subject A is an adult ... [static identity block]. Her face, hair, clothing and body proportions remain identical in all shots.

[Shot 1] 0.00-2.80 seconds: [shot size + composition + blocking + one action + motivated light + camera behavior].
[Shot 2] At 2.80 seconds, the camera cuts to [new shot size/angle]. This is a hard cut. [new information + reaction + camera behavior].
[Shot 3] At 5.60 seconds, the camera cuts to [new shot]. This is a hard cut. [turn + end state reaching Picture 2].
At 9.00 seconds, <Picture 2> (from the final shot) is fully referenced.
overall_soundscape: [one continuous bed, 2-3 ambience elements, perspective, physical sounds].
non_diegetic_music: [one cue with instruments/tempo/dynamics, or N/A].
```

- look block 只写一次；身份块只写一次；每个 beat 只写新信息。
- 每个切点后重述景别、机位、朝向和关键道具状态。
- 最后的锚点时间用目标时长，不用自然补帧后的实际时长。
- 3–4 拍是目标，不是合同；如果模型把两拍合成一次有动机的运镜，按视觉段验收。

## 10. 反模板检查

提交前，如果出现以下任何一条，重写：

- look block 只有形容词，没有光源、颜色来源或材质；
- 每一拍都是 wide → close-up → reaction 的固定模板；
- 摄影机运动没有动机，或者运动终点和构图要求矛盾；
- 光线没有来源，或切镜后主光方向无故改变；
- 情绪只写 sad/angry/afraid，没有身体事实；
- 构图没有视线路径，前景遮挡没有理由；
- 声音只有“环境声”三个字，没有透视和因果；
- 一条 10 秒里塞进超过 4 个 beat、超过 3 个重要角色或超过 1 个地点。

## 来源

- StudioBinder, rules of shot composition: https://www.studiobinder.com/blog/rules-of-shot-composition-in-film/
- StudioBinder, film blocking: https://www.studiobinder.com/filmmaking-techniques-film-blocking/
- OSideMedia, higgsfield-ai-prompt-skill（摄影、表演与声音写法参考）: https://github.com/OSideMedia/higgsfield-ai-prompt-skill
- 公开摄影、色彩与声音写法参考（非运行时依赖）：https://github.com/higgsfield-ai/skills
