# 双角色视频复刻：Preprocessor Map + Regional

适用于“保留原片场景、构图、机位和表演轨迹，同时替换两位角色”的任务。该路线不是背景像素级锁定，也不保证逐帧复刻；必须通过身份、配饰、动作和持续双人可见门禁。

## 路线合同

- 使用 Character Swap Preprocessor Map LoRA、DWPose guide、SAM subject map 与 `BFSH3RegionalReferenceAttention`。
- guide 中源人物被擦成灰色，只保留彩色骨架；骨架颜色只标识表演轨道，不表示目标服装颜色。
- 双角色默认绑定：
  - Subject 1 / 红色骨架 / Picture 1
  - Subject 2 / 蓝色骨架 / Picture 2
- Picture 顺序必须与提示词和 `BFSH3KeyframeConditioning` 的 `picture_1/picture_2` 一致。
- 身份图只负责脸、发型、体型、服装和配饰；guide/map 只负责姿态、表情、运动、构图和镜头。
- 原演员脸、历史发型和服装不能进入目标 cast；背景群众保持匿名。

提示词必须逐帧锁定两位主角、各自表演轨道和最终双人可见，即使后段 subject map 已丢失。不要写成“每帧都有两个非空 mask”。

## BFSNodes 颜色合同

`HYBRID_COLORS_RGB`：

```python
[
    (235, 40, 40), (35, 110, 235), (60, 205, 60),
    (240, 205, 30), (220, 50, 220), (30, 205, 225),
]
```

双角色 map 只允许前两色。纯 `(255,0,0)` / `(0,0,255)` 可能通不过 0.1 色距门禁，导致跟踪伪主体和骨架残留。

检测口径：

```python
rgb = frame.astype(np.float32) / 255.0
distance = np.max(np.abs(rgb - np.asarray(color) / 255.0), axis=-1)
mask = distance < 0.1
```

重采样 map 使用 nearest-neighbor，不能用 Lanczos/bicubic 混合颜色。校验时必须逐帧比较检测色序列，而不是只比较文件大小或首帧。

后段真实 mask 消失是已接受输入的真实情况。此时双人持续可见依赖未改动的 prompt + Regional `tracking=propagate`；不能要求每帧两个 mask 都非空，否则会拒绝接受源本身。

## 工作流最小变更

从已验收工作流克隆，只允许修改输入文件、输出几何和文件名节点。提示词、参考图、seed、步数、sampler、scheduler、VAE 和 Regional 参数保持不变。

```bash
python scripts/h3_prepare_regional_workflow.py \
  --base accepted_workflow.json \
  --plan regional_plan.json \
  --output candidate_workflow.json \
  --report qa/regional_workflow_validation.json
```

plan 至少声明：

```json
{
  "allow_changed_nodes": ["9", "11", "21", "23"],
  "set": {
    "9": {"inputs": {"file": "guide.mp4"}},
    "11": {"inputs": {"output_scale": 2.0, "max_megapixels": 1.1}},
    "21": {"inputs": {"filename_prefix": "community_tests/remake_v24"}},
    "23": {"inputs": {"file": "subject_map.mp4"}}
  },
  "require_classes": {"25": "BFSH3RegionalReferenceAttention"},
  "require_values": {
    "25.inputs.routing": "soft",
    "25.inputs.tracking": "propagate",
    "25.inputs.isolation": "people"
  },
  "require_links": {
    "25.inputs.guide": ["10", 0],
    "25.inputs.subject_map": ["24", 0]
  },
  "geometry": {
    "source_width": 672,
    "source_height": 384,
    "output_scale": 2.0,
    "max_megapixels": 1.1,
    "expected_width": 1344,
    "expected_height": 768
  }
}
```

脚本必须报告实际 changed nodes；任何额外节点变化都失败。不要用“看起来只改了一点”替代图级 diff。

## Subject map 校验

```bash
python scripts/h3_validate_subject_map.py \
  --map subject_map.mp4 \
  --reference accepted_subject_map.mp4 \
  --guide guide.mp4 \
  --allowed-colors 0,1 \
  --json qa/subject_map_validation.json
```

门禁：

- 只出现允许的 hybrid 色；额外颜色失败。
- 每个允许的角色色至少在一帧中出现；双角色图不能从头到尾只有一种主体色。
- 与接受源的逐帧检测色序列完全一致。
- guide/map 的帧数、fps 和时长一致。
- 后段空 mask 或单主体 mask 只有在接受源也如此时才通过；没有 `--reference` 时，空 mask 直接失败。
- 校验结果记录每帧颜色与像素计数，便于区分“真实主体消失”和“调色/压缩污染”。

## Regional 接线

`routing="soft"` 不是充分条件。soft bias 必须同时接 `guide` 与 `subject_map`；否则仍可能按 hard-mask 规划。

预期日志：

```text
attention tracking from subject_map seeds, routing: soft, isolation: people
tracked 2 subjects at layer 12
```

`bias_start/bias_end=24` 是速度优化，不构成显存安全证据。`BFSH3RegionalReferenceAttention` 与 `BFSMiniMaxH3NativeTemporal` 的 optimized attention override 明确冲突；不要组合 TARA 原生 temporal 节点。

## 分辨率与帧数门禁

- 24 fps；H3 合法帧数满足 `n % 17 == 5`。
- 先低清验证内容，再按 768×416 → 960×544 → 1344×768 阶梯升级。
- 每次只改几何和输入资产，保留同一 prompt、参考、seed、采样和 Regional 参数。
- 升分辨率前必须通过：身份、服装/配饰隔离、双人持续可见、动作/blocking、最终构图。
- 生产画布通过后仍要单独验显存、运行时、网格和全分辨率关键帧。
- 技术 PASS ≠ 内容 PASS；低清正脸 PASS ≠ 生产分辨率正脸 PASS。

## 验收证据

至少保留：

- 完整解码与 ffprobe；
- source / guide / map / output 接触表；
- A/B 各自 crop；
- 转身、停步、靠近段；
- 尾段持续双人与负空间；
- 全分辨率首/中/尾帧；
- 显存采样与 allocator 警告分类；
- 工作流 changed-node 报告和输入 SHA。

如果某角色始终背向/侧向，正脸和眼镜必须标为 `not exercised`，不能外推为生产分辨率验收。

## 一手来源

- https://huggingface.co/Alissonerdx/Minimax-H3-ComfyUI/blob/main/docs/character-swap-preprocessor-map.md
- https://github.com/alisson-anjos/ComfyUI-BFSNodes
- https://github.com/alisson-anjos/ComfyUI-BFSNodes/blob/main/H3_REFERENCE_BINDING.md
