---
name: h3-workstation
description: 安装、迁移、体检、修复本机 MiniMax H3 / ComfyUI 环境；选择组件集、解决显存与页面文件问题、清理运行记录。当用户提到装 H3、ComfyUI 起不来、换显卡、生成变慢、磁盘或显存清理时使用。
---

# H3 工作站：安装、体检、修复与维护

目标：把本机变成可复现的 MiniMax H3 工作站。**只在环境未知、报错、换机或维护时进入**；正常生成不重跑医生。安装/体检完成后把控制权交给 `h3-generate`。

## 平台矩阵

先探测操作系统与加速器，再给任何安装命令。

| 平台 | 状态 | 指引 |
|---|---|---|
| Windows + NVIDIA CUDA | 主路线，本机已验证 | 走 ComfyUI + H3 Lite 快路径与本目录脚本 |
| macOS Apple Silicon | 社区替代，非等价验证 | 明确说明 ComfyUI 路线未在 Metal 验证；MLX/`mmh3turbo` 是外部资源，独立许可与更新 |
| macOS Intel | 不建议 | 不承诺本地生成，建议托管/API 或其他后端 |
| Linux + NVIDIA | 未验证 | 概念可迁移，Windows 路径、打包节点与耗时不可照搬；需用户明确选择实验 |

非 Windows 用户保留跨平台有用的部分（提示词结构、32 像素对齐、低分辨率预览、磁盘/日志检查），但每个资源与耗时都要标注平台属性。

## 安装目标契约

下载或移动任何组件前，先确定并复述一个目标：

```text
Install mode: reuse-existing | current-project | dedicated-folder
ComfyUI: <absolute path>
Models: <ComfyUI>\models
Custom nodes: <ComfyUI>\custom_nodes
Output: <ComfyUI>\output
```

- `reuse-existing`：用用户给出或确认的现有路径，不克隆、不重装、不建第二套模型目录。
- `current-project`：放在 `<workspace>\.h3lite\ComfyUI`。
- `dedicated-folder`：用户给的绝对路径，优先非仓库盘（例如 `<fast-disk>:\AI\MiniMax-H3\ComfyUI`）。
- 没有现成安装也没有目标路径时，先推荐专用目录并请用户确认，不得静默选盘或装进项目根。
- 不把本机路径写死到脚本或工作流；不覆盖已有安装、不静默替换模型文件。

## 冷路径顺序

1. 平台/加速器检查；
2. `h3_doctor.py` 体检（只读）；
3. 选档（fast / balanced / quality / 6 GB 实验）；
4. 安装或修复；
5. 再跑一次医生，确认无缺失节点/模型；
6. 启动 ComfyUI，交给 `h3-generate` 提交。

## 1. 体检

```powershell
$environment = '<ComfyUI>\user\h3lite_runs\_environment'
python scripts/h3_doctor.py --json `
  --report-file "$environment\doctor.json" `
  --root <chosen-root> --comfyui <ComfyUI-path>
```

记录：GPU 型号与显存、系统内存、磁盘余量、Python、CUDA/PyTorch 可见性、ComfyUI 位置、模型与自定义节点存在性、页面文件余量、GPU 进程。

- 低内存/低显存只是警告：8 GB 路线可在 offload 下完成。
- **页面文件接近耗尽必须阻止**：它曾导致 `hostbuf_file_reader_read failed` 与系统级分页失败，`h3_preflight.py` 会直接 blocked。
- 没有 NVIDIA CUDA 设备时，不承诺本地方案，说明限制并给替代后端。

## 2. 选档

- **Fast（默认）**：W4A8/4B/Turbo 组件集，640x352，124 帧，4 步；8 GB/极低显存启动用 `--lowvram`，10–16 GB 正常 VRAM。
- **Balanced**：8 GB 笔记本保持 640x352、6 步、绕过 Block Cache；中高显存可由 planner 选 864x480。
- **Quality**：8 步；8 GB 仍 640x352，并说明 W4A8/4B 是质量上限。
- **6 GB 实验**：608x352、4 步、低显存 offload，仅在 32 GB 内存、SSD、页面文件充足时谨慎尝试。
- **低于约 6 GB 或内存/磁盘不足**：不要下载、不要排队；解释缺口并建议托管/API 或别的模型。

小文件不等于快：低显存下 CPU offload、内存带宽、内核兼容与首次编译常占主导。

### 组件集

- 扩散权重、文本编码器、Turbo LoRA、工作流、节点版本是**一个组件集**，不可从各自合理的文件名拼装。
- `--component-set auto` 用于唯一明确的一套；两套都装时才显式 `A`/`validated-low-vram-a` 或 `B`/`portable-16gb-b`。记录到 run manifest，不逐角色解析半套。
- Set B 文件首次使用或大小/mtime 变化后要求记录 SHA-256；同尺寸损坏的 W4A8 曾产出彩色马赛克，字节数不是完整性证明。
- `minimax_h3_turbo_v4_step600_ema.safetensors` 在加速图（Sage/Sol/Chunk/T8 与原生 BlockSparseAttention）上 **<6 步被拒绝**：4 步重影/拖影/偏色，6/8 步本机实测干净（稀疏与稠密都干净），护栏按步数判定；4 步想用 v4 配 `*_compat_api.json`。
- **Set C（2026-11-19，RTX 4060 Ti 16 GB）**：Sol INT8 convrot 视频 VAE、BlockSparseAttention sol-attn、Pika lite LoRA 以 strength 1.0 替换 turbo v1.0、启动参数 `--fast fp16_accumulation fp8_matrix_mult cublas_ops autotune`。六个自钉模板（speed640 / t2va768 / quality864 / i2va768 / fl2va768 / ref2va768）**不在** `COMPONENT_SETS` 里：用 `--component-set auto` 或不带 `--resolve-models` 运行，**绝不传 A/B**，否则会重写 unet/clip/lora 角色并破坏 Pika/Ref2VA 配对。0.1.1 起，16 GB 机器上默认 `auto` 会按实测路线/画布自动选 C；显式 A/B、显式模板或 `--acceleration compat` 仍走注册的 A/B 路线，判定理由见 dry-run 的 `set_c_auto`。
- 实测（124 帧、4 步、含音频）：640x352 约 23 s；864x480 约 42 s；1344x768 T2VA 约 129 s（`h3_c_t2va768`，已取代 bundled `h3_w4a8_t2v` 的 768p 推荐位）；1344x768 FL2VA 约 150–165 s；1344x768 Ref2VA 约 161 s。

### 下载源

| 硬件 | 包 | 链接 | 提取码 |
|---|---|---|---|
| 约 8 GB 显存 | Set A | https://pan.baidu.com/s/1IBlH0VY7tWGvxqMtniraow | `4hri` |
| 16 GB 级 | Set B | https://pan.baidu.com/s/1x5GGuJv0h8chApgVoDgIaQ | `1hjx` |
| 16 GB 级 | Set C（Set B 的 overlay） | https://pan.quark.cn/s/6f8f5ce9f8a6 | 口令 `/~67293cXj30~:/` |

Set C 不是第三套底座：先装 Set B，再把 `H3lite_SetC_0.1.1/core` 合并进 `<ComfyUI>`；只有 Ref2VA 路线才加 `ref2va`。四个模型文件必须与包内 `SHA256SUMS.txt` 一致。

- Set C 校验与 manifest：`python scripts/h3_setc_assets.py --package <pkg> --comfyui <ComfyUI>`。默认写 `<pkg>/component_manifest.json`；`--quick` 只核大小，完整模式会流式复算四个 SHA-256。

只让用户下载与硬件匹配的一整套；把包内 `models`、`custom_nodes` 合并进 `<ComfyUI>`，保留 `component-manifest.json`，合并后跑医生。包不可用或用户要求上游下载时，用 `references/component-sets.md` 里的精确文件名、大小与哈希。

大文件下载前先做冷路径探测：测试候选 URL 的小段可续传请求，报告最快速度与预计时间，再决定 `aria2c` 或 `curl.exe -L -C -`；保留 `.part` 续传，不轻易从零重来。

## 3. 安装或修复

顺序：运行时依赖 → ComfyUI → 必需自定义节点 → 模型文件 → 医生复检 → 启动。

- 只装所选工作流真正引用的节点；基线需要 ClipProj 或兼容实现；KJNodes、H3 Turbo helper、Sol Attention、T8 Block Cache 是可选，除非加速图显式使用。
- 装完再跑医生；有任何必需模型/节点缺失时不得开始生成。
- Torch 导入错误立即停；comfy-kitchen/Torch 不匹配按修复决策处理，不要下载完大文件才发现。
- 8 GB 常用 `--lowvram --fast-disk`；10–16 GB 正常不加 `--lowvram`，除非预检或 OOM 证明需要。
- 后台启动 ComfyUI 必须把 stdout/stderr 重定向到持久文件。管道在会话清理后失效会让进程活着但 tqdm/logger 抛 `OSError: [Errno 22] Invalid argument`；遇到该签名只重启并修日志，不重下模型。
- **连续第二条 H3 任务前**：若同一服务刚完成一条，或出现过 ClipProj `_encode` access violation，用干净进程重启再提交；不要复用崩溃后的服务状态。空队列不等于服务干净。
- Sage Attention 只有在 PyTorch/CUDA 兼容确认后再加；Easy Cache 等缓存节点是 opt-in 实验，不得仅凭速度宣传开启，先与无缓存基线做短对比。
- 冷路径允许慢：记录组件 URL、替换文件名、大小/哈希、加载器选择、导入探测与任何小补丁——这比发现 20 GB 错模型便宜。

## 4. 预检与显存争用

```powershell
python scripts/h3_plan.py --doctor-json "$environment\doctor.json" `
  --install-mode reuse-existing --comfyui <ComfyUI-path> `
  --mode auto --aspect landscape --video-seconds 5 `
  --report-file "$environment\plan.json" --json

python scripts/h3_preflight.py --doctor-json "$environment\doctor.json" `
  --plan-json "$environment\plan.json" --refresh-runtime --require-audio --json
```

`ready` = 无观察到风险；`caution` = 可继续但必须显式提醒；`blocked` = 先修环境或换后端。预检忽略 ComfyUI 自身进程与零显存桌面助手，只警告有意义的外部 GPU 竞争者。

与其他 CUDA 重负载共存时：

- 先 `python scripts/h3_vram.py --json` 看真实每进程显存；`nvidia-smi` 总量无法定位占用者。
- 确认对方空闲再处理。ComfyUI 空队列**不会**释放常驻模型，进程仍占数 GB，直到重启或 offload。
- 绝不停止有排队/运行任务的 ComfyUI。
- 脆弱提交前用 `python scripts/h3_vram.py --check-free-gb 5` 做门禁。
- 案例与诊断见 `references/gpu-contention.md`。

## 5. 缓存与维护

- 医生报告缓存于 `<ComfyUI>/user/h3lite_runs/_environment/`，正常会话 30 分钟内复用；ComfyUI/模型/节点/驱动变化或失败后失效；波动资源用 `h3_preflight.py --refresh-runtime`。
- 不要每次生成前重验大模型；信任缓存清单，除非文件缺失、大小/mtime 变化、用户换组件或上次因模型/节点/加载器错误失败。
- 清理是显式维护，不是热路径：`python scripts/h3_cleanup.py` 先 dry-run，确认后才 `--apply`；保留 `_environment`、`_hotpath`、`_workflows`、`_experiments`、提示词目录、耗时数据与生成输出。

## 6. 边界与交接

- 本 skill 不写创作提示词、不提交生成任务。
- 环境 `ready`/可接受 `caution` 后，把 `<ComfyUI>`、组件集、分辨率与启动状态交给 `h3-generate`。
- 需要“为什么慢/为什么卡”的诊断时，先看预检与 GPU 争用，不要重新下载模型。

## 资源

- `references/deployment-matrix.md`：低显存档、官方回退档、模型目录、节点角色、启动参数（含 Set C）、16 GB 加速阶梯与故障排序。
- `references/component-sets.md`：Set A/B/C 的精确文件、大小、运行 ABI 与下载完整性规则。
- `references/gpu-contention.md`：WDDM 显存争用、每进程读数、处理顺序与实测案例。
- `references/cache-and-qa-reuse.md`：doctor/preflight/QA 的缓存 key、TTL、失效条件与不该缓存的状态。
- `scripts/h3_doctor.py`、`h3_plan.py`、`h3_preflight.py`、`h3_cleanup.py`、`h3_vram.py`、`h3_paths.py`、`h3_setc_assets.py`、`h3_cache.py`。
- `scripts/h3_setc_assets.py`：校验 Set C 四个模型与包结构，生成 `component_manifest.json`。
- `scripts/h3_cache.py`：文件指纹、显式 key 的 JSON 缓存、成功命令输出回放。

## 来源

- 官方 ComfyUI H3 教程：https://docs.comfy.org/tutorials/video/minimax/minimax-h3
- H3 Turbo 节点：https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo
- MiniMax H3 仓库：https://github.com/MiniMax-AI/MiniMax-H3
