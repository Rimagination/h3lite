# H3Lite 更新说明

## 0.2.0（2026-11-25）— 插件化生产版（含 Sol VAE 修复）

这是 H3Lite 从“单体 H3 Lite skill”升级为“Qoder 生产插件”的第一个大版本。线上 `Rimagination/h3lite` 仍停留在单体 `SKILL.md`（最后提交 `9bafafa`，2026-08-24）；0.2.0 把本地验证过的生产链路收敛为六个 skill 的插件，并把 Sol VAE 的 128px 接缝发现一并入库。

### 新能力

| 能力 | 变化 |
|---|---|
| **六 skill 插件架构** | 单体 `SKILL.md` 拆成 `h3-workstation / h3-prompt / h3-director / h3-generate / h3-post / h3-whitemodel`，每个 skill 自包含 SKILL/references/scripts/assets |
| **Set C 生产路线** | Sol INT8 VAE、原生 `BlockSparseAttention`、Pika lite LoRA；6 个自钉模板（speed640 / t2va768 / quality864 / i2va768 / fl2va768 / ref2va768）；16 GB 自动路由 |
| **Set C 资产分发** | 夸克网盘 core/ref2va 两包；`h3_setc_assets.py` 校验四个模型完整 SHA-256 并生成 `component_manifest.json` |
| **开拍前合同** | `show.json` / `canon.json`、镜头卡、参考包冻结、`h3_show_init.py`、`h3_show_validate.py`；先校验再占 GPU |
| **批量 showrunner** | `h3_showrunner.py` 一次校验、逐镜 `--queue-only`、逐镜验证、`--resume/--only/--force`；`h3_generate.py --show-spec` 自动门禁 |
| **原生参考视频** | `h3_generate.py --ref-video` 自动接 `LoadVideo → GetVideoComponents → ref_videos.ref_video_N`；白模 proxy 直喂 Ref2VA |
| **白模预演** | 第 6 个 skill：静态白模、单镜白模视频、室内三镜 previz、12fps motion proxy、360° 环绕验收、上下对比 QA |
| **Blender 集成** | headless bpy 脚本 + 通用 `blender_bpy` 片段适配 + 可选 `mcp-for-blender`；`blender_scene_snapshot.py --audit` 检查相机/命名/帧率/分辨率/动作 |
| **AI 控 Blender playbook** | 从 `arjun988/blender-skills`、`ahujasid/mcp-for-blender`、`blender-open-mcp`、`scenario-labs/blender-plugin` 提炼的镜头简报、相机先匹配、几何分层、截图对比循环、MCP 协议与 H3 交接 |
| **FaceRefine 经验** | 实验性修脸 reference：已知 bug、wobble/接缝指标、身份拒绝案例与止损线；明确“没有完美方案”，不默认套 |
| **final-lite 画布** | 1184×672 / 1152×640 三臂 A/B 协议与单镜实测；1184 约 −40% 墙钟，未晋升 auto |
| **缓存/QA 复用** | `h3_cache.py` 文件指纹、显式 key/TTL JSON 缓存、成功命令输出回放；只缓存可复算报告 |
| **视频 VAE 质量档** | `h3_grid_check.py` 测 128px 接缝；`h3_generate.py --video-vae` / fastpath / showrunner 支持单变量换 fp16 视频 VAE |
| **声音与后期** | `h3_voice_audit.py`、VOICE 块、选角声学距离、参考音频、字幕/响度/放大/交付规则补齐 |

### Sol VAE 128px 接缝（2026-11-25 同日追加）

- `minimax_h3_sol_vae_int8_convrot` 在 x/y=128n 留下固定接缝；v3b 1344×768 / 124 帧实测 x 1.369×、y 1.643×，x 124/124 帧、y 123/124 帧超阈值；v2/v3 同周期。
- 根因：Sol 解码器 16×16 token 局部窗口 + 半窗移位，对应 128px 主网格、64px 半移位；ComfyUI #17429 同症状；Sol fp16 也有同样接缝；不是 tiled decode、播放器或 H.264 几何。
- 单变量修复：只把视频 VAE 换成 `minimax_h3_video_vae_fp16.safetensors`；x −13.5%、y −27.2%，y 薄线 1.359×→0.996×；动作/角色/构图/音轨不变。
- 策略：Sol INT8 定位预览/速度档；平滑背景、大色块或舞台类最终交付先跑 `h3_grid_check.py`，`suspected` 时只换 fp16 视频 VAE；不要换 Sol fp16。
- `h3_grid_check.py` 输出 profile/overlay/JSON，判定 clean/residual/suspected；`--fail-on-suspected` 可做门禁。

### 与线上 H3 Lite 的差异

| 项目 | 线上 | 0.2.0 |
|---|---:|---:|
| 形态 | 单体 `SKILL.md` | 6 个 skill 的 Qoder 插件 |
| 文件数 | 78 | 84（含 LICENSE、CHANGELOG） |
| references | 11 | 32 |
| 工作流 | 6 个 W4A8 | 12 个：6 W4A8 + 6 Set C |
| 核心脚本 | 11 | 11 个核心 + showrunner / 白模 / 资产 / 缓存 / 网格 QA 等新增 |
| `h3_generate.py` | 1615 行 | 1895 行 |
| `h3_fastpath.py` | 861 行 | 1155 行 |
| `component-sets.md` | 117 行 | 452 行 |

线上仍保留 `docs/` 站点、示例视频、hero、tests 等展示/开发资产；插件包有意不带这些大文件，但已补回 `LICENSE`。

### 验证

- 6 个 skill、84 个文件、0 个坏链、Python 全量编译通过
- Set C 自动路由静态矩阵 16 项通过
- showrunner / `--show-spec` 正负例通过
- `--ref-video` dry-run 正例、非 Ref2VA 负例通过
- `h3_setc_assets.py` 对 staging 包四个模型完整 SHA-256 校验 4/4 通过
- `h3_cache.py` fingerprint/put/get/run/prune 冒烟通过
- Blender 4.5.9 headless：scene JSON、1 帧 smoke、`--audit` 正例与 `--fail-on-warnings` 负例通过
- MCP 实测：`mcp-for-blender` addon 2.0 / server 1.30.0 / protocol 16，`get_scene_info`、`execute_blender_code`、`look` 均通
- `h3_grid_check.py`：v3b suspected（x 1.369× / y 1.643×）；v3c residual（x 1.184× / y 1.196×）
- `--video-vae` dry-run：node 4 变 fp16 VAE，node 5 音频 VAE 不变；showrunner 命令包含 `--video-vae`

### 已知边界

- Sol INT8 VAE 可能有 128px 网格；fp16 VAE 是减轻不是完全消除（v3c residual 1.184/1.196）。
- FaceRefine 是实验性方案，身份/画风/几何不对时应重生成，不用贴回。
- 1184×672 只是单镜 final-lite 候选，未进 auto，也未替代 1344×768 终版。
- MCP 需要 Blender GUI + addon + uvx；socket 无认证，只在本机 localhost 使用。
- 481 帧单段仍禁止提交；16 GB 卡不要并行两条 H3。
- Set C 必须先装 Set B；Ref2VA 才加 ref2va 资产。
- 连续第二条 H3 任务前，若出现过 ClipProj `_encode` access violation，用干净 ComfyUI 进程重启再提交。

## 历史版本

- **0.1.7**：社区 AI 控 Blender playbook；`blender_scene_snapshot.py --audit`。
- **0.1.6**：Blender 集成适配（headless bpy / blender_bpy / 可选 MCP）；场景快照 smoke。
- **0.1.5**：final-lite 单镜 A/B（1184×672 −39.9%；1152 一次 ClipProj 崩溃）；旧输出归档释放 E 盘。
- **0.1.4**：Set C 资产校验与 manifest；final-lite A/B 协议；`h3_cache.py` 与缓存策略。
- **0.1.3**：FaceRefine 实验记录、已知 bug 与止损线。
- **0.1.2**：原生 `--ref-video`；showrunner 支持白模 proxy。
- **0.1.1**：第一个 GitHub 对齐的插件版本；六 skill 拆分、Set C、16 GB 自动路由、show contract、白模与声音一致性。
