# WAVE — Articulated Station V3A

**Isolated evidence candidate, not a finished website or an owner-approved experience.**

The original owner-approved dark cosmic 2D music production illustration has been rigged into **24 independently mounted moving parts** (12 illustrated MPC pads, 8 true knob caps and 4 speaker membranes). Twelve additional recolored pad states are carried as optional on-state sprites. The chassis has a filled underlayer for pad/knob displacement; all original sources and two logos remain unchanged. The attached `rig-manifest.json` contains per-part coordinates, pivot position, source SHA-256 and activation time.

## How to inspect without installing software on A15

The **complete** HTML with all images embedded exists at:
- `apps/hazewave-site/public/experimental/articulated-rig-v3a.html`

The GitHub version is a single self-contained HTML (media bytes inlined), so the compiled Astro build can serve `/experimental/articulated-rig-v3a.html`. This is *not* the existing homepage and is *not* production-published.

Editable source, 24-piece manifest, QA receipt and reproducible extraction script are also in `docs/prototypes/wave-articulated-rig-v3a/`. The full set of individual image assets and the original art references are stored in the user's persistent ChatGPT Library:

`/Hazewave/Living-Universe/Articulated-Rig-V3A/HAZEWAVE-ARTICULATED-RIG-V3A-COMPLETO.zip`

**Do not claim the standalone HTML is the full site**. It demonstrates causal pad lighting, physical displacement, independent knob rotation, speaker membrane scale, SVG waveform trace, inpainting and independently drifting nebula. It is a first physical-art rig; five-act integrated world and cinematic transitions still require human review and further production.

## Measured validation

Local Chromium `page.set_content` of exported HTML:
- 360×800, 393×852 and 1280×800: no JS exceptions, no horizontal overflow.
- p=0 → .2 → .45 → .7 → 1 → .45 → 0: activated pad counts 0/2/6/11/12/6/0; knob counts 0/0/4/8/8/4/0; speaker counts 0/0/1/3/4/1/0.
- SVG path rises to 100% and reverses to 0%.
- Idle motion confirmed with motion allowed; `prefers-reduced-motion` eliminates the ambient clock while preserving the scroll-driven state.
- Screenshot sheet and browser recording saved in Library. No Android hardware benchmark or external designer endorsement claimed.

## Hard stop boundaries

Preserve existing main, existing homepage, original source assets and logos. No force push, production publication, additional paid credits/second Codespace or A15 workload. This is **WAVE only**; no changes in HAZE or harness authority. No QR code until actual owner-approved public HTTPS.

Continuation work order: `docs/creative/HAZEWAVE_ARTICULATED_RIG_V3A_EXECUTION.md`.
