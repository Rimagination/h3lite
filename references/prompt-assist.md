# Optional prompt-pattern assist

This reference is for an underspecified creative brief, not a new inference
route. It adapts the public prompt organization used by
[Higgsfield's open skills](https://github.com/higgsfield-ai/skills) and its
[prompt generator](https://higgsfield.ai/ai-prompt-generator) to H3 Lite's
local ComfyUI workflow.

H3 Lite still owns the route, canvas, component set, native-audio policy, and
verification. Higgsfield is a pattern library only: do not call its API, copy
its model-specific flags, or claim that a Seedance/Kling/Veo feature is
available in the local H3 graph.

## When to use it

Use this assist when a request contains a broad adjective or an incomplete
brief, for example “做得电影感一点”“镜头高级一点” or “做一个好看的 3D
动画”, but does not say enough about the subject, action, camera, setting, or
sound. Do not add it to a concrete prompt merely to make the prompt longer.

First check whether a missing detail changes the route or acceptance criteria:

| Missing information | Action |
| --- | --- |
| First/last/reference image, identity persistence | Route to `I2VA`/`FL2VA`/`Ref2VA`; build anchors before wording. |
| Duration, aspect, or hard time budget | Ask one targeted question when it materially changes planning; otherwise state the bounded default. |
| Subject, visible action, or setting | Ask when the omission makes the scene ambiguous; never invent a factual topic. |
| Camera, lighting, sound, or finish | Use the compact defaults below and label them as assumptions. |

For a normal unspecified short clip, the local default is one continuous 5-second
landscape shot, the planner's `640x352` fast canvas, one main camera move, and
native H3 ambience unless the user requests otherwise. This is a planning
default, not a Higgsfield or model requirement.

## What to borrow, and what to translate

The public Higgsfield templates consistently separate a style description from
the block's scene, motion, audio, and negative constraints. They also keep one
clear action per block and repeat the same style tokens when several clips
must match. Use those ideas as a writing scaffold:

| Public pattern | H3 Lite translation |
| --- | --- |
| `STYLE` descriptor | Stable visual lock: medium, palette, lighting, lens/render finish, and the small set of style bans that prevent drift. |
| `SCENE` | One observable state or action in `integrated_multimodal_description`. |
| `MOTION` | A physical camera move plus subject movement, with direction, amplitude, and speed when useful. |
| `AUDIO` | Causes of diegetic sound in the timeline and persistent ambience in `overall_soundscape`; audience-only score goes in `non_diegetic_music`. |
| `NEGATIVE` | A short anti-drift clause in the main H3 prompt, because the bundled native node has no separate negative input. |
| Repeated style key/reference | Reuse the same anchor labels and style lock across H3 shots; do not turn a style image into an identity reference unless the user asks for that role. |

The word “negative” here means a compact exclusion clause, not a Stable
Diffusion-style negative-prompt field. Avoid generic piles such as “no bad
quality”; name only a concrete failure (`no face drift, no extra limbs, no
subtitles, no watermark`).

## The assist procedure

1. **Intent** — write one sentence describing what the audience must see by the
   end of the clip.
2. **Locks** — freeze subject identity, wardrobe/markings, props, location,
   time of day, palette, and reference roles. Separate what may change from
   what must not drift.
3. **Scene cards** — split a multi-shot request into labeled cards. Each card
   has one clear action; do not turn every adjective into a new shot.
4. **Motion** — choose one main camera move (for example, a slow 20-degree arc
   at eye level) and one subject state change. Add a cut only when a new
   composition is necessary.
5. **Audio and exclusions** — state ambience, physical sounds, dialogue/music
   policy, and only the anti-drift constraints that protect the user's intent.
6. **H3 translation** — emit the selected route's native schema and keep the
   prompt in the graph's accepted field. For base modes use
   `integrated_multimodal_description`, `overall_soundscape`, and
   `non_diegetic_music`; for `Ref2VA` use its six-section schema.

If the user gives a reference image, distinguish its role explicitly: identity
and composition for `I2VA`, an endpoint for `FL2VA`/`L2VA`, or style/motion/audio
evidence for `Ref2VA`. Never silently copy people, text, logos, or props from a
reference that the user supplied only as a style example.

## Copyable H3 Lite templates

### One continuous shot

Use this when the brief is vague but does not require multiple compositions:

```text
integrated_multimodal_description: [Opening state and stable subject/scene locks.] The camera [one physical move with direction, amplitude, and speed] while [one observable action]. [Describe the visible state at the end.] Keep [concrete anti-drift constraints].
overall_soundscape: [Persistent environment] with [physical/action sounds].
non_diegetic_music: [Audience-only score, or N/A].
```

For a 3D animation, replace the style lock with observable tokens such as
`stylized high-end 3D animation, rounded expressive forms, physically based
materials, soft global illumination, controlled depth of field`; do not rely on
“cinematic” alone.

### Multi-shot or three-part sequence

Keep the same stable style/identity lock in every card and map the cards into
one H3 timeline:

```text
STYLE/IDENTITY LOCK: [same subject, wardrobe, markings, palette, medium, and finish in every shot]

Shot 1 [0s-2s] — SCENE: [one action and composition]. MOTION: [camera move]. AUDIO: [diegetic sound].
Shot 2 [2s-5s] — SCENE: [one continuation/action]. MOTION: [camera move or motivated cut]. AUDIO: [diegetic sound].

NEGATIVE: [only concrete anti-drift constraints].
```

Then remove the labels that the selected node does not accept and translate the
content into H3's native fields. Do not paste a template's model name,
resolution, duration, or command-line flag into the local workflow.

## Example: vague brief → bounded H3 prompt

User brief: “两个欧美男生在海边对话，做得真实、电影感，镜头慢慢绕过去。”

Assumptions: T2VA, one continuous 5-second landscape shot, 640x352 fast canvas,
eye-level 20-degree arc, no music unless requested. A useful rewrite is:

```text
integrated_multimodal_description: Two distinct adult Western men stand on a windswept coastal path under cool overcast daylight, both in a front three-quarter medium close-up with both eyes visible. The camera makes one slow, smooth 20-degree clockwise arc at eye level from the left man toward the right while they exchange a brief natural look and one small hand gesture; keep their faces, hairstyles, black and navy coats, body proportions, cliffline, sea horizon, and weather stable. End on the same two-shot with both men still clearly recognizable; no face drift, extra people, wardrobe changes, or subtitles.
overall_soundscape: Steady ocean surf, wind moving through grass, and faint coat movement surround the quiet conversation.
non_diegetic_music: N/A.
```

The rewrite adds only observable choices needed to render the vague request. It
does not invent dialogue, a biography, or a second model pass. If the user's
acceptance criteria require exact words, a reference frame, or a different
duration, ask for that missing input before queueing.

## Browsing and fallback policy

When the user's brief is genuinely ambiguous, the agent may browse the public
Higgsfield pages for a similar prompt structure. Prefer official pages and
record the consulted URL in the explanation when the research materially
changes the wording. Search is for composition and vocabulary patterns, not for
facts about the user's subject. If the network or site is unavailable, use this
local reference and `prompt-writing.md` without blocking generation.

Any live lookup must follow the host environment's `web-access` policy
(including its browser safety warning and public-page preference). Do not log
in, upload a user asset, or send a prompt to a third-party service just to
obtain wording.

The optional lookup must not add a cloud dependency, an API key, a second
inference model, or a second video generation pass. Any route, component,
resolution, timing, and capability claim still comes from the local H3 Lite
doctor/planner/preflight and verified ComfyUI run.

## Public sources

- Higgsfield open skills: <https://github.com/higgsfield-ai/skills>
- Higgsfield video-explainer prompt templates: <https://github.com/higgsfield-ai/skills/blob/main/higgsfield-video-explainer/references/prompts.md>
- Higgsfield prompt generator: <https://higgsfield.ai/ai-prompt-generator>
