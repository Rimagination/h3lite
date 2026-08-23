# GPU memory contention with other heavy CUDA apps

同机共存多个重 CUDA 负载时（ComfyUI 之外还有独立视频工具、游戏串流、另一个生成后端），显存争用会以“假空闲”的形式出现：`nvidia-smi` 总量显示还有 14 GB 可用，CUDA 却连几十 MiB 的分配都失败，或者直接访问违例崩溃而不是报 Out of Memory。这份说明给出根因、诊断命令和处理顺序，包含 2026-08-23 在 RTX 4060 Ti 16 GB 上测得的完整案例。

## 现象与根因

- **进程级显存读数不可信。** 在新版 Windows WDDM 驱动上，`nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory` 对每个进程返回 N/A（或列出 0 MiB），无法据此找到“谁占着显存”。
- **PyTorch 的 free 值虚高。** CUDA 在 WDDM 下看到的是全局可用显存的乐观估计，而不是扣除其他进程实际占用后的余量。于是错误信息里写着 `8.91 GiB free`，实际分配 432 MiB / 28 MiB 就失败。
- **两种失败形态：** 干净的 `CUDA out of memory`，或 Windows 访问违例（如 Topaz Video AI 进程退出码 `-1073741819`，即 `0xC0000005`）。后者没有 OOM 字样，单看日志极易误判为驱动/模型问题。
- **常见元凶：** ComfyUI 在队列清空后仍把模型常驻显存（本次实测 9,805 MB）；游戏串流/加速器服务、另一个 `python.exe` 后端同理。

## 诊断命令

```powershell
# 1) GPU 总量 + 每个进程的真实专用显存（读 WDDM 计数器，含回退）
python scripts/h3_vram.py --json

# 2) 作为门禁：空闲显存低于阈值时退出码为 1
python scripts/h3_vram.py --check-free-gb 5; echo $LASTEXITCODE
```

`h3_vram.py` 通过一次 PowerShell 调用读取 `\GPU Process Memory(*)\Dedicated Usage` 计数器（注意 `Get-Counter` 必须带前导反斜杠，否则报 “The specified counter path could not be interpreted”），按 PID 汇总后与 `nvidia-smi` 总量配对输出。计数器不可用时回退到 `--query-compute-apps`。

核对竞态方是否真的空闲：ComfyUI 检查自己的队列：

```powershell
Invoke-RestMethod http://127.0.0.1:8188/queue | ConvertTo-Json | Select-String -Pattern '"queue_running"|"queue_pending"'
```

队列清空不等于模型已释放：空队列也要看 `h3_vram.py` 里那个 python 进程的占用，常驻模型需要重启 ComfyUI（或重新排队触发卸载）才会释放。

## 处理顺序

1. 跑 `h3_vram.py --json`，确认占用者的 PID、进程名和 MB。
2. 确认竞态方空闲：没有正在运行/排队中的任务；需要的话先等它的任务完成。
3. 释放显存：正常退出，或
   `python scripts/h3_vram.py --stop <pid>`（破坏性操作；禁止用于仍有排队或运行中任务的 ComfyUI）。
4. 重跑被阻塞的任务；成功后按需重启之前的 CUDA 程序（H3 生成时 ComfyUI 本身就是宿主，不需要重启自己）。
5. 如果争用经常发生：给常驻方上资源限制（如 ComfyUI `--lowvram`），或在脚本里先 `--check-free-gb` 再提交。

## 实测案例（2026-08-23，RTX 4060 Ti 16 GB，驱动 610.88）

ComfyUI 后端（`python.exe main.py --listen 127.0.0.1 --port 8188`）在**空队列**下常驻显存 9,805 MB；同一个 16 GB 显卡上 Topaz Video AI 导出星光 Starlight Fast 2 模型时：

- 模型初始化已进入 `<16GB VRAM Mode: Minimal settings`（temporal_chunk_size 45/25、kv_ratio 0、topk_ratio 1.4、batch_size 21），主 state_dict 加载成功；
- 加载 VAE 解码器 `.to(cuda)` 时失败：日志“Tried to allocate 28.00 MiB … 8.91 GiB free”，同时 `nvidia-smi` 显示 11.6 GB 已用 / 4.5 GB 空闲；
- 前台导出表现为 CUDA OOM，后台单次运行（neuroserver `--max-gpu-mem 9`）表现为退出码 `0xC0000005` 访问违例。

处理：确认 `http://127.0.0.1:8188/queue` 为空后停止该 python 进程 → 显存 11.6 GB 用到 1.7 GB（14.4 GB 空闲）→ 导出越过 VAE 加载阶段。修复后的实测：20:09 的 1.125x 导出（命令记录 1296x720；实际文件编码 1280x720、显示 1280x710，209 帧全部导出，音频完整）约 4.5 分钟成功完成；20:14 的 2x 导出（2304x1280，209 帧）正常推进至第 122 帧的 Tiled Decode 后完整写完 `__slf_1.mp4`（34,876,728 字节，20:27 落盘），未再出现 OOM 或 0xC0000005 崩溃。诊断期间 `nvidia-smi --query-compute-apps` 对全部进程显示 N/A，唯一可靠的是 WDDM 计数器。

## 附录：本次同机的 Topaz Video AI 修复记录

同类问题的一部分来自程序自身，记录如下以供复用（与 H3 无关，属通用“修复重 CUDA 应用”经验）：

- **模型反复下载/卡在 “Finalizing model download…”：** Windows 区域为 zh-CN 时国际化资源缺失，QML 缓存按中文重新生成后版本检查失败。修复：临时切到 en-US 区域，删除 `%AppData%\Topaz Labs LLC\Topaz Video\qmlcache` 及其 qml/本机缓存文件，重启应用生成英文缓存后再恢复区域设置。
- **显存上限：** 应用内最大内存使用率由 100% 调为 60%（导出命令行实测收到 `--max-gpu-mem 9`）。注意：该设置由 Topaz UI/配置传递，`HKCU\Software\Topaz Labs LLC\Topaz Video` 下并不存在 `maxMemoryUsage` 键，不要按注册表键名去找它。环境变量 `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`（仅对 PyTorch 用户进程有效）。
- **模型包完整性：** `C:\ProgramData\Topaz Labs LLC\Topaz Video\models\astrafast.json` 的 `validate_install.windows.model.zipHash`（SHA-512）与本地 `astrafast-1.0.zip`（6,439,256,676 字节，4 个 blob）比对，下载恢复后校验通过，目录校验 `numFiles: 4`。
- **“修复程序没关干净”：** 部分进程为 UWP/后台驻留，需任务管理器或 `taskkill` 全部 `Topaz Video*`/`neuroserver*` 进程后再运行修复程序。
