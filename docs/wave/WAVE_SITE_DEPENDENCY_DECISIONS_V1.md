# WAVE Site Dependency Decisions V1

Status: DEVELOPMENT EVIDENCE  
Scope: `apps/hazewave-site`  
Branch: `work/wave-hazewave-site-v1`

This log records the bounded dependency decisions for the first Hazewave interactive music vertical slice. It does not grant execution authority.

## ADOPT — Astro 7.3.0

Problem: production HTML-first shell, routing, static build and bounded client hydration.

Why native HTML alone is insufficient: the site needs a maintainable build/content boundary while preserving semantic HTML outside the immersive renderer.

License/cost: Astro upstream is MIT and locally buildable. No paid hosted service is required.

Decision: ADOPT.

## ADOPT — Three.js r186 / npm 0.186.0 as a tiered visual capability, not core interaction authority

Problem: advanced 3D scene graph, materials, shaders, GLB assets, camera work and future WebGPU/TSL layers.

Evidence update: the first A15 proof showed the initial WebGL LOW scene running only around 23–55 FPS with poor frame pacing while still looking materially below the target art direction. Replacing the core mobile interaction with semantic DOM + CSS + GSAP reduced the shipped JS from roughly 680 kB to about 91 kB and produced a substantially stronger visual composition.

Decision: ADOPT Three.js for bounded HIGH/ULTRA visual layers, GLB/product assets and later measured WebGPU/TSL work. DO NOT require it for the core music-object interaction on LOW/MEDIUM.

Core selection/insertion/playback choreography is now renderer-independent and lives in the DOM/GSAP layer. This preserves clarity, accessibility and performance while allowing Three.js to enhance—not own—the experience.

License/cost: MIT. Client-side runtime. No SaaS requirement.

Renderer note: `WebGPURenderer` remains a measured enhancement behind an adapter. WebGPU must never be required for correctness.

## ADOPT — GSAP 3.15.0 primary authored choreography

Problem: the owner rejected the first native-rAF prototype as technically functional but below the required interaction/motion quality. The product now needs a dedicated cinematic timeline system with robust sequencing, interruption, reverse/eject behavior, DOM/3D synchronization and path authoring.

Why native requestAnimationFrame is no longer sufficient as the primary authoring layer: the first slice proved that custom interpolation can make the state machine work, but it creates too much bespoke timeline/cancellation logic for the level of choreography now required.

Capabilities selected:
- core timelines;
- MotionPath for explicitly authored trajectories;
- Flip for DOM continuity where useful;
- Observer only where unified gesture velocity/direction materially improves interaction;
- SplitText only for bounded editorial motion.

Current upstream package version researched: 3.15.0.

License/cost: GSAP uses GreenSock's current standard no-charge license. Webflow/GSAP state that the full toolset, including formerly paid plugins, is free and the standard license covers commercial use. It is not being classified as OSI open-source; it is admitted because the owner requires zero monetary cost plus maximum quality.

Decision: ADOPT.

Migration rule: replace primary home-grown choreography incrementally behind a local motion adapter. Do not let GSAP become application-state authority.

## SPIKE_ONLY — Motion current line

Current upstream documentation now provides direct Three.js integration for Object3D transforms, materials, shader uniforms and TSL uniform nodes, with sequence support.

Potential advantage: compact open-source motion primitives and first-class Three.js/TSL binding.

Reason not to ship beside GSAP: two overlapping motion engines would increase bundle and conceptual complexity without proven product value.

Decision: SPIKE_ONLY / not installed. Re-evaluate only for a bounded feature where it clearly outperforms the GSAP implementation.

## ADOPT — Playwright 1.63.0

Problem: browser-level regression proof for selection, playback state, reduced motion and mobile emulation.

License/cost: Apache-2.0. Local/CI execution; no hosted service required.

Decision: ADOPT as a development dependency.

## OPTIONAL / SPIKE-ONLY 2026 FRONTIER

**Rive runtime — OPTIONAL.** MIT open-source runtime with interactive state machines. Candidate only for small 2D HUD/microinteraction surfaces, never as main 3D authority.

**Three.js WebGPURenderer + TSL — SPIKE_ONLY for HIGH/ULTRA.** Upstream supports WebGPU with WebGL2 fallback, TSL/node materials, compute and a modern post stack, but still describes the renderer as experimental. Keep WebGL2 production fallback.

**OffscreenCanvas — SPIKE_ONLY.** Use for procedural/secondary canvas work if profiling proves main-thread contention.

**AudioWorklet — OPTIONAL/ADOPT WHEN NEEDED.** Use for low-latency custom analysis/processing off the main thread; HAZE semantic analysis remains authoritative.

## REJECT FOR NOW

React / React Three Fiber / Drei / Rapier / Theatre.js / Tone.js / Meyda / Lenis / postprocessing / Spline runtime / Babylon migration / PlayCanvas migration / WebXR / Gaussian splatting.

Reason: no demonstrated product gap in the current music interaction justifies their runtime cost or architecture disruption. Re-evaluate only from a concrete measured gap.

## Zero-cost status

No payment method, paid SaaS, metered runtime service, commercial template or proprietary hosted builder is required for this vertical slice.
