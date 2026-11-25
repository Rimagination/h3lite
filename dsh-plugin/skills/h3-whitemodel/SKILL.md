---
name: h3-whitemodel
description: 用 Blender 参数化白模（blockout）产出 H3 的运动与构图参考，并直接接入 Ref2VA：静态白模、白模视频、室内多镜 previz、12fps motion proxy、360° 环绕运镜、版本同步与上下对比 QA。包含专业调动作规范、相机时间参数重复归一化、旧代理错配、H3 自然补帧与“节奏不完全一致”的实测边界。当用户要白模、blockout、previz、预演、运动参考、Blender 人偶、打斗走位、用白模生成 H3、检查白模有没有运镜，或反映白模/H3 节奏对不上时使用。
---

# 白模预演与 H3 视频参考产线

输出物：白模静帧、白模视频、可直接接入 H3 Ref2VA 的 motion proxy。**本 skill 只产参考，不提交 H3 生成**；生成走 `h3-generate`，成片拼接与交付走 `h3-post`。白模负责动作、构图和相机，角色身份始终由原始角色图负责。

## 运行时与磁盘红线

- Blender 4.5.9 LTS portable：默认 `E:\Blender\blender-4.5.9-windows-x64\blender.exe`，headless 调用 `blender.exe -b --python <script> -- --args`。
- Workbench 灰模渲染走 CPU，不占 H3 的 GPU 队列；1344×768 单帧约 1–2 s，240 帧通常数分钟。
- 大帧序列、代理和成片优先写 E 盘或项目工作区。C 盘接近满会连带触发 H3 的 HostBuffer/提交错误，不要把白模帧序列堆在系统盘。
- 编码统一用已安装 ffmpeg / ffprobe；脚本也可通过 `H3LITE_FFMPEG` / `H3LITE_FFPROBE` 指定。
- 网格只建一次，逐帧更新变换（胶囊 scale + 四元数）；不要每帧重建网格。

## 三条产线

| 脚本 | 产物 | 关键参数 |
| --- | --- | --- |
| `scripts/whitemodel.py` | 静态白模参考图 | `--out --res --pose` |
| `scripts/whitemodel_video.py` | 单镜白模视频（关键帧 + 运镜） | `--outdir --frames --fps --res` |
| `scripts/whitemodel_indoor.py` | 室内景、可翻倒道具、三镜切 10 s previz | 同上；改 SHOTS 机位表 |

输出先低清全量快验，再高清全量渲染。验收时必须同时看动作相位和相机位置，不能只验“文件存在、帧数正确”。

## Blender 集成：headless / bpy / MCP

- 最终白模用 headless 脚本；交互搭景、看机位、搜资产才用可选的 `mcp-for-blender`。
- 通用 bpy 片段、MCP 安装与安全边界、从 MCP 到 headless 的交接见 [`references/blender-integration.md`](references/blender-integration.md)。
- 社区 AI 控 Blender 的实战经验（计划→相机→分层→截图对比循环→MCP 协议→headless 交接）见 [`references/ai-blender-playbook.md`](references/ai-blender-playbook.md)。
- 场景交接用 [`scripts/blender_scene_snapshot.py`](scripts/blender_scene_snapshot.py) 导出 `scene_info.json` + 1 帧 smoke；`--audit` 检查相机/命名/帧率/分辨率/动作，`--fail-on-warnings` 可当门禁。不要把 viewport 截图当 H3 参考。
- MCP 需要 Blender GUI + addon + `uvx`；socket 无认证，只在本机 localhost 使用，且只留一个 server。

## 调动作六条

不自然的白模视频几乎总是缺其中一条；细则与反例见 [`references/motion-craft.md`](references/motion-craft.md)。

1. **Pose-to-pose + breakdown**：先摆极端姿势，再加 breakdown 定弧线；禁止稀疏关键帧直接补中间。
2. **预备、过冲、缓冲**：出手前反向蓄力，命中后过冲回弹，收势前微沉降。
3. **接触帧锁脚**：迈步只发生在换步帧；站定期间共享踝坐标，杜绝滑步。
4. **Catmull-Rom 穿关键帧**：保证速度连续和关节弧线；不用分段 smoothstep 硬拼。
5. **次要运动**：头部约 1.5 帧滞后；胸和手不滞后，避免吃掉打击 snap。
6. **间距调节奏**：快慢靠关键帧时间戳，不靠改插值公式。

## 相机：必须一眼可见

“强运镜”“强视差”不是验收语言。验收要能指出画面里的人或景在什么时间从哪个方向移动到哪里。

### 360° 环绕配方

固定目标、固定半径、固定高度，匀速绕主体一圈。10 秒轨道按 0 s 正面 → 2.5 s 右侧 → 5 s 背面 → 7.5 s 左侧 → 10 s 回正面验收。

```python
TARGET = (0.20, 0.20, 1.45)
RADIUS, HEIGHT, LENS = 5.80, 2.80, 32.0

def sample_camera(t_seconds):
    u = min(max(t_seconds / 10.0, 0.0), 1.0)
    theta = math.radians(-90.0) + math.radians(360.0) * u
    pos = (TARGET[0] + RADIUS * math.cos(theta),
           TARGET[1] + RADIUS * math.sin(theta), HEIGHT)
    return pos, TARGET, LENS

def place_camera(t_seconds):
    pos, target, lens = sample_camera(t_seconds)
    cam.location = pos
    cam_data.lens = lens
    cam.rotation_quaternion = (Vector(target) - cam.location).to_track_quat("-Z", "Y")
```

时间单位只允许换算一次：`sample_camera()` 若内部已经执行 `t / duration`，调用端就必须传秒，不能再传 `t / duration`。本机曾因 `place_camera(t / 10)` 再被除一次，10 秒轨道实际只走了 36°。

### 相机验收

1. 在 0%、25%、50%、75%、100% 五个进度点打印 `camera_location`、前向向量和目标点，确认机位跨越正面、右侧、背面、左侧、回正面。
2. 抽五帧做接触表，不看代码自证。若五格没有侧面、背面和回正，就是没环绕。
3. 检查主体是否始终在框内、是否被树/墙/道具挡住；必要时调整半径、机位高度或目标点，不靠“镜头有动机”辩解。
4. 复杂动作用低清全量代理看节奏，高清只渲已通过的版本。

## 接 H3：白模视频直接作为 Ref2VA 参考

本机已实测：灰模视频可以直接作为 Ref2VA 的视频条件输入，**不需要先转 depth/pose**。白模只控制动作、阻断和相机；身份、材质、服装从原始角色参考图来。旧版本“白模原片不能直接喂”的结论已作废。

### 两份文件

- **审片母版**：24 fps、与成片同画幅（例如 1344×768）、带完整相机；用于检查动作、构图和接触表。
- **motion proxy**：只给 H3 的轻量序列。本机稳定配方为 12 fps、864×480、SAR 1:1；10 秒片源对应 120 帧。用 [`scripts/make_motion_proxy.py`](scripts/make_motion_proxy.py) 生成并校验。

```bash
python scripts/make_motion_proxy.py \
  --input <white_model_24fps.mp4> \
  --output <project>/<name>_motionproxy_12fps_864_sar1.mp4
```

### 工作流接线

插件自带的 `h3_generate.py` 已支持原生 `--ref-video`，会自动完成下面的 LoadVideo/GetVideoComponents 接线并按 sha256 staged 代理；这段 JSON 只用于非插件用户或手工模板。

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

自定义 Set C Ref2VA API 图中的最小接线：

```json
"18": {"class_type": "LoadVideo", "inputs": {"file": "<proxy_in_ComfyUI_input>.mp4"}},
"19": {"class_type": "GetVideoComponents", "inputs": {"video": ["18", 0]}},
"6": {
  "class_type": "MiniMaxH3ReferenceToVideo",
  "inputs": {
    "ref_videos.ref_video_0": ["19", 0],
    "ref_image_size": "match"
  }
}
```

角色图仍走 `ref_image_0`。参考视频不要带音轨；白模没有对白时更不要让模型把参考音轨当成声音条件。文件必须 staged 到 ComfyUI 的 `input/`，路径只写该目录内的文件名。

### 请求与提示词

- 10 秒单条用 244 请求帧，Set C 实际常自然补到 260 帧 / 10.833 秒；这是正常补帧，不裁尾、不重跑。
- 提示词仍要完整写动作时间线、机位路径、景别、朝向和完成态。参考视频只提供条件，不保证逐帧复刻。
- 明确写视频参考的职责：动作、阻断、相机和接触点；明确禁止复制灰模材质、球关节和场景。
- 身份描述一律绑定原始角色图，不把白模当身份参考。
- H3 会重定时、平滑或合并动作。白模 240 帧 / 10.0 s 与 H3 260 帧 / 10.833 s 不是逐帧同步关系；相似是提示词和参考共同作用的结果，不是 motion transfer 的精确保证。

## 版本合同与节奏

- **H3 与任何对比片必须使用同一版白模**。白模修正后，旧 H3 不能继续当作同一运动参考；要么重跑 H3，要么明确说明“上段新白模、下段旧 H3，仅做近似对照”。
- 上下对比需要补齐长度时，用 `tpad=stop_mode=clone:stop=N` 停住上段白模尾部，不会让两段动作变成同步。报告时写清上段停住、下段继续。
- 用户说“节奏不完全一致”时，先查版本和时长，再谈模型：常见根因是旧代理、12 fps 降采样、H3 自然补帧和末尾冻结，而不是播放器。
- 若用户要求严格同步，先说明 Ref2VA 的边界；可重生成 H3、统一时间基准，或单独做时间重映射，但不能把语义参考包装成帧级控制。

## 接入 show.json

- 每个使用白模的镜头在 `show.json` 写 `white_model.source`、`white_model.proxy`、`white_model.version`；`mode` 必须是 `ref2va`，并同时有身份参考图。白模只承担动作/走位/相机，不承担身份。
- 提交前跑 `h3-generate/scripts/h3_show_validate.py --spec <show.json> --check-sha --strict`；校验器会核对白模是否走 Ref2VA、proxy 实际 fps/尺寸、源片与代理是否不同、版本字段是否缺失。
- 白模修正后先更新 `version`，再重跑 H3；不要用旧 H3 配新白模做“同源”对比。合同见 [`../h3-generate/references/show-contract.md`](../h3-generate/references/show-contract.md)。

## 验收流程

1. 低清全量预览：`--res 320x184 --frames 全量`，抽 2–3 帧看构图和动作相位。
2. 高清全量渲染，ffprobe 验分辨率、fps、帧数和时长。
3. 相机五点日志 + 五格接触表，确认完整环绕和主体不被遮死。
4. 生成 motion proxy，确认 fps、分辨率、SAR 1:1、帧数和来源 SHA-256。
5. H3 成片验帧数、时长、音轨、身份、动作密度；12 fps 输入不代表成片也是 12 fps。
6. 上下对比用 [`scripts/qa_reference_stack.py`](scripts/qa_reference_stack.py) 验面板来源、运动、尾部冻结和旧版差异；数值合格后仍要看接触表。
7. 交付命名、封面、响度和最终 SHA 交给 `h3-post`。

```bash
python scripts/qa_reference_stack.py \
  --stack <stacked.mp4> --reference <current_white.mp4> \
  --h3 <h3.mp4> --old-reference <old_white.mp4> \
  --out-json <stacked_qa.json> --contact-sheet <stacked_contact.jpg>
```

判定参考：上段对当前白模的 MAE 应接近压缩噪声（通常 <1–2）；若它对旧白模的 MAE 明显更低，说明拿错了视频。上、下段近静止比例应为 0；补齐尾帧后上段末 20 帧应接近 0，而下段仍有运动。

## 失败模式

| 症状 | 根因 | 处理 |
| --- | --- | --- |
| 脚本写着 360°，视频只轻微移动 | 时间参数被重复归一化 | 只换算一次；打印五点机位；出五格图 |
| “强运镜/强视差”用户仍说没变化 | 视差不是轨道运动 | 改完整 cardinal orbit，看到侧面、背面、回正 |
| 白模/H3 节奏对不上 | 旧代理、12 fps、补帧、尾帧冻结 | 先锁版本和时长，再决定是否重跑 |
| 用新白模配旧 H3 做对比 | 运动参考不是同一版 | 重跑 H3，或明确标注只作近似对照 |
| H3 角色身份漂移 | 白模被当成身份参考 | 身份锚定原图，白模只写动作/相机职责 |
| 五格中主体被树/墙挡住 | 机位或场景碰撞 | 调半径/高度/目标点，低清重验 |
| 直接喂白模失败 | 把旧 skill 的 depth/pose 限制当事实 | 本机已验证可直接喂 Ref2VA；检查接线和 staging |
| 打斗/交手被 H3 演成拥抱、靠近或静止 | 只有身份参考，没有动作/接触约束 | 用白模视频约束走位、接触点和分段过招；不要只改提示词或加“打斗”形容词 |

## 资源

- [`references/motion-craft.md`](references/motion-craft.md)：调动作六条细则、反例台账、关键帧时间线、helper 清单、相机反例。
- [`references/h3-video-reference.md`](references/h3-video-reference.md)：白模直喂 Ref2VA 的实测数据、精确接线、proxy 规格、相机 bug 复盘、上下对比 QA 与节奏边界。
- [`../h3-generate/references/show-contract.md`](../h3-generate/references/show-contract.md)：白模镜头的 `show.json` 字段、版本锁定与提交前门禁。
- `scripts/whitemodel.py`、`whitemodel_video.py`、`whitemodel_indoor.py`：静态图、单镜视频、室内多镜 previz。
- `scripts/make_motion_proxy.py`：生成并验证 12 fps / 864×480 / SAR 1:1 的 H3 motion proxy。
- `scripts/qa_reference_stack.py`：验证对比片上下段来源、运动比例、尾部冻结和旧白模误用。
- [`references/blender-integration.md`](references/blender-integration.md)：headless bpy、通用 `blender_bpy` 片段适配、可选 `mcp-for-blender` 的能力/安装/安全边界/交接。
- [`references/ai-blender-playbook.md`](references/ai-blender-playbook.md)：社区 AI 控 Blender 的镜头简报、相机匹配、几何分层、动作管线、截图对比循环、MCP 协议、资产/生成与 H3 交接。
- `scripts/blender_scene_snapshot.py`：在 Blender 内导出场景 JSON（相机、帧率、分辨率、动作、物体），可选渲 1 帧 smoke；`--audit` 做命名/相机/目标/帧率/分辨率/动作检查；供 MCP→headless 交接。
