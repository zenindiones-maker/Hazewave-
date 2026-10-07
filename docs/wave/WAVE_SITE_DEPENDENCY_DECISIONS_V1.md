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

## ADOPT — Three.js r186 / npm 0.186.0

Problem: production 3D scene graph, camera, materials, raycasting and WebGL rendering.

Why native WebGL is insufficient: direct WebGL would require rebuilding scene graph, geometry/material abstractions, loaders, color management and raycasting without a product-quality advantage.

License/cost: MIT. Client-side runtime. No SaaS requirement.

Decision: ADOPT.

Renderer note: the first slice deliberately uses `WebGLRenderer` behind a local `RendererAdapter`. Upstream's `WebGPURenderer` can automatically use WebGPU with a WebGL2 backend fallback, but upstream still describes it as experimental. WebGPU is therefore a later measured migration, not a launch dependency.

## ADOPT — native deterministic choreography for first slice

Problem: deterministic module travel, alignment, insertion and ejection.

Implementation: requestAnimationFrame + Three.js curves/quaternions + explicit easing + an application state machine.

Reason: the first working implementation does not yet prove a gap that requires a second animation runtime.

Decision: ADOPT for the first slice, subject to measured comparison before final art lock.

## SPIKE_ONLY — Motion 14.x

Current upstream research: Motion 14 was released in October 2026. Recent Motion releases include Three.js-oriented effects.

Potential advantage: compact animation primitives and Three.js integration.

Current reason not to ship: the native deterministic implementation must first be profiled. A second animation runtime is unjustified until it demonstrates a measurable authoring, cancellation, reversibility or performance advantage.

Decision: SPIKE_ONLY / not installed.

## SPIKE_ONLY — GSAP

Potential advantage: mature authored timelines, MotionPath-style choreography and sequencing.

Current reason not to ship: zero-cost availability does not make an additional runtime necessary. License must be captured separately from OSI open-source classification, and native/Motion alternatives must be measured first.

Decision: SPIKE_ONLY / not installed.

## ADOPT — Playwright 1.63.0

Problem: browser-level regression proof for selection, playback state, reduced motion and mobile emulation.

License/cost: Apache-2.0. Local/CI execution; no hosted service required.

Decision: ADOPT as a development dependency.

## REJECT FOR NOW

React / React Three Fiber / Drei / Rapier / Theatre.js / Tone.js / Meyda / Lenis / postprocessing / Spline runtime / Rive runtime.

Reason: no demonstrated gap in the first implementation requires them. Re-evaluate only when a concrete capability gap exists.

## Zero-cost status

No payment method, paid SaaS, metered runtime service, commercial template or proprietary hosted builder is required for this vertical slice.
