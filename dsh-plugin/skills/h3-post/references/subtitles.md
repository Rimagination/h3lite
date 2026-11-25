# 字幕：样式、对齐与烧录

用户当前审美（当次明确要求优先）：

- 纯白、衬线优先、字号偏大；不要彩色、渐变、阴影、装饰线或色块。
- 双语：日语在上、字号略小；中文在下、字号更大。
- 去标点：句末和句中不出现 `。，！？、；：` 等；需要停顿用换行或空格。
- 一行一个语义单元；最多两行；每条不短于 0.4 s。

## 对齐

- 时间轴按**实测语音**，不按字数估算。
- 有本地转写工具（faster-whisper 等）时用词级时间戳；没有就按波形与试听手工对齐。
- 一句一条；台词跨镜时按镜头切分成多条，不要一条横跨两个镜头。
- 字幕起点略早于语音 0.1–0.2 s，终点略晚 0.2–0.4 s；不要盖住下一句。
- 日语与中文两轨共用同一时间码，逐句对齐。

## ASS 模板（竖屏 768×1344）

```ini
[Script Info]
ScriptType: v4.00+
PlayResX: 768
PlayResY: 1344
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: BIL,STZhongsong,48,&H00FFFFFF,&H000000FF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,1.5,0,2,40,40,185,134

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.42,0:00:01.90,BIL,,0,0,0,,{\fnSTZhongsong\fs34}裁定は{\r}\N裁决
Dialogue: 0,0:00:02.10,0:00:03.40,BIL,,0,0,0,,{\fnSTZhongsong\fs34}コインに任せる{\r}\N交给这枚硬币
```

要点：

- 同一事件里：日语行 `\fs34`，`\r` 恢复主样式，`\N` 换行，中文行用默认 48。
- 字体按本机可用替换：`STZhongsong`（华文中宋）、`Noto Serif CJK SC`、`SimSun`；找不到就用其他衬线字体，不要用彩色艺术字。
- 描边只用于亮背景可读性（1–2 px 中性深色）；不要彩色描边、外发光、投影。
- 旁白可用独立样式放左上（`\an7\pos(...)`），但不要与对白字幕抢位置。
- 1080×1920 交付时把 PlayRes 改为 1080×1920，字号与边距按比例放大（约 ×1.4）。

## 烧录

```bash
ffmpeg -i final.mp4 -vf "ass=subs.ass" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a copy out_captioned.mp4
```

- 路径含空格/中文时用正斜杠并整体加引号；必要时加 `fontsdir=...`。
- 只烧字幕时音频 `-c:a copy`，不要二次编码。
- 需要软字幕时改用 `-c:s mov_text` 输出 MP4，或按用户要求给 SRT。

## 验证

1. 抽每条字幕的首/中/末帧，确认无截断、无重叠、无出屏；
2. 全片看一遍，核对措辞、语言、标点与同步；
3. 确认字幕没有盖住关键表情或动作；
4. 重验成片时长、音轨与可播放性；
5. 对齐失败不得当作成功字幕交付。
