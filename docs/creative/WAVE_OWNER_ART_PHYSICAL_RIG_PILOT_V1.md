# WAVE — Original-Pixel MPC Articulation Pilot (V1)

**Date:** 2026-10-09. **Status:** EXPERIMENTAL / SOURCE-OWNER ONLY / HUMAN ART REVIEW PENDING.

This work addresses the next priority after PRs #56–#61. It is **not** a site redesign, asset publication, completed animation rig, agent integration or Codespace attestation. It does not modify any prior Colibri, BR-no-GTA, A15, HAZE, agent, or WAVE worktree.

## What was physically built

Using the exact owner-approved `controlador_mpc_cyberpunk_neon.png` and `nebulosa_roxa_em_camadas_transparente.png` from the owner's PRIVATE Library, a separate analysis container executed `scripts/creative/wave_original_art_rig_pilot.py` with a private output directory and found **nine true orange pad surface regions**, as nine distinct connected components of pixels in the approved painterly MPC image. It extracted nine alpha-masked original-pixel PNGs, one separate rotary encoder cutout and one independently moveable atmospheric layer. It also generated a first-pass OpenCV inpaint of the material hidden behind detached pieces. The inpaint is explicitly experimental and the masks need professional visual review; it cannot reconstruct inaccessible original painted pixels.

A browser-based prototype created from the actual source pixels, not poster replacements or generic procedural pads, responds to normalized scroll: one drawn SVG waveform appears from zero; individual pads lift and illuminate in causal progression; one original-pixel encoder rotates; the background fog shifts independently; returning to zero restores the source-image pose. Chromium was actually exercised locally (separate container, NOT Codespace) at 360×800, 393×852 and 1280×720. The operator proof recorded eight scroll positions per viewport; local tests passed, but a small fractional anti-alias discrepancy during desktop forward/reverse means the video is not accepted as final pixel-perfect production.

A short H.264 proof animation and private derivative/source bundle were generated as review-only artifacts outside this repository. Original inputs in the Library remain unchanged. Owner art binaries, derived PNGs, screenshot frames, and the private preview are **not checked into GitHub**.

## No new install, host mutation, or public media

Two source scripts and contracts have been added to this isolated, stacked development PR. To reproduce in a *separate authorized environment* that already has Pillow, OpenCV and NumPy installed:

```bash
# Do not execute in Termux A15. Supply exact owner-private source paths.
python scripts/creative/wave_original_art_rig_pilot.py \
  --source /private/owner/APPROVED_ILLUSTRATED_LAYERS/controlador_mpc_cyberpunk_neon.png \
  --fog /private/owner/APPROVED_ILLUSTRATED_LAYERS/nebulosa_roxa_em_camadas_transparente.png \
  --output /private/new/rig-pilot-sha-bound-v1

python scripts/creative/wave_original_art_rig_preview.py \
  /private/new/rig-pilot-sha-bound-v1
```

The SHA-256 source pin is checked before any output is written, and both approved originals are copied byte-exactly in the private proof package. A second run to an existing output path is blocked to preserve WIP.

For strict browser testing, serve the directory through an authenticated local preview environment, never expose the media publicly. Browser or renderer tests require an approved and already installed Chromium/Playwright runtime, avoiding extra workstations or paid capacity.

## Deficiencies that still BLOCK professional sign-off

- Only the nine glowing pad surfaces and one encoder have independent cutouts. The complete chassis, cable physics, secondary encoders/faders, three machine rigs, hub mechanical awakening, full occlusion and original-geometry wave contours remain to be articulated.
- The cleanplate is reconstructed by approximate OpenCV inpainting, not owner-reviewed paint restoration; some seam artifacts may remain, especially around bright-pad borders.
- The pilot is an independent offline prototype, **not yet merged into `apps/hazewave-site`**, and creative art files have not been made available within the existing Codespace.
- Source-level CI does not attest installed OpenCV/browser tools, client MCP, Hermes/Agent Office/Codex runtime, or owner Codespace.
- Owner visual comparison and approval of forward/reverse recordings must precede promotion. Never mark `HUMAN_ART_APPROVED=PASS` or `PRODUCTION_READY` from screenshots or static tests alone.

## Next strict engineering gate

1. Human review the pilot's **real masks**, removed-region cleanplate and brush contours on dark/light backgrounds; correct mask edges and paint restoration where needed.
2. Isolate original art foreground/background occlusion and true cable/fader paths; add test-visible articulated states for each critical part.
3. Stage PRIVATE media into a detached worktree on the SAME authenticated Codespace, only after its resources and source SHA are independently checked; connect to the existing WAVE site application only in an isolated development branch.
4. Capture a production-quality browser recording with full 360/393 mobile interaction, accessibility and site performance gates. Protect the artist logos and all five canonical originals; obtain human approval before any merge or public deployment.

**Authority:** HAZEWAVE_HARNESS only; generated learning packets and test receipts have no mutation or publication authority.
