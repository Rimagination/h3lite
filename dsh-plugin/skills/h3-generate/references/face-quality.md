# Face-quality routing

这份说明只影响规划、提示词和生成后的检查，不会向视频推理图增加采样步数、额外模型或后处理推理。

## 路线选择

| 目标 | 默认路线 | 说明 |
|---|---|---|
| 物体、风景、卡通 | T2VA | 先用 fast 基线；没有人脸时通常更容易得到稳定画面。 |
| 单镜头可辨认人物 | I2VA / FL2VA 首帧 | 使用清晰首帧；限制为单人、正脸或四分之三脸、稳定发型和服装。需要精确首尾构图时用 FL2VA 双关键帧。 |
| 人像/角色成片、身份一致性优先 | Ref2VA（已验证，2026-11-19） | 使用 Set C 的专用 ref2va W4A8 底模 + Pika ref2va lite LoRA + `MiniMaxH3ReferenceToVideo`，`ref_image_size=match`。见下方“已验证的 Ref2VA 人像路线”。 |
| 高细节输出 | 先生成 1344×768 基础结果 | 官方 H3-Regenerate-2K 不是本地低显存默认路径。 |

I2VA 会重新生成首帧，因此参考图和视频首帧不一定逐像素相同。它可以改善构图和大致身份，但不能保证“就是同一张脸”。如果身份一致性是验收条件，应优先使用已验证的 Ref2VA 路线，或把参考图作为视频开头的静态画面再进行剪辑衔接。

## 已验证的 Ref2VA 人像路线（2026-11-19，RTX 4060 Ti 16 GB）

受控 A/B（同一角色首帧、1344×768、124 帧、seed 6、4 步、均通过含音频校验与三帧人脸抽检）：

| 路线 | 总耗时 | 人脸表现 | 运镜/构图 |
|---|---|---|---|
| FL2VA 双关键帧 + Pika fl2va lite | 151.97 s | 身份稳定，脸较小 | 严格遵循提示词运镜，首尾帧锚定 |
| Ref2VA match + Pika ref2va lite | 161.23 s（+6.1%） | 脸更大更清晰，身份更稳 | 自发推近更强，运镜指令遵循较弱，无末帧锚定，背景道具有轻微漂移 |

选型结论：人像/角色成片默认 Ref2VA `match`；需要精确端点构图或严格运镜时用 FL2VA 双关键帧。`ref_image_size=max`（短边 2048px）未实测且慢数倍，不作默认。

组件要点（详见 `component-sets.md` Set C）：

- FL2VA 与 Ref2VA 是两个独立的 transformer 底模；ref2va LoRA 必须配 ref2va 底模（`minimax_h3_ref2va_pruned_w4a8_mixed.safetensors`，11,770,657,048 B）。Set A 混合底模是唯一例外。
- 参考图绑定必须用 autogrow 点号键 `"ref_images.ref_image_0": ["<LoadImage节点>",0]`；扁平键会通过校验但在执行期抛 TypeError。
- 提示词用 `<Picture 1>` 锚定身份（"the woman in <Picture 1> ... exactly as shown in <Picture 1>"），shift_video 12.0 / shift_audio 3.0。
- Pika lite LoRA 以 strength 1.0 整体替换 turbo LoRA，不叠加；4 步音频偏弱是路线固有特性。

## 社群人像工具现状（2026-11 调研结论）

- Temporal Face Detailer（nikythebikky）：GitHub 仓库 404，comfy.icu 页面为过期缓存，不可用。
- Impact Pack FaceDetailer / ZenFaceDetailer：逐帧修复会引入闪烁，且 SDXL 修复模型对 16 GB 显存叠加 H3 不友好；不作为 H3 默认后处理。
- facerestore_advanced（flickleafy 分支）：维护停滞（2025-07 后无更新），CodeFormer/GFPGAN 类逐帧修复同样有闪烁与“换脸感”风险。
- 换脸类节点属于事后补丁，改变身份而非提升生成质量，仅在用户明确要求时使用。
- 结论：在 H3 上提升人脸质量的第一手段是路线选择（Ref2VA）+ 提示词护栏 + 更高分辨率，而不是外挂逐帧修复器。

## 人脸提示约束

- 第一镜只保留一个人；眼睛、鼻子、嘴和发际线清晰可见。
- 固定正脸或四分之三角度，避免快速转头、强烈表情、说话和大幅运镜同时出现。
- 先验证无对白的人脸稳定性，再加入对白或口型同步。
- 首帧、中帧、末帧都要检查；视频存在、动态正常和音频存在，不等于人脸质量合格。

## 零推理开销约束

人脸质量判断只允许使用提示词改写、已有首帧、抽帧检查和轻量媒体分析。不得因为“人脸模式”自动增加采样步数、叠加额外采样器、加载第二个生成模型或重复生成一遍。
