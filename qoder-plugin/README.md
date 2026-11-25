# h3lite 插件

版本 **0.2.0**。把本机 MiniMax H3 视频生产工作流打包成 Qoder 插件：环境、提示词、导演、生成、后期、白模六个 skill 各自独立，并共享 Set C 生产路线、开拍前合同、showrunner、原生参考视频与实测 QA 规则。

> 0.2.0 是插件化生产版。线上 [`Rimagination/h3lite`](https://github.com/Rimagination/h3lite) 仍是单体 `SKILL.md`（最后提交 `9bafafa`，2026-08-24）；完整差异与版本历史见 [`CHANGELOG.md`](CHANGELOG.md)。代码许可见 [`LICENSE`](LICENSE)。

## 0.2.0 修复：Sol VAE 128px 接缝

- 确认 `minimax_h3_sol_vae_int8_convrot` 会在 x/y=128n 留下固定网格；v3b 实测 x 1.369× / y 1.643×，x 向 124/124 帧、y 向 123/124 帧超阈值。Sol fp16 同样有接缝，不是量化单独造成。
- 新增 `h3-post/scripts/h3_grid_check.py`：原生分辨率检测 128px 网格，输出 profile/overlay/JSON，判定 clean / residual / suspected。
- 新增 `h3_generate.py --video-vae`：单变量换视频 VAE，不改音频 VAE；showrunner 支持 `video_vae`。
- 单变量修复实测：只换 `minimax_h3_video_vae_fp16.safetensors`，x −13.5%、y −27.2%，y 薄线 1.359×→0.996×；动作/角色/构图/音轨不变。
- 文档更新 `component-sets.md` / `deployment-matrix.md` / `h3-generate` / `h3-post`：Sol INT8 定位预览/速度档，最终平滑背景/舞台类画面先跑网格检查；连续第二条 H3 前用干净 ComfyUI 进程；打斗动作漂移用白模动作参考。

## 0.2.0 新能力

| 能力 | 说明 |
|---|---|
| **六 skill 插件** | `workstation / prompt / director / generate / post / whitemodel`，每个 skill 自包含 references/scripts/assets |
| **Set C 生产路线** | Sol INT8 VAE + 原生稀疏 + Pika lite；6 个自钉模板；16 GB 自动路由 |
| **Set C 资产分发** | 夸克网盘 core/ref2va；`h3_setc_assets.py` 完整 SHA-256 校验 + `component_manifest.json` |
| **开拍前合同** | `show.json` / `canon.json`、镜头卡、参考包冻结、`h3_show_validate.py` |
| **批量 showrunner** | 一次校验、逐镜 queue-only、逐镜验证、`--resume/--only/--force` |
| **原生参考视频** | `--ref-video` 自动接 `LoadVideo → GetVideoComponents → ref_videos.ref_video_N` |
| **白模预演** | 静态白模、单镜白模视频、室内三镜 previz、12fps proxy、360° 环绕、上下对比 QA |
| **Blender 集成** | headless bpy + 可选 `mcp-for-blender`；`blender_scene_snapshot.py --audit` 场景门禁 |
| **FaceRefine 经验** | 实验性修脸记录、已知 bug、指标与止损线；明确不默认套、不承诺完美 |
| **final-lite 画布** | 1184×672 / 1152×640 三臂 A/B；1184 单镜约 −40% 墙钟，未晋升 auto |
| **缓存/QA 复用** | `h3_cache.py` 显式 key/TTL、文件指纹、成功命令回放 |

## Skill 表

| Skill | 何时触发 | 产出 |
|---|---|---|
| `h3-workstation` | 安装、迁移、体检、修复、显存/页面文件、清理 | 环境报告、启动命令、组件集选择 |
| `h3-prompt` | 写/改/诊断 H3 提示词、人物声音不一致 | 三字段/六字段提示词 + 预检清单 |
| `h3-director` | 短剧、多镜、分镜、连续角色、原生台词、声音圣经 | 分镜表、关键帧计划、连续性锚点 |
| `h3-generate` | 渲染、重跑、查进度、接音色参考、开拍前合同与 show 校验 | 已验证 mp4 + manifest + 通过校验的 show.json |
| `h3-post` | 拼接、字幕、响度、声音一致性审计、放大、交付 | 成片 + 字幕 + QA 回执 |
| `h3-whitemodel` | 白模、blockout、previz、运动/相机参考、白模直喂 Ref2VA、检查环绕运镜、白模与 H3 节奏不一致 | 白模静帧 / 白模视频 / 12fps motion proxy / 上下对比 QA |

## 安装与升级

- 安装通过 `~/.qoder/plugins/installed_plugins_v2.json` + Qoder plugin-registry watcher 完成；当前活动版本以该文件为准。
- 安装/升级时保留现有缓存里的 `.mcp.json` 与 `runtime/`，否则会丢 h3lite 的 MCP 工具。
- 安装前备份在工作区 `backups/h3lite-cache-0.1.12-20261125/`（旧缓存、`.mcp.json`、`runtime/`、注册表、settings）。
- 旧版本缓存（0.1.12 / 0.1.1–0.2.0）保留作回滚；安装仍需用户明确确认。

## Set C 资产网盘

Set C 的四个模型、六个工作流和许可已打包到夸克网盘，供 16 GB 机器直接取用：

- 分享：<https://pan.quark.cn/s/6f8f5ce9f8a6>（永久有效，43 项 / 13.4 GB）
- 口令：`/~67293cXj30~:/`
- `core/`：15 文件、2.14 GiB，含 Sol INT8 VAE、Pika FL2VA LoRA，覆盖 speed640 / quality864 / t2va768 / i2va768 / fl2va768。
- `ref2va/`：15 文件、11.25 GiB，含 Ref2VA 底座与 Ref2VA Pika LoRA，只给 Ref2VA 路线。
- 安装顺序：先装 Set B；合并 `core/models/*` 到 `<ComfyUI>/models/*`；需要 Ref2VA 时再加 `ref2va/models/*`。保留 `licenses/`、`NOTICE.txt`、`SHA256SUMS.txt`。
- 校验：`python skills/h3-workstation/scripts/h3_setc_assets.py --package <pkg> --comfyui <ComfyUI>`；完整模式会复算四个模型 SHA-256 并写 `component_manifest.json`。

## 与线上 H3 Lite 的关系

- 线上：单体 `SKILL.md` + 11 个 references + 11 个核心脚本 + 6 个 W4A8 工作流 + docs/示例/tests，共 78 文件。
- 本地 0.2.0：六个 skill、32 个 references、12 个工作流（6 W4A8 + 6 Set C）、84 文件；新增 showrunner/白模/资产/缓存/Blender 集成/网格 QA 等脚本。
- 线上 `SKILL.md`、`docs/`、`assets/examples/`、`tests/` 等展示/开发资产没有随插件包分发；`LICENSE` 已补回。
- 线上尚未收到 0.1.2–0.2.0 的更新；若要发布，需要把本地插件说明与线上单体 skill 的定位分开维护。

## 已知边界

- Sol INT8 VAE 可能在平滑背景/大色块上留下 128px 固定网格；最终交付前跑 `h3_grid_check.py`，疑似时只换 fp16 视频 VAE，不要换 Sol fp16。
- FaceRefine 是实验性后期，身份/脸型/画风/动作不对时应回 `h3-generate` 重生成，不靠贴回。
- 1184×672 只是单镜 final-lite 候选，未进 auto 路由，也未替代 1344×768 终版；至少再跑 2–3 个不同景别/动作/带台词镜头。
- MCP 需要 Blender GUI + addon + `uvx`；socket 无认证，只在本机 localhost 使用，只留一个 server，最终渲染回 headless。
- 481 帧单段仍禁止提交；16 GB 卡不要并行两条 H3；Set C 必须先装 Set B。

## 来源

- 由本机 `~/.qoder/skills/h3lite`（v1，单体 SKILL.md）拆分、插件化并扩展而来；线上基线为 `Rimagination/h3lite@9bafafa`。
- 提示词方法论参考 MiniMax 官方 H3 prompt guide、Higgsfield 公开 skills、AkCodez/OSideMedia 社区提示词库；插件不调用云端 API。
- 动作戏参考（只作写作/路线判断，非运行时依赖）：Wushu Action v7、Combat Base V2、General Motion Continuity Repair、PDD Acc；以及本机 E1 AddGuide 测试、v2 动作密度 QA 和公开工作流 JSON 解析。
- 专业制作参考：StudioBinder 的 180° 轴线/构图/blocking；Walter Murch 的 Rule of Six；Higgsfield/OSideMedia 的镜头、声音、剪辑笔记。
- 声音一致性参考：官方 MiniMax-H3 README、comfy.org R2V 工作流、issue #17/#95、ComfyUI #16289、Runware、DomoAI；完整链接与取用状态见 `h3-prompt/references/voice-consistency.md`。
- Blender/AI 参考：`arjun988/blender-skills`、`ahujasid/mcp-for-blender`、`dhakalnirajan/blender-open-mcp`、`scenario-labs/blender-plugin`、`agmmnn/awesome-blender`；只作流程与 MCP 协议参考，不复制其运行时逻辑。
- 本机证据：Ref2VA/`LoadAudio` 的 `object_info` 实测；Set C I2VA/FL2VA 结构核对；Ref2VA + `--ref-audio` 真实渲染；17 镜短片声音审计；Blender 4.5.9 headless 场景审计与 1 帧 smoke。

## 目录约定

- 每个 skill 自包含：`SKILL.md` + `references/` + 可选 `scripts/` / `assets/`。
- `h3-workstation` 与 `h3-generate` 各保存一份 `h3_plan.py`、`h3_paths.py`、`h3_doctor.py`、`h3_preflight.py`：**必须成对更新**（当前两份哈希一致）。
- `h3-director` 与 `h3-generate` 各保存一份 `references/face-quality.md`，同样成对更新。
- 动作戏长文只在 `h3-director/references/action-combat.md`；声音一致性长文只在 `h3-prompt/references/voice-consistency.md`；其他 skill 交叉链接。
- 工作流 JSON 只放在 `h3-generate/assets/`，是生成路由的唯一来源。
- 不包含 `.git`、`__pycache__`、`*.bak`、展示用视频、OpenAI 代理配置。
