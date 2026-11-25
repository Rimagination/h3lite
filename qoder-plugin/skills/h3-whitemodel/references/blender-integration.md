# Blender 集成：headless bpy、blender_bpy、MCP

白模产线有三层工具，职责不同，不要混用：

| 场景 | 用什么 | 原因 |
|---|---|---|
| 最终白模静帧/视频、可重复交付 | 本 skill 的 headless 脚本 | 确定性、可重跑、无 GUI 依赖 |
| 通用 bpy 片段/场景自动化 | 本文的 bpy 适配段（源自通用 `blender_bpy` skill） | 不依赖外部 skill 安装 |
| 交互搭景、看机位、搜资产、试构图 | `mcp-for-blender`（可选） | 实时反馈；但不保证可复现 |
| 最终渲染 | headless 脚本 | MCP 的交互修改不进版本控制 |

社区 AI 控 Blender 的镜头简报、相机匹配、几何分层、截图对比循环和 MCP 执行协议，见 [`ai-blender-playbook.md`](ai-blender-playbook.md)。场景审计用 `blender_scene_snapshot.py --audit`。

## 0. Headless 基线

```powershell
E:\Blender\blender-4.5.9-windows-x64\blender.exe -b --python <script.py> -- `
  --outdir <dir> --res 1344x768 --fps 24 --frames 124
```

- 必须 `-b`（background）；`--` 之后是本脚本参数。
- 先用低清全量（如 `--res 320x184`）看动作/相机，再高清全量。
- 渲染用 Workbench 灰模：`sc.render.engine = 'BLENDER_WORKBENCH'`。
- 输出 PNG 序列后由 ffmpeg 编码；不要让 Blender 直接决定最终编码参数。

## 1. blender_bpy 适配（通用 skill 的本地子集）

通用 `blender_bpy` skill 只有 bpy API 片段；H3Lite 采用其原则，但把参数、相机和验收接到白模产线：

```python
import bpy, math
from mathutils import Vector

# 清空场景，避免默认 Cube/灯光污染
bpy.ops.wm.read_factory_settings(use_empty=True)

# 原语：球/圆柱/立方体
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(0, 0, 1.4), segments=20, ring_count=12)
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=0.5, location=(0, 0, 1.0), vertices=14)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.05))

# 材质：灰色哑光，不反光
mat = bpy.data.materials.new("ClayGray")
mat.diffuse_color = (0.55, 0.55, 0.55, 1.0)
obj = bpy.context.object
if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)

# 相机
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam.location = (4.0, -4.0, 2.5)
cam_data.lens = 32
cam.rotation_quaternion = (Vector((0.2, 0.2, 1.4)) - cam.location).to_track_quat("-Z", "Y")

# 关键帧：位置/旋转只打需要的最小集合
cam.keyframe_insert(data_path="location", frame=1)
cam.location = (3.0, -3.0, 2.9)
cam.keyframe_insert(data_path="location", frame=60)

# Workbench 灰模 + 输出
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x, sc.render.resolution_y = 1344, 768
sc.render.resolution_percentage = 100
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 124
sc.render.filepath = r"E:\Blender\wm_out\frame_"
bpy.ops.render.render(animation=True)
```

注意：

- 系统 Python 不能 `import bpy`；bpy 只在 Blender 进程里存在。`blender -b --python` 或 MCP `execute_blender_code` 才是执行入口。
- 避免每帧重建网格；用关节/物体变换和关键帧更新（现有 `whitemodel_video.py` 就是这样）。
- `bpy.data` 是全局数据，`bpy.context` 依赖当前选择/活动对象；headless 下不要假设有选中对象。
- 长渲染不要占住 agent 前台；用后台任务或分帧渲染，完成后编码。
- 相机时间参数只归一化一次；`sample_camera(t/10)` 再被内部除 10 会把 10 秒轨道压成约 36°（见 SKILL 的 360° 配方）。

## 2. mcp-for-blender（可选交互层）

项目：`ahujasid/mcp-for-blender`（原 `blender-mcp`，MIT，社区项目，非 Blender 官方）。

- 要求：Blender 3.0+、Python 3.10+、`uv`/`uvx`；Windows/macOS/Linux。
- 通信：Blender 插件在 localhost 开 TCP JSON socket，默认端口 **9876**。
- 安装：
  1. `uvx mcp-for-blender setup`（自动找客户端并装 addon），或手动 `uvx mcp-for-blender install-addon`。
  2. Blender Preferences → Add-ons → 启用 **Interface: MCP for Blender**；打开 Blender 时 addon 启动服务器。
  3. 在 MCP 客户端加：
     ```json
     {"mcpServers":{"blender":{"command":"uvx","args":["mcp-for-blender"]}}}
     ```
     Qoder 侧用自定义 MCP/Connector 加入同样的 command/args；改完配置需重载客户端。
- 工具（README 所述）：`execute_blender_code`、`look`、`get_scene_info`、`generate_3d`、`generate_gaussian_world`、`search_assets`、`import_asset`、`get_addon_status` 等。
- 适合：
  - 交互 blockout、试机位、看 viewport/camera 截图；
  - 搜索/导入 Poly Haven、Sketchfab、Poly Pizza 资产；
  - 让 LLM 写一段 bpy 并立即执行看结果。
- 不适合：
  - 最终白模成片的确定性渲染；
  - 需要版本化、可重跑的交付；
  - 无人值守批处理（需要 Blender GUI 和 addon 在线）。

### 安全边界

- `execute_blender_code` 可执行任意 Python；socket **无认证、无加密**。只在本机 localhost 使用，不要暴露到公网或不可信网络。
- 只运行一个 MCP server 实例；不要同时在多个客户端里连同一个 Blender。
- 不运行来源不明的脚本/资产；Qoder 的权限确认不能绕过。
- 可用 `BLENDER_MCP_SAFE_MODE=1` 限制高风险脚本；遥测可用 `DISABLE_TELEMETRY=true` 关闭。
- 资产下载可能阻塞 Blender 主线程（Poly Haven）或因 Cloudflare 失败（Poly Pizza）；失败不要让主流程卡死。

### 从 MCP 交接到 headless

MCP 里的修改不是交付物。每次交互搭景后：

1. 保存 `.blend`，记录 Blender 版本、addon 版本、相机、fps、分辨率、帧范围。
2. 用 [`scripts/blender_scene_snapshot.py`](../scripts/blender_scene_snapshot.py) 导出场景 JSON：
   `blender -b scene.blend --python blender_scene_snapshot.py -- --out scene_info.json`
   或在 MCP 里 `execute_blender_code` 读取该脚本执行。
3. 先渲 1 帧 smoke（`--render-frame`），确认机位/构图；再跑现有 `whitemodel_video.py` 或项目脚本高清全量。
4. 最终 H3 参考只用 headless 渲染出的母版/代理；不要把 viewport 截图当参考视频。

## 3. 失败模式

| 症状 | 根因 | 处理 |
|---|---|---|
| MCP 连不上 | Blender 没开、addon 没启用、端口不是 9876、多个客户端抢一个 server | 开 Blender → 启用 addon → 查端口；只留一个客户端 |
| `execute_blender_code` 成功但画面没变 | 改的是 `bpy.data` 副本/未更新 depsgraph | 用 `bpy.context.view_layer.update()`；在 viewport 截图确认 |
| 最终渲染和 MCP 看到的不一样 | MCP 改了临时场景但没保存/没记录；渲染设置不同 | 保存 `.blend` + snapshot JSON + 1 帧 smoke |
| 资产导入后比例/朝向不对 | 资产单位、坐标系、父级不同 | 导入后统一 scale/rotation，先单独渲染检查 |
| 相机路径首尾相似但没环绕 | 时间参数重复归一化 | 只归一化一次；打印五点机位 + 五格接触表 |
| 长任务被 MCP 超时打断 | 复杂操作/下载/渲染在主线程 | 拆小步骤；最终渲染走 headless 后台任务 |
