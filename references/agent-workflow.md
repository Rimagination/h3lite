# Agent production workflow

H3 Lite uses a small, explicit production contract for complex requests:

```text
intent route → reference/identity anchors → prompt enhancement → execute → verify
```

This is a local ComfyUI workflow pattern. It is informed by public agent-skill
designs such as Higgsfield's open skills, but it does not call Higgsfield,
MCP, or any cloud model and it does not change the H3 inference graph.

If the brief is underspecified, use the optional
[`prompt-assist.md`](prompt-assist.md) reference. It borrows the public
`STYLE → SCENE → MOTION → AUDIO → NEGATIVE` organization as a writing scaffold,
then translates it to H3's native prompt fields. It is deliberately a fallback
for ambiguity, not an extra generation stage.

## 1. Route the intent before writing the prompt

Choose one primary route from the user's actual input and acceptance criteria.
Do not choose a route from a style adjective alone.

| User intent or input | Route | First decision |
| --- | --- | --- |
| Text describes the whole clip | `T2VA` | Build the opening state and audiovisual timeline. |
| One image must be the opening frame | `I2VA` | Lock the image at `0.00` and describe only forward motion. |
| Start and end images are supplied | `FL2VA` | Describe one continuous path between both anchors. |
| Only an end image is supplied | `L2VA` | Work backward toward the final anchor. |
| Several images/video/audio references must be retained | `Ref2VA` | Define reference roles and retention before the timeline. |
| Same person or object across multiple shots | `Ref2VA` when installed; otherwise `I2VA` per shot | Create a master anchor and shot-specific continuation anchors. |
| Install, repair, or diagnose the environment | doctor → planner → preflight | Do not queue generation until the selected set is usable. |

Use one main route per job. If a required reference is missing, ask one
targeted question or state the fallback; do not silently switch from identity
preservation to a text-only generation.

## 2. Build an anchor sheet for identity and continuity

Before writing a multi-shot prompt, make a compact internal anchor sheet. Use
stable labels throughout the prompt and manifest:

```text
Subject A: dark-haired man, black wool coat, charcoal knit sweater
Picture 1: master two-shot keyframe, opening composition
Picture 2: reverse keyframe, same coast, same wardrobe and weather
Retention: face, hair, clothing, body proportions, location palette
Allowed change: gaze, small hand movement, camera angle, wave motion
Forbidden drift: new clothing, age change, extra people, changed weather
```

For each reference, record four things:

1. **Role** — identity, first frame, last frame, pose, camera, style, motion, or sound.
2. **Retention** — what must remain fully preserved, partially preserved, or only used as a weak reference.
3. **Allowed change** — the action, camera move, focus shift, or expression that may evolve.
4. **Forbidden drift** — identity, wardrobe, markings, props, background, aspect ratio, or audio details that must not change.

For a character-driven sequence, prefer one master reference plus one
continuation/reverse keyframe per new composition. The keyframe is an anchor,
not a second story: keep its wardrobe, markings, lighting, weather, and
background consistent with the master before adding motion.

Mode-specific anchor rules remain strict:

- `I2VA`: `<Picture 1>` is fully referenced at `0.00` seconds.
- `FL2VA`: the first reference is anchored at `0.00`, the final reference at the actual requested duration, and the middle path is physically continuous.
- `L2VA`: the reference belongs to the final shot, not the opening shot.
- `Ref2VA`: define `Subject`, `Picture`, `Video`, and `Audio` roles before `summary`, `retention_analysis`, `detailed_description`, and sound fields.

If official Ref2VA components are not installed, do not present this anchor
sheet as proof that Ref2VA is available. Use it to prepare I2VA/FL2VA shots or
stop with a clearly labeled experimental choice.

## 3. Enhance the prompt in five passes

Do not ask the user to write a schema. Convert a natural-language brief into
these internal passes, then emit the field order required by the selected H3
workflow:

1. **Intent sentence** — what should be visible by the end of the clip?
2. **Observable locks** — subjects, wardrobe, props, location, lighting, framing, and reference retention.
3. **Timeline** — one action per state change, in playback order; add a cut only when it reveals new information.
4. **Camera and sound** — camera position, movement amplitude/speed, focus plane, ambience, physical sounds, dialogue, and music policy.
5. **Compact anti-drift checks** — only exclusions that prevent a concrete failure, such as identity drift, extra limbs, subtitles, or a focus hunt.

Then translate the result to:

```text
integrated_multimodal_description: ...
overall_soundscape: ...
non_diegetic_music: ...
```

For `Ref2VA`, use the six-section reference schema instead. Prompt length is
not the objective; every sentence should bind an identity, spatial relation,
state change, sound event, or reference constraint. Keep camera language
physical and testable: `slow 10-degree arc at eye level`, not only
`cinematic camera`.

When the user supplies only a style adjective or a loose creative idea, consult
`prompt-assist.md` before asking a long list of questions. Fill only the missing
production choices that can be bounded safely (one clear action, one main
camera move, native ambience, and the local fast canvas); ask one targeted
question when a missing reference, duration, dialogue, or route would change
the acceptance criteria. If a public Higgsfield page is browsed, use it for
structure and vocabulary, not for factual claims or local model capabilities.

## 4. Execute and verify as one contract

- On an unchanged installation, use one `h3_fastpath.py` submission and one bounded watch; do not run a second identical job while the manifest is active.
- Keep polling silent for the user, but save the effective prompt, route, anchors, workflow fingerprint, queue ID, actual execution time, and output metadata. The runtime writes the generated anchor card to `anchors.json` and links it from `manifest.json`.
- Verify both media and creative acceptance: video/audio streams, duration/FPS, non-black frames, motion, and first/middle/last identity/wardrobe continuity.
- When references or multi-shot signals are present, `h3_status.py` records advisory `anchor_qa` comparisons for the first/middle/last frames. A valid MP4 is not proof of face or reference consistency: pixel similarity is only a drift signal, so inspect sampled frames before reporting success.
- If a higher-resolution run is too slow or fails preflight, keep the same prompt and anchors while falling back to the approved lower canvas; do not silently remove audio or identity constraints.

## 5. Local boundary

H3 Lite is a Windows-first, local ComfyUI skill. The workflow patterns above
can be learned from cloud-agent skills, but generation still uses the installed
H3 component set, local GPU/RAM/pagefile, and native H3 audio path. Cloud
features, proprietary identity models, and advertised resolutions must not be
reported as local H3 capabilities until the matching node, checkpoint, and
verification path exist on the user's machine.

## Source design reference

- Higgsfield public skill bundle: <https://github.com/higgsfield-ai/skills>
- Higgsfield video-explainer prompt templates: <https://github.com/higgsfield-ai/skills/blob/main/higgsfield-video-explainer/references/prompts.md>
- Higgsfield prompt generator: <https://higgsfield.ai/ai-prompt-generator>
- Higgsfield skill landing page: <https://higgsfield.ai/skills>
- H3 prompt-writing reference: <https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing>
