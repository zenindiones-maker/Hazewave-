# WAVE DESIGN FRONTIER 2026

**Status:** AUTHORITATIVE DEVELOPMENT STANDARD  
**Owner:** WAVE  
**Applies to:** Hazewave interactive sites, spatial UI, web motion, 3D/2D interactive experiences  
**Cost policy:** zero-monetary-cost by default; open-source first where quality is equivalent  
**Primary product:** `apps/hazewave-site`

## 1. Purpose

WAVE is not a generic frontend agent.

WAVE is the Hazewave visual-design authority and must operate as a senior multidisciplinary creative-technology studio covering:

- interaction design;
- visual art direction;
- industrial/product design for digital objects;
- typography and editorial composition;
- motion direction;
- 3D modeling and rendering;
- shader/VFX design;
- responsive spatial composition;
- touch interaction;
- accessibility;
- performance engineering;
- production web architecture.

The quality target is not "a website that works".

The target is an authored, tactile, cinematic, responsive experience whose interaction is clear without explanation and whose implementation remains measurable, accessible and performant.

## 2. 2026 research conclusion

The strongest architecture for Hazewave is a **hybrid progressive-enhancement stack**, not a single bleeding-edge renderer.

### Production baseline

- Astro 7.x: semantic HTML shell, SEO, content, islands.
- Three.js current: scene graph and 3D runtime.
- WebGL2: guaranteed production fallback.
- GSAP: primary authored choreography/timeline engine.
- Web Audio API: playback graph, analysis, timing.
- Blender 4.5 LTS or later validated LTS: final production assets.
- glTF/GLB: runtime asset format.
- KTX2/Basis Universal: GPU texture distribution.
- meshoptimizer/glTF-Transform: mesh and asset optimization.
- Playwright: interaction/browser proof.

### High-tier 2026 enhancement

- Three.js `WebGPURenderer`.
- Three Shading Language (TSL).
- Node materials.
- WebGPU compute.
- WebGPU post-processing where measured:
  - selective bloom;
  - basic/quality DoF;
  - SSGI only on capable devices;
  - motion blur only if it materially improves the shot;
  - GPU particles only when they serve art direction.

WebGPU is an enhancement, never the only path.

Three.js currently documents that WebGPURenderer can use WebGPU and fall back to WebGL2, but remains experimental. The production architecture therefore keeps renderer-specific implementation behind an adapter.

## 3. Motion decision

### ADOPT — GSAP as primary cinematic choreography engine

Reason:

- deterministic timelines;
- interruption/cancellation control;
- precise sequencing;
- MotionPath;
- Flip;
- Observer;
- SplitText;
- mature browser behavior;
- framework agnostic;
- current zero-cost commercial usage including formerly paid plugins.

Use GSAP for:
- object selection choreography;
- camera/object synchronization;
- Deck anticipation;
- insert/eject/contact timelines;
- DOM/3D synchronized transitions;
- artist-world transitions.

Do not use uncontrolled physics as authority for primary transitions.

### OPTIONAL — Motion

Motion has first-class Three.js/TSL integration and can animate Object3D, materials, shader uniforms and TSL nodes.

Do not ship both GSAP and Motion for the same responsibility.

Use Motion only if an isolated spike proves a concrete advantage for a bounded feature.

## 4. Rendering frontier

### HIGH / ULTRA

Investigate and benchmark:

- WebGPURenderer;
- TSL node materials;
- compute-driven particles;
- GPU audio-reactive fields;
- selective bloom;
- high-quality DoF;
- SSGI;
- advanced refraction/transmission;
- clustered/dynamic lighting where needed;
- FSR/TAAU/upscaling only if it improves measured quality/performance.

### LOW / MEDIUM

Prefer:

- WebGL2;
- baked/limited lighting;
- simple contact shadows;
- no expensive transparent layers;
- restrained particle counts;
- compressed textures;
- lower internal DPR;
- simpler materials;
- no SSGI;
- no expensive DoF;
- deterministic composition instead of effect density.

A15 is an explicit LOW-tier physical benchmark.

## 5. Interaction design standard

Every important interaction must define:

1. **affordance** — user understands what can be touched;
2. **immediate feedback** — input is acknowledged inside one visual frame where possible;
3. **anticipation** — the destination/device reacts before contact;
4. **trajectory** — deliberate authored path;
5. **mass** — easing matches the apparent object;
6. **alignment** — object visibly resolves to the target;
7. **contact** — visual + sound + optional haptic converge;
8. **state transition** — application state changes at a defined boundary;
9. **settle** — camera/object/environment return to stable composition;
10. **reversibility** — interruption and track switching do not corrupt state.

A beautiful object with weak interaction is a FAIL.

A technically complex scene with unclear affordance is a FAIL.

## 6. Spatial composition

Hazewave must read as a spatial music experience, not as a flat site with a 3D widget.

Primary scene hierarchy:

1. hero media/player object;
2. collectible track/release objects;
3. artist-world environment;
4. semantic DOM content and controls as supporting layer.

On mobile the 3D stage remains the protagonist.

Avoid long card stacks above the core interaction.

## 7. 2026 browser-native capabilities to use

### View Transition API

Use progressively for DOM state continuity and same-origin navigation.

Never make it required for core correctness.

### CSS scroll-driven animation

Use for secondary editorial sections where scroll truly communicates progression.

Do not force the main track-selection choreography onto scroll.

### Pointer Events

Use one pointer model for touch, mouse and pen.

Touch is first-class.

### Vibration API

Optional progressive enhancement for contact/haptic confirmation.

Never rely on it because browser support is limited.

### OffscreenCanvas

Evaluate for:
- procedural texture generation;
- secondary canvas work;
- expensive non-DOM visual computations.

Do not move the primary renderer to a worker unless profiling proves the main thread is the bottleneck and target-browser behavior is validated.

### AudioWorklet

Use for low-latency custom audio processing/analysis that should not block the main thread.

HAZE semantic analysis remains authoritative.

### WebCodecs

Optional for future video-heavy artist experiences requiring frame-level processing.

Do not add to the first music interaction without a real requirement.

## 8. 2D interactive graphics

### OPTIONAL — Rive runtime

Rive web runtimes are MIT and support interactive animations/state machines.

Use only for:
- small interactive HUDs;
- microinterfaces;
- icon/state animation;
- lightweight 2D character/graphic moments.

Do not use Rive as a substitute for the main Three.js spatial world.

The hosted/editor product must not become a mandatory paid runtime dependency.

## 9. Authoring tools

### Blender — ADOPT

Final 3D asset studio.

WAVE must learn and use:
- product modeling;
- bevel discipline;
- UV;
- procedural materials;
- Geometry Nodes where useful;
- animation;
- camera;
- lighting;
- baking;
- export to glTF;
- pivot/origin discipline;
- LOD authoring;
- texture budgets.

### Penpot — OPTIONAL AUTHORING / DESIGN SYSTEM

Open-source, self-hostable design platform.

Useful for:
- responsive UI system;
- component states;
- typography;
- grid;
- design tokens;
- accessible UI specs;
- collaborative design documentation.

It is not a runtime requirement.

### Vector/raster creation

Prefer open formats and zero-cost tooling.

Assets must remain exportable and pipeline-safe.

## 10. Asset frontier

Production pipeline:

```
concept
-> Blender/source asset
-> topology/pivots/UV
-> glTF/GLB
-> meshoptimizer / glTF-Transform
-> KTX2/Basis textures
-> visual diff
-> size/GPU measurement
-> tier assignment
```

Use instancing when repeated geometry exists.

Use LOD where the same object appears at materially different screen sizes.

Do not ship raw Blender exports.

Do not use 4K textures when the object occupies a small mobile region.

## 11. Advanced technologies deliberately not adopted by default

### Gaussian splatting

Three.js now includes WebGPU Gaussian-splat examples.

Status: EXPERIMENTAL / PROJECT-SPECIFIC.

Use only if Hazewave needs scanned/photoreal spatial environments.

Do not use because it looks fashionable.

### WebXR

Status: FUTURE / OPTIONAL.

WebXR and WebGPU-backed XR remain uneven across devices.

Do not burden the first public music experience with XR.

### Physics engines

Status: SECONDARY ONLY.

Rapier/Jolt/etc. may be used for secondary ambient motion.

Primary selection/insertion remains authored.

### Babylon.js / PlayCanvas engine migration

Both are strong engines and support WebGPU.

Do not migrate from Three.js without measured evidence of a blocking deficiency.

Architecture stability matters.

## 12. Artist-world system

Each artist must have a typed **Visual Identity Manifest** controlling more than color:

- palette;
- tone mapping intent;
- environment;
- material family;
- surface roughness/metalness logic;
- typography;
- light temperature;
- camera behavior;
- particle/VFX grammar;
- motion signature;
- transition signature;
- sonic-reactivity mapping;
- reduced-motion variant;
- LOW/MEDIUM/HIGH/ULTRA variants.

New artists should be addable without editing renderer core logic.

## 13. Audio-reactive design

Do not create generic frequency-bar visualizers.

Visual response hierarchy:

```
HAZE semantic analysis
+ musical section/beat events
+ live Web Audio signal
+ artist visual identity
= WAVE visual direction
```

Examples:

- section change -> world state;
- downbeat -> physical Deck response;
- chorus/drop -> controlled environmental expansion;
- vocal/motif event -> material/light motif;
- energy change -> subtle camera/light density;
- transient -> micro-contact/particle response.

Real-time amplitude alone is insufficient.

## 14. Performance as art direction

Performance is part of design.

Every effect receives:
- visual-value score;
- GPU cost;
- CPU cost;
- memory cost;
- bandwidth cost;
- fallback.

If removing an effect improves clarity and responsiveness, remove it.

A15 LOW-tier current evidence showed roughly 44–55 FPS in IDLE with p95 frame times around 37–57 ms in Firefox. Therefore LOW must be simplified before adding costly effects.

Targets:

- capable hardware: 60 FPS;
- supported low tier: stable 30 FPS minimum in the main transition;
- no input-latency spikes that make the interaction feel broken;
- no visual effect may hide bad frame pacing.

## 15. WAVE expertise curriculum

WAVE must continuously deepen competency in:

### Visual design
- composition;
- contrast;
- typography;
- editorial hierarchy;
- responsive systems;
- color science;
- branding;
- accessibility.

### Product / industrial design
- silhouette;
- material hierarchy;
- affordance;
- physical plausibility;
- mechanisms;
- contact/assembly;
- product lighting.

### Motion
- timing;
- spacing;
- anticipation;
- follow-through;
- overlap;
- easing;
- camera choreography;
- interruption;
- continuity.

### 3D
- modeling;
- materials;
- lighting;
- camera/lens language;
- shaders;
- post;
- optimization.

### Creative development
- Three.js;
- WebGPU;
- TSL;
- Web Audio;
- GSAP;
- browser APIs;
- profiling;
- testing.

### Production
- accessibility;
- Core Web Vitals;
- mobile thermal/memory constraints;
- fallback architecture;
- provenance/license review.

## 16. Daily frontier research rule

WAVE may update its knowledge daily, but must not convert novelty into dependencies automatically.

Daily research sources should prioritize:

1. official browser/platform docs;
2. Three.js documentation/examples/releases;
3. WebGPU/W3C/Khronos standards;
4. upstream GitHub projects;
5. Blender release notes;
6. motion/design-tool upstream documentation;
7. strong production case studies.

Every new technique receives:

- relevance;
- maturity;
- license;
- cost;
- browser support;
- A15 impact;
- spike result;
- ADOPT / OPTIONAL / SPIKE_ONLY / REJECT.

## 17. Hazewave site immediate architecture decision

For the next redesign iteration:

### ADOPT NOW
- Astro semantic shell;
- DOM/CSS + GSAP as the renderer-independent core interaction layer;
- Web Audio;
- current typed state/content architecture;
- View Transitions progressive enhancement where useful;
- Three.js as a bounded HIGH/ULTRA visual capability, not core authority;
- Blender asset pipeline for final product-grade 3D assets;
- glTF optimization pipeline for optional higher-tier 3D.

Evidence rule: the A15 LOW proof demonstrated that a heavy WebGL core can consume frame budget without delivering equivalent visual value. The production interaction therefore stays semantic and cinematic in DOM/GSAP, while Three.js/WebGPU may enhance capable devices only after measured proof.

### SPIKE NOW
- WebGPURenderer + TSL HIGH-tier ambient/product layer;
- one compute/VFX experiment driven by HAZE/WAVE data;
- one selective post-processing chain;
- Rive for one bounded 2D microinteraction only if it beats CSS/SVG.

### DO NOT ADD YET
- physics engine;
- React/R3F;
- Babylon/PlayCanvas migration;
- Gaussian splatting;
- WebXR;
- WebCodecs;
- large post-processing stacks.

## 17.1. Owner review gate

The owner is not a substitute for internal visual QA.

Do not repeatedly ask the owner to inspect raw engineering checkpoints, prototype geometry, debug-heavy screenshots or visually rejected directions.

Before requesting owner visual review, WAVE must internally prove:

- normal-mode screenshot contains no diagnostics/debug/prototype chrome;
- idle composition is deliberately art-directed;
- PLAYING composition is deliberately art-directed;
- selected media remains visually legible through travel/contact/dock;
- interaction is understandable without explanatory text;
- mobile is designed as its own composition;
- desktop is not merely the mobile layout widened;
- motion is captured in browser proof and reaches coherent PLAYING state;
- accessibility/reduced-motion remains functional;
- CI and repository contracts are green;
- initial runtime is within the declared performance/bundle budget;
- WAVE itself judges the result as suitable to show as a premium creative-technology prototype.

If any item fails:

`OWNER_VISUAL_REVIEW_READY=FALSE`

Continue iteration without asking the owner to inspect it.

Only after all items pass may WAVE set:

`OWNER_VISUAL_REVIEW_READY=TRUE`

This gate does not mean the design is final. It means the result is finally worth the owner's review.

## 18. Definition of frontier quality

The result passes only when:

- the user immediately understands what to touch;
- the chosen object behaves like a designed physical artifact;
- animation feels authored, not generic;
- sound/visual/contact state agree;
- each artist creates a recognizably different world;
- mobile feels designed rather than reduced;
- advanced effects disappear gracefully on LOW;
- the experience remains semantic and accessible;
- real-device metrics remain within the declared tier budget;
- no technology is present only to impress engineers.

**The purpose of advanced technology is to make the experience feel inevitable, not to make the stack look complicated.**


## 19. Research refresh — 2026-10-07

Current upstream research was refreshed before the next implementation pass.

### GSAP MotionPath — ADOPTED FOR THE CORE INSERTION ARC

Official reference:
https://gsap.com/docs/v3/Plugins/MotionPathPlugin/

Why:
- supports authored curved trajectories rather than generic linear x/y travel;
- keeps timing deterministic;
- allows the media object to move through a designed path while application state stays independent;
- does not require physics or drag precision.

Implementation consequence:
the selected music object now travels through a controlled multi-point path, aligns, inserts and docks. Ejection uses a deliberate return path.

### GSAP Flip — APPROVED FOR A FUTURE BOUNDED STATE SWAP

Official reference:
https://gsap.com/docs/v3/Plugins/Flip/

Useful for:
- future artist/release layout morphs;
- continuity between archive and focused views;
- interruption-safe state changes.

Status:
OPTIONAL. Do not add until a concrete layout transition benefits from it.

### Browser View Transitions — ADOPTED AS PROGRESSIVE ENHANCEMENT

Official references:
https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API
https://developer.mozilla.org/en-US/docs/Web/API/Document/startViewTransition

Current platform status:
document-scoped same-document transitions are broadly available in current browsers, with newer typed transition capabilities continuing to mature.

Rule:
never make correctness depend on View Transitions. The DOM update path must remain normal and accessible without them.

### CSS scroll-driven animation — ADOPTED FOR NON-CRITICAL EDITORIAL MOTION

Official reference:
https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Scroll-driven_animations

Why:
- declarative;
- progressive;
- avoids unnecessary scroll listeners;
- suitable for the artist archive below the interactive stage.

Rule:
music selection/insertion remains GSAP/state-machine driven. Scroll timelines are only for editorial/progressive motion.

### Three.js WebGPURenderer / TSL — HIGH/ULTRA ONLY

Official reference:
https://threejs.org/manual/pages/webgpurenderer

Current upstream reality:
- WebGPU-first with WebGL2 backend fallback;
- TSL/node materials and newer post-processing are strong;
- upstream still describes the renderer as experimental and acknowledges cases where WebGLRenderer is faster or more complete.

Decision:
keep the renderer-independent DOM/GSAP core. Use WebGPU/TSL only for optional measured visual enhancement on capable hardware.

### AudioWorklet — OPTIONAL, NOT REQUIRED YET

Official references:
https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet
https://developer.mozilla.org/en-US/docs/Web/API/AnalyserNode

Current need:
the present interaction only needs stable playback, semantic HAZE section data, BPM timing and lightweight real-time energy.

Decision:
AnalyserNode remains sufficient for V1. AudioWorklet becomes ADOPT only when custom low-latency processing or analysis must leave the main thread.

### Creative-development benchmark scan

Current 2026 Codrops work reinforces several useful patterns without becoming code authority:

- selective WebGPU/TSL for advanced effects;
- GSAP MotionPath/Flip for authored continuity;
- Blender-authored camera/path work for cinematic 3D;
- audio-reactive systems that combine Web Audio with deliberate art direction;
- persistent GPU scenes only where they materially improve continuity;
- progressive rather than mandatory GPU complexity.

Evidence source:
https://tympanus.net/codrops/hub/tutorials/

WAVE rule:
study techniques, not templates. No demo or showcase becomes a dependency or visual identity source by default.

## 20. Current design consequence

The site is no longer being treated as a 3D-engine showcase.

The premium path is:

semantic Astro shell
+ typed artist/music content
+ deterministic GSAP physical choreography
+ real Web Audio state
+ HAZE BPM/section semantics
+ artist-specific procedural art direction
+ progressive browser-native transitions
+ optional higher-tier GPU enhancement

This is the current evidence-based design spine.
