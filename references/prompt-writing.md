# MiniMax H3 prompt-writing reference

This is a compact operational digest of MiniMax's official base prompt guide and the official `h3-prompt-writing` skill. Use the linked sources for changes or edge cases. The model is audiovisual: a prompt that does not mention sound can still produce native audio, so explicitly describe the intended ambience and music policy.

## Choose the mode first

| User input | Mode | Main idea |
| --- | --- | --- |
| Text only | `T2VA` | Describe the complete audiovisual timeline from the initial frame onward. |
| One first-frame image | `I2VA` | Anchor the image at 0.00 seconds, then describe forward motion and sound. |
| First and last images | `FL2VA` | Anchor the first image at 0.00 and the last image at the final timestamp, then describe the continuous path. |
| One last-frame image | `L2VA` | Anchor the image at the final timestamp, then describe the lead-in and convergence. |
| Reusable image/video/audio references | `Ref2VA` | Define references first, then describe retention, transformation, shot details, and sound. |

Do not paste a T2VA prompt into an image/reference graph without adapting the schema expected by that graph.

## Base-mode field order

For `T2VA`, `I2VA`, `FL2VA`, and `L2VA`, keep these three labels and this order:

```text
integrated_multimodal_description: <visual timeline, actions, shots, speech, singing, and diegetic sound>
overall_soundscape: <ambience, physical sounds, and nonverbal sounds>
non_diegetic_music: <audience-only background music, or N/A>
```

For T2VA, begin directly with these three fields. For image modes, put the
reference anchor at the correct time before continuing the same three-field
structure:

```text
I2VA: For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
FL2VA: At 0.00 seconds, <Picture 1> (from [Shot 1]) is fully referenced. At <final timestamp>, <Picture 2> (from the final shot) is fully referenced.
L2VA: At <final timestamp>, <Picture 1> (from the final shot) is fully referenced.
```

`integrated_multimodal_description` is the timeline body. Put visible actions, subject state, composition, lighting, camera behavior, dialogue, singing, and sounds that occur in the scene there. Use `overall_soundscape` for environmental and physical sound that should persist or surround the action. Use `non_diegetic_music` only for music heard by the audience but not produced by the scene.

If the user did not mention sound, preserve the default native-audio behavior and make a sensible soundscape explicit. If the user asks for complete silence, say so explicitly and use `N/A` only where the guide permits it. `N/A` in the music field means no non-diegetic music; it does not mean no diegetic sound.

Treat `不要对白`, `无对白`, and `no dialogue` as a dialogue-only constraint.
Keep native ambience, sound effects, animal or action sounds, and the audio
stream. Do not convert this request into silence. Only `完全静音`, `无任何
声音`, or `no audio` means that all audio should be disabled.

Keep `overall_soundscape` to 1-4 English sentences and `non_diegetic_music`
to 1-3 English sentences. Use `N/A` for `non_diegetic_music` when no
audience-only music is wanted; use `overall_soundscape: N/A` only when
complete silence is explicitly requested.

## Shot and time rules

- Establish the opening composition and state in Shot 1; it does not need a cut timestamp.
- Add a later shot only for a meaningful cut or new composition. Use strictly increasing times within the requested duration, for example `[Shot 2] At 00:03.500, the camera cuts to ...`.
- Keep the last-frame timestamp equal to the real requested duration in `I2VA`, `FL2VA`, or `L2VA`. For 124 frames at 24 fps, treat the requested clip as approximately 5 seconds and keep the graph's own duration convention.
- Write continuous movement inside a shot in playback order. Do not use a pile of contradictory camera commands.

Useful camera vocabulary includes `Zoom`, `Push`, `Pan`, `Truck`, `Tilt`, `Pedestal`, `Arc`, `Tracking`, `Static`, `Shake`, `POV`, and `Roll`. When a camera move matters, state its type plus a useful amplitude and speed, such as a slow, subtle push-in or a fast handheld shake.

For cinematic or film-like requests, also use
[`cinematic-prompting.md`](cinematic-prompting.md). It adds a pre-writing film
decision card without changing H3's required fields: relationship pressure,
audience position, gaze flow, practical color thesis, capture base, and
anti-template checks.

For complex multimodal or full-reference requests, use
[`official-h3-insights.md`](official-h3-insights.md) as a compact guide to the
official Context-IR mindset, reference-role labels, retention analysis, and
local-vs-official capability boundaries.

## Camera position and subject orientation

Describe subject orientation separately from camera movement. A location or
activity does not determine whether a face is visible: “two people watch the
sunset” commonly produces a back view unless the camera relationship is stated.

- Front view: `The subject faces the camera directly; both eyes and the full face remain clearly visible. The camera slowly pushes in from the front.`
- Three-quarter view: `The body turns slightly away while the face stays at a three-quarter angle toward the camera; both eyes remain visible.`
- Profile: `The subject faces screen right in a clean side profile; the camera holds at eye level.`
- Back view: `The subject stands with their back to the camera, facing the sunset; the face is not visible.`
- Front-facing sunset composition: `The camera is positioned between the sunset and the subjects, looking back toward their faces; both subjects face the camera with the sunset glowing behind them.`

When facial identity matters, combine orientation with shot size and visibility,
for example `front-facing medium close-up, unobstructed face, both eyes visible`.
Avoid contradictory instructions such as “back to camera” and “full face
visible” in the same shot. Restate orientation after a cut when the new camera
position changes it.

## References and image modes

For `I2VA`, make the first-frame anchor explicit at 0.00 seconds, then describe what develops from it. For `FL2VA`, anchor the first reference at 0.00 seconds and the second at the final timestamp; describe a physically and narratively continuous path between them. For `L2VA`, state that the reference is reached at the final timestamp and describe the lead-in.

For `Ref2VA`, use these six sections in order:

```text
subject_definitions: <stable names and roles for every reference subject>
summary: <one-sentence transformation or story arc>
retention_analysis: <what each reference must retain and what may change>
detailed_description: <shot-by-shot composition, environment, actions, camera, dialogue, and diegetic sound>
overall_soundscape: <ambience and physical sound>
non_diegetic_music: <audience-only music, or N/A>
```

Define references before referring to them. Use stable names such as `Subject A`, `Picture 1`, or `Reference Video 1`; do not introduce an alias and then switch names. For every shot, specify composition, subjects, environment, actions, camera, and relevant sound/reference points. Do not leave a reference token, timestamp, or transformation unresolved.

The bundled local Ref2VA graph binds repeated `--ref-image` arguments in order:
the first image becomes `<Picture 1>`, the second `<Picture 2>`, and so on.
Assign one job to each image (identity, scene, wardrobe/prop, pose, or style)
and state its retention explicitly. The graph keeps the ClipProj encoder
resident for image references; this is more memory-hungry than I2VA and must
pass the local preflight before queueing.

## Dialogue, singing, and visible text

- Use stable speaker IDs such as `(S1)` and `(S2)` across the whole prompt.
- Put exact spoken text inside the guide's dialogue marker, for example `<d>[English] ...</d>`. Preserve the user's original words and language; translate the surrounding scene description, not the dialogue itself.
- If a person speaks off camera, say that the speaker is off screen and that the visible subject's lips remain closed.
- The guide's explicit off-screen wording is `says in an off-screen voiceover`; retain the closed-lips constraint for the visible subject.
- Preserve lyrics verbatim when supplied. Describe singing in the timeline body and identify the singer.
- Preserve on-screen words exactly in double quotation marks. Do not translate, paraphrase, or silently correct visible text.
- If a cut interrupts speech, describe the transition and use the guide's cutoff convention rather than inventing the missing words.
- Use `<scenetrans>` when a scene transition carries speech across a cut, and `<cutoff>` when a cut intentionally truncates speech.

H3 should not be treated as “unable to make dialogue” without a measured
failure. The official base guide models speakers, dialogue, singing, and
diegetic audio, and a local W4A8/ClipProj test has produced clear speech in a
realistic live-action two-person scene. On the bundled simplified route,
natural-language dialogue is a valid default:

```text
The middle-aged man (S1), with a low and slightly tired voice, looks toward the woman and says in Mandarin: "你吃了没？" She pauses, then answers in a softer voice: "还没。"
```

Use exact user-provided words and keep the order of turns observable. The
official `<d>` marker and `<scenetrans>` notation are valuable when the graph
accepts the official prompt schema, but they are not universal tokens. Inspect
the selected workflow before adding them to a simplified ClipProj prompt.

For a new dialogue capability, separate the test questions: inspect frames for
realistic people and inspect/listen to the audio for speech intelligibility.
The presence of an audio stream or a frequency band alone does not prove that
the requested words were spoken clearly.

## An operational writing pattern

Use this order when rewriting a casual idea:

1. Opening frame: subject, setting, time of day, visual style, framing, lighting, and initial sound.
2. Action timeline: visible state changes in causal order.
3. Camera: shot size and motivated movement, including cut times only when needed.
4. Audio: dialogue/singing and diegetic sounds alongside their causes; persistent ambience in `overall_soundscape`.
5. Music policy: audience-only score in `non_diegetic_music`, or `N/A` when none is desired.
6. Constraints: duration, aspect ratio, reference retention, and text fidelity only when the graph exposes those controls.

Do not add random cinematic adjectives that do not change what the model should render. Prefer observable, testable descriptions: who moves, where, when, how fast, what the camera sees, and what the audience hears.

Do not add a Stable Diffusion-style negative prompt: the native
`MiniMaxH3ImageToVideo` T2VA node exposes one prompt input, not a separate
negative input. Put essential exclusions such as no dialogue, no subtitles, or
no readable text into the main description.

For strict Minecraft-like geometry, prefer explicit English such as `blocky
voxel Minecraft scene`; a vague translation of “pixel style” can drift toward
generic low-poly imagery. Give every visible character an observable state or
action. Strong static wording can suppress motion beyond the intended subject.

## Minimal examples

### T2VA

```text
integrated_multimodal_description: A close-up of a red ball rests on wet soil in soft morning light. [Shot 2] At 00:02.000, the camera makes a slow, subtle push-in as a tiny green shoot breaks through the soil; moist earth crumbles and a quiet insect chirp comes from the garden. The camera remains steady as the first leaves unfold.
overall_soundscape: Soft garden ambience, faint birds, and the delicate crumble of damp soil surround the action.
non_diegetic_music: N/A.
```

### I2VA anchor

```text
integrated_multimodal_description: For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced. The camera holds the opening composition, then slowly tracks forward as the subject begins the described action and the surrounding sound develops naturally.
overall_soundscape: Natural environmental ambience and action sounds remain consistent with the reference image.
non_diegetic_music: N/A.
```

The examples are patterns, not fixed wording. Preserve exact user dialogue, lyrics, and visible text when present.

## Sources

- Official base prompt guide: https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md
- Official H3 prompt-writing skill: https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing
