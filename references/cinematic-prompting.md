# Cinematic prompting for MiniMax H3

Use this extension when the user asks for a cinematic, film-like, short-film,
trailer, realistic movie shot, or 电影感 video. It combines Cinema DNA's
composition reasoning with MiniMax H3's official audiovisual prompt schema.
It is a writing aid, not a new ComfyUI mode.

## 1. Film decision card

Before writing the H3 fields, decide the following internally:

- **Irreducible state:** What cannot be solved immediately? For example, two
  people know the truth but wait for the other to speak.
- **Audience position:** Is the camera inside the event, outside it, behind
  glass, at a threshold, above the scene, or trapped in a narrow space?
- **Relationship pressure:** Who watches whom, who has more information, who
  is leaving, and what spatial structure limits the characters?
- **Gaze flow:** Write one sentence: “The eye enters from A, slows at B,
  lands on C, and exits through D.” If this cannot be stated, the composition
  is probably an element pile.
- **Color thesis:** Name the main and accent colors and their physical source:
  clothing, walls, weather, practical lamps, water, glass, soil, or metal.
- **Capture base:** Choose one plausible base such as a 35mm feature-film
  camera, 16mm documentary transfer, early digital cinema camera, or a
  restrained handheld 35mm look.
- **Rhythm:** Decide whether the clip is one continuous shot, a reveal cut, a
  reaction cut, or a short transition. Do not default to wide shot → close-up.

Keep this card internal unless the user asks for the reasoning. It should
control the final prompt, not become abstract prose in it.

## 2. Translate the card into H3

Keep the official base-mode order:

```text
integrated_multimodal_description: ...
overall_soundscape: ...
non_diegetic_music: ...
```

Within `integrated_multimodal_description`:

1. Establish the opening composition, subject state, practical location,
   capture base, framing, and light source.
2. Describe one main action and one secondary clue in causal playback order.
3. State the camera's physical position, focal-length range, distance,
   height, focus plane, and motivated movement when they affect the shot.
4. Add a later `[Shot N] At 00:MM.SSS` only for a meaningful cut that reveals
   new information. For a 5-second action, prefer one continuous shot or at
   most two shots.
5. End with the unresolved visual state or reaction rather than an explanatory
   plot summary.

Use `overall_soundscape` for persistent ambience, physical actions, and
nonverbal human sounds. Use `non_diegetic_music` only for audience-only music;
describe instruments, tempo, and dynamic change rather than only saying
“emotional cinematic music”.

### Dialogue is an audiovisual action

Do not remove human dialogue merely because the route is low-VRAM or because a
previous prompt failed. For a short capability test, write the exact line,
speaker identity, voice quality, turn order, pause, facial orientation, and
reaction in the timeline. On the bundled W4A8/ClipProj route, start with
natural-language dialogue; reserve official `<d>` and `<scenetrans>` markers
for graphs that accept the official schema. Verify the words by listening or
speech analysis rather than inferring speech from a visible mouth or a generic
audio spectrum.

## 3. Composition pressure library

Choose one primary pressure and, at most, one supporting device:

| Pressure | Useful visual evidence |
| --- | --- |
| Being watched | glass, doorway, crowd, shoulder in foreground, incomplete information |
| Being trapped | corridor, desk, steps, seat, institutional geometry, small subject in a large room |
| Estrangement | empty space, glass, table, bed, floor, or averted eyelines between people |
| Unequal power | stairs, wall, gate, screen, elevated position, crowd controlling scale |
| Psychological imbalance | subject at the edge, excess headroom, slight tilt, focus on the background |
| Sensory insertion | hand, shoe, wet fabric, key, paper, breath, machine edge; action stops before completion |
| Aftermath | open door, empty chair, wet ground, unextinguished lamp, displaced object; do not make it the default ending |

Foreground blur must have a reason for the camera to be there. Use a door
frame, vehicle window, passer-by, railing, curtain, reflection, or a relevant
object edge—not a random black shape added for “film feeling”.

## 4. Camera and optical grammar

Write camera movement as a natural sentence with motion type, amplitude, and
speed when useful:

```text
The camera pushes in with small amplitude at slow speed toward the unopened letter.
The camera pans right with large amplitude at fast speed, revealing the empty platform.
The camera holds a static eye-level shot as the subject leaves the frame.
```

Useful focal-length tendencies:

- `24–28mm`: environment and spatial pressure; avoid exaggerated distortion.
- `32–40mm`: natural observation and relationship blocking.
- `50mm`: neutral human distance.
- `65–85mm`: compression and surveillance; do not turn every shot into creamy bokeh.

Use practical-location language where appropriate: `live-action feature-film
still`, `real actor`, `physically plausible set and props`, `natural skin
texture`, `soft highlight roll-off`, `restrained production design`, and
`local optical softness`. These are supporting constraints, not substitutes for
an action or composition.

## 5. Color and anti-template checks

Write a color thesis with a physical source, for example:

```text
A faded vermilion garment remains the only saturated color against wet blue-gray concrete and overcast daylight; the accent shifts from the person to the abandoned ticket by the final beat.
```

Do not automatically use blue-gray darkness, teal-orange grading, heavy film
grain, fog, particles, lens flares, artificial rim light, plastic skin, HDR
sharpness, or glossy commercial lighting.

Before submission, reject the prompt if it reads as any of the following:

- a game key art or CG concept image;
- an AI wallpaper or commercial beauty advertisement;
- a generic TV-drama conversation;
- a reusable “wide establishing shot → POV → face close-up” template;
- a sequence whose camera position cannot be justified by the event.

Compact negative constraints are acceptable in the main description because H3
does not expose a separate negative-prompt input:

```text
no CGI concept art, no game key art, no glossy AI rendering, no HDR, no plastic skin, no excessive particles, no artificial rim light, no commercial beauty lighting, no television-drama blocking, no generic teal-orange grading
```

Use only the constraints that prevent a real risk; do not turn the prompt into
a long negative list.

## 6. Reusable cinematic T2VA pattern

```text
integrated_multimodal_description: [Shot 1] Live-action feature-film scene, a 35mm camera at eye level holds a medium-wide view inside a nearly empty night train. A tired woman sits beside a rain-covered window, her face in three-quarter view and both eyes visible; a folded red ticket rests in her hand. The camera tracks right with small amplitude at slow speed as the train enters a tunnel and the reflected carriage lights slide across her face. She notices a second reflection standing behind her, but does not turn before the shot ends. The practical fluorescent ceiling lights remain uneven, with soft highlight roll-off and restrained optical softness; the faded red ticket is the only saturated color. No cut.
overall_soundscape: Train wheels keep a steady metallic rhythm under the ventilation hum. Rain taps against the glass, paper rustles in her hand, and the carriage gives a low vibration as it enters the tunnel.
non_diegetic_music: Sparse low piano notes at a slow tempo, joined by a distant sustained cello tone that stops before the final frame.
```

Adapt the example to the user's subject. Preserve the official H3 field names,
audio semantics, timing rules, and reference anchors; only the film grammar is
being added.

## Sources

- Cinema DNA 21:9 × 3: <https://github.com/dacnay816y62-hub/cinema-dna-21x9x3>
- Official H3 prompt-writing skill: <https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing>
- Official H3 base prompt guide: <https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md>
