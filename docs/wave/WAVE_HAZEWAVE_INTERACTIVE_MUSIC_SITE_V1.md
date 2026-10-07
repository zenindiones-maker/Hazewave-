# HAZEWAVE — WAVE INTERACTIVE MUSIC SITE V1

**Status:** DEVELOPMENT / EXECUTION REQUIRED  
**Owner:** WAVE  
**Harness capability:** `visual.site`  
**Requested domain:** `WAVE`  
**Bridge dependency:** `bridge.haze_to_wave` only for structured sonic state consumed by visuals  
**Repository:** `zenindiones-maker/Hazewave-`  
**Candidate branch:** `work/wave-hazewave-site-v1`  
**Quality rule:** the provided Spotify-3D/cassette interaction is a QUALITY FLOOR, not a design to copy.

---

## 1. Mission

WAVE MUST BUILD the public Hazewave interactive music site.

This is a real implementation mission.

It is NOT complete with:
- an architecture document;
- a moodboard;
- a Figma-only prototype;
- static screenshots;
- an isolated Three.js demo;
- a list of tools;
- a generic music player;
- a landing page with decorative 3D.

The result must be a working, production-oriented, tactile and cinematic music experience where artists and songs are represented through original Hazewave visual objects and a simple user action triggers a tightly authored audiovisual sequence that culminates in real music playback.

The owner-provided reference demonstrates the interaction principle:
- multiple music objects;
- one tap/click selects one;
- the selected object performs an automatic polished transition;
- it integrates into a player/device state;
- the visual identity changes with the music;
- playback starts;
- the whole experience feels continuous rather than like page navigation.

WAVE must produce an original Hazewave system that is visibly more polished, more scalable, more musically integrated and more distinctive than that reference.

---

## 2. WAVE specialization required

This project establishes an expert bar for WAVE in:

- immersive and interactive website design;
- Three.js/WebGL/WebGPU production architecture;
- high-end 3D web interaction;
- authored motion design and timeline choreography;
- Blender-to-web production asset pipelines;
- glTF/GLB optimization;
- cinematic camera staging;
- artist-specific design systems;
- Web Audio-driven visual behavior;
- touch-first interaction;
- responsive 3D composition;
- accessible motion systems;
- performance profiling on real devices;
- progressive enhancement;
- browser QA;
- visual quality control;
- typography and editorial hierarchy inside immersive interfaces;
- production deployment for media-heavy websites.

Knowing library APIs is not enough.

WAVE must show professional judgment in:
- composition;
- spatial hierarchy;
- lighting;
- material design;
- easing;
- anticipation;
- timing;
- depth;
- camera movement;
- sound feedback;
- latency;
- GPU cost;
- network cost;
- accessibility;
- device constraints.

---

## 3. Core interaction principle

Do NOT copy:
- the cassette;
- the iPod/player product design;
- exact layout;
- exact color system;
- exact camera path;
- exact materials;
- branding;
- artwork.

Preserve the deeper interaction idea:

```
ONE SIMPLE ACTION
-> IMMEDIATE FEEDBACK
-> AUTHOR-CONTROLLED CINEMATIC SEQUENCE
-> OBJECT CHANGES STATE
-> PLAYER / WORLD RESPONDS
-> AUDIO STARTS
-> EXPERIENCE REMAINS CONTINUOUS
```

The primary music-selection action must be effortless.

Do not require precision drag-and-drop for the central playback action.

A tap/click must be sufficient to trigger the principal sequence.

---

## 4. Original Hazewave concept — Resonance Deck

Working concept: **RESONANCE DECK**.

The visual form is not frozen by this name. WAVE is expected to improve the art direction.

Each artist owns a visual world.

Each release/track owns a **Resonance Module**:
- an original digital object;
- artist-specific materials;
- artist-specific visual language;
- scalable through data;
- compatible with the shared interaction grammar.

Selection sequence:

1. User taps/clicks a Resonance Module.
2. Immediate visual/sonic micro-feedback confirms the input.
3. Non-selected modules recede while remaining spatially coherent.
4. Selected module gains visual priority.
5. Camera and object begin a coordinated authored move.
6. The module follows a deliberate 3D trajectory toward the Resonance Deck.
7. The Deck anticipates arrival before contact through light, geometry, mechanism or material response.
8. Module aligns and inserts/connects with precise final deceleration.
9. Mechanical and visual feedback land on the same contact event.
10. The world transitions into the selected artist identity.
11. Real audio playback begins.
12. Playback state persists while the user continues exploring.
13. Selecting another track triggers a polished eject/replace sequence without conventional page reload.

The Deck must not look like a copied consumer product.

---

## 5. First vertical slice

Do not build the entire catalog before proving the interaction.

First shippable slice:

- 3 artists;
- 2 tracks per artist;
- 1 shared Resonance Deck system;
- data-driven artist/release manifests;
- a unique visual identity per artist;
- click/tap -> automatic cinematic insertion;
- real playback path;
- persistent player state;
- one artist-to-artist transformation;
- one track-to-track transformation;
- desktop implementation;
- touch/mobile implementation;
- reduced-motion mode;
- non-WebGL functional fallback;
- semantic content outside the canvas;
- automated tests for core state transitions.

If this slice does not clearly meet or exceed the owner reference quality, WAVE must iterate on the slice instead of scaling catalog content.

---

## 6. HAZE + WAVE integration

The website is a WAVE-owned visual product.

HAZE owns audio analysis and sonic meaning.

Cross-domain behavior must use the typed BRIDGE.

Target:

```
AUDIO / MUSIC
-> HAZE analysis
-> HAZE_STATE
-> typed BRIDGE
-> WAVE_STATE / visual manifest
-> WAVE scene + animation + rendering
```

WAVE must not collapse musical intelligence into a generic amplitude visualizer.

The visual system should be able to consume structured events such as:
- BPM;
- beat grid;
- downbeats;
- section boundaries;
- onset density;
- loudness;
- spectral regions;
- breaks;
- drops;
- chorus transitions;
- motif identity;
- artist identity;
- track-specific visual cues.

Real-time Web Audio analysis may supplement structured HAZE analysis.

---

## 7. Technical baseline

Default production direction:

- Astro + TypeScript for semantic site shell and progressive hydration;
- Three.js for primary 3D rendering;
- GSAP or a validated zero-cost/open alternative for deterministic authored motion;
- Blender for production 3D asset work;
- glTF/GLB for runtime assets;
- Web Audio API for audio state, analysis and synchronization;
- WebGPURenderer only where its fallback behavior is validated;
- WebGL2-compatible fallback as a production requirement;
- Playwright for interaction/browser tests;
- Lighthouse/performance profiling for measurable web quality.

The implementation must remain replaceable at module boundaries. No library becomes architecture authority.

---

## 8. ZERO-COST CAPABILITY ACQUISITION POLICY

**ZERO_COST_REQUIRED = TRUE**

WAVE must first use capabilities already present in Hazewave.

If a required capability is missing or inadequate, WAVE MUST perform focused upstream research before implementing or adding a dependency.

The objective is NOT to accumulate repositories.

The objective is to acquire the smallest, strongest capability set required to ship the best site.

### 8.1 Admission gate for an external project

Before any third-party project becomes a dependency, record:

1. exact problem it solves;
2. why native browser/Three.js/Astro capability is insufficient;
3. repository/project URL;
4. current maintenance state;
5. latest stable release or current supported line;
6. license;
7. commercial-use implications;
8. whether it requires a paid account, SaaS, API key or hosted service;
9. runtime bundle/asset impact;
10. mobile/GPU implications;
11. security/provenance risk;
12. browser support;
13. fallback/exit strategy;
14. whether a smaller dependency can solve the same problem;
15. measured proof that it improves the vertical slice.

If these fields are not known, the dependency is **NOT ADMITTED**.

### 8.2 Repository hygiene

Do NOT:
- clone entire repositories into Hazewave merely for reference;
- vendor demo projects wholesale;
- copy visual identities;
- copy third-party assets without rights;
- add frameworks whose only benefit is convenience;
- add multiple libraries that solve the same problem;
- keep experimental dependencies after rejecting them;
- depend on a remote service when local/client-side execution is viable;
- enable a paid plan to unblock development;
- add a payment method automatically;
- enable metered paid fallback;
- assume "free tier" means permanently zero-cost.

Prefer:
- pinned packages;
- minimal adapters;
- isolated experimental branches;
- small proof-of-capability spikes;
- explicit removal of rejected experiments;
- license and provenance records.

### 8.3 Decision classes

Every researched dependency gets one status:

- **ADOPT** — proven necessary, zero-cost under intended usage, acceptable license and measured value.
- **OPTIONAL** — useful but not required for the baseline.
- **SPIKE_ONLY** — evaluate in isolation; do not ship until evidence exists.
- **REJECT** — unnecessary, risky, duplicative, incompatible, paid/lock-in, or license-problematic.

No dependency is admitted because it is popular or visually impressive.

---

## 9. Research-backed capability shortlist

The following projects are candidates, not blanket approvals.

### ADOPT / strong baseline

**Astro**
- Role: semantic site shell, content, islands/progressive hydration.
- License: MIT.
- Why: lets the immersive surface remain a bounded interactive island rather than turning all content into client JS.
- Source: https://github.com/withastro/astro

**Three.js**
- Role: scene, camera, materials, loaders, rendering.
- License: MIT.
- Why: mature direct 3D web layer; current WebGPURenderer can choose WebGPU and fall back to WebGL2.
- Source: https://github.com/mrdoob/three.js
- Renderer reference: https://threejs.org/manual/en/webgpurenderer.html

**Blender**
- Role: modeling, UV, animation, optimization, asset preparation.
- License: GPL for Blender itself.
- Why: complete zero-cost professional 3D creation suite.
- Source: https://projects.blender.org/blender/blender

**glTF-Transform**
- Role: glTF/GLB inspection and optimization; Meshopt/Draco/texture transforms.
- License: MIT.
- Why: dedicated production asset optimization instead of shipping raw Blender exports.
- Source: https://github.com/donmccurdy/glTF-Transform

**Basis Universal / KTX2**
- Role: GPU texture compression.
- License: Apache-2.0 for the reference encoder/tools with NOTICE obligations.
- Why: reduce transfer and GPU memory for mobile assets.
- Source: https://github.com/BinomialLLC/basis_universal
- Standard context: https://www.khronos.org/ktx/

**Playwright**
- Role: real-browser interaction and regression tests.
- Why: verify click/touch/state/playback flows in browsers rather than relying only on unit tests.
- Source: https://github.com/microsoft/playwright

**Lighthouse**
- Role: performance/accessibility audits.
- License: Apache-2.0.
- Source: https://github.com/GoogleChrome/lighthouse

### ZERO-COST, USE IF IT WINS THE EVALUATION

**GSAP**
- Role: deterministic timelines, MotionPath, Flip, Observer, cinematic choreography.
- Current commercial use is available at zero monetary cost, including previously paid plugins.
- Treat its exact license terms separately from OSI-open-source classification.
- Use only after lockfile/license capture.
- Sources:
  - https://gsap.com/docs/v3/
  - https://webflow.com/blog/gsap-becomes-free

**postprocessing**
- Role: optimized Three.js post-processing.
- License: Zlib.
- Use only effects justified by art direction and measured GPU budget.
- Source: https://github.com/pmndrs/postprocessing

**Motion**
- Role: DOM/UI motion and gestures; possible open-source alternative for some non-3D GSAP work.
- License: MIT.
- Source: https://github.com/motiondivision/motionone
- Current project: https://motion.dev/

**Lenis**
- Role: smooth scrolling only if the final interaction actually needs scroll-driven storytelling.
- License: MIT.
- Do not add merely because showcase sites use it.
- Source: https://github.com/darkroomengineering/lenis

**Meyda**
- Role: lightweight real-time browser audio feature extraction.
- License: MIT.
- Use as a supplemental client analyzer only if HAZE/BRIDGE manifests do not cover the live requirement.
- Source: https://github.com/meyda/meyda

**Tone.js**
- Role: Web Audio scheduling/transport abstractions.
- License: MIT.
- Do not use if native Web Audio solves the playback/scheduling requirement with less code.
- Source: https://github.com/Tonejs/Tone.js

**Theatre.js**
- Role: high-fidelity authored motion workflow.
- Core: Apache-2.0.
- Studio: AGPL-3.0 and current development has temporarily moved to a private repository according to upstream.
- Status: SPIKE_ONLY until maintenance and license boundary are accepted.
- Source: https://github.com/theatre-js/theatre

**Rive runtime**
- Role: vector/state-machine micro-interactions, not main 3D world.
- Runtime: MIT.
- Status: OPTIONAL; no editor/SaaS dependency may become required without a separate cost gate.
- Source: https://github.com/rive-app/rive-runtime

### REJECT BY DEFAULT FOR THIS PRODUCT

**Essentia.js as a shipped browser dependency**
- Powerful audio analysis, but current upstream repository is AGPL-3.0 and warns that APIs are evolving.
- HAZE already owns the primary audio-analysis domain.
- Do not bundle into the public site unless license architecture and need are explicitly reviewed.
- Source: https://github.com/MTG/essentia.js

**Vercel Hobby for public commercial Hazewave deployment**
- Current Vercel terms restrict Hobby to personal/non-commercial use.
- Do not build the production deployment strategy on it.
- Source: https://vercel.com/legal/terms

**Paid Webflow / Spline / proprietary hosted builders as architecture requirements**
- May be used as visual references or optional design tools only when no cost/lock-in is introduced.
- They must not become required runtime infrastructure.

---

## 10. Zero-cost deployment research

For the static/content shell, Cloudflare Pages is a strong candidate:
- static asset requests are currently free and unlimited;
- current Free plan documentation lists 500 builds/month;
- individual Pages static assets have a 25 MiB limit.

Source:
- https://developers.cloudflare.com/pages/functions/pricing/
- https://developers.cloudflare.com/pages/platform/limits/

Media requires separate thinking.

Cloudflare R2 currently includes a monthly free allowance for Standard storage and operations and has no egress charge, but using R2 is a metered product and setup can involve enabling an R2 subscription.

Therefore:

**R2 MUST NOT be activated automatically.**

If R2 is ever proposed:
- prove the free allowance is sufficient for the vertical slice;
- preserve a hard zero-cost operational policy;
- require owner approval before enabling any billing-capable account feature;
- never enable paid overflow;
- monitor storage and request use.

Source:
- https://developers.cloudflare.com/r2/pricing/

GitHub Pages must not be treated as unlimited music hosting. Current documentation describes a 1 GB published-site limit and a 100 GB/month soft bandwidth limit.

Source:
- https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits

For development and QA, use rights-cleared placeholder/demo audio or local test fixtures. Do not commit private artist media or credentials.

---

## 11. Motion quality direction

Primary transitions MUST be authored and deterministic.

For the central music-selection choreography:
- do not use free physics as the final motion authority;
- use explicit paths;
- explicit timing;
- explicit camera choreography;
- explicit terminal state;
- explicit audio synchronization.

Physics can be used for secondary ambience where nondeterminism cannot break the composition.

Quality failures:
- linear UI slides pretending to be cinematic;
- teleportation;
- gratuitous camera movement;
- long transitions before feedback;
- imprecise insertion;
- animation/audio state mismatch;
- excessive bloom;
- particle spam;
- template-like transitions;
- motion that does not communicate state.

The final portion of insert/eject is a critical quality gate:
**alignment + deceleration + contact + sound + light response must land as one event.**

---

## 12. Audio behavior

Playback must be real.

Required:
- user gesture unlocks audio correctly;
- persistent playback across internal site states;
- play/pause/seek are functional;
- track switching is deterministic;
- visual state never falsely claims playback;
- no arbitrary timer chains as source of musical truth;
- use Web Audio timing where precise scheduling is required;
- preserve mastered stereo unless an artistic requirement explicitly changes it;
- spatial audio may be used for interface/mechanical effects.

---

## 13. Asset pipeline

Target:

```
concept/reference
-> Blender
-> final topology / scale / pivots / UV / materials
-> GLB
-> glTF-Transform optimization
-> Meshopt/Draco where justified
-> KTX2/Basis textures where justified
-> visual verification
-> runtime size + GPU measurement
```

AI-generated geometry may accelerate ideation.

It is not automatically production-ready.

No third-party 3D asset ships without:
- rights;
- provenance;
- license compatibility;
- optimization;
- visual QA.

---

## 14. Mobile is first-class

The site must be designed for real touch devices.

Required:
- immediate one-finger selection;
- no essential hover-only state;
- responsive camera composition;
- adaptive pixel ratio;
- adaptive effects quality;
- staged assets;
- stable audio while rendering;
- memory awareness;
- thermal awareness;
- no mobile layout that is simply desktop scaled down.

Samsung A15 is an explicit real-device QA target when runtime access is available.

---

## 15. Performance gate

Measure:
- first meaningful content;
- LCP;
- INP;
- CLS;
- JS transfer;
- GLB transfer;
- texture transfer;
- frame rate;
- frame-time spikes;
- memory pressure where measurable;
- audio-start latency;
- transition latency;
- mobile thermal degradation.

Loading order should be staged:

1. semantic HTML / brand frame;
2. critical Deck representation;
3. selected/nearest interactive assets;
4. secondary artist assets;
5. optional post-processing.

WAVE must reduce effect quality before accepting poor interaction latency.

---

## 16. Accessibility / fallback

Required:
- `prefers-reduced-motion` behavior;
- semantic artist and track information outside the canvas;
- keyboard-accessible playback and selection;
- functional non-WebGL path;
- animation cannot be the only source of application state;
- controls have accessible names;
- visual contrast remains usable.

Reduced motion should preserve the concept while removing large camera travel, aggressive parallax and unnecessary spatial motion.

---

## 17. Research workflow for every missing capability

When WAVE encounters a missing capability:

```
DEFINE THE GAP
-> SEARCH UPSTREAM
-> IDENTIFY 3-5 REAL CANDIDATES
-> VERIFY LICENSE
-> VERIFY MAINTENANCE
-> VERIFY ZERO-COST STATUS
-> CHECK BROWSER/MOBILE SUPPORT
-> MEASURE BUNDLE / PERFORMANCE
-> BUILD ISOLATED SPIKE
-> COMPARE AGAINST NATIVE IMPLEMENTATION
-> ADOPT ONE OR ADOPT NONE
-> REMOVE REJECTED EXPERIMENTS
-> RECORD DECISION
```

Research must prioritize:
1. official project documentation;
2. upstream repository;
3. release/changelog;
4. standards bodies;
5. browser/platform documentation;
6. proven production references.

Do not select tools from affiliate listicles or social hype.

---

## 18. Cost guard

The owner requirement is maximum quality with zero development/runtime software cost wherever feasible.

Rules:
- no paid dependency by default;
- no paid fallback;
- no automatic billing enablement;
- no trial that silently converts to paid;
- no required SaaS whose useful path is paywalled;
- no metered service without an owner-approved hard cost boundary;
- if a free tier can incur overage, treat it as billing-capable and fail closed;
- a free/open-source local tool is preferred to a hosted paid dependency when quality is equivalent;
- quality must not be reduced merely to avoid a paid library if a professional open/free alternative exists: research harder first.

Zero-cost does not mean pretending infrastructure is free forever.

If real public traffic exceeds a free allowance, WAVE must report the capacity boundary with measured evidence instead of silently creating cost.

---

## 19. Required implementation outputs

WAVE must produce code, not only prose.

Required repository outputs:

- site application directory;
- typed artist/track content model;
- renderer abstraction;
- Resonance Deck scene;
- module selection state machine;
- deterministic insert/eject choreography;
- persistent audio controller;
- HAZE/WAVE bridge adapter surface;
- reduced-motion mode;
- non-WebGL fallback;
- performance instrumentation;
- browser tests;
- dependency/license inventory;
- upstream capability decision log.

Every dependency added to the site must have a recorded admission decision.

---

## 20. Acceptance gates

### Interaction gate
A single tap/click produces immediate feedback and a polished deterministic transition into playback state.

### Originality gate
No cassette/iPod clone and no third-party showcase copied as the product identity.

### Audio gate
Real playback state and visual state agree.

### Mobile gate
Core experience works on a real touch device.

### Performance gate
No obvious jank in the primary transition on the target quality tier; measurements are recorded.

### Accessibility gate
Reduced-motion, keyboard and fallback paths work.

### Cost gate
No required paid service or paid fallback.

### Dependency gate
Every added external project has a license, provenance, maintenance and measured-value record.

### Quality gate
The owner reference is the floor. If the result does not clearly feel more professional, WAVE iterates rather than declaring completion.

---

## 21. Immediate execution order

1. Refresh the candidate branch HEAD.
2. Inspect existing WAVE/Living Resonance architecture and do not overwrite legitimate work.
3. Create the site application in an isolated path.
4. Implement the smallest working shell with semantic content and the renderer boundary.
5. Implement one Resonance Module and one Deck interaction end-to-end.
6. Add real playback state using rights-cleared demo/test audio.
7. Profile mobile.
8. Research only capabilities proven missing by the slice.
9. Run the capability admission gate before adding each dependency.
10. Expand to 3 artists × 2 tracks only after the first interaction meets the quality bar.
11. Add Playwright/performance/accessibility validation.
12. Record exact HEAD, changed files, dependency decisions, validation results and unresolved blockers.
13. Do NOT promote to canonical or publish publicly without explicit authorization.

---

## 22. Non-negotiable definition of done

This mission is not done when WAVE can explain how to make the site.

It is done when a human can open the built vertical slice, tap a song, watch an original Hazewave object perform a premium cinematic transition into the music system, hear real playback, switch artists/tracks, and experience the same quality on desktop and mobile within the defined fallbacks — with zero-cost tooling/runtime choices proven and documented.
