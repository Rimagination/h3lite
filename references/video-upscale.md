# Video upscale (post-processing)

超分是生成后的后处理：它不改变 H3 的生成图、不增加采样步数，只对用户明确要求的 “1080p/4K 等超生成画布范围” 的目标做像素级放大与增强。本地 H3 画布上限约 0.5 MP（960x544），超出一般不应靠重新生成来“放大”分辨率，而是走这条后处理路线。本机实测以 Topaz Video AI 为主，FlashVSR CLI（E:\FlashVSR，本机已装）为脚本化首选备选，ComfyUI + 4x-UltraSharp 与纯 ffmpeg 依次回退。

## 路线选择

| 场景 | 路线 | 说明 |
| --- | --- | --- |
| 本机已装 Topaz、要视频级增强（降噪+锐化+超分一体） | Topaz Video AI（主推） | GUI 稳定，模型齐全；无官方 CLI 文档，命令形态仅用于诊断（见下）。 |
| 只要几何放大、想离线/全脚本（本机） | **FlashVSR CLI** | `E:\FlashVSR` 独立安装 + 自带 Python 环境，一条命令跑完；注意 tile 网格陷阱与截断校验（见下）。 |
| 无 FlashVSR 时再退一步的脚本化备选 | ComfyUI venv + 4x-UltraSharp | spandrel + PyAV + 自带 ffmpeg，分块处理防 OOM，音频重封装。 |
| 快速预览、无权重、仅改分辨率 | 纯 ffmpeg `lanczos + unsharp` | 无模型推理，速度最快；只适合预览和轻度锐化。 |
| 想让视频变慢/补帧 | Topaz 帧插值（apo-8/Chronos） | 默认关闭；注意它会改变帧数与时长，属于另一类需求。 |

## Topaz Video AI 主路线（本机实测）

安装位置 `D:\Program Files\Topaz Labs LLC\Topaz Video`（1.6.2.0，neuroserver 20260601.1）；模型库 `D:\ProgramData\Topaz Labs LLC\Topaz Video\models`；日志 `%AppData%\Roaming\Topaz Labs LLC\Topaz Video\logs\2026-08-23-*.tzlog`。

GUI 步骤：打开视频 → 增强模型选 Starlight（星光）/ Astra Fast（内部代号 slf-2，`--filters` 里写 `astrafast`）或 Proteus/Rhea 等 → 输出大小选 1.125x（1296x720）或 2x（2304x1280）→ 导出。日志里 `EventTracker: Video Export Started` 记录完整导出参数，一次导出生命周期：

```text
neuroserver --once --input-path IN --output-path OUT.带编号.mp4
  --start-frame-idx 0 --end-frame-idx N --max-gpu-mem 9
  --filters [{"model": "astrafast"}] --output-width 2304 --output-height 1280
  --upscale-factor 2 --ffmpeg-encoding "-c:v h264_nvenc ... -bf 0"
→ 编码期间写 OUT.编号.mp4.temp.<uuid>.mp4（0 字节占位先建）
→ 完成后 cleanupPass 用 ffmpeg 重封装：
   -c:v copy -map 0:v -map 1:a:0 -c:a copy -bsf:a:0 aac_adtstoasc
   -metadata "videoai=Enhanced using slf-2. Changed resolution to 2304x1280"
   -fps_mode passthrough → 最终 __slf.mp4（同源第二次导出为 __slf_1.mp4）
```

`--max-gpu-mem 9` 来自应用内内存上限设置（实测 60% 档生效），不要在 UI 找不到时去改注册表：本机 `HKCU\Software\Topaz Labs LLC\Topaz Video` 下并不存在 maxMemoryUsage 键，实测该设置通过 UI 传递。音频由 cleanupPass 原样保留（`-c:a copy` + `aac_adtstoasc`），无需额外处理。

已装模型：Artemis（AAA/AHQ/ALQ 系）、Proteus、Rhea/Rhea XL、Iris、Gaia、Theia、Themis、Dione、Hyperion HDR、Aion、Nyx、Chronos/Chronos Fast（插帧）、Starlight Astra、Astra Fast、SLP-2.5。目录里有描述但**未安装**：Astra HQ、Astra Sharp、整个 Starlight Mini（slm* 及编码器/解码器/U-net 组件）。

耗时参考（RTX 4060 Ti 16 GB，209 帧输入）：1.125x（1296x720）约 4.5 分钟；2x（2304x1280）到第 122 帧耗时约 9.5 分钟，全程约 20 分钟量级。确认效果先用预览或 1.125x 跑一遍。

## 潜在问题与对策

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 导出报 `Out of memory` / 直接崩溃（退出码 0xC0000005，无 OOM 字样） | ComfyUI 等进程常驻显存；WDDM 驱动下 CUDA 虚报空闲 | 见 [gpu-contention.md](gpu-contention.md)：`python scripts/h3_vram.py --json` 找占用者，确认 `/queue` 空闲后再停；空队列≠模型已释放。本机实测：停掉常驻 9,805 MB 的 ComfyUI 后，20:09 的 1296x720 导出成功，20:14 的 2x 导出顺利推进到第 122 帧无 OOM。 |
| 模型管理器显示缺模型/一直下载 | Astra HQ、Astra Sharp、Starlight Mini 未安装到磁盘 | 检查 `D:\ProgramData\Topaz Labs LLC\Topaz Video\models\` 与 `models\models\<name>\` 是否有对应 blob；确需下载再让管理器执行。 |
| 卡在 “Finalizing model download…” 并无限重下 | zh-CN 区域下 QML 缓存导致版本校验失败 | 区域临时切 en-US → 删除 `%AppData%\Topaz Labs LLC\Topaz Video\qmlcache`（含 qml 缓存文件）→ 重启生成英文缓存 → 恢复区域设置。 |
| 下载中断留 `.zip.corrupt` 占位 | 断点续传损坏 | 用完整文件覆盖：`unzip -t` + 与 `C:\ProgramData\...\models\astrafast.json` 的 `validate_install.windows.model.zipHash`（SHA-512）比对；本地实测 6,439,256,676 字节校验通过。 |
| 输出没有声音/音画不同步 | （少见）源音频流异常 | 检查源视频音频流；cleanupPass 会 `-c:a copy`，不要手动抽掉音频流再封装。 |
| 帧率/时长变了 | 误开了帧插值（apo-8） | 默认 `out_fps=in_fps`；只有明确要慢动作才开插帧。 |
| 尺寸不对/或拉伸变形 | 源带旋转元数据（rotation=3 等） | Topaz 自动按 `adjustedSize` 处理；自定义 ffmpeg 时要保持原比例、禁止拉伸，输出宽高必须为偶数（yuv420p）。 |
| 修复程序提示“没关干净” | Topaz 有后台驻留进程/UWP 进程 | 结束全部 `Topaz Video*`、`neuroserver*`、`crashpad_handler` 进程后再运行。 |
| 想确认视频是否已被增强过 | 防止二次超分 | `ffprobe -show_entries format_tags=videoai`；含 `videoai=Enhanced using slf-2...` 表示已导出，一般不再重复超分。 |
| 授权/版本报错 | 授权文件或应用版本问题 | 日志 `has valid license: True` 表示校验通过；出现授权失败时走原安装渠道处理（本 skill 不提供绕过方案）。 |

导出后验证（用 Topaz 自带 ffprobe：`D:\Program Files\Topaz Labs LLC\Topaz Video\ffprobe.exe`）：

```powershell
& "D:\Program Files\Topaz Labs LLC\Topaz Video\ffprobe.exe" `
  -show_entries "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate" `
  -of json OUTPUT.mp4
```

必须确认：视频流存在、尺寸符合预期、帧率与源一致（24 fps）、音频流存在、时长接近源时长。

## FlashVSR 备选路线（本机已装，脚本化首选）

FlashVSR v1.1 独立安装于 `E:\FlashVSR\`（约 15 GB）：自带 Python 环境 `E:\FlashVSR\env`、CLI 工程 `E:\FlashVSR\ComfyUI-FlashVSR_Stable`、模型 `E:\FlashVSR\FlashVSR\examples\WanVSR\FlashVSR-v1.1\`。启动器 `E:\FlashVSR\run_flashvsr.bat` 已设好 PYTHONPATH、模型目录并**内置 `--tiled_dit --tiled_vae --tile_size 128 --force_offload`**（这是下面网格问题的直接根源，见案例），需要非 tiled 运行时直接调 `E:\FlashVSR\env\python.exe cli_main.py` 去掉这些参数：

```bat
E:\FlashVSR\env\python.exe cli_main.py --models_dir "E:\FlashVSR\FlashVSR\examples\WanVSR" ^
  --model FlashVSR-v1.1 --mode tiny --vae_model Wan2.1 --scale 2 ^
  --input IN.mp4 --output OUT.mp4
```

参数要点（CLI 实测）：`--mode` = `tiny`（快、标准显存）/ `tiny-long`（长视频专项优化、更省显存）/ `full`（质量最好、显存最大）；`--vae_model` 有 Wan2.1（质量最好）、LightVAE_W2.1（省显存）等 5 种；`--scale 2|4`；`--frame_chunk_size` 0 = 全部帧一次处理（长片会爆显存）；`--tile_size` 默认 256（32-1024）、`--tile_overlap` 默认 24（8-512，help 原文 "Overlap pixels between tiles to blend seams. Higher = smoother transitions"）；`--keep_models_on_cpu` 把模型常驻 CPU（16 GB 卡官方推荐档）；`--unload_dit` 在 VAE 解码前把 DiT 卸出显存；`--resize_factor 0.5` 先减半输入再超分（1080p 输入净出 2x）。官方 README 显存分档：**24 GB+：`full`/`tiny` + 关闭 tiling + chunk 0；16 GB：`tiny` + 仅 `tiled_vae` + chunk 0 或 ~100 + `keep_models_on_cpu`；12 GB：`tiny` + `tiled_vae+tiled_dit` + chunk ~50；8 GB：`tiny-long` 强制 tiling + chunk ~20**。注意：官方 16 GB 档建议“仅 tiled_vae”的**全帧路径在本机 1024x576/2x 实测 >4 分钟/帧，实际不可用**（见下方案例），正确做法是保留 tiled_dit 并把 overlap 提到 64。

模型包（FlashVSR-v1.1，约 7 GB）：`diffusion_pytorch_model_streaming_dmd.safetensors`（5,676,070,392 字节）、`Wan2.1_VAE.pth`（507,609,880）、`LQ_proj_in.ckpt`（575,694,948）、`TCDecoder.ckpt`（189,018,333），另有 `config.json` / `model_index.json`。

### 网格/棋盘格伪影（本机实测案例：1024x576、24 fps、479 帧的 H3 片段）

现象：2x 输出天空出现规则的 128 px 网格、海面带色带。原因链（`E:\FlashVSR\run_2x.log` 实测）：`--mode tiny` 下 50 帧分块两次 OOM → 运行中自动开启 Tiled VAE → 仍不够再自动开启 Tiled DiT（15 个 tile）；而 bat 固定传了 `--tile_size 128`（低于 CLI 默认 256）且 overlap 保持默认 24——相邻 tile 重叠太少、接缝融合不足，于是网格化。官方 README 本意 tiling 是 OOM 自动降级（声称 8-24 GB "without artifacts"），但本机预检 14.8 GB 可用 / 13.6 GB 需求只留 1.2 GB 余量，偏乐观——50 帧分块两次 OOM 后触发降级。对照实验：非 tiled 处理的测试片段（`output_test_2x_notiled.mp4`，85 帧）抽帧完全无网格。

解决顺序（实测修订，2026-08-23）：

1. **首选：保留 tiled，`--tile_size 256 --tile_overlap 64`**（配 `--frame_chunk_size 50 --keep_models_on_cpu`，即 `E:\FlashVSR\run_flashvsr_best.bat`）。同机 8 帧切片实测：256/64 总耗时 2:58、512/64 为 3:33，两者抽帧均**无网格**。稳定态 0.14 fps（约 7 秒/帧，50 帧 chunk 约 6 分钟），479 帧全片约 55-60 分钟（含模型加载）——速度与旧 128/24（约 7 秒/帧）基本相当但无网格。
2. **不要用 128/24（旧 `run_flashvsr.bat` 的固定参数）**：它是实测唯一出网格的组合（15 个 tile、overlap 过小，接缝融合不足）。
3. **不要把“非 tiled 全帧”当首选**：该路径不会 OOM（预检 5.3 GB 需 / 14.6 GB 可用，chunk 8-16 即可），但本机实测 8 帧跑了 25 分钟、2 帧跑了 8 分钟都未完成（>4 分钟/帧），实际不可用。
4. 仍 OOM：`--unload_dit`；1080p 以上输入加 `--resize_factor 0.5`（净出 2x）。
5. 长片想更省显存：`--mode tiny-long` 替代 `tiny`。
6. 跑完必须校验帧数：`ffprobe -show_entries stream=nb_frames` 应等于输入帧数。实测 `H3CliffV2_FINAL_2x.mp4` 只有 100 帧（输入 479 帧），说明该次运行中途被截断——被截断的输出容易让人误判为“效果差/伪影”，先确认完整再下结论。尺寸/帧率/音频流验证同 Topaz 一节。

### 音频：输出不含音轨（实测）

FlashVSR CLI 的 VideoWriter 只编码视频——输入即使带 AAC 音轨，输出也只有视频流（实测 H3CliffV2 输入 2 声道 AAC，切片输出无音频流）。跑完后用 ffmpeg 从源视频复制音轨（顺序：视频流用 FlashVSR 的、音频流用源的）：

```powershell
& "E:\MiniMax-H3\ComfyUI\ffmpeg.exe" -y -i FLASHVSR_OUT.mp4 -i IN.mp4 `
  -map 0:v -map 1:a:0 -c:v copy -c:a aac -b:a 192k -movflags +faststart FINAL.mp4
```

要求两边帧率一致、时长接近（同源同 fps 超分即满足）；输出被截断（帧数不足）时先重跑，不要给残缺输出配音轨。

## ComfyUI 备选路线（4x-UltraSharp）

权重已就位（本机）：

```text
E:/MiniMax-H3/ComfyUI/models/upscale_models/4x-UltraSharp.pth
字节数: 66,961,958
SHA-256: a5812231fc936b42af08a5edba784195495d303d5b3248c24489ef0c4021fe01
架构: ESRGAN（spandrel 0.4.2 实测加载正常，scale=4）
来源: https://hf-mirror.com/Kim2091/UltraSharp/resolve/main/4x-UltraSharp.pth
      （huggingface.co 直连在本机网络超时；any URL=清单里的远程地址，下载后必须校验上述哈希）
```

注意同目录的 `4xHFA2k.pth` 是 **0 字节** 占位文件——大小≠完整，文件名正确不代表能用；用之前先 `ls -l` 确认字节数并校验哈希，这类文件应替换为完整下载或删除后重新下载。

处理要点（必须在 ComfyUI venv 下运行，`E:/MiniMax-H3/ComfyUI/venv/Scripts/python.exe`，已含 torch 2.13.0+cu130、spandrel 0.4.2、av 18.1）：

1. spandrel `ModelLoader` 加载权重，确认 `scale`（4）；
2. 抽帧（PyAV 解码为 rgb24），先试整帧；1152x640 会被放大到 4608x2560，显存不足就分块：每块约 512x512、重叠 16 像素、边缘羽化再拼接；
3. 输出只编码视频（libx264, yuv420p），音频用 ffmpeg 从原视频复制（参照上面 Topaz cleanupPass 的 `-c:v copy -map 0:v -map 1:a:0 -c:a copy` 写法）；
4. 帧数与 fps 保持不变；写文件后同样用 ffprobe 验证。

如果不想写处理脚本，ComfyUI 内置 `UpscaleModelLoader` + `ImageUpscaleWithModel`（KJNodes 的 `ImageUpscaleWithModelBatched` 会分帧批量、更省显存）也可用，但输入视频需要先拆成帧（VHS 类节点或脚本），不如直接走 venv 脚本一条链。

## 纯 ffmpeg 回退（无权重、预览用）

```powershell
& "E:\MiniMax-H3\ComfyUI\ffmpeg.exe" -y -i IN.mp4 `
  -vf "scale=1920:1080:flags=lanczos,unsharp=5:5:0.8:5:5:0.4" `
  -c:v libx264 -preset medium -crf 18 -c:a copy -movflags +faststart OUT.mp4
```

`scale` 目标先按源比例换算成 2 的倍数（防止拉伸与奇数尺寸），或改用 `-vf scale=-2:1080:flags=lanczos` 让其自动计算宽度。它只缩放+锐化，不改善细节；当临时预览或确认构图时用。

## Sources

- 官方 Real-ESRGAN（备选权重，x4plus 稳定版）: <https://github.com/xinntao/Real-ESRGAN>
- 4x-UltraSharp 权重仓库: <https://huggingface.co/Kim2091/UltraSharp>
- spandrel（模型加载工具）: <https://github.com/chaiNNer-org/spandrel>
- Topaz Video AI（外部 GUI 工具，本机实测路径）: <D:\Program Files\Topaz Labs LLC\Topaz Video\Topaz Video.exe>
