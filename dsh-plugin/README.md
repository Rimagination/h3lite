# H3Lite for DeepSeek Harness

H3Lite 是一个通用的 AI Agent 插件：把本机 MiniMax H3 / ComfyUI 视频生产流程打包成六个可移植 skill，并在 DeepSeek Harness（DSH）里额外注册四个原生工具。

- **六个 skill**：`h3-workstation`、`h3-prompt`、`h3-director`、`h3-generate`、`h3-post`、`h3-whitemodel`。
- **四个 DSH 原生工具**：`h3_generate`、`h3_status`、`h3_doctor`、`h3_list_runs`。
- **同一份脚本**也服务于 Qoder、Claude Code、Codex、ZCode 和标准 MCP 客户端；插件不调用云端 API。

版本与仓库主插件对齐：**0.2.1**。

## 前置条件

- Windows + NVIDIA CUDA 主路线；其他平台可复用提示词/skill，但 ComfyUI 与 H3 推理未验证。
- Python 3.11+，能执行 `skills/h3-generate/scripts/*.py`；脚本本身以标准库为主，视频 QA 需要 ffmpeg/ffprobe。
- 已安装 ComfyUI 与 H3 组件集（Set A/B/C）；Set C 必须先装 Set B。
- 至少一次机器级路径配置（二选一）：

```powershell
# 方式一：写入 ~/.h3lite/config.json
python skills/h3-workstation/scripts/h3_doctor.py --comfyui "E:/MiniMax-H3/ComfyUI" --write-config

# 方式二：环境变量
$env:H3LITE_COMFYUI = "E:/MiniMax-H3/ComfyUI"
```

解析顺序：`--comfyui` → `H3LITE_COMFYUI` → `~/.h3lite/config.json` → `<project>/ComfyUI` → `~/ComfyUI`。新会话不依赖上一个任务的目录。

## 安装到 DSH

### 本地目录（开发/未发布）

DSH 的 **Plugins → Add plugin** 支持本地绝对路径：

```text
<本仓库>/dsh-plugin
```

安装后 bundle 显示为 **H3Lite**，新会话技能目录出现六个 skill，工具列表出现四个 `h3_*` 工具。

### npm / tarball

```bash
cd dsh-plugin
npm pack --dry-run   # 确认 skills/**、lib/**、runtime/**、cordis.patch.yml 在清单里
npm publish --access public
```

发布后用户在 **Add plugin** 填 `h3lite` 或 `h3lite@0.2.1`。也可把 `npm pack` 生成的 `.tgz` 上传到 GitHub Release，直接填 tarball URL。

## 工具

| 工具 | 作用 |
|---|---|
| `h3_generate` | 一次完成规划、预检、提交和验证；支持 T2VA/I2VA/FL2VA/L2VA/Ref2VA、参考图/音频/视频、Set C 模板和视频 VAE 覆盖 |
| `h3_status` | 按 `prompt_id` 查状态、输出路径、时长/帧率/音频和动态 QA |
| `h3_doctor` | 只读体检：GPU、RAM、页面文件、磁盘、模型/节点、ComfyUI 路径，以及 Blackwell 量化风险 |
| `h3_list_runs` | 扫描最近 run manifest，恢复全局流水线状态 |

工具参数与对应 Python CLI 保持一致。批量多镜、白模、后期、show contract 和网格 QA 仍由 skill 指导调用脚本：

```powershell
python skills/h3-generate/scripts/h3_showrunner.py --spec projects/ep04/show.json --strict --check-sha --output-dir <ComfyUI>/output
python skills/h3-post/scripts/h3_grid_check.py --video <output.mp4> --json
```

## Skill 与脚本布局

`index.js` 从包内 `skills/` 读取六个 `SKILL.md`，并把每个目录作为 `resourceBase` 注册。npm tarball 不包含仓库根目录，因此 `prepack` 会运行 `scripts/sync-skills.mjs`，把规范 skill 复制到包内；`npm run check-skills` 用于防漂移。

脚本仍然使用 `H3LITE_*` 环境变量和 `~/.h3lite/config.json`，不依赖 DSH 专有路径。这样同一套 skill 可以被其他 agent 直接复用。

## 可选：标准 MCP

包内附带 `runtime/h3-mcp-server.cjs`。其他 MCP 客户端可以直接启动：

```json
{
  "command": "node",
  "args": ["<安装路径>/runtime/h3-mcp-server.cjs"],
  "env": {
    "H3LITE_COMFYUI": "E:/MiniMax-H3/ComfyUI"
  }
}
```

DSH 不需要这个 MCP：四个工具已经以原生 `ctx.tools` 注册。MCP 服务器保留给 Qoder/Claude/Codex 等标准 MCP 宿主。

## 配置

| 变量/文件 | 用途 |
|---|---|
| `H3LITE_COMFYUI` | ComfyUI 根目录（含 `main.py` 与 `models/`） |
| `H3LITE_CONFIG` | 配置文件位置，默认 `~/.h3lite/config.json` |
| `H3LITE_PYTHON` | 运行 H3Lite 脚本的 Python；默认 ComfyUI venv 或系统 Python |
| `H3LITE_OUTPUT` | ComfyUI output 目录 |
| `H3LITE_RUN_ROOT` | run manifest 根目录 |
| `H3LITE_BASE_URL` | ComfyUI HTTP 地址，默认 `http://127.0.0.1:8188` |
| `H3LITE_SCRIPTS` | 覆盖脚本目录（一般不需要） |

## 已知边界

- 16 GB 卡不要并行两条 H3；481 帧单段禁止提交。
- Set C 的 Sol INT8 VAE 可能有 128px 接缝；最终交付前跑 `h3_grid_check.py`。
- RTX 50 系 + W4A8/INT8 convrot 有上游内核风险；先跑 640×352/4 步双提示词测试，受影响时只换 DiT 到 `fp8_scaled`。
- 插件不安装 ComfyUI、模型或 Python 包；只提供执行层和知识层。
