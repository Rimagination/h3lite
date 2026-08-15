# Official MiniMax H3 insights distilled for h3lite

This is an operational distillation of the official H3 repository, its base
and full-reference prompt guides, and the official reproducible examples. It
keeps the rules that improve prompt reliability without copying the entire
documentation set.

## 1. Think like Context-IR, even on the local route

The official system separates context understanding from video generation. Its
Context-IR stage resolves instruction parsing, cross-modal relationships,
temporal structure, and logical constraints before H3-Base generates the
audio-video result.

The local W4A8/ClipProj route does not automatically provide that official
preprocessing stage. Before writing the final prompt, emulate the useful part:

1. Identify the task type: text generation, keyframe completion, reference
   generation, video editing, video continuation, audio reuse, or audio
   reference.
2. Name every reusable subject and every concrete frame or media anchor.
3. Decide what must remain unchanged, what may change, and what is merely a
   style or voice reference.
4. Build the timeline only after identities, reference roles, and timing are
   unambiguous.
5. Put visible actions, reactions, dialogue, and diegetic sounds in playback
   order; keep ambience and audience-only music in their dedicated fields.

Do not mistake a longer prompt for better context. Every sentence should bind
an identity, a spatial relationship, a state change, a sound event, or a
reference constraint.

## 2. Base-mode anchors are strict

Use the mode that matches the supplied media:

| User input | Mode | High-value rule |
| --- | --- | --- |
| Text only | `T2VA` | Construct the complete audiovisual timeline from the opening state. |
| One first-frame image | `I2VA` | Anchor `<Picture 1>` at `0.00`, preserve its identity and composition, then develop forward. |
| First and last images | `FL2VA` | Describe the continuous physical path between the two states; a single shot is usually more reliable. |
| One last-frame image | `L2VA` | Infer a plausible earlier state and converge on the supplied image at the final timestamp. |
| Images/video/audio references | `Ref2VA` | Define reference roles and retention before writing the shot timeline. |

For `I2VA`, do not describe the first image as a loose inspiration. It is the
actual first frame. For `FL2VA`, do not repeat two static image descriptions;
describe the observable intermediate changes. For `L2VA`, the supplied image
belongs to the final shot, not automatically to Shot 1.

## 3. Full-reference labels prevent semantic drift

Use one stable label for each role throughout the prompt:

```text
<Subject 1>  reusable person, object, environment, style, action, or pose
<Picture 1>  concrete image/keyframe or storyboard anchor
<Video 1>    source video, continuation source, or temporal structure
<Audio 1>    copied or referenced audio signal
```

The same asset can provide multiple roles, but the labels remain independently
numbered. A video that only supplies camera movement or rhythm is normally a
`reference generation` input, not automatically `video editing`. An audio
track inside a reference video is not automatically an `<Audio N>` input.
Define it separately only when it is copied or referenced.

Use a short task prefix in `summary` when working in full-reference mode, for
example:

```text
[video editing + audio reference + audio reuse] ...
```

## 4. Retention is explicit, not implied

For visible references (`<Subject N>`, `<Picture N>`, `<Video N>`), use the
official relationship vocabulary when the workflow accepts the full-reference
schema:

- `fully_preserved`: the defined role remains intact;
- `partially_preserved`: some defined characteristics change;
- `attribute_transfer`: a characteristic moves to another identifiable subject;
- `weak_reference`: only broad style, category, composition, or atmosphere is retained.

For audio references, distinguish:

- `fully_copy`: the complete source signal becomes the final track;
- `partially_copy`: selected audio layers or timeline segments are reused;
- `reference`: only timbre, rhythm, music style, dialogue, lyric content, or
  sound texture is followed;
- `weak_reference`: only broad audio similarity remains.

This distinction is especially valuable for cinematic dialogue: a voice clip
can be a timbre reference without copying its words or waveform, while a
background track can be partially reused beneath newly generated speech.

## 5. Official cinematic writing patterns

The official examples are detailed because they bind multiple modalities at
the same time, not because every prompt needs decorative prose. Keep these
patterns:

- Establish subject identity, clothing, position, environment, light, and
  initial state before describing motion.
- Give every important action a visible state change and a consequence.
- When focus changes, state both what leaves focus and what becomes sharp.
- When speech ends, describe the mouth/jaw returning to a non-speaking state;
  this helps audio-visual timing.
- When an audio reference supplies voice timbre, state that it is a timbre or
  delivery reference rather than silently copying the source audio.
- Let sound events follow causes: a door closes, then the latch clicks; an
  engine charges, then the vibration and impact arrive.
- Let music specify instruments, tempo, texture, and dynamic change. Do not
  use only “emotional cinematic music”.

The official T2VA example uses a 10-second two-shot escalation, while the I2VA
example uses an 8-second static composition with a deliberate focus shift. The
lesson is to choose shot count from the event: use a cut for new information,
and use focus, blocking, or camera movement when the information can remain in
one composition.

## 6. Dialogue and sound are first-class generation targets

H3's official structure treats dialogue, singing, and diegetic audio as part of
`integrated_multimodal_description`; it does not require a separate TTS stage.
For an ordinary local W4A8/ClipProj prompt, begin with natural language unless
the workflow explicitly supports the official tags. For an official-schema
prompt, use stable speaker IDs, exact `<d>` content, and `<scenetrans>` or
`<cutoff>` only when the event requires them.

For a short dialogue test, specify:

1. who speaks and where they are facing;
2. voice quality, pace, and language;
3. exact spoken words and turn order;
4. the pause or reaction between turns;
5. the visible mouth and body reaction after speech;
6. room tone and physical sounds around the dialogue;
7. whether music is diegetic or audience-only.

Verify the result at three levels: frames, audio stream, and intelligibility.
An audio stream or a frequency band alone does not prove that the requested
words were spoken clearly.

## 7. Official capability facts versus local promises

The official repository describes H3 as supporting 4–15 seconds, 24 FPS, 32 kHz
stereo audio, stable dialogue support for 11 named languages, and up to 2K
through the separate H3-Regenerate-2K stage. Ref2VA accepts multimodal inputs
within official limits, including multiple images, video clips, and audio
clips.

These facts describe the official system, not automatically the local bundled
W4A8 graph. h3lite should therefore:

- preserve the validated 5-second, 640x352 low-VRAM baseline by default;
- use the planner before increasing duration, resolution, or steps;
- treat official 2K as a separate multi-stage/API capability unless a local
  2K path is installed and verified;
- report dialogue language support as an official capability, while still
  validating intelligibility on the selected checkpoint and workflow;
- never convert an official limit into a guaranteed local result.

## 8. Compact pre-submit checklist

Before queueing a complex H3 prompt, confirm:

- mode and reference anchors are correct;
- every subject has one stable identity;
- the first and final frame rules match the selected mode;
- every cut adds information or is replaced with motivated camera/focus motion;
- dialogue is exact, ordered, and assigned to stable speakers;
- diegetic sound, ambience, and non-diegetic music are separated;
- retention and audio-reference roles are explicit;
- duration, FPS, resolution, and local hardware plan are compatible;
- the result will be verified visually and audibly, not inferred from the prompt.

## Sources

- Official H3 repository: <https://github.com/MiniMax-AI/MiniMax-H3>
- Official base prompt guide: <https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/base-en.txt>
- Official full-reference guide: <https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt>
- Official video prompt guide: <https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md>
