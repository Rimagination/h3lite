# 多镜拼接

## 先判断是否需要拼接

如果一条 H3 生成已经包含 3–4 个镜头，不要为了“后期规范”再拆开逐镜处理；直接整条视频 copy、一次 loudnorm、字幕/交付。拼接只用于超过 4 拍、需要不同参考/路线、单镜台词过长，或同一条生成连续两次都形成不了新构图的情况。

必须拼接时，先把每镜用 ffprobe 量一遍：分辨率、帧率、像素格式、视频/音频流、时长。不一致先统一，再拼。

## 切点先服从情绪与故事

优先顺序按 Murch Rule of Six：Emotion > Story > Rhythm > Eye-trace > 2D plane > 3D space。技术连续性（180°、30°、动作匹配）是最后一道，不是第一道；不要为了完美轴线牺牲一个真实反应。切在动作中段、听完/说完之后；J/L cut、match cut 与 sound bridge 见 [`professional-edit-sound.md`](professional-edit-sound.md)。

## 避免割裂的拼接规则

1. **首尾帧链**：上一镜的真实尾帧直接作为下一镜首帧（FL2VA），切在动作中段，不要切在收势。
2. **动作/视线切**：硬切落在动作中段、视线转移或声音先入处；不要连续同景别同机位。
3. **连续底床**：全片铺一条连续的雨声/房间 tone/BGM；接缝处交叉淡化 20–50 ms，不要每镜重启环境声。
4. **J/L cut**：下一镜声音提前 2–4 帧进，或上一镜声音延后 2–4 帧出，接缝更自然。
5. **整条 loudnorm**：先拼再归一，禁止逐镜 loudnorm；逐镜增益会把安静段抬高几十 dB，产生抽气感。
6. **不为帧数硬裁**：每镜保留自然帧数，拼接偏移按真实时长算。

## 硬切（快切短剧默认）

`list.txt`：

```text
file 'shot01.mp4'
file 'shot02.mp4'
file 'shot03.mp4'
```

```bash
ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4
```

- 路径含空格/中文时用单引号，并确保列表文件是 UTF-8。
- `-c copy` 报 DTS/参数不一致时，改为重编码：

```bash
ffmpeg -f concat -safe 0 -i list.txt \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k out.mp4
```

## 叠化

`xfade` 视频 + `acrossfade` 音频，偏移按累计公式：

```text
offset_1 = d1 - T
offset_k = offset_{k-1} + d_k - T
```

示例（3 段各 3.042 s，T=0.3，偏移 2.742 / 5.484）：

```bash
ffmpeg -i s1.mp4 -i s2.mp4 -i s3.mp4 -filter_complex "
[0:v][1:v]xfade=transition=fade:duration=0.3:offset=2.742[v01];
[v01][2:v]xfade=transition=fade:duration=0.3:offset=5.484[v];
[0:a][1:a]acrossfade=d=0.3[a01];
[a01][2:a]acrossfade=d=0.3[a]" \
-map "[v]" -map "[a]" -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac out.mp4
```

- `transition` 名称以本机 ffmpeg 为准：先 `ffmpeg -h filter=xfade`。`smoothstep` 不可用时用 `fade`，不要因一个名字失败就放弃叠化。
- 所有段必须有音频流才能 `acrossfade`；缺音频先补静音轨或改硬切。
- 叠化会缩短总时长 `(段数-1)×T`，交付时长要按缩短后的值报告。

## 不硬修时长

- 73 帧 = 3.042 s，124 帧 = 5.167 s，244 帧参数的 Set C FL2VA 实测 260 帧 / 10.833 s；不要为凑整裁尾帧，也不要因自然补帧重跑。
- 拼接偏移用每镜真实时长计算。
- 需要整秒交付时，调镜头数量或在片头片尾留黑，不逐镜硬裁。
- 多镜之间 1–2 帧的节奏呼吸可以保留。

## 顺序与连续性检查

1. 镜头顺序与分镜表一致；
2. 相邻镜景别/机位有变化；
3. 动作跨镜连续时，接缝落在动作中段而不是收势；
4. 角色服装、光位、天气在接缝两侧一致；
5. 音频接缝没有爆音/断拍；必要时在切点加 2–5 ms 淡入淡出，但不要用静音补洞；
6. 单次多镜只核对请求切点 ±0.5 s，不做全片阈值扫；某个切点变成连续运镜但仍有新构图，按视觉段验收。

## 常见失败

| 症状 | 原因 | 处理 |
|---|---|---|
| 拼接后音画不同步 | 某些段 VFR/时间戳异常 | 逐段转 CFR 后重拼 |
| 总时长少了几帧 | xfade 重叠扣除了时长 | 按公式重算偏移，或改硬切 |
| 接缝闪黑 | 段首/段尾黑帧 | 裁掉黑帧或改叠化 |
| 声音在接缝爆音 | 波形不连续 | 切点加短淡入淡出 |
| `-c copy` 失败 | 编码参数/时基不一致 | 重编码 |
| 中文字幕文件名乱码 | 列表编码非 UTF-8 | 转 UTF-8 |

## 验证

```bash
ffprobe -v error -show_entries format=duration -show_entries stream=codec_type,width,height,r_frame_rate -of default=nw=1 out.mp4
```

再抽首/中/末帧与每个接缝前后各一帧，确认没有黑帧、花屏、错序。
