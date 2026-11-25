# AI 控 Blender 的白模/previz playbook（社区经验）

来源（均为社区项目，不是 Blender 官方）：

- `arjun988/blender-skills`（MIT，94 个 Blender skills）：reference-image-match、camera-cinematography、animation、rendering、qa-review、blender-director 等。
- `ahujasid/mcp-for-blender`（MIT，原 `blender-mcp`）：`look`、`get_scene_info`、`execute_blender_code`、资产/生成工具、safe mode。
- `dhakalnirajan/blender-open-mcp`：主线程串行、长渲染阻塞、MCP 工具分层。
- `scenario-labs/blender-plugin`：camera path planner、timeline capture、review scene、headless 入口（实验性）。
- `agmmnn/awesome-blender`：AI/MCP 工具索引。

这些项目的共同经验，压缩成 H3Lite 能执行的白模/previz 规则：

## 0. 五条硬规则

1. **先分析/计划，再碰 Blender**：镜头意图、参考图、相机、时长、fps、交付规格先写下来；不要边看边搭。
2. **相机先匹配**：机位/焦距/构图不对，后面所有细节都白做。
3. **每阶段截图/渲染对比**：viewport 或 hero camera；列 top 5 gaps；最多 3 轮收敛。
4. **MCP 是执行/观察层，不是导演**：最终白模渲染走 headless；MCP 只做交互 blockout、看机位、搜资产。
5. **保存再执行**：`execute_blender_code` 可跑任意 Python；执行前保存 `.blend`，只在本机 localhost 用。

## 1. 开拍前：镜头简报

先写：

| 字段 | 内容 |
|---|---|
| 镜头目的 | 建立/揭示/动作/情绪 |
| 主体 | 角色/道具/场景，画面占比 |
| 景别 | 全身/腰上/胸上/近景 |
| 机位 | 正面/3/4/侧面/低角/高角 |
| 镜头 | 18–28 广角 / 35–50 叙事 / 85–135 人像 / 150+ 长焦 |
| 运动 | 固定/推/拉/横移/升降/环绕/手持 |
| 时长/帧率 | 5s / 24fps；H3 网格 124 帧 |
| 交付 | 母版 24fps 1344×768；proxy 12fps 864×480 |

参考图/参考视频有的话，先做 Reference Analysis：

- 主体、剪影、比例
- 相机角度、镜头感、主体占画面比例
- 光位、明暗、色板 5–8 个值
- 独特特征、情绪

## 2. 场景审计（动手前）

```powershell
blender -b scene.blend --python blender_scene_snapshot.py -- `
  --out scene_info.json --audit --expected-fps 24 `
  --expected-width 1344 --expected-height 768
```

审计项：

- 有 active camera；frame_end > frame_start；resolution 100%
- 相机名 `CAM_*`；有 `EMPTY_CamTarget_*` 目标空物体
- action 名 `AN_*`；有 `COL_*` 集合
- 需要镜头运动时 active camera 有 action（`--expect-camera-move`）
- `--fail-on-warnings` 可把命名/目标缺失判失败

命名约定（社区通行）：

- `CAM_[Shot]_[Angle]`、`EMPTY_CamTarget_[Shot]`
- `COL_Cameras` / `COL_Props` / `COL_Env`
- `SM_*` 静态网格、`AN_[Char]_[Action]` 动作、`LGT_*` 灯光、`MAT_*` 材质

## 3. 相机：先匹配，再细节

| 感觉 | 焦距（全画幅等效） | 注意 |
|---|---|---|
| 广角建立 | 18–28mm | 边缘畸变 |
| 叙事/产品 | 35–50mm | 自然 |
| 人像/英雄 | 85–135mm | 压缩空间 |
| 长焦戏剧 | 150mm+ | 空间扁平 |

- 相机 + target empty 一起动；不要只动相机。
- 运动要 ease-in/out；起/中/尾三个点都检查构图。
- 运动库：slow dolly in（聚焦/压迫）、orbit（展示）、crane up（揭示尺度）、handheld noise（不安/纪录）、lock off（产品/建筑）。
- 先定画幅（16:9 / 9:16），再构图；H3 的母版/代理都按同一画幅。
- 360° 环绕：固定目标、固定半径/高度/焦距；0/2.5/5/7.5/10 秒对应正面/右侧/背面/左侧/回正面；五点机位 + 五格接触表双验收。

## 4. 白模几何：三层，不要一上来抠细节

1. **Tier 1 剪影/比例**：胶囊人偶、体块、主 masses；1 unit = 1 m；前向轴锁定。
2. **Tier 2 结构/断层**：关节、肩/胯、衣摆/道具的大转折；白模通常到这里就够。
3. **Tier 3 greebles**：只给真实需要辨识的道具/环境；白模不要堆小零件。

反模式：几百个无命名小方块堆在原点。正模式：命名、定位、父子关系清楚。

## 5. 动作：blocking → breakdown → spline

社区动画管线：

```text
Reference → Blocking（stepped）→ Breakdown → Splining → Polish
  → Cycle/loop 验证 → 相机验收 → 渲染
```

- 先摆极端姿势，再加 breakdown；不要稀疏关键帧直接补中间。
- Graph Editor：先 constant/stepped，再 Bezier auto handles，再加权 ease，最后清冗余键。
- 有机运动不要线性插值；循环动作首尾帧要对齐；idle 要克制。
- 相机 shake 用 location noise modifier，幅度小；不要靠随机关键帧。
- H3Lite 的六条调动作规则继续优先：预备/过冲/缓冲、接触帧锁脚、Catmull-Rom、头部滞后、间距调节奏。

## 6. 材质/灯光/渲染

- 白模用 **Workbench 灰模**；不要为了“好看”上 PBR，参考视频要的是可读的几何和运动。
- 如果做彩色 previz：材质按物体分开，**不要给共享结构材质打 emission/强度关键帧**（会整片爆白）。
- 预览用 EEVEE，motion blur off，taa samples 低；最终才 Cycles/高质量。
- 色彩管理 AgX；曝光先保证主体可读，不靠拉爆灯光。
- 渲染 passes / persistent data 只在最终需要时开；白模通常 PNG 序列 + ffmpeg 编码即可。
- 先渲 1 帧 smoke，再低清全量，再高清全量；不要直接全量。

## 7. 截图对比循环

每个阶段：

1. `look` / viewport screenshot / hero camera render
2. 与参考并排，列 top 5 gaps（相机→剪影→结构→材质→灯光→细节）
3. 修 gaps
4. 再截图
5. 最多 3 轮；仍不过就停，报告 remaining gaps

自动失败条件（社区 QA checklist 常见）：

- 相机看到的是错误侧面/背面
- 主体爆白/材质动画把结构材质带亮
- 参考要全身，画面只给局部
- 细节漂浮在原点/未贴到表面
- 预览模糊是 Cycles viewport + 低采样，不是模型问题

白模验收可简化为：相机、剪影/比例、动作相位、接触/锁脚、主体不出框、无漂浮道具、proxy 规格。

## 8. MCP 执行协议

- 先 `get_scene_info`，确认场景不是空的/命名/集合；不要假设。
- 优先用专用工具；只有 modifier/UV/批量/导出才 `execute_blender_code`。
- 小步执行，每步后查 scene/screenshot；一次大脚本失败难定位。
- Blender 主线程串行：长渲染/重建会阻塞后续命令；不要在一次 MCP 调用里塞整段高清渲染。
- 超时/断连：拆小、重连 addon、查端口 9876；只留一个 MCP server。
- 安全：socket 无认证/加密；`execute_blender_code` 任意代码；只在本机 localhost；可用 `BLENDER_MCP_SAFE_MODE=1`；执行前保存 `.blend`。
- 最终渲染回 headless；MCP 修改要保存 `.blend` + snapshot JSON + 1 帧 smoke，才能复现。

## 9. 资产与 AI 生成

- 资产库：Poly Haven（CC0）、Poly Pizza（低模）、Sketchfab；导入前确认许可，发布要保留 attribution。
- Poly Haven 下载走 Blender 主线程，可能卡 UI；1k/2k 足够近景以外。
- AI 生成：Hyper3D / Hunyuan3D / Tripo / Meshy 可做 base mesh/环境道具，但不是确定性交付；白模人偶和身份参考不要用生成网格替代。
- World Labs Gaussian world 需要 Blender 5.3+，当前 4.5.9 不适用。

## 10. 交回 H3Lite

```text
MCP/交互搭景 → 保存 .blend → blender_scene_snapshot --audit + smoke
→ headless 母版 24fps 1344×768 → make_motion_proxy 12fps 864×480
→ h3_generate --ref-video → 上下对比 QA
```

- viewport 截图不能当 H3 参考视频；必须 headless 渲染母版/代理。
- 白模改了运动/相机 → 重跑 H3；对比必须同源。
- 命名、场景信息、版本、SHA 记录在项目目录；不要只留在聊天里。
