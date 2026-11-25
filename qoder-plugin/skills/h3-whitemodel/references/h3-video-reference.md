# 白模视频 → H3 Ref2VA：实测记录与接线

本文件记录 2026-11-25 本机完整案例：10 秒独角兽玩偶广播体操。它证明灰模视频可直接作为 Ref2VA 参考，也记录了最容易重犯的时间归一化、代理版本和节奏误判。

## 1. 实测结论

- **白模原片可直接喂 Ref2VA**，不要求先转 depth/pose。旧版 skill 的“灰模不能直接喂”结论已作废。
- 白模控制动作、阻断和相机；最终身份、材质、服装由原始角色图负责。
- 10 秒白模审片母版为 24 fps / 1344×768 / 240 帧；给 H3 的是 12 fps / 864×480 / SAR 1:1 / 120 帧 motion proxy。
- H3 请求 244 帧，实际自然补到 260 帧 / 10.833 秒；画面有效，不裁尾、不重投。
- 参考视频是语义条件，不是帧级 motion transfer。H3 会重定时、平滑或合并动作；白模与成片只能做到动作设计相似，不能承诺逐帧一致。

## 2. 本例时间线（含错误路径）

1. v2“强运镜”、v3“强视差”都被用户否定为“没运镜/没啥变化”。机位振幅不等于可读的轨道运动。
2. v4 改成名义 360°，并生成了 H3；但脚本把 `t / 10` 传给内部再次执行 `t / 10` 的 `sample_camera()`，实际只转约 36°。
3. 用户看穿“并没有 360° 环绕”；v5 改为固定半径 5.8、固定高度 2.8、固定焦距 32，匀速 0 s 正面 → 2.5 s 右侧 → 5 s 背面 → 7.5 s 左侧 → 10 s 回正面。
4. 白模原位替换后，**没有重跑 H3**，只把新白模与旧 H3 重新上下拼接。因此当前对比片是“新上段 + 旧下段”，不是同一运动来源。用户随后指出两者节奏不完全一致；这不是播放器问题，而是版本与时间基准不同。
5. 结论：白模修正必须触发 H3 重跑，才能称为同源对比；只拼接必须明确标注近似关系。

## 3. 相机时间 bug 复盘

错误写法：

```python
def sample_camera(t):
    u = min(max(t / 10.0, 0.0), 1.0)   # 内部已归一化
    ...

# 调用端又归一化一次
place_camera(min(max(t / 10.0, 0.0), 1.0))
```

结果：变量名和函数名都像 360°，调试输出也“有轨道”，但 10 秒只走 36°。正确做法是只归一化一次：

```python
def sample_camera(t_seconds):
    u = min(max(t_seconds / 10.0, 0.0), 1.0)
    ...

place_camera(t_seconds)
```

必须做双验收：

- 打印 0%、25%、50%、75%、100% 的相机位置和注视方向；五处应分别在正面、右侧、背面、左侧、正面。
- 抽同样五个时间点做接触表；不看代码、不看变量名，只看画面是否出现侧面、背面和回正。
- 首尾画面接近不代表完整环绕；36° 短弧的首尾也可能接近。要看中途是否真的绕到背面。

## 4. motion proxy 规格

| 项 | 值 |
| --- | --- |
| 审片母版 | 24 fps、1344×768、240 帧、10.000 s、无音频 |
| H3 proxy | 12 fps、864×480、120 帧、SAR 1:1、无音频 |
| H3 画布 | 1344×768 |
| 请求帧数 | 244 |
| 实际输出 | 260 帧、24 fps、10.833 s |
| 路线 | Set C Ref2VA、4 步、`res_multistep` + `simple`、Pika H3 Flex Turbo LoRA |

```bash
python scripts/make_motion_proxy.py \
  --input white_model_full.mp4 \
  --output project/white_model_motionproxy_12fps_864_sar1.mp4
```

不要用审片母版直接占 GPU 解码；proxy 是为了让 H3 只取运动与构图。proxy 必须从**当前版**白模生成，记录源文件与 proxy 的 SHA-256。

## 5. Ref2VA 接线

自定义 Set C Ref2VA API 图中最小结构：

```json
"18": {
  "class_type": "LoadVideo",
  "inputs": {"file": "white_model_motionproxy_12fps_864_sar1.mp4"}
},
"19": {
  "class_type": "GetVideoComponents",
  "inputs": {"video": ["18", 0]}
},
"6": {
  "class_type": "MiniMaxH3ReferenceToVideo",
  "inputs": {
    "length": 244,
    "height": 768,
    "ref_image_size": "match",
    "ref_videos.ref_video_0": ["19", 0]
  }
}
```

- 代理文件名必须写在 ComfyUI `input/` 目录内，`LoadVideo.file` 只放文件名，不放绝对路径。
- 角色图仍绑定 `ref_image_0`；不要把白模截帧当角色身份图。
- 参考视频不要带音轨。若要音色参考，走 `ref_audios`；不要把“续接视频音轨”和“独立音色参考”混接。
- 提交前在 API JSON 里确认 `ref_videos.ref_video_0` 指向 `GetVideoComponents` 的 `images` 输出，而不是原视频对象。

## 6. 提示词写法

视频参考不会替模型理解动作。提示词仍要写完整：

- 写清动作时间线、开始状态、每个主要事件、完成态。
- 写清相机路径；360° 环绕必须写出正面、侧面、背面、回正的顺序。
- 明确视频参考职责：动作、阻断、相机、接触点；明确禁止复制灰模材质、球关节、空场景。
- 角色外观只绑定原始角色图；动作段不复述外貌，避免每帧重新解释身份。
- 不把“参考视频已有”当成省略动作和相机的理由。
- 不要在提示词里承诺“帧级复刻”；模型并不按逐帧对齐生成。

## 7. 时间基准与节奏

白模 240 帧 / 10.000 秒，H3 260 帧 / 10.833 秒：

- 两端完全对齐时，H3 比白模多约 0.833 秒；即使同源，动作节拍也可能被模型重新分配。
- 上下对比为对齐长度会把白模末 20 帧冻结；最后约 0.833 秒只让下段继续运动。
- 旧 H3 新白模混拼时，运动来源不同，节奏差异会在转向、落脚和停顿处放大。
- 用户要求严格同步时，先说明 Ref2VA 边界，再选择重生成、统一时间基准或单独时间重映射；不要靠加 `setpts` 假装同源。

## 8. 上下拼接与 QA

拼接命令（上段白模、下段 H3）：

```bash
ffmpeg -n \
  -i white_model_full.mp4 -i h3_final.mp4 \
  -filter_complex "[0:v]tpad=stop_mode=clone:stop=20,scale=1344:768:flags=lanczos,setsar=1[top];[1:v]scale=1344:768:flags=lanczos,setsar=1[bottom];[top][bottom]vstack=inputs=2:shortest=1[outv]" \
  -map "[outv]" -map 1:a:0 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -r 24 -frames:v 260 -c:a copy -movflags +faststart stacked.mp4
```

QA 脚本：

```bash
python scripts/qa_reference_stack.py \
  --stack stacked.mp4 \
  --reference current_white.mp4 \
  --old-reference old_white.mp4 \
  --h3 h3_final.mp4 \
  --out-json stacked_qa.json \
  --contact-sheet stacked_contact.jpg
```

本例实测：

| 指标 | 数值 | 含义 |
| --- | --- | --- |
| 上段 vs 当前白模 MAE | 0.2073 | 接近重编码噪声，来源匹配 |
| 上段 vs 旧白模 MAE | 15.2775 | 旧版明显不同 |
| 下段 vs H3 MAE | 0.7777 | 下段来源匹配 |
| 上段 mean MAD | 2.4791 | 有运动 |
| 上段近静止比例 | 0 | 无冻结 |
| 下段 mean MAD | 14.5329 | 明显运动 |
| 上段末 20 帧 MAD | 0.0118 | 只有补齐尾帧停住 |
| 下段末 20 帧 MAD | 10.8736 | 下段继续运动 |

## 9. 交付检查

- 上段、下段、对比片、封面各自有 SHA-256。
- 对比片音轨从 H3 复制，不二次 loudnorm；若截断在视频尾帧，记录共同窗口的 decoded MD5，不拿整条容器 MD5 误判不同源。
- 交付路径、规格、机位接触表、最终 SHA 一并报告。
- 若上段是修正版、下段是旧 H3，必须在交付说明里写清；不能把它描述成同源同步。

## 10. 已知边界

- 12 fps proxy 是本机验证可跑的输入，不是官方帧率承诺；官方输入上限仍按 `ref_videos` 2–15 s、总时长约束执行。
- 灰模直接喂养可行，不代表所有风格都能稳定；强风格化时仍以提示词和角色图为主。
- H3 的自然补帧、重定时和动作合并属于模型行为，不是白模导出错误。
- 白模只能保证参考本身正确；它不能保证 H3 身份、口型、手部或画面质量。身份与成片验收仍在 `h3-generate` / `h3-post`。
