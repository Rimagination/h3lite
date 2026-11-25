---
name: h3-generate
description: 在本机 ComfyUI 上提交 MiniMax H3 生成任务（T2VA/I2VA/FL2VA/Ref2VA），选择路线与分辨率，绑定参考图与参考音频（--ref-image / --ref-audio）做身份与音色参考，监控进度并验证输出。当用户要求渲染、重跑、查看进度、批量生成或接音色参考时使用。
---

# H3 生成：热路径

目标：一次提交、一次等待、一次验证。环境未验证时先交给 `h3-workstation`；提示词未定稿时先交给 `h3-prompt`。

## 开拍前合同（强制）

多镜、角色一致、台词或白模项目，先把 `show.json` + `canon.json` 落盘并通过校验，再提交任何 GPU 任务。单条测试可以只写镜头卡，但同样先写验收条件。

```powershell
python scripts/h3_show_init.py --dir projects/ep04 --project ep04
python scripts/h3_show_validate.py --spec projects/ep04/show.json --check-sha --strict
```

- `show.json` 是唯一调度源：交付规格、镜头 ID、prompt、route/template、length、seed、参考图/音频、首尾帧、白模版本、验收条件都写在里面；聊天记录不算。
- `canon.json` 是身份块、VOICE 块和参考包的唯一正本；每镜逐字复用，不重新发明同义词。
- `0 errors` 才允许提交；`--strict` 下 warnings 也算失败。校验器会抓 481 帧、Ref2VA 混首尾帧、Set C 传 A/B、缺文件/缺 canon、模板与路线不匹配、白模未走 Ref2VA、参考包哈希漂移。
- 规则全文见 [`references/show-contract.md`](references/show-contract.md)；示例见 `assets/show.example.json`、`assets/canon.example.json`。
- 新建项目用 `h3_show_init.py`；它只建骨架，不伪造提示词或参考图。真实 prompt、参考包和 `refs.sha256` 仍要人写/人审。
- 多镜批量执行用 `scripts/h3_showrunner.py --spec ...`：一次校验、逐镜 `--queue-only`、逐镜验证、`--resume` 续跑；单镜 `h3_generate.py --show-spec` 自动套同一门禁。

## 前置

- 医生报告缓存不超过 30 分钟，且 ComfyUI 在 `http://127.0.0.1:8188` 健康；已健康就复用，不重启、不重新发现工作流。
- 同一配置的 manifest 处于 `submitting`/`queued`/`running` 时**不得重复提交**；返回已有 prompt ID。只有用户明确要求第二条相同任务时才 `--allow-duplicate`。
- 不在热路径里查 Git、模型哈希、依赖版本或官方文档；只有上一条命令给出具体错误指向那里时才查。

## 一条命令的默认路径

已配置环境上的普通生成只跑一次 fastpath：

```powershell
python scripts/h3_fastpath.py `
  --comfyui <ComfyUI-path> `
  --prompt-text "<定稿提示词>" `
  --resolution 640x352 `
  --video-seconds 5 `
  --filename-prefix video/H3Lite_my_clip `
  --json
```

- 不带帧参数 = T2VA；`--mode auto` 会按传入的帧参数推断模式。
- I2VA：`--mode i2va --first-frame <png>`。
- FL2VA：`--mode fl2va --first-frame <png> --last-frame <png>`。
- L2VA：`--mode l2va --last-frame <png>`（会移除 I2V 模板的首帧占位）。
- 已确认的分辨率只提醒一次风险，预检 `blocked` 才停。
- 提示词里要求“完全静音”才移除音频；`不要对白` 仍保留环境音与音频流。

fastpath 复用医生缓存、内联规划/预检、提交、一次有界 watch，并把计划与提示词写进 run 目录。终端出现运行中的 cell 就等它，不要再开第二个监控。

## 帧数与画幅约定

| 用途 | `--length` | 实际 | 备注 |
|---|---|---|---|
| 快切短剧 | 72 | 73 帧 ≈ 3.042 s | 不硬裁成 3.000 s |
| 文戏常规 | 124 | ≈ 5.167 s | 默认 |
| 动作单元 | 124 | ≈ 5.167 s | 动作戏默认；5–7 个主要事件 |
| 中段 | 243 | ≈ 10.1 s | 链式常用；动作 9–13 事件 |
| 10 秒单条多镜 | 244 | 260 帧 ≈ 10.833 s | Set C FL2VA 实测自然补 16 帧，不裁不重跑 |
| 单段上限 | 362 | ≈ 15.1 s | 竖屏实测约 12 min；动作 13–18 事件 |
| 禁止 | 481 | — | 本机曾 48 W 自旋死锁，必须重启服务 |

- 24 fps，低显存基线 640x352、4 步、`res_multistep` + `simple`。
- 0.4 MP 官方风画布（16:9 → 864x480）只在 planner 批准或用户明确要求时用。
- 32 像素对齐是 VAE 16 像素空间降采样与 DiT 2 像素 patch 的共同约束；不要承诺“720p”等消费标签，报告真实画布。
- 帧数校验允许向上最多 16 帧（约 8%）的自然补帧；短于请求超过 2 帧仍判失败。244→260 是正常补帧，状态应报 success。

## 模板与路线

Set C（16 GB，2026-11-19 验证）是当前速度/质量默认：

| 模板 | 用途 | 画布 | 实测 |
|---|---|---|---|
| `h3_c_speed640` | T2VA 快速 | 640x352 | 约 23 s |
| `h3_c_t2va768` | T2VA 768p | 1344x768 | 约 129 s |
| `h3_c_quality864` | T2VA 质量 | 864x480 | 约 42 s |
| `h3_c_i2va768` | I2VA 单首帧 | 1344x768 | 约 145–160 s |
| `h3_c_fl2va768` | FL2VA 首尾帧 | 1344x768 | 约 152 s |
| `h3_c_ref2va768` | Ref2VA 人像 | 1344x768 | 约 161 s |

- 六个模板是**自钉**的：`--component-set auto` 或不带 `--resolve-models`；**绝不传 `--component-set A/B`**。
- **视频 VAE 接缝**：Set C 默认 `minimax_h3_sol_vae_int8_convrot` 可能在 128 px 边界留下固定网格；最终交付前用 `h3-post/scripts/h3_grid_check.py` 检查。若 `suspected`，保持其他变量不变、只加 `--video-vae minimax_h3_video_vae_fp16.safetensors` 做 A/B；不要换 Sol fp16（同接缝）。详见 `h3-workstation/references/component-sets.md`。
- **16 GB 自动选 C（0.1.1）**：默认 `--workflow-template auto` + `--component-set auto`、未加 `--acceleration compat` 时，fastpath 在 ≥15.5 GB GPU 上按实测画布自动选 C——T2VA 640×352→`h3_c_speed640`、864×480→`h3_c_quality864`、1344×768→`h3_c_t2va768`；I2VA/FL2VA/Ref2VA 1344×768→各自模板（竖屏同理）。缺任一模型/节点类、L2VA、未实测画布（如 960×544、864 I2VA），或显式 A/B/模板/compat 时回退注册的 A/B 路线。自动选 C 不下载、不改组件集；`--dry-run` 的 `workflow_template_selection` 与 `set_c_auto.reason` 写明本次为何选或不选 C。
- 需要 Set C 启动参数 `--fast fp16_accumulation fp8_matrix_mult cublas_ops autotune` 才有上表耗时。
- **768p 文生视频用 `h3_c_t2va768`，不要用 `h3_w4a8_t2v`**：同画布 1344×768 / 124 帧 / 4 步实测 128.8 s vs 185.1 s（快约 30%），且不需要 Triton/Sage。它与 speed640 同一套 turbo v1.0 + Sol INT8 VAE 栈，但 768p 下原生稀疏必须 `start_percent=0.0`；沿用 speed640 的 0.2 会让首个 768p 稠密步多花约 70 s（实测 198.4 s）。
- `h3_w4a8_t2v` 保留给低显存 `_compat` 兜底与交叉验证；768p T2VA 的推荐路线是 `h3_c_t2va768`。
- **单首帧一律用 `h3_c_i2va768`，不要用 `h3_w4a8_i2v_compat` 跑 768p**：后者没有稀疏注意力、用 stock fp16 VAE，本机同画布同帧数实测 369 s vs 145 s（约 2.5×）。`h3_c_i2va768` 就是 `h3_c_fl2va768` 去掉尾帧锚点，其余（Pika lite LoRA、Sol INT8 VAE、原生 BlockSparse sol-attn、SigmaShift 6/3）逐项相同。
- 在 `h3_c_i2va768` 上再传 `--last-frame`，脚本会自动补 `LoadImage` 与 `last_frame` 输入，等价于 FL2VA；不需要换模板。
- Ref2VA 用 `--ref-image` 按 `<Picture 1>` 顺序重复；不要与 `--first-frame`/`--last-frame` 混用。参考图是真实条件输入，不是风格附件。
- 低显存 Set A/B：`h3_w4a8_t2v`、`h3_w4a8_i2v`、`h3_w4a8_ref2va` 及对应 `_compat`。`v4` turbo 在加速图（含 Set C 稀疏）上 **<6 步被护栏拒绝**（4 步重影/拖影），≥6 步放行（本机 6/8 步稀疏与稠密均干净）；4 步想用 v4 就走 `_compat`。
- 路线选择：人像/身份优先 Ref2VA；精确首尾构图用 FL2VA；单首帧 I2VA；其余 T2VA。详见 `references/face-quality.md`。

## 参考音频（Ref2VA 音色参考）

人物声音一致性**先做满提示词层**：VOICE 块逐字复用 + 选角声学距离（同场同性别说话人 F0 目标带差 ≥25–30 Hz）。方法见 [`../h3-prompt/references/voice-consistency.md`](../h3-prompt/references/voice-consistency.md)。仍漂时才上音色参考，且只有 Ref2VA 图有音频输入——I2VA/FL2VA 上传 `--ref-audio` 会被拒绝。

```powershell
python scripts/h3_generate.py `
  --workflow-template h3_c_ref2va768 `
  --prompt-file prompts/shot03.txt `
  --ref-image <identity.png> `
  --ref-audio <voice_A_dry.wav> `
  --comfyui <ComfyUI-path> --output-dir <ComfyUI>\output `
  --resolution 1344x768 --length 124 `
  --component-set auto --watch --json
```

- `--ref-audio` 可重复，按 `<Audio 1>` `<Audio 2>` 顺序绑定到 `ref_audios.ref_audio_0/1/2`；脚本自动新增 `LoadAudio` 节点，并把样本按 sha256 命名 staged 进 ComfyUI `input/`，不覆盖用户文件。`--dry-run` 可先看绑定结果。
- 上限（官方文档 + 本机 `object_info` 实测一致）：`ref_images` ≤9、`ref_audios` ≤3、`ref_videos` ≤3、`ref_video_audios` ≤3；每条音频 2–15 s、总 ≤15 s；混合文件 ≤12；**音频不能是唯一输入**，必须至少有一张 `--ref-image`。
- `audio_vae` 必须接上（Set C `h3_c_ref2va768` 已接）。节点 tooltip 原文：没有它，参考音频只条件化文本编码器，不会进入音频分支。
- 样本要求：单人、干声、无环境底噪、5–8 s、与目标同语言同情绪。从成片里截的带环境声样本会引入开头抢话、台词重复、首音节被切（MiniMax-H3 issue #95）。
- **不要同时接"续接视频自带音轨"和"独立音色参考"**：ComfyUI issue #16289 会直接崩 `RuntimeError: shape mismatch: value tensor of shape [938, 32] cannot be broadcast to indexing result of shape [1010, 32]`（`comfy/ldm/minimax/model.py:711`），两者单独都正常。二选一。
- A→B→A：给第三次发声**新槽**（同一文件再传一次 `--ref-audio` → `<Audio 3>`），提示词写 `S3 using Audio 3`；写 `S1/S2/S1` 会错人。
- 提示词里显式写 `<Audio 1> is only this character voice timbre; do not copy its words.`，音色参考用 `reference` 关系标记，不要用 `fully_copy`。
- 接了参考音频仍漂时按 #95 的 A/B/C 对照诊断：A 接音频 / B 同提示词同 seed 断开音频 / C 在 B 基础上再删悬空 `<Audio 1>` 文本。实用结论可能是断开音频（代价：一致性更难），不要盲目重试同一配置。
- 时长敏感：同一提示词可能 12.5 s 失败、14 s 成功。重试**只改时长 ±1–2 s**，seed/步数/提示词/参考全锁；跑通的配置原样记录成基线。

## 参考视频（Ref2VA 运动/运镜参考）

白模/灰模视频可以直接作为 `<Video 1>`，不需要先转 depth/pose。`--ref-video` 可重复（≤3），脚本自动新建 `LoadVideo → GetVideoComponents`，绑定到 `ref_videos.ref_video_0/1/2`；文件按 sha256 staged 到 ComfyUI `input/`。参考视频不要带音轨；身份仍由 `--ref-image` 的 `<Picture 1>` 负责。

```powershell
python scripts/h3_generate.py `
  --workflow-template h3_c_ref2va768 `
  --prompt-file prompts/shot05.txt `
  --ref-image <face.png> --ref-image <body.png> `
  --ref-video <white_proxy_12fps_864x480.mp4> `
  --comfyui <ComfyUI-path> --output-dir <ComfyUI>\output `
  --resolution 1344x768 --length 244 `
  --component-set auto --watch --json
```

- 代理规格：12 fps / 864×480 / SAR 1:1 / 无音轨；白模母版另存 24 fps 审片。
- 提示词写清视频参考只负责动作、走位、相机和接触点，不复制灰模材质/球关节/场景；身份绑定原图。
- `--ref-video` 只对 `MiniMaxH3ReferenceToVideo` 工作流有效；I2VA/FL2VA 会拒绝。
- `--dry-run` 可看自动新增的 LoadVideo/GetVideoComponents 节点。

## 文戏单次多镜（10 秒 3–4 拍）

约 10 秒、3–4 拍、首尾构图要锁时，直接用 `h3_c_fl2va768` **一条生成**，不要逐镜生成后拼。这是文戏/叙事默认；动作戏先看下一节的 9–13 个事件门槛。提示词按 `h3-prompt` 的 `[Shot N]` 写法，切点写 `This is a hard cut.`。

```powershell
python scripts/h3_fastpath.py `
  --comfyui <ComfyUI-path> `
  --mode fl2va `
  --first-frame <first.png> --last-frame <last.png> `
  --workflow-template h3_c_fl2va768 `
  --component-set auto `
  --resolution 768x1344 --video-seconds 10 --seed 20261120 `
  --filename-prefix video/H3_multi_shot --json
```

- Set C 图的 `--component-set` 必须是 `auto`；fastpath 会以 auto 提交，绝不把 auto 归一成 C 后再传给自钉模板。
- 切点数是目标，不是合同。模型可能把相邻两拍合并为一次运镜；只要成片仍有 3–4 个清楚视觉段、尾帧落到 `<Picture 2>`，按成功验收。
- 不为“少一个硬切”重跑；只有整条没有形成新构图或首尾锚点明显漂移时才重跑。

低层提交（自定义图、Ref2VA、Set C）：

```powershell
python scripts/h3_generate.py `
  --workflow-template h3_c_ref2va768 `
  --prompt-file prompts/shot03.txt `
  --ref-image <identity.png> `
  --comfyui <ComfyUI-path> --output-dir <ComfyUI>\output `
  --resolution 1344x768 --length 124 `
  --component-set auto --watch --json
```

`--workflow <file>` 仍支持自定义 API 图；`--queue-only` 只在另一个进程负责监控时用。不要用短超时的同步等待命令。

## 动作戏：5 秒单元与测试阶梯

动作戏默认 5 秒（124 帧）一个生成单元，5–7 个主要动作事件、1–3 个视觉段。不要先做 10 秒再靠后期剪快；先按 [`../h3-director/references/action-combat.md`](../h3-director/references/action-combat.md) 编好因果链。

```powershell
python scripts/h3_fastpath.py `
  --comfyui <ComfyUI-path> `
  --mode fl2va `
  --first-frame <action_loaded_first.png> --last-frame <mid_action_last.png> `
  --workflow-template h3_c_fl2va768 `
  --component-set auto `
  --resolution 768x1344 --video-seconds 5 --seed 20261120 `
  --filename-prefix video/H3_action_unit --json
```

- 首帧要“动作已上膛”，尾帧选动作中段/命中后位移；不选中立站姿或收势定式。
- 加载 Wushu 动作 LoRA 时可在提示词开头加 `wushu_action`；没有加载 LoRA 时不要写触发词。
- 当前 Set C API 图只带固定 Pika turbo LoRA，**没有动作 LoRA 槽位**。加 Combat/Motion/Wushu 必须用自定义 API 图走 `h3_generate.py --workflow`，不要假设 fastpath 会自动挂载。
- 同一条连续打斗不要用 3 个以上 `MiniMaxH3AddGuide` 动作相位锚点；本机 E1 已证明会钉帧、硬切和定格。

测试阶梯（每次只改一个变量，保留同一提示词/种子做 A/B）：

1. **纯提示词 5 秒**：先修事件密度、因果链、具体招式和实时速度；这是基线，不加 LoRA、不加锚点。
2. **提示词修正**：仍然慢时，指出是哪一拍慢，补招/补受击/删复位；不要重跑同一文本。
3. **Motion Continuity Repair 0.9**：自定义图；先做权重 0 与 1 的对比，确认 LoRA 真的生效。约 155 MB。
4. **Combat Base V2 0.9 + Motion 0.5–0.7，两段采样 25%**：采样器用 `res_multistep` + `simple` 或 `euler` + `beta`；二采 Motion 0.2–0.3。Combat 约 155 MB。
5. **PDD Acc 8 步**：仅在前述路线仍因采样软/慢时尝试；euler、CFG 1、SigmaShift 12/3，移除其他蒸馏 LoRA。约 1.37 GB，模型卡称支持 pruned/W4A8，本机未实测。
6. **Wushu 全量路线**：需要 34 GB 全量 int8 底座 + 32B bf16 文本编码器，不是 16 GB W4A8 + 4B TE 的 drop-in；不要当轻量补丁下载。

动作 LoRA 的 W4A8 兼容性未在本机验证；先做权重 0/1 对比。任何大体积组件下载前先征得用户同意。

## 监控

- Windows 桌面默认打开原生 Tkinter 进度窗；`--no-monitor-gui` 关闭，`--monitor-gui` 强制开。窗口只监控，关闭不会中断生成。
- 节点数是结构进度，不是时间百分比：H3 各节点耗时差异极大。报告时区分 `progress_basis`（node_completion / sampling_steps）与 `eta_basis`（empirical / live_progress），不要把 4/5 当成 80% 时间。
- 独立查看：

```powershell
python scripts/h3_status.py --base-url http://127.0.0.1:8188 `
  --prompt-id <id> --comfyui <ComfyUI-path> --output-dir <ComfyUI>\output `
  --run-root <ComfyUI>\user\h3lite_runs --require-audio --dynamic-check `
  --anchor-check --compact --json
```

有界等待加 `--watch --watch-interval 20 --watch-timeout 3600`。默认紧凑输出；只有失败诊断才 `--verbose` 拿完整 history。

## 批量 showrunner（show.json）

`h3_showrunner.py` 把 `show.json` 变成一次批处理：校验一次、逐镜 `--queue-only` 提交、逐镜 `h3_status.py` 验证，状态写进 `show_manifest.json`，支持断点续跑。

```powershell
python scripts/h3_showrunner.py --spec projects/ep04/show.json `
  --output-dir E:/MiniMax-H3/ComfyUI/output --comfyui E:/MiniMax-H3/ComfyUI `
  --strict --check-sha
```

- `--only s02,s03` 只跑指定镜头；`--resume` 跳过已完成、继续已提交未验证的镜头；`--force` 重跑。
- `--dry-run` 只校验并打印每镜将执行的命令，不占 GPU；`--no-watch` 只提交并记录 prompt_id。
- `--json` 输出机器可读汇总；默认 `show_manifest.json` 在项目根，`runs/` 放单镜 manifest。
- 白模镜头提供 `white_model.proxy` 后，showrunner 会作为 `--ref-video` 提交；需要同时传 `--comfyui` 以便 staged 代理。`white_model.source` 只用于审片/校验，不送 H3。
- 单条 `h3_generate.py` 加 `--show-spec <show.json>` 会在提交前自动跑合同校验；`--show-strict` 把 warning 也当失败。showrunner 已校验过，单镜调用无需重复。

## 验证

不能凭 queue ID 报成功。逐项确认：

1. 任务无执行错误；
2. 目标 MP4 存在，有视频流与音频流；
3. 时长、帧数、FPS 接近请求值；帧数多出不超过 16 帧（约 8%）视为自然补帧，不重跑、不裁尾；短于请求超过 2 帧仍判失败；
4. 首/中/末帧非黑、非纯色，未被判 `suspected_mosaic`；`dynamic` 只是首/中/末 3 帧的烟测，不能证明动作密度。动作片另抽 8–12 帧或接触表，5 秒至少 5 个主要动作事件、没有 >0.5 秒定格；近静止（帧间 MAD < 1.0）超过 20% 判慢放，回 `h3-prompt`/重编，不靠后期变速；
5. 身份、服装、道具、参考构图等验收条件在抽帧中保持一致；带台词的另**听**说话人是否正确、台词是否只说一次、音色是否与正典样本一致（跨镜漂移交给 `h3-post` 的 `scripts/h3_voice_audit.py` 量化，不要凭"有音频流"判过）；
6. 单次多镜只核对请求切点附近（±0.5 s），不做全片阈值扫；请求切点变成连续运镜但仍有清楚新景别/机位，按 3–4 个视觉段验收；
7. 记录输出路径、实际耗时、配置指纹与 run manifest；动作片另记实际事件数、近静止比例、是否用了两段采样/LoRA；
8. 计划估计与实际执行时间对比；低显存首次运行可能因内核编译慢很多，这是经验值不是承诺。

`ffprobe_not_found` 只说明验证器路径缺失：保留已生成文件，设置 `H3LITE_FFPROBE` 或在 `<ComfyUI>` 附近找 `ffprobe.exe`；不要因为元数据不可读就重跑模型。动态 QA 用的 `ffmpeg` 同理，可设 `H3LITE_FFMPEG`；脚本也会在 `<ComfyUI>` 根目录与 `ffmpeg/bin`、`tools/ffmpeg/bin` 下查找，不要把“找不到 ffmpeg”当成视频失败。

## 失败排查顺序

1. 页面文件/RAM 极低，或其他 GPU 进程；
2. 缺模型或缺自定义节点；
3. 模型目录/文件名错误；
4. CUDA/PyTorch/自定义内核不兼容；
5. OOM 或过量 CPU offload；
6. H3 flow/音频图无效；
7. 提示词或参考对齐问题。

- 黑屏/马赛克：恢复官方 H3 flow/sigma-shift 节点，简化可选 attention/cache 补丁。
- 4 步音频失真：检查视频/音频 schedule，必要时用兼容 Turbo 采样器。
- 同尺寸损坏的 W4A8 会产生彩色马赛克：按完整性记录重验哈希，不要只看字节数。
- 第二次运行更快不等于复用了结果：权重常驻/上游节点缓存会加速，但改提示词或种子仍会重新采样。
- 后台 ComfyUI 抛 `OSError: [Errno 22] Invalid argument`：用持久日志重启，不重下模型。

## 边界

- 不改生成图、不加采样步数、不加第二个生成模型、不做二次推理“增强”。人脸质量靠路线 + 提示词 + 分辨率。
- 放大、拼接、字幕、响度、交付都交给 `h3-post`。
- 运行历史清理是维护，交给 `h3-workstation`。

## 资源

- `scripts/h3_fastpath.py`、`h3_generate.py`、`h3_status.py`、`h3_anchor.py`、`h3_monitor_gui.py`、`h3_plan.py`、`h3_paths.py`、`h3_doctor.py`、`h3_preflight.py`；`h3_show_init.py`、`h3_show_validate.py` 负责开拍前骨架与门禁。`h3_doctor.py` 与 `h3_preflight.py` 各有一份副本在 `h3-workstation/scripts/`，必须同步更新。
- `assets/`：Set A/B/C 的 API 工作流（T2VA/I2VA/Ref2VA + compat + Set C 六模板）。脚本按 `Path(__file__).parents[1] / "assets"` 解析，不要再套子目录。
- `references/show-contract.md`：开拍前合同全文（交付、canon、镜头卡、参考包、预览阶梯、版本锁定、QA 门禁、返工/停止条件）。
- `assets/show.example.json`、`assets/canon.example.json`：可直接复制修改的 spec 模板。
- `references/face-quality.md`：人像路线 A/B 与护栏。
- `references/final-lite-canvas.md`：1184×672 / 1152×640 中间画布的三臂 A/B 协议、验收与磁盘边界；未验证前不进 auto 路由。
- [`../h3-prompt/references/voice-consistency.md`](../h3-prompt/references/voice-consistency.md)：声音圣经、选角声学距离、参考音频上限与已知坑（#95 / #16289）、验收门限。
- [`../h3-director/references/action-combat.md`](../h3-director/references/action-combat.md)：动作密度、5 秒单元、慢放诊断、动作 LoRA 兼容性与测试阶梯。
