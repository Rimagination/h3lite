# FaceRefine / 贴回式修脸：实验记录与止损线

**状态：实验性，不是默认后期，也不是身份修复。没有一个参数组合达到完美。**

“清晰度更高”“wobble 更低”“接缝指标 PASS”都不等于身份、脸型、画风和几何被接受。2026-11-24 的 JOJO 宫殿远景案例里，FaceRefine、FaceRefine-Plus、face_only、full_crop、FlowLock、freq_sep 都被逐一试过，最终用户否决了“先画坏再贴回”的结构，回到原生 Ref2VA 重生成。本文件只固化经验、已知 bug 和止损条件，不提供“一键修脸”承诺。

## 0. 先分清两类失败

- **清晰度不足**：底片本身脸是对的，只是远景像素少、糊、五官不可读。才可能考虑修脸。
- **身份/脸型/画风/动作错**：脸不是同一个人、眉眼鼻嘴比例错、画风立体/蜡感、动作或机位不对。修脸不能修这些；贴回只会把错误底片的脸锁住。应回 `h3-generate` 重生成。

**技术 PASS ≠ 人脸 PASS。** 检测率、wobble、接缝差分、解码和音频相关性全部通过，也不能推翻用户对脸型/画风/身份的否决。

## 1. 什么时候才考虑 FaceRefine

同时满足才考虑：

- 用户**明确要求**修脸，并接受这是实验性、可能失败；
- 失败主要在清晰度/细节，不是身份或几何；
- 单镜、5–6 秒单元，有原片、有回滚；
- 已先试过原生 Ref2VA 重生成：正确主脸 `Picture 1`、20 步 `beta`、去掉 4 步蒸馏 LoRA、必要时把远景改成中景/近景；
- 有原片与修正版的 A/B，能做连续帧目视与接缝/五官稳定性检查。

## 2. 不要用 FaceRefine 的场景

- 身份、脸型、画风不对；动作、运镜、构图不对；
- 全片自动套、跨镜批量套；
- 没有原片备份、没有 A/B；
- 想靠改 mask、加大 feather、full_crop、FlowLock 解决“五官在静止头上滑动”；
- 想用后期掩盖生成失败。

## 3. 历史管线与接线

典型链路（FaceRefine 原版）：

```text
H3FaceSelect → TrackCrop（动漫脸检测 + clip_vision 身份）
→ Ref2VA（512² 画布）→ InjectVideoLatent → PerFrameDenoise
→ Sampler → VAEDecode → Stitch → CreateVideo/SaveVideo
```

FaceRefine-Plus 在原链路后接：

```text
VAEDecode + 原帧 → H3FaceStitchPlus → H3FaceFlowLock → CreateVideo/SaveVideo
```

- Flow Lock 的 `base_images` 与 `refined_images` 必须同为输出分辨率，`base_offset=0`。
- 只改 Stitch/FlowLock 时可能走服务器缓存，实测 8–16 s；改 TrackCrop/Denoise 要整跑。
- 历史案例是 5.875 s / 1344×768 / 24 fps / 141 帧；`frame_load_cap` 必须落在 H3 网格 `5+17k`，6 秒 24 fps 用 141，不要用 144。

## 4. 已知 bug 与坑（每条都在本机踩过）

| 症状 | 根因 | 处理 |
|---|---|---|
| 任务跑完 GPU 工作后在最后一步崩 `TypeError: missing 'format'` | SaveVideo 缺 `format`/`codec` | 显式写 `format: "auto"`, `codec: "auto"` |
| 跟踪 20 帧后丢 122 帧 | `largest_face` 被画面顶部壁画/天花板纹样假脸劫持（88px conf 0.30 > 真脸 55px） | 远景点单主体用 `select=closest_to_xy`（角色脸中心 + frame_index=0），`confidence 0.35` 滤假脸 |
| 远景脸修不动 | PerFrameDenoise ramp 默认 30/120px 是给中近景校准的，55–92px 远景只拿到 0.55–0.82 乘数 | 远景用 `face_px_small=100`, `large=140`，按源像素填 |
| ramp 参数看似对但效果错 | face height 口径是**源视频像素**，不是输出/画布像素 | 用源视频的真实脸高；不要拿放大后的坐标填 |
| 整张脸被羽化糊掉 | feather 单位也是源像素；示例 24 是给大脸的 | 55px 脸用 feather 4 左右；full_crop 才考虑 16 |
| 日志里没有节点报告，以为没执行 | FaceSelect/TrackCrop/PerFrameDenoise 的 stdout 块缓冲 | 以 `/history` 的 `status` + `outputs` 为准，不要拿“日志没刷出”当失败 |
| 误判重复任务、中断错实例 | 用户可能用系统 Python + `--fast --lowvram` 重启服务器，新实例节点缓存为空；陌生 prompt 可能是浏览器重试 | 先查 `/history` 的 prompt 图、PID/命令行，再决定是否中断 |
| clip_vision 身份后端静默返回 None | 用了 ViT-B/32；该格式不可用 | 用 CLIPViT-L/14-336（openai `pytorch_model.bin`，layers.22 + pos_embed 577×1024） |
| 动漫检测器不出现在下拉 | `extra_model_paths.yaml` 注册后未重启 | 注册 `ultralytics_bbox` 后重启 ComfyUI；检测器用 `yolov8x6_animeface.pt` |
| 贴片边缘/头发里有一条锐糊过渡线 | face_only 矩形边界横穿头发，精修发丝与原片糊发不一致 | 可试 full_crop + feather 16 + `colour_match 0.8`；但这只是接缝修补，不解决身份 |
| 五官在静止头上“跳舞” | 主因不是接缝：H3 在 crop 上重画五官，特征相对底片每帧偏 1–2px（75px 脸实测 5–7px），头发/头轮廓不动 | 改 mask/贴片/full_crop/跟踪都不能根治；回原生重生成，或只在已通过身份的生脸上试稳定性后处理 |
| 关掉 colour_match 后整头色调逐帧呼吸 | 色调匹配缺失 | 保留 `colour_match 0.8`；不要为了“更自然”关掉 |
| 低 wobble 但脸仍被拒 | wobble 只证明时间稳定，不证明身份/几何/画风 | 必须做设定图/原片/修正版并排 + 连续帧目视；用户不接受就停 |
| 正确生脸被 FlowLock/freq_sep 拉回错误几何 | 后处理把正确五官往底片错误脸型叠 | 身份版生脸已正确时，不要接 FlowLock/freq_sep；用 full_crop + tone none + feather16 |
| 接缝环 diff 或裸 Laplacian 看似变大 | 锐化内容自身运动就会抬高帧间 diff；单次 decimation alias 也会抬高 Laplacian | 不要拿单一指标判失败；结合五官 offset、接缝环、连续帧目视 |

## 5. 历史参数（只作案例参考，不是通用配方）

FaceRefine 原版：

- 去噪 0.4 × 乘数 1.0；首版 `face_only + dilation24 + feather4` 被用户判“贴图片边缘跳动”。
- V2b `full_crop + feather16 + colour_match0.8` 让接缝环带差分低于原片（横移段 3.90 vs 5.54，升降段 7.59 vs 8.60，推近段 4.83 vs 6.35），但后续身份版仍被拒。
- 椭圆遮罩 + 大膨胀做过，指标与 V1 同档，没有解决。

FaceRefine-Plus 稳定性参数（S2，仅稳定性参考）：

- `paste_region=face_only`, `mask_dilation=24`, `feather=8`,
  `tone_mode=freq_sep`, `lowpass_face_frac=0.03`, `detail_gain=1.2`, `blend=1.0`
- Flow Lock：`sigma_frac=1/150`, `threshold=4.0`, `base_offset=0`
- 实测 wobble 0.197% 脸高/帧（旧 V2b 1.143%），但用户明确拒绝 S2 的脸：眼型、眉峰、鼻嘴、下颌被重画，比设定图更偏立体/蜡感。
- `lowpass_face_frac` 必须按脸大小调：0.15 是给 206px 脸的，75px 脸会把眼嘴低频也换回糊底片；0.03 保留精修形状。
- Crop 实际是 512²，不是 768；不要按 768 估 magnification。

## 6. 验收口径

1. **像素 diff 只证明“贴回去了”**：整帧 mean |diff| ≈2（编码噪声级）、脸区 13–18 说明输出是原片 + 精修脸，不证明身份。
2. **wobble**：逐帧真实脸框（YOLO 动漫）内 DIS base→refined 的 median flow，再测相邻帧 offset 变化 / face_height。案例：V1 1.025%、V2b 1.143%、S2 0.197%、同参数重渲 stock 1.120%；指标噪声底约 0.02 个百分点。低 wobble 不等于身份通过。
3. **接缝**：接缝环带相邻帧差分应低于原片；全帧检查无矩形鬼影；发际连续帧放大条里贴片边界不扫动。
4. **身份/画风/几何**：设定图、原片、修正版 0.5/3/5 s 并排；连续帧条；必要时 24 帧接触表；必须**人看**，不能只看检测率。
5. **音频**：原音频透传后与源波形相关 >0.999、最佳延迟 0 samples；保存原声内容。
6. **残差要写清**：修后头部内部逐帧差分可能比原片高 10–30%，主要是“变锐后运动天然产生更大帧间差”；若仍有细碎闪，去噪 0.3 重渲是未验证方向，不要写成保证。

## 7. 版本、交付与止损

- **保留原片**：不要把唯一的成片覆盖掉；除非用户明确要求原位替换，否则输出新文件并记录哈希。
- **版本绑定**：修脸结果绑定到这一版 H3/白模/参考；源变了就重跑，不要拿旧修脸结果配新片。
- **只做单镜**：不做全片自动套；多镜逐镜授权、逐镜 A/B。
- **用户否决脸就停**：不要继续调 mask/feather/FlowLock 试图“把脸修对”；回原生重生成，或改景别让脸有足够像素。
- **正确生脸不要叠后处理**：身份版生脸已经正确时，`freq_sep`/FlowLock 可能把正确五官拉回错误几何；只用 full_crop + tone none + feather 清理贴片边。
- **没有完美方案**：当前已知残留包括五官滑动、接缝/色调、身份偏移和细碎闪；任何“全 PASS”都只覆盖它测过的指标。

## 8. 本机案例与工具（非运行时依赖）

- `Carasibana/ComfyUI-H3-FaceRefine`（MIT）与 `AnniCodex/ComfyUI-H3-FaceRefine-Plus`，装在 `E:/MiniMax-H3/ComfyUI/custom_nodes/`。
- 2026-11-24 JOJO 宫殿 0–6 s 远景：141 帧、5.875 s、1344×768；从 face_only 到 full_crop、Plus/FlowLock、身份优先 Ref2VA 重生成，最终采用原生重生成，不采用贴回。
- 本地实验驱动与审计：`D:/H3lite/facerefine_ab/`（`plus_run.py`、`wobble.py`、`footprint2.py`、`identity_preview.py`、`final_visual.py`、`deliver_*.py`）。这些是案例脚本，不是插件依赖，也没有达到“一键可复用”的稳定度。
