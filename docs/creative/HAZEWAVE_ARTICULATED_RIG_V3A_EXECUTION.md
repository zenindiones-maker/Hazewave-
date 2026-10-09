# WORK — HAZEWAVE / WAVE / ARTICULATED RIG V3A

**EXECUTE, NOT PLAN.** Preserve the approved 2D cosmic cartoon visual identity, assets, author logos, Harness governance and present repository. Work only on `zenindiones-maker/Hazewave-`, in isolated candidate `work/wave-articulated-rig-v3a`; the current main/home/Termux A15 are out of scope. No paid services, second Codespace, new repository, secrets, main merge or publishing. Avoid `git reset`, force push, delete, recreating AGENTS.md or architecture restart.

## Canon

Read `AGENTS.md`, `docs/creative/HAZEWAVE_LIVING_UNIVERSE_CANONICAL_IDENTITY.md`, `docs/creative/HAZEWAVE_HAND_DRAWN_SCROLLOLOGY_V3.md`, and `docs/creative/HAZEWAVE_V3_PRODUCTION_ASSET_HANDOFF.md`. Respect Harness authority. HAZE is not involved: this is exclusively the WAVE website/animation domain.

The owner-approved art comes from original sources in ChatGPT Library `/Hazewave/Living-Universe/V3-CANONICAL-ASSETS/` and `/APPROVED_ILLUSTRATED_LAYERS/`. The rig proof is `/Hazewave/Living-Universe/Articulated-Rig-V3A/` as `HAZEWAVE-ARTICULATED-RIG-V3A-COMPLETO.zip`. **The Library must be materialized or the ZIP uploaded to the Codespace before running the site. Do not silently assume binaries are already in GitHub.**

## Already built; verify before changing

The source archive contains:
- `site/rig-manifest.json`: exact owner-art provenance and pivots for **24 articulated assets**: 12 true source pads + 12 energized overlays, 8 real knob caps, 4 speaker membranes;
- `site/assets/chassis_clean.webp`: separately reconstructed base for displaced parts;
- `site/assets/painterly_fog.webp`, `site/assets/cosmos_reference.webp`, official logos, cutout for display;
- `site/index.html`, `site/engine.js`: mobile-first isolated scroll demo with deterministic scroll state + independent ambient time + reversible SVG path;
- `source/build_assets.py`: rebuilds the physically articulated assets from approved original illustration, without changing master;
- `source/browser_verify.py`: reproducible Chromium visual/behavior regression;
- `proof/BROWSER_QA.json`: results from 360×800, 393×852 and 1280×800;
- `HAZEWAVE-RIG-V3-ABRIR.html`: completely standalone preview, no Codespace required;
- `HAZEWAVE-RIG-V3-SCROLL-REAL.mp4`: actual browser frame recording from top to bottom and back.

Initial isolation is a mechanism proof, **not** an aesthetically approved 10/10 site. Do not recycle the static vector MPC/ellipse prototype.

## Immediate mission: finish the high-fidelity 2D rig

1. Verify source SHAs and inspect `rig-pivots.jpg` against full-resolution owner artwork. Inspect halos/transparency and contact shadows, correct inaccurate masks by editing source polygons (not master image).
2. Upgrade **pad mechanics**: separately rendered pad body and pad face, pressed/unpressed displacement in original perspective, shadows/rim highlights, 12 unique energy timings from one causal source curve. The idle-to-on transition must maintain original brush style. Add independently controllable white/purple side-strikes.
3. Upgrade **knobs/faders**: create 2–3 actual painted poses and correct inpainting of their mounting sockets. Rotating a symmetric cap without a painted reference mark is insufficient. Move an actual fader slider along its mechanical travel, with matching shadow.
4. Upgrade **speakers/cables**: independent cone deformation/scale and energy that physically traverses original cable shapes; no random glowing line disconnected from the illustration.
5. Upgrade **fog/occlusion**: at least three clean alpha planes with distinct drift and correct foreground/background hiding. Repair black or jagged matte edges. No generic purple gradient as a substitute.
6. Camera and sonic path: use source-art space coordinates, a stable mobile crop, and progress-driven SVG trace `stroke-dasharray` / `stroke-dashoffset`. Every impact activates only hardware reached by the wave. All states must be a pure deterministic function of `progress`, plus optional subtle idle time. The resulting scene must be visually different as drawing, not just zoom or fade.
7. Integrate in an isolated Astro route **only once the media files are present**, preferably reusing pinned `gsap@3.15.0` and `pixi.js@8.21.0`, without changing shared package budgets, existing home, HAZE modules or canon. Keep source-path manifest; avoid adding another rendering engine.
8. Validate Chromium touch emulation 360×800, 393×852 and desktop with forward and backward scroll; verify at p=[0,.2,.45,.7,1,.45,0] that pad/knob/speaker counts and path are monotonic and return to zero. Also verify stationary ambient motion, `prefers-reduced-motion`, image integrity and 0 console errors.
9. Capture uncut visual browser recording on mobile and at least 5 screenshots; run an adversarial art review against The Boat and Ponpon Mania principles. If the artwork still looks like a slide or zoom, FAIL and improve, rather than declaring finished.
10. Preserve each accepted checkpoint in GitHub isolated development branch; send proof link and exact HEAD after verified. No publishing until explicit owner approval; only after owner approves a public HTTPS URL should a QR pointing to it be generated.

## Stop gates

- Never invent an external specialist endorsement or say `10/10` without the owner.
- No separate Codespace, paid products, downloads or installs on A15.
- No creation of additional poster scenes as a substitute for real mechanical motion.
- No modifying logos' source bytes.
- Any attempted CI/push/publish must report actual results, failures, and exact SHA.

## Required output

A **real** mobile-first playable animated proof using approved pixels with independent articulated parts, an inspected video, browser test receipts and a GitHub development checkpoint. No empty design-only delivery.