# Final-lite 中间画布 A/B（未验证）

**状态：候选方案，未在本机通过 A/B。不要把它当默认，也不要先加进 auto 路由。**

目标是找 864×480 与 1344×768 之间的“final-lite”画布，降低最终片的采样成本，同时不牺牲脸、身份和动作。候选：

| 候选 | 像素 | 相对 1344×768 | 预期采样成本 |
|---|---:|---:|---:|
| 1344×768（基线） | 1,032,192 | 100% | 100% |
| 1184×672 | 795,648 | 77% | 约 −10–20% |
| 1152×640 | 737,280 | 71% | 约 −15–25% |

估算是按像素面积，不是实测；H3 的稀疏注意力、VAE 解码和固定开销会让实际差距偏离。必须在同一画面、同一提示词、同 seed、同参考、同模板、同 4 步下做三臂 A/B。

## 0. 先决条件

- 三个画布都必须能被模板接受并 32 像素对齐；`--resolution` 是 `WIDTHxHEIGHT`，竖屏要交换。
- 用显式 `--workflow-template`，不要依赖 auto 路由；auto 只覆盖已验证的 640×352 / 864×480 / 1344×768。
- 参考图、参考视频、提示词、seed、步数、LoRA、组件集全锁；只改分辨率。
- 磁盘至少 12 GB 空闲；当前 E 盘约 11.57 GB，差约 0.43 GB，预检会拒绝。不要绕过预检；先清理/归档，再跑。
- 单条 5 秒、124 帧先做；不要直接跑 10 秒整片。

## 1. 三臂命令

以 Ref2VA 为例（T2VA/I2VA/FL2VA 换成对应模板）：

```powershell
# 基线
python scripts/h3_generate.py --workflow-template h3_c_ref2va768 `
  --prompt-file prompts/ab.txt `
  --ref-image refs/face.png --ref-image refs/body.png `
  --comfyui <ComfyUI> --output-dir <ComfyUI>\output `
  --resolution 1344x768 --length 124 --seed 20261125 `
  --component-set auto --watch --json

# 1184×672
python scripts/h3_generate.py --workflow-template h3_c_ref2va768 `
  --prompt-file prompts/ab.txt `
  --ref-image refs/face.png --ref-image refs/body.png `
  --comfyui <ComfyUI> --output-dir <ComfyUI>\output `
  --resolution 1184x672 --length 124 --seed 20261125 `
  --component-set auto --watch --json

# 1152×640
python scripts/h3_generate.py --workflow-template h3_c_ref2va768 `
  --prompt-file prompts/ab.txt `
  --ref-image refs/face.png --ref-image refs/body.png `
  --comfyui <ComfyUI> --output-dir <ComfyUI>\output `
  --resolution 1152x640 --length 124 --seed 20261125 `
  --component-set auto --watch --json
```

跑之前先 `--dry-run`，确认模板没有因为画布不是实测档而拒绝或改写模型角色。

## 2. 必测项

1. **墙钟时间**：用 `h3_status.py` 的 elapsed 或 `/history` 时间，不看 manifest 的估算。
2. **脸像素预算**：终帧/中段脸的像素宽高；和 1344×768 比，是否还够身份验收。
3. **身份/画风**：设定图、基线、候选 0.5/3/5 s 并排；连续帧条；必须人看。
4. **动作与运镜**：动作事件数、近静止比例、切点/机位是否被画布改变。
5. **音频**：原生音轨是否存在、是否变弱；4 步音频本来就弱，不能因候选画布更差。
6. **帧数/时长**：124 请求帧的自然补帧是否仍在容忍范围。

## 3. 验收与晋升规则

- 只有“身份、画风、动作、音频都不比 1344×768 差，且脸像素仍够验收”才可标为 final-lite 候选。
- 任何一项变差，就不晋升；保持 1344×768 终版。
- 通过后也只作为“预算档”写进文档，**不要自动改 auto 路由**；auto 只选已验证矩阵。
- 中间画布不能替代 1344×768 的最终验收；它只是降成本档。

## 4. 磁盘清理边界

- 不删模型、`input/` staged 参考、`custom_nodes`、venv。
- 可安全预览 `h3_cleanup.py --run-root <ComfyUI>/user/h3lite_runs`；旧 run 快照通常只有几十 MB。
- 旧成片/测试片可归档到 D 盘或项目 archive，不要直接删；记录移动映射。
- 清完后重跑 `h3_preflight.py`，确认 ≥12 GB；不要用“差一点”硬跑。

## 5. 本机实测（2026-11-25，单镜 Ref2VA 5 秒）

**素材与配置**：`jojo_face_identity_v2.png` 作 `Picture 1`；`D:/H3lite/native_regen/palace_native_prompt_v2.txt`；`h3_c_ref2va768`；124 帧；seed 20261125；4 步；`component_set=auto`；启动参数含 `--fast fp16_accumulation fp8_matrix_mult cublas_ops autotune`。

| 画布 | 实测耗时 | 时长/帧数/音轨 | 脸高（0.5/3/5 s） | 检测 confidence |
|---|---:|---|---|---|
| 1344×768 | 162.41 s | 5.167 s / 124 / 有 | 147.0 / 196.8 / 269.9 px | 0.904–0.917 |
| 1184×672 | 97.64 s（−39.9%） | 5.167 s / 124 / 有 | 105.1 / 149.6 / 211.3 px | 0.874–0.917 |
| 1152×640 | 107.24 s（−34.0%） | 5.167 s / 124 / 有 | 109.3 / 146.4 / 209.2 px | 0.884–0.917 |

- **脸/身份**：三档的银灰背头、粗直眉、窄灰眼、直鼻、薄唇、方下颌、青绿金边外套与金心别针都与设定图一致；1184/1152 细节更软，但同一人、同一画风，单镜目视可接受。
- **稳定性**：1152 第一次提交在文本编码阶段触发 ComfyUI-ClipProj `clipproj_nodes.py:443 _encode` 的 Windows access violation，服务崩溃；重启后同配置成功。1184 没有崩溃。重复提交 1152 只用了 6.17 s，是 ComfyUI 缓存命中，不是有效计时样本。
- **结论**：本镜优先候选是 **1184×672**：约 −40% 墙钟，脸仍可读、身份一致；1152 本轮没有速度优势且有一次性崩溃记录，暂不推荐。两者都**不能**直接进 auto 路由，也还不能替代 1344×768 终版；至少再跑 2–3 个不同景别/动作/带台词镜头，确认脸像素、动作密度、音频与稳定性。
- **磁盘**：清理前 E 盘 11.57 GB；把 135 个旧 output 视频（607.9 MB）归档到 `D:/H3lite/archive/comfyui_output_video_20261125/`，附 `archive_manifest.json`，未删除；清理后约 12.18 GB，满足 12 GB 预检门槛。测试结束已停止本次启动的 ComfyUI 服务。
