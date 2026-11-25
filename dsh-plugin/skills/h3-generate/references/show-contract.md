# 开拍前合同（Show Contract）

一句话：**先写清“交付什么、谁来演、每镜怎么算过”，再让 GPU 开工。** 聊天记录不是调度源，口头约定不是验收标准。

## 0. 什么时候必须用

满足任一条，就必须先有 `show.json` 并通过校验：

- 超过一条镜头，或需要跨镜身份/服装/声音一致；
- 有台词、声音圣经、参考音频；
- 使用白模/previz 视频作为运动参考；
- 需要交付成片、字幕、封面，而不是只看一条测试片。

单条 5 秒测试可以只写镜头卡，但同样先写验收条件；不要“先跑出来看看”。

## 1. 项目目录

```text
<project>/
  show.json              # 唯一调度源：交付、镜头、参数、验收
  canon.json             # 身份/VOICE/look 的唯一正本
  prompts/               # s01.txt, s02.txt...
  refs/                  # 主脸、去头身体、场景、白模、音频
  refs.sha256            # 参考包冻结哈希（可选但推荐）
  frames/                # 首/尾/构图关键帧
  qa/                    # 接触表、审计 JSON、抽帧
  subs/                  # SRT/ASS
  output/                # 生成原片，不直接交付
```

- `show.json` 里的路径**相对项目根**；不要写死 Windows 盘符绝对路径。需要跨盘时用项目内 staging，不把盘符带进 spec。
- 提示词、参考图、首尾帧、白模代理各有一个稳定文件名；不要用 `final_final_v3.png`。
- 中间文件留项目目录；只有验收通过的成片进 `%USERPROFILE%\Downloads`。

## 2. 交付定义

`deliverable` 必须在开拍前写死：

| 字段 | 说明 |
|---|---|
| `duration_seconds` | 目标成片时长；允许 H3 自然补帧，不硬裁 |
| `aspect` | `16:9` / `9:16` / `4:3` / `1:1` |
| `resolution` | 真实画布，如 `1344x768` / `768x1344`；32 像素对齐 |
| `fps` | 默认 24 |
| `audio` | `native` 或 `silent`；`native` 必须验音频流 |
| `subtitles` | 目标字幕文件，或 `null` |
| `delivery_dir` | 默认 `%USERPROFILE%/Downloads` |
| `cover` | 是否需要封面及规格 |

不能在生成后才发现要竖屏、要字幕、要双语或要 10.8 秒。交付规格变了就是新版本，不静默覆盖旧文件。

## 3. Canon 锁定

`canon.json` 是身份和声音的唯一正本。每个角色至少：

```json
{
  "identity": "adult woman, black hair ..., deep gray trench coat ..., right eyebrow scar",
  "voice": "Japanese; F0 around 100 Hz; dry, slightly hoarse; slow pace; falling endings; close-miked",
  "ref_images": ["refs/face_A.png", "refs/body_A.png"],
  "ref_audio": "refs/voice_A_dry.wav"
}
```

规则：

- 同一角色在每镜的身份块**逐字一致**；不改同义词、不加新配饰。
- VOICE 块与身份块分开；同场同性别说话人 F0 目标带差 ≥25–30 Hz（约 4 个半音），一条 ≤2 个说话人最稳。
- 参考图一张一职：`<Picture 1>` 主身份头肩近景，`<Picture 2>` 去头全身/服装；不要把多张头肩近景拼成一张设定图。
- 参考音频必须单人、干声、5–8 s、无环境底噪；从成片截的带环境声样本会引入抢话/重复。
- 底床声（念经、雨、嗡鸣）指定唯一正典来源；不要每镜各自生成。

## 4. 分镜表与镜头卡

每个 `shots[]` 条目是一张可执行的镜头卡，不是一句创意：

```json
{
  "id": "s01",
  "prompt": "prompts/s01.txt",
  "mode": "ref2va",
  "template": "h3_c_ref2va768",
  "length": 124,
  "seed": 20261125,
  "ref_images": ["refs/face_A.png", "refs/body_A.png"],
  "ref_audios": [],
  "first_frame": null,
  "last_frame": null,
  "white_model": null,
  "acceptance": {
    "identity": "A",
    "requires_audio": true,
    "requires_dialogue": false,
    "min_action_events": 0,
    "notes": "结尾手完全攥紧硬币并停住"
  }
}
```

- `id` 全片唯一；文件名与输出前缀用同一 ID。
- `length` 是请求帧数，不是承诺时长；244 常补到 260 帧，不裁不重跑。上限 362；**481 禁止提交**。
- 每镜只写一个主运镜、一个强动作（动作戏按 5–7 个事件算一条因果链）。
- 文戏动作写到完成态；动作戏写到命中结果/位移/新劣势，不回起手式。
- 相邻镜头景别交替；切点落在动作中段或视线转移；过线用中性镜头或可见运镜。
- 每镜写 `Visible actors in this shot: ...` 与 `Do not swap, duplicate, or add cast members.`。
- 台词必须进 H3 原生生成，不做后期 TTS 拼接；每镜一句为主，说话者写 `says the line once and nothing else`。
- 画面里有第二张脸，就给它正向静止事实：`lips at rest, jaw closed, breath lifting the chest`。

## 5. 参考包冻结

提交前把参考包当成一个版本，而不是随手换图：

- 每张参考图记录用途和 `<Picture N>` 槽位；顺序就是提交顺序。
- 主脸长边约 1024、脸 ≥512 px；AI 水印条先裁掉：`crop=iw:ih-80:0:0`。
- 生成 `refs.sha256`（`sha256sum` 或 PowerShell `Get-FileHash`），并在 `version_lock` 记录参考包版本。
- 换参考图、换 prompt、换白模、换 seed 都是新版本；不要在旧成片上“解释”差异。
- 参考图数量上限：图 ≤9、音频 ≤3、视频 ≤3、混合 ≤12；音频不能是唯一输入。

## 6. 路线与参数锁定

| 目标 | 路线 | 本机模板 |
|---|---|---|
| 只有文字 | `t2v` | `h3_c_t2va768` / `h3_c_speed640` |
| 单首帧 | `i2va` | `h3_c_i2va768` |
| 首尾帧 | `fl2va` | `h3_c_fl2va768` |
| 只有尾帧 | `l2va` | `h3_c_i2va768` + 尾帧 |
| 人像/身份/白模运动参考 | `ref2va` | `h3_c_ref2va768` |

- Set C 模板一律 `component_set: "auto"`；**绝不传 A/B**，否则会重写 unet/clip/lora 角色。
- Ref2VA 不要与首/尾帧混用；参考图是真实条件输入，不是风格附件。
- Ref2VA + 白模视频：`white_model` 必须存在，`mode` 必须是 `ref2va`，且至少一张身份参考图；白模只负责动作/走位/相机。
- I2VA/FL2VA 没有音频参考输入；不要写悬空 `<Audio 1>`，声音只靠 VOICE 块与声学距离。
- 动作 LoRA 只能走自定义 API 图；Set C 图没有动作 LoRA 槽位。
- 视频 VAE 可选 `defaults.video_vae` 或镜头级 `video_vae`。Set C 默认 Sol INT8；若 `h3_grid_check.py` 判 `suspected`，最终交付镜头改为 `minimax_h3_video_vae_fp16.safetensors`，showrunner 会传 `--video-vae`，其余参数不动。

## 7. 预览阶梯

不要在最终画布上试故事：

1. **blockout / 白模**：先确认走位、相机、节奏；
2. **低清预览**：`640x352` 或 `864x480`，4 步，确认身份/动作/台词；
3. **最终画布**：预览 PASS 后才提交 `1344x768` 或竖屏；
4. **只重跑失败镜头**：不因一镜失败重跑整集。

预览不是交付；不要把低清预览混进成片。0.4 MP 不是“清晰人像”的验收标准。

## 8. 版本锁定（白模尤其）

```json
"version_lock": {
  "prompt_revision": "r1",
  "reference_pack_sha256": "<refs.sha256 的哈希>",
  "white_model_version": "v5",
  "model_fingerprint": "set-c-2026-11-19"
}
```

- 白模源片、12fps 代理、H3 成片三者的版本必须能对应；白模改了就必须重跑 H3，不能只重拼对比片。
- 12fps 代理只用于 H3 输入；审片用 24fps 母版。代理规格：864×480、SAR 1:1、无音轨。
- 同一配置的 manifest 处于 `submitting`/`queued`/`running` 时不得重复提交；只有用户明确要求第二条相同任务才 `--allow-duplicate`。
- 输出不静默覆盖；失败重跑保留旧件并写清新版本号。

## 9. QA 门禁

每镜过以下门，才允许进入下一镜/后期：

1. 任务无执行错误；目标 MP4 存在，有视频流与音频流（`native` 时）。
2. 帧数/时长/FPS 接近请求；向上补帧 ≤16 帧视为正常，短于请求 >2 帧判失败。
3. 首/中/末帧非黑、非纯色；身份、服装、道具、构图在抽帧中保持一致。
4. 动作片另抽 8–12 帧：5 秒 ≥5 个主要事件，无 >0.5 s 定格，近静止（帧间 MAD <1.0）不超过 20%。
5. 带台词必须**听**：说话人正确、台词只说一次、音色与正典样本一致；跨镜漂移另跑 `h3_voice_audit.py`。
6. 单条多镜只核对请求切点 ±0.5 s；请求切点变成连续运镜但仍有清楚新景别/机位，按视觉段验收。
7. 记录输出路径、实际耗时、配置指纹、run manifest；对照计划估计与实际执行时间。

技术指标 PASS ≠ 人脸 PASS。身份/画风不被接受时，回生成路线重做，不用贴脸/换脸/后期频率分离修补。

## 10. 返工规则

- 先定位失败层：提示词、参考包、路线、参数、环境。不要同一配置盲重试。
- 只改一个变量；保留同提示词/种子做 A/B。
- 台词时长敏感时只改 ±1–2 s，seed/步数/提示词/参考全锁。
- 动作慢放优先补事件、补受力、删复位；不用变速/插帧/碎剪掩盖。
- 白模修正后必须重跑 H3 才算同源对比；只重拼会把旧 H3、代理帧率、自然补帧和尾帧冻结混进结论。
- 一镜失败不重跑整集；一镜成功不因“想更好”无限重抽。用户明确要求新版本才开新轮。

## 11. 停止条件

出现任一条，先停并报告，不提交：

- 481 帧或超过 362 帧的单段；
- 页面文件/RAM 接近耗尽、C 盘无空间、ComfyUI 已有同配置运行中；
- 缺模型/节点/音频 VAE，或参考图/提示词路径不存在；
- Ref2VA 同时接了首/尾帧，或 I2VA/FL2VA 接了参考音频；
- 白模版本与 H3 版本对不上；
- 交付目录/字幕/封面规格未定，却准备跑最终画布。

## 执行入口

- 批量：`python scripts/h3_showrunner.py --spec <show.json> --strict --check-sha --output-dir <ComfyUI/output> --comfyui <ComfyUI>`。一次校验、逐镜 `--queue-only` 提交、逐镜验证，状态写 `show_manifest.json`。
- 单镜：`python scripts/h3_generate.py --show-spec <show.json> ...` 在提交前自动跑同一套合同校验；`--show-strict` 把 warning 也判失败。
- 白模镜头把 `white_model.proxy` 写进 `show.json`；showrunner 会作为 `--ref-video` 提交，并需要 `--comfyui` 把代理 staged 进 `input/`。`white_model.source` 只用于审片和版本核对，不送 H3。

## 开拍前检查清单

- [ ] `show.json` 通过 `h3_show_validate.py`，0 errors；
- [ ] `canon.json` 的身份块、VOICE 块、参考图槽位已定稿；
- [ ] 每个镜头有 ID、prompt 文件、路线、模板、帧数、seed、验收条件；
- [ ] 参考图一张一职，主脸独立、身体图去头，水印已裁；
- [ ] 参考音频单人干声 5–8 s；没有音频唯一输入；
- [ ] Set C 模板 `component_set=auto`；Ref2VA 未混首尾帧；
- [ ] 白模 proxy 为 12fps / 864×480 / SAR 1:1 / 无音轨，版本已记录；
- [ ] 预览阶梯与最终画布已定；失败只重跑单镜；
- [ ] 交付目录、命名、字幕、封面、响度目标已写进 spec；
- [ ] 当前没有同配置任务在跑，磁盘/页面文件/显存通过预检。
