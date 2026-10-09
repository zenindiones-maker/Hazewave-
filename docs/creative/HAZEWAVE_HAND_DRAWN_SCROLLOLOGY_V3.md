# HAZEWAVE — HAND-DRAWN SCROLL REVERSE-ENGINEERING GATE / V3

**Owner creative constraint: if the drawing itself does not change under scroll, it does not count.**
This tightens the already owner-approved visual identity in docs/creative/HAZEWAVE_LIVING_UNIVERSE_CANONICAL_IDENTITY.md. This note does not supersede AGENTS.md or authorize merging/deployment, changes to HAZE audio or Termux computation.

## Confirmed, useful visual references

- **SBS / The Boat**, original https://www.sbs.com.au/theboat/, artist statement https://www.matthuynh.com/stories/theboat-9rw43 — ink-painting comic with 222 hand-painted illustrations and 59 animation sequences. Take the scroll-led *drawn weather/terrain/physical event*, not intellectual property. Source: https://www.commarts.com/project/23899/the-boat
- **Ponpon Mania**, https://ponpon-mania.com/ — direct production case study https://tympanus.net/codrops/2025/10/07/ponpon-mania-how-webgl-and-gsap-bring-a-comic-sheeps-dream-to-life/ confirms every drawn element from Illustrator exported to texture atlas, rebuilt as animatable layers and driven with GSAP + WebGL. WebGL is optional for *our* initial line animation, but illustrated assets must really move and change.
- **NYT / Attila Futaki visual comic**, historical report https://www.creativebloq.com/web-design/parallax-scrollling-gives-life-gorgeous-illustrations-10134797 — verified comic-inspired illustrations with animated alterations/parallax. Do not claim it uses SVG stroke-dasharray; that implementation detail is **unverified**.
- **NASA: Prospect**, https://nasaprospect.com/ — confirmed text invites user to scroll ("Pump up the volume"). However legacy Flash implementation and mobile limitations mean its implementation architecture is **not** our technology template. Use the *poetic illustrated journey* idea only.

## Not independently source-confirmed; no fabricated endorsements

- "Who's Guilty / Living Sketchbook": exact site and SVG stroke implementation **NOT verified** despite search. Use the technique independently, without claiming this particular site uses it.
- "Genie Studio App" precise scroll/mascot implementation: not source-confirmed; optional soft-motion inspiration only, not a Hazewave design authority.
- "Esimple" source-confirmed as a mostly **3D** experience, so fails the owner's strict drawn-2D implementation filter. Source: https://www.esimple.it/

## Independent, documented graphics technique

**Actual hand-drawn stroke appearing from nothing**: create SVG paths that trace _details of the approved artwork_ (energy rail, cable, machine circuit, pad edge). Set stroke-dasharray to complete SVG path length, then progress-linked stroke-dashoffset goes from 100% invisible to 0% visible. Do not overstate: this is an independently established SVG technique, **not evidence of Who's Guilty's source**.
- GSAP DrawSVG docs: https://gsap.com/docs/v3/Plugins/DrawSVGPlugin/
- SVG standard MDN: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/stroke-dasharray
- ScrollTrigger (GSAP): https://gsap.com/docs/v3/Plugins/ScrollTrigger/

The five-category NZZ scrollytelling taxonomy is descriptive, **not five mandatory effects**. Prefer **animated transition + graphic sequence with physical change**; use moviescroller only if per-frame animation is truly authored, never as a slideshow of the same poster. Taxonomy: https://data.europa.eu/apps/data-visualisation-guide/scrollytelling-introduction

## Hard acceptance requirements, scoped to only Hazewave and Indionesbala

1. First ~15% scroll: on the approved 2D cartoon illustration, a *previously invisible* violet stroke physically grows from origin, traced in the artwork's own geometry. At 0 it must be absent; at ~0.15 be visible. Reverse back to 0 means it becomes fully absent again.
2. 15–40%: traced energy physically reaches the nearest independently detached MPC; pad **surface**, at least one fader/encoder and connected cable react in causal order, not an arbitrary global color overlay.
3. 40–70%: camera passes **behind and in front** of separate hand-drawn structures using alpha/occlusion; foreground artwork displaces relative to background. No generic geometric hand-coded substitute for the approved drawn machine.
4. 70–95%: arrival causes the Indionesbala station to structurally awaken, with **an intermediate state drawn on top of original pieces** (component movement, moving faders, electric circuits, vents opening); appearance/scale of the poster alone is insufficient. Use byte-original logo file.
5. Standing still: ambient painterly fog continues to drift and machine idle breathes slightly. This time component cannot overwrite normalized scroll narrative state.
6. Reversibility: at normalized progress positions [0,.1,.3,.5,.75,1,.5,0], assert deterministic narrative pose, physical causal state, correct paint order and no residual activation when back at zero.
7. Mobile-first: proof on 393x852 *and* 360x800, scroll touch interaction, no horizontal overflow, title never occludes artwork's action, reduce-motion still navigable. Browser safety fallback when WebGL unavailable.
8. Quantifiable visual causality test: compare screenshots at 0/15/40/70/95%; the scene must change in **content, not merely cropping, blur, glow or camera zoom**. Motion tracking of at least one piece remains stable across adjacent frames; captures and continuous browser recording required.
9. No auto-approve by CI. Owner retains artistic approval; target 10/10 is a goal, not a guaranteed score.
10. QR only after a real HTTPS deploy of an owner-reviewed candidate, never 127.0.0.1.

## What NOT to do

Do not generate more complete posters as a substitute for animation; don't switch visual styles; no castles, stones, alien characters, musical-note icons, cards or desktop-only nav; no blanket green QA based on compilation; no HTML-only "finished" claims before scroll video and mobile visual inspection. Keep pre-existing owner-approved artworks and original logos immutable. No merge/main or public publication without owner approval.

## Production method

Build versioned *line path set* aligned to actual approved paths; individually rig existing painted MPC/speakers/cables/nebula plates. Add an invisible->drawn SVG signal independent from camera pan and rim light; integrate foreground plane masking and hand-illustrated pose sequences or scroll-scrubbed short frame runs for **actual** mechanical activation. GSAP is adequate to drive SVG/DOM; WebGL isn't mandatory unless measured browser need justifies it. No extra paid accounts or Codespaces. Always inspect frame-by-frame comparison and video proof BEFORE saying this qualifies.
