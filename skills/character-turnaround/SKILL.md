---
name: character-turnaround
description: Generate character turnaround sheets (three views - front, true profile, back) for comic, animation, game and AI-image character design. This skill should be used when the user asks for 三视图, 角色设定图, 人物设定图, 角色设定三视图, turnaround, model sheet, or needs a multi-angle reference of a character so that later shots keep the same face, silhouette and costume. Covers the four-line prompt skeleton, reference-image anchoring for existing characters, the prompt rules that stop the model from drifting, the five failure modes, and the acceptance checklist.
agent_created: true
---

# Character Turnaround (角色三视图)

> **怎么装**：把本目录的地址发给你的 Agent，说「帮我装上这个 skill」。
> **怎么叫**：`用 character-turnaround 给我出一张三视图`。
> **验证**：装完问它「你现在会哪几步」，它应能复述 SKILL.md 里的条目名。

## Purpose

Produce one image containing the same character seen from front, true profile and back, on a plain white background, with identical costume, hairstyle and body proportion across all three views.

The output is a **working reference, not a beauty shot**. Its job is to make structure readable so every later shot can be generated from it.

## When to use

Use when the user asks for 三视图 / 角色设定图 / 人物设定图 / turnaround / model sheet, or when a character is about to appear across many shots and has no multi-angle reference yet.

Do not use for a single hero pose or a portrait — that is a 立绘 (key visual), a different task with a different prompt structure.

## The four-line skeleton

Build every turnaround prompt from four independent blocks. Keep them separate: mixing lighting words into the costume block is the most common cause of drift.

```
Line 1  Task    what image + what background + how many views + which views
Line 2  Person  reference anchor (existing character) OR description (new character)
Line 3  Costume + pose + framing
Line 4  Light + consistency + style
```

Keep the whole prompt short. Short text means each word carries more weight; long text dilutes both the description and the reference image.

### Template — existing character (reference-anchored)

```
角色设定三视图，纯白背景，同一个人物分三个视角并排：正面、正侧面、背面。
三个视角从左到右等距排列，站姿完全相同，身高、头身比、体型完全一致。

@图片1 中的这个人，这是他的脸，三个视角是同一张脸，严格保持脸型、五官、发型不变。@图片2 是他身上的这身衣服。

服装与发型在这三个视角完全一致：{costume list, semicolon-separated, one feature per item}。

背面同样是完整细节：{back-view specifics}。

全身完整入镜，从头到脚，头顶留白、双脚完整，双臂自然垂在身侧，表情中性平视前方，不摆动作。

平光均匀照明，无投影，没有强阴影。布料质感、剪裁结构与配件位置清楚。

写实摄影，角色设定图风格。
```

### Template — new character (text-described)

Replace Line 2 with a single line:

```
{age} {gender}，{hairstyle}，{eyes}，{one distinguishing feature}。
```

Do not stack adjectives. One feature a viewer could draw from is worth ten mood words.

## Reference images: how many, and which

| Situation | References |
| --- | --- |
| Existing character with a face anchor and a full-body costume anchor | 2 images — face anchor first, costume anchor second |
| Only a full-body sheet exists | 1 image; rewrite the anchor sentence as `@图片1 中的这个人` |
| New character | 0 images, use the text line |

Two references only work when their jobs are stated explicitly (`@图片1 是脸，@图片2 是衣服`). Without that split the model averages them and the face drifts.

**The reference image always beats the text.** When text and reference conflict the reference wins, every time. If a detail must change, change the reference image or change the requirement — do not try to out-write the picture.

## Thirty-one prompt rules

Detail and evidence for each: 见项目 `项目根/Agent框架/07_视觉提示词规则.md`。
本 skill 目录里的 `references/prompt-rules.md` 是 2026-10-25 的冻结快照，**2026-11-01 起只留指针，不要再当规则读**。

1. **Never describe the face of a reference-anchored character.** Write only `@图片1 中的这个人`. Every adjective competes with the reference.
2. **To avoid a form, never name that form.** Wanting a collar folded down means the words 立领 / 高立 must not appear anywhere — writing "folded down" inside parentheses does nothing. Use the name of the opposite form: `领子向下翻折、平贴在后颈`.
3. **Do not describe structures that are not visible.** An internal cinch described as "hidden under the outer layer" gets drawn on the outside.
4. **Material: write the behaviour of light, not the material's adjective.** "Matte" alone fails; "surface is dry and powdery, light spreads across it, no sharp highlight" works.
5. **Do not name a fabric category.** "Denim" returns jeans, "canvas" returns a work jacket. Write colour as colour, fabric as function.
6. **Measure length against something already in frame.** "Hem drops to the middle of the trouser chain" beats "hem sits at the hip bone".
7. **State consistency twice** — once in Line 2, once in Line 3 — and open the whole prompt with `同一个人物`.
8. **Translate jargon into picture.** "Three-view sheet" is a label; "three identical people standing side by side, the first facing the camera, the second in full profile, the third facing away" is a picture. The model responds to pictures.
9. **Anchor every proportion to the head, and give the number.** `Head-to-body 1:7.5`, `shoulder width is 2.8 head-widths`. Never express a ratio between two other variables (e.g. shoulder ÷ waist) — the model satisfies it by shrinking whatever is left unconstrained.
10. **Fix which way the profile view faces.** Write which way the nose points, not which cheek you want: nose toward frame-left shows the right cheek. Any feature that exists on one side only also needs "visible in these views, not in that one".
11. **A reference image reproduces one character, it cannot produce a different person of the same class.** Same costume and build with a *different face* requires zero references — generate each character from text alone, repeating the shared block verbatim. Text cannot out-argue a reference face; the race is unwinnable.
12. **"Along / around / ring" collapses into a full loop.** Any band-like feature needs a size plus an explicit stop point (`from under the ear, forward and down, stopping at the chin midline`) and a positive statement about the other side (`the right jaw is clean skin`).
13. **Rugged and ape sit one sheet of paper apart.** Five plausible "tough guy" traits stacked become a primate: heavy brow, sunken nose bridge, jutting jaw, protruding ears, narrow sloped forehead. Write the opposite of each. A *broken* nose is still a *straight, high* nose with one kink at mid-bridge — never a flat nose. Shoulder ÷ head width near 3.0 also reads ape (human 2.5–2.8); give shoulder width as an absolute value.
14. **A turnaround is a structure sheet, not a material sheet.** Do not spend generations chasing surface quality. Ask only: is the part in the right place, the right thickness, exposed at the right point, split into the right number of segments. Material reads in the final shots, where rain, neon and directional light reshape it. Matte industrial hardware is *supposed* to look cheap.
15. **"Seam" turns an implanted part into a stuck-on panel.** Never write 接缝 / 边缘 / 一圈 around a metal body part. Write depth instead: `the metal sits inside the skin plane, slightly below it; the skin slopes down into it; the edge is skin overlapping metal`. Same for ports, eye sockets, subdermal wiring. And use matte gunmetal, not light grey — light grey on dark skin reads as a sticker.
16. **A surface becomes a sticker; a line becomes embedded.** Wording alone cannot save a plate: a flat panel on a curved neck is geometrically guaranteed to have an edge. Turn the part from a *plane* into a *line* — one column of separate small inserts along the spine, with skin between them, each with its own size and spacing. Lines have direction and vanish into the body. Also: never locate a hidden feature by saying "not visible from the front" — the silent views get erased with it. Say what the profile *does* show. And when hardware sits under clothing, fix the garment length explicitly (`sleeve fully covers the upper arm, ends below the elbow`), otherwise it becomes a half sleeve and the machinery floods out.
17. **A turnaround is not a video keyframe.** Two different products: the turnaround is flat-lit, plain-background, three views, judged by "can I count the parts"; the keyframe is single-view, lit, in-scene, judged by "is something already happening in this frame". Never feed a turnaround as a keyframe (the video will stay a turnaround) and never feed a keyframe as a turnaround (you cannot read structure through dramatic light). Four keyframe rules: the keyframe sets the ceiling for the video (video only reproduces it, then drifts); the frame must show an action mid-flight, not a preparation; keep shadow and highlight away from the extremes so the light can still breathe; leave 15–25% of the frame as movement margin.
18. **Describe rendering as the behaviour of light, never as a style name.** "Cel" and "CG" summon the most generic version of that word. Cel = 2–3 flat value steps with hard edges + black outline + highlight as a sharp-edged block. CG = continuous value gradient + no line (form reads through the value break) + skin that is matte with pores and lets a little blood through at the nostril and ear rim (subsurface) + metal whose highlight stretches into a thin elongated line (anisotropy). And never convert style with image-to-image: the model redraws rather than re-renders, so the face is re-grown. Use two references (face anchor + costume anchor) with a text-only rendering description.
19. **Game feel = high-frequency material detail; filters = post.** Words like "game feel / CG / AAA" push the model toward smooth and idealized — you get a figurine. The dividing line is micro-surface: pores and fine facial hair, a little red at the nostril wings, a blue-grey shave shadow, off-white sclera, blood through the ear and nose rim, moist eye surface with iris texture, individual hair strands catching rim light, canvas weave with broken fibres at wear points, individually separated zipper teeth, sandblasted metal with fine scratches, leather grain, plus three-point light (key + cool rim + floor bounce). In short: **imperfection is the signal for "not a cartoon"** — write flaws, not "realistic". And never generate the cyberpunk colour grade: chromatic aberration, bloom, grain, teal-orange split and vignette belong to one post preset applied to all 103 shots, exactly like film grain.
20. **Test style with shot grammar, never with turnaround grammar.** Front-facing, symmetrical, flat-lit, plain-background, full-body is *product-photo grammar* — render it realistic, cel or CG and it still reads "this is a product". Three tests in a row landed on figurine. Game feel comes from the frame having a story: half-body framing, weight on one leg, shoulders and hips at an angle, camera slightly low or off-axis, real environment with depth, a key light and a large dark area.
21. **Describe texture through light, not through facial features.** Adding "red at the nostril wings, blue-grey shave shadow, yellowish sclera, under-eye bags" in order to kill the cartoon look *redrew the face* and broke the anchor. Write `侧光扫过他的脸，皮肤在受光的一侧显出毛孔与细小的绒毛` instead of listing features. Light paths do not change a face's shape; feature lists do.
22. **Asset-level frames are judged on skeleton; shot-level frames on the whole.** A scene sheet, turnaround or prop plate gets reused, cropped and graded, so accept it if the *skeleton* is right — camera grammar, depth layering, light position, proportion. Darkness, saturation, rain amount are post-fixable and not worth another generation. A frame destined for the cut needs everything right. The practical question is always: "is the skeleton right?" Skeleton right, parameters off → keep it. Skeleton wrong, parameters gorgeous → regenerate. **Skeleton costs money; skin is free.**
23. **Pick *which* frame of the action.** "Mid-action" has three time points. If the shot shows the action itself (yanking, slamming, pushing), take the frame 0.2 s *before* it lands: tendons taut, object pulled straight, surfaces about to meet. If the shot shows the aftermath, take the frame just after — and it must carry physical evidence (torn skin of the cable, exposed braid, loose wires), not just "the connector popped out". A frame with no evidence of the action reads as a still life. First frame is not "painting a state", it is "where the cut is".
24. **Body-part anchors need the same age and build as the face.** Hands reveal age faster than faces and appear as often in medium shots. Write a separate hand spec: young lean male — longish fingers, knuckles clear but not enlarged, thin back of hand showing bone and tendon, taut skin with shallow creases, no spots, faint veins, thin callus at the web and finger bases, short flat nails with dirty edges, a few small old cuts. **"Weathered" is not "old"**: callus, grime and small cuts are weathered; loose thin skin, deep creases, spots and knobby joints are old. And when using local redraw on one corner, state that the surrounding areas stay unchanged — otherwise the model redraws the nearby skin and re-reads "weathered" as "older".
25. **The keyframe must be shot at the delivery aspect ratio.** A keyframe shot at a different ratio than the delivery video makes the platform *recompose*, not crop: subject shrinks, background gets invented, the isolation is gone. Measured first-frame drift was 40.8 with mismatched ratios versus 2.3 with matched ones — a tenfold loss for one setting. Scene assets may use a wider ratio (a wide frame crops down and reuses well); **keyframes must match the delivery ratio exactly**. And vertical framing is not a crop of horizontal framing — rewrite the composition by vertical layers (subject occupies the bottom two-thirds, the thing that matters sits in the upper third).
26. **For a hand close-up: either name all five fingers, or crop the hand out of frame.** "Thumb and index gripping, the other three curled" only gives a grouping (3+2) and the model merges them — measured result was a four-fingered hand with fused finger creases, on the opening shot. Fix A: name each finger and state that creases stay clear between every pair, in both the keyframe prompt and the video prompt ("holding still" is an empty instruction). Fix B, preferred: **show only thumb and index**, put the rest outside the frame — the shot needs "a hand exerting force", not "whose hand this is". A defect you can crop out is better than one you argue with.
27. **Video models push irregular things back toward a stable form.** A freshly torn cable end — ragged sheath, splayed wires — shortened and closed up within 3.5 seconds, as if healing. Same for wounds, broken glass, scattered debris, torn packaging: **anything "just destroyed" will not survive four seconds.** Cheapest fix is a shorter shot (2–3 s); next is moving the focal point off the defect; writing "keep the torn sheath and splayed wires as they are" helps but is weaker than the first two.
28. **A cylinder needs a stated orientation or you get a button.** Asking for "a cylindrical multi-pin connector" produced a **coin cell** — flat disc, ring of pins facing camera, looks like a shirt button. A cylinder seen end-on *is* a disc, and the model turns the end toward camera so you can see the pins. Fix: state the orientation (`barrel sideways to camera, end face toward upper right, side profile and one end’s ring of pins visible`), give length and diameter (otherwise it becomes a pancake), and give a side-wall feature that only a cylinder can have (`knurled thread around the barrel`). Second rule, more important: **do not put detail on something that will be out of focus.** A blurred ring of pins reads as "pattern on a disc", reinforcing the button. In focus and large → detail is fine; defocused, small, or leaving frame → outline + one texture + one metal highlight only. Defocus does not blur detail, it turns detail into stains.
29. **Never write "the light" — write where the light lands.** Third time on this: "glowing crystal slab" blew out into an emitter; "light dims slowly" went fully dark; "the blue light retracts inward" sprayed a **column of blue smoke** clear to the top of frame. The model has no concept of illumination — light is an object that drifts. Best answer is to not write light at all in a video prompt: keep it static and animate brightness in post (see rule 19). If you must, describe the *surface*: `the small blue patch on the inner wall of the break dims; the blue on the thumb skin returns to flesh tone`. Priority: ① no light in the prompt > ② light-on-surface > ③ light itself (guaranteed failure).
30. **A video prompt must restate the key forms of the keyframe, item by item.** The keyframe had thumb pressing from the left, index from above, cable running diagonally. The prompt only said "the two fingers flinch back" — result: the hand was re-blocked into a vertical pinch on a vertical cable, paler and smoother, and the background bokeh doubled. The video model *re-performs* the shot, it does not *retain* the frame. `Keep unchanged` / `stay the same` are empty instructions — name the thing: position, facing, pose. Same for stance, the angle of a prop in the hand, gaze direction, and the relative placement of objects.
31. **Every movement needs a force behind it.** "The connector pops up and to the right, leaving the top edge within 1.5 s" produced a connector that **flew at the camera, growing, and punched out of frame in 0.4 s** — the first thing a viewer asks is "why is it flying by itself", because nothing explains the motion. The real chain: the hand pulls down, tension is released, the connector loses its tether, gravity takes it **downward and out the bottom edge**. Before writing any movement, answer three questions: who pushes it, which way does the force point, where does it come to rest. If you cannot answer all three, delete the movement. And never invent a movement just to give the frame "something happening" — this shot\u2019s script said "the light dies, only an afterglow trembling in the socket", which is *aftermath*, not an action beat. After destroying evidence comes stillness, not an action movie.

## Workflow

1. Decide existing vs new character; pick the reference set.
2. Write the four-line prompt, keeping the body under roughly 300 Chinese characters outside the costume list.
3. Generate at 16:9, highest resolution, 1 image. Budget 2–3 attempts.
4. Verify against the checklist. For any failure, read `references/failure-modes.md`.
5. Fix **only** what failed. Do not re-word anything that already passed — every regeneration drifts, and re-litigating settled details never converges.

### Two-pass for a character that must be *new* but belong to a group

Reference images reproduce one character; they cannot produce a different person of the same class (rule 11). But pure text alone makes the three views drift into three people.

Resolve it in two passes:

1. **Pass 1 — text only, zero references.** Goal is only *"this person exists"*. Get the ethnicity, build and the one distinguishing body modification right. Ignore view-to-view drift and ignore face polish.
2. **Pass 2 — self-anchor.** Crop the strongest single view out of the Pass 1 output (usually the front figure), feed it as `@图片1`, and rewrite the person block as `@图片1 中的这个人`. Keep only the correction sentences for the modification and costume.

Pass 1 exists to *invent* the person; Pass 2 exists to *lock* them. They are sequential, not alternatives.

### Delivery rule: hand over whole prompts, never diffs

Every prompt delivered to the user must be one complete block they can copy in a single action. Never say "reuse the block above and swap these three lines" — with a prompt this long, manual splicing produces errors that cost a generation to discover.

If two characters share a common block, write both prompts out in full. The duplication is cheaper than the mistake.

### Delivery rule: name the inputs, but never wrap the prompt in a block

Over a long project the biggest waste is not a badly written prompt — it is **not knowing whether a reference should be attached**. One too few and the face drifts; one too many and it locks up; no answer at all and the user guesses, which costs a generation.

So every delivered prompt states its inputs — but **in running text, with the filenames highlighted**, not inside a framed box:

> 首帧图用 `outputs/04_首帧/S01-01_手部特写_定稿.jpg`（就是上一版那张，管构图与手的形态），额外参考：无。参数 16:9 · 1920×1080 · 4 秒。
>
> ```
> （整段提示词，纯文本，可直接复制）
> ```

**Write `无` when there is no reference.** "Not mentioned" and "none" are different things — the first makes the user hesitate.

**Why no `━━` frame and no `■` bullets:** the user copies the prompt straight out of the chat. Box-drawing frames, `■` markers and table scaffolding get captured into the selection and have to be deleted by hand — and on a prompt this long, hand-editing is where mistakes hide. Decoration goes *around* the prompt, never inside the copyable region. The prompt itself is one fenced block with nothing else in it.

Every reference must be named individually with its job. Two references with no stated division of labour get averaged, and the face drifts.

**A keyframe is not a reference.** A reference means "draw it like this"; a keyframe means "start moving from here". Keyframes must match the delivery aspect ratio exactly, and their key forms must still be restated in the video prompt — the model re-performs the frame rather than retaining it.

### Resuming work: pre-stage, do not hand back a to-do list

When a character is approved, or when a session picks up an old project, the reply should be the **next usable artefact**, not a status summary. Assemble the fully finished prompt for whatever comes next and put it in the reply, ready to paste — even if it means repeating a block that already exists in a file. Do not say "the prompt is in `xxx.txt`"; do not ask the user to reopen an older document and splice a paragraph out of it.

The test: after reading the reply, the user should be able to act without opening anything else.

Same principle for variants: if a character gets rejected on one detail, rebuild the *whole* prompt with that detail corrected. Never reply with "change line 4 to X".

### Pre-flight check before every generation

- Which side is the distinguishing feature on? Set the profile direction to *match* it — a scar on the right cheek needs `nose toward frame-left` (frame-left nose shows the right cheek). Getting this backwards silently loses the feature.
- Is every number in place — head-to-body, shoulder width, crotch line, hem drop?
- Any band-like part ("along", "around", "ring")? Add a stop point.
- Any word that names the thing you want to avoid? Delete it.
- Reference images: are you trying to reproduce *this* character (yes → use them) or invent a *different* one (yes → zero references)?

## Settings

- Aspect ratio **16:9**. 3:4 squeezes the three figures and leaves no horizontal breathing room.
- Resolution: highest available.
- Text enhancement **OFF** — any text belongs in post.
- Image enhancement / upscale **OFF** — it erases fabric texture.

## Acceptance checklist

Pass:
- Three views are the same person, same costume, same height and head-to-body ratio. A few percent of variation is fine.
- Profile is a true 90° side view, not three-quarter.
- Feet complete, nothing cropped.
- Collar shape readable and jaw line unobstructed. **A stand-up collar passes if it opens backwards and does not cover the jaw** — the sheet's job is legibility, not a specific collar state.
- Distinctive elements countable at a glance: number of straps, pockets, buckles.
- Clean plain background.

Fail, any one vetoes the sheet:
- Three different costumes, or a face that is not the anchored character.
- Muddied silhouette, broken legs or feet.
- The character reads as a generic archetype rather than the specific design.
- Background with gradient, grey edges, or stray figures.

## Output organisation

A few days of work turns three files into a hundred. Keep the structure from day one — see `references/output-organisation.md`.

Short version:

```
outputs/
├── 00_索引.md      task-oriented index (not a file listing)
├── 01_导演表/       deliverables
├── 02_锚点/         finalised references, read-only
├── 03_场景/         scene assets
├── 04_首帧/         keyframes ready for video
├── 05_提示词/       当前 / 旧版
├── 06_文档/         specs, reports, plans
└── 99_过程稿/       rejects, intermediates, comparisons
```

Name as `{subject}_{content}_{version-or-state}`, so the first two characters identify the subject and the state vocabulary stays at three words (`vN` / `定稿` / `通过`). Anything superseded, or kept only for a look, goes to `99_过程稿/`. After moving files, update every document that cites the old names **and** change the generator's output path — otherwise the next rebuild recreates the mess.

## Post-processing

- Crop tight to the figures. The shipped sheet should have roughly equal margins and no dead space above or below.
- If a platform watermark sits on **plain background**, remove it by harmonic diffusion: hold known pixels fixed, repeatedly blur the masked region and composite it back inside the mask, then feather the edge. Do not clone a block from elsewhere — a studio backdrop has a vertical gradient and the patch will show.
- If the watermark **overlaps the character**, leave it and note it. The sheet is a working reference, not a deliverable.
