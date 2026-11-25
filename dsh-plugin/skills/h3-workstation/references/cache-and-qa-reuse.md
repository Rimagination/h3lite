# 缓存与 QA 复用

原则：**缓存的是“可复算的报告”，不是“任务状态”。** 队列、GPU 占用、文件是否存在、模型哈希漂移都必须重新查；只有输入指纹相同、TTL 内的静态结果才复用。

## 已经内置的复用

- **参考图/音频/视频 staging**：`h3_generate.py` 按 sha256 命名 staged 副本；同一文件不重复拷贝，目标已存在但哈希不同会报错。
- **showrunner 续跑**：`show_manifest.json` 记录 `submitted/completed/failed`；`--resume` 跳过已完成、继续已提交未验证的镜头。
- **run manifest**：每镜的提示词、配置、参考、timing、输出都落盘；`h3_status.py` 可按 prompt_id 找回。
- **doctor 报告**：文档约定 30 分钟内复用；环境/模型变化后必须重跑。
- **preflight**：只在环境、模型、画布、组件集变化时刷新；不要每镜重跑医生。

## 新增工具：`h3_cache.py`

只做三件事：文件指纹、显式 key 的 JSON 缓存、缓存命令的成功输出。

```powershell
# 文件指纹（默认 size+mtime；--sha 会读文件）
python scripts/h3_cache.py fingerprint E:/MiniMax-H3/ComfyUI/output/video/shot01.mp4 --sha

# 缓存一份报告 30 分钟
python scripts/h3_cache.py put --cache-dir <ComfyUI>/user/h3lite_runs/_cache `
  --key doctor:20261125 --payload-file doctor.json --ttl 1800

# 读取（未命中/过期返回非 0）
python scripts/h3_cache.py get --cache-dir <ComfyUI>/user/h3lite_runs/_cache --key doctor:20261125

# 缓存命令成功输出：命中时直接回放 stdout/stderr
python scripts/h3_cache.py run --cache-dir <ComfyUI>/user/h3lite_runs/_cache `
  --key doctor:20261125 --ttl 1800 -- python scripts/h3_doctor.py --json

# 清理过期/过旧条目
python scripts/h3_cache.py prune --cache-dir <ComfyUI>/user/h3lite_runs/_cache --older-than-days 14
```

## key 设计

- doctor / preflight：`doctor:<环境指纹>` / `preflight:<环境指纹>:<画布>:<组件集>`；环境指纹至少包含 GPU、驱动、ComfyUI 版本、节点 commit、模型文件大小/mtime。
- 参考 staging：直接用 sha256，不用 TTL。
- 单镜 QA：`qa:<输出文件指纹>:<请求帧数>:<fps>:<require_audio>:<dynamic_check>`；文件指纹用 path+bytes+mtime_ns，必要时再加 sha256。
- 拼接/对比 QA：`stack:<stack指纹>:<reference指纹>:<h3指纹>`。

## 不该缓存

- `/queue`、`/history` 的运行状态、GPU 功耗/占用、显存；
- 文件是否存在、模型是否被替换；
- 失败结果（除非 key 明确包含错误指纹且 TTL 很短）；
- 用户还没验收的内容质量结论。技术 QA 可缓存，身份/画风/剧情必须人看。

## 失败与失效

- 缓存 JSON 损坏：当 miss 处理，重算覆盖。
- 输出文件 mtime/size 变了：key 变化，自然 miss。
- 模型/节点/驱动变了：环境指纹变化，doctor/preflight 必须重跑。
- 不要把缓存当成“已验证”的证明；它只证明“同样的输入上次算过这个结果”。
