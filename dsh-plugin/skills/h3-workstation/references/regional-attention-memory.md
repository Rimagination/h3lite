# Regional Attention 显存与运行时诊断

适用于 BFSNodes `BFSH3RegionalReferenceAttention`、双角色 subject map、guide-connected soft bias 和 107 帧级诊断。结论来自本机 RTX 4060 Ti 16 GB / W4A8 Ref2VA / 4B TE / fp16 VAE 路线；其他硬件和模型组合必须重新实测。

## 有效与无效优化

- `--reserve-vram 3.0` 是当前唯一材料级优化：强制更多权重页换出，降低采样峰值。
- `--reserve-vram 1.5` 只降低约 16 MiB，不应作为解决方案。
- `output_scale=0.92` 不能实质降低采样峰值。
- `bias_start/bias_end=24` 只缩短偏置窗口，不是显存安全证据。
- `--normalvram` 未定义；`--lowvram` 不禁用 DynamicVRAM，也不解决该图。
- `--cpu-vae` 只移动 VAE 执行，不降低采样激活。
- `--disable-smart-memory` 不是已验证的内容安全路线。

## 不要推荐伪分块

- 原生 `VAEDecodeTiled` 对 H3 不能按参数真正分块；`MiniMaxH3VideoVAE.decode_tiled()` 忽略参数并调用普通 `decode()`。
- H3 已使用内部 256 像素空间 tile、17 帧时间块和 CPU-resident output。
- `MiniMaxH3VAELoaderTiled` 存在，但质量未验证，也不能解决采样峰值。
- `MiniMaxH3ContextWindows` 与 Regional override 不安全。
- Sol/block-sparse kernel 会绕过 Regional routing；BFS temporal alignment 会拒绝 Regional override / Add Guide 布局。

## 测量口径

跨运行比较必须使用同一指标：

- NVIDIA 峰值：`nvidia_used_peak_mib`，不要混用 `system_stats_used_peak_mib`。
- generation-window 最低空闲：按 execution_start / execution_success 时间窗过滤。
- RAM 最低空闲、GPU utilization、power、elapsed reset count 同时记录。
- 运行时以 ComfyUI history 的 execution 时间戳为准。
- allocator 警告记录请求字节、当时 free/total 和是否恢复。

## Allocator OOM 警告分类

单次 `memory allocation failed with OOM` 不等于终态失败。按以下顺序判断：

1. `/queue` 是否仍有同一 prompt_id 在运行；
2. GPU 是否维持高利用和健康功耗；
3. 采样步数是否继续推进；
4. 最终是否出现 execution_success、VAE decode 和 SaveVideo；
5. 输出是否存在、SHA 和 ffprobe 是否通过。

若上述全部成立，归类为 `recovered_allocator_warning`，不要重复提交或重启。若队列消失、GPU 掉到死锁带或 history 报错，再按失败处理。

## 分辨率阶梯的解读

本机 107 帧 Regional 实测：

| 画布 | latent grid | 空间 token | NVIDIA peak | generation-window 最低空闲 | 耗时 |
|---|---:|---:|---:|---:|---:|
| 640×352 | 20×11 | 220 | 14460 MiB | 2114.347 MiB | 200.281 s |
| 768×416 | 24×13 | 312 | 14478 MiB | 2752.082 MiB | 290.297 s |
| 960×544 | 30×17 | 510 | 14600 MiB | 6761.894 MiB | 600.485 s |
| 1344×768 | 42×24 | 1008 | 14495 MiB | 4127.882 MiB | 1780.844 s |

1344×768 比 960×544 多 97.647% 空间 token，但峰值低 105 MiB，耗时增加 196.568%。这说明该路线升分辨率的主要成本已是时间，而不是 NVIDIA peak；不要把单次峰值外推为所有负载的安全保证。

## 报告字段

每次诊断至少输出：

```json
{
  "status": "completed",
  "canvas": [1344, 768],
  "frames": 107,
  "spatial_tokens": 1008,
  "nvidia_used_peak_mib": 14495.0,
  "generation_window_free_min_mib": 4127.882,
  "ram_free_min_mib": 5768.184,
  "elapsed_seconds": 1780.844,
  "allocator_warning": {
    "fatal": false,
    "resolution": "recovered during model initialization"
  },
  "content_acceptance": "passed_with_scope_limitation"
}
```
