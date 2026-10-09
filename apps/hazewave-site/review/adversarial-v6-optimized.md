# Independent review — V6 shader optimization

**KEEP_OPTIMIZATION=YES. INTERNAL_SCORE=83/100. PRODUCT_ACCEPTANCE=HOLD.**

**Corrected performance claim:** the focused shader change reduces explicit shader work and shows no material visual regression in the inspected captures, but the subsequent paired run does **not** reproduce a uniform cadence improvement. Mobile idle p50 was worse in that paired observation. Keep the change as a visually accepted, bounded rendering-cost candidate, not as a validated universal speedup. The full-product score remains 83/100 and physical-device cadence remains unqualified. The paired-evidence addendum below takes precedence over conclusions drawn from the earlier separate runs.

## Scope and evidence

- Repository: `zenindiones-maker/Hazewave-`; branch `work/wave-cinematic-worlds-v6`.
- Observed baseline HEAD: `4255ce4e3a2f535ae4846a87380cf8dfd7a27640`.
- Reviewed WIP file: `src/experience/fieldShader.ts`.
- Reviewed shader SHA256: `d6c48ac5c44fb7279574d20ccd09e8ecf4677d0d1fe05624adc73dfaff7ee2f9`.
- Evidence directory: `/workspace/scratch/f593a5ba37dc/proofs-v6-optimized`.
- Directly inspected actual desktop/mobile captures of origin, all five artist worlds, reveal, transition and wave, plus desktop reverse. Read the shader diff and `performance-accessibility.json`. Compared composition against the prior V6 review and previously inspected baseline captures.
- This reviewer changed only this report. No implementation, test, asset or measurement code was modified.
- Final 50-case browser run was forthcoming at review time; its exact outcome must be supplied separately by the executor. No new full-suite PASS is asserted here. This review did not inspect new optimized video playback or test a physical phone.

## Technical assessment

The change replaces a transcendental noise hash with an arithmetic hash, interpolates analytic texture coordinates before one artwork fetch instead of blending three fetched colors, and skips transition-frontier evaluation when progress has reached the settled state.

The coordinate interpolation is **not mathematically equivalent** to blending three sampled colors. It can change filtering and ghosting around high-contrast boundaries. The bounded offsets are small, and no objectionable structural or identity regression was observed in the inspected captures. This is an accepted visual approximation, not a bit-exact optimization. The new hash also changes atmospheric noise realization; the review found no distracting repeating grid in these views, but screenshots do not establish all-time temporal noise quality.

The source lettering, scene framing, recognizable Hazewave origin, Aquaverno moon/ocean/beacon, Hemorragia wire/bone structure, Barak angular monochrome space, Indionesbala heated corridor and Baazü mechanical city remain intact. World-window expansion and transition boundaries remain visible. No new clipping, missing artwork, duplicate logo, layout displacement or return to cassette/demo art direction was observed.

## Earlier separate-run observations and limits

The artifacts describe local Chromium SwiftShader software rendering, without network throttling. Warm draw-call observations are:

| Surface | Baseline p50 / p95 | Optimized p50 / p95 | Optimized warm samples | Baseline / optimized pixels |
|---|---|---|---:|---:|
| Desktop | 83.6 / 122.7 ms | 50.0 / 53.4 ms | 62 | 350,064 / 384,160 |
| Mobile emulation | 49.9 / 59.2 ms | 33.5 / 50.1 ms | 72 | 174,660 / 329,160 |

In these earlier separate runs, the optimized mobile run remained at balanced quality with more rendered pixels than the baseline economy sample. That observation did not come from lowering the mobile pixel count, but subsequent paired evidence does not reproduce the general cadence-gain inference. The desktop sample was still economy tier. These are single-run observations with adaptive quality, not a fixed-resolution controlled benchmark or proof of statistical significance.

Draw-call intervals are not physical presentation intervals, and exported video FPS is not runtime FPS. A15 behavior, Safari, physical input latency, energy/thermal impact and real-user Core Web Vitals remain unqualified. The observations do not promote technical execution to 4/5 or establish 60 FPS.

The optimized artifact reports zero automatic axe violations for field, search, ready world and transport on desktop and mobile emulation. Manual/incomplete `color-contrast` and, in some states, `aria-prohibited-attr` remain. This is not full WCAG certification. Audio is still explicitly unavailable because the authorized catalog is empty; no playback success is claimed.

## Exact requested rubric

The patch changes the amount and kind of shader work, not the underlying art direction. Its net cadence benefit is mixed in the paired evidence. Scores remain reviewer judgments with the same evidence limitations as the main V6 review.

| # | Category | Score / 5 | Remaining concrete improvement |
|---|---|---:|---|
| 01 | ART DIRECTION | 4.5 | Integrate canonical vortex pigment more naturally without losing source recognizability. |
| 02 | FIRST IMPRESSION | 4.5 | Reduce repeated location/nucleus copy and separate mobile source lettering from the beacon. |
| 03 | VISUAL STORYTELLING | 4.0 | Give middle chapters individually composed approaches and arrivals rather than equal chapter grammar alone. |
| 04 | MOTION QUALITY | 4.0 | Use object-specific occlusion/motion masks for structural depth; broad analytic coordinate bands remain a 2.5D approximation. |
| 05 | WORLD COHERENCE | 4.5 | Refine per-world material frontiers while retaining a legible origin trace through traversal. |
| 06 | ARTIST EXPRESSION | 4.5 | Differentiate Barak and Indionesbala camera/arrival rules beyond two differently colored monumental corridors. |
| 07 | INTERACTION DESIGN | 4.0 | Reduce duplicate discovery/rail naming and validate first-time touch preview versus entry comprehension. |
| 08 | MOBILE EXPERIENCE | 4.0 | Preserve more of Aquaverno's defining curled wave in portrait and complete physical/manual access verification. |
| 09 | TECHNICAL EXECUTION | 3.5 | Keep the bounded rendering-cost candidate provisionally, investigate the paired mobile idle slowdown, and qualify hardware cadence under controlled conditions. |
| 10 | ORIGINALITY | 4.0 | Develop artist-specific movement laws grounded in the supplied art rather than adding generic effects. |

**Sum = 41.5/50; normalized = 41.5 × 2 = 83/100.** The 90/100 target is not reached; category 09 remains below the required minimum of 4. No score was increased merely to clear the gate.

## Decision and next priorities

1. Keep this bounded optimization, bind final test/proof artifacts to the resulting commit, and preserve the baseline for comparison.
2. Qualify cadence on representative hardware; separate settled world, active wave, traversal and interrupted navigation measurements before choosing the next optimization.
3. Improve portrait Aquaverno framing and individual middle-world choreography, then repeat targeted visual inspection rather than broad unrelated testing.

The product remains an internally reviewed candidate on HOLD. This recommendation does not grant owner acceptance, merge/publication authorization, external certification or production approval.

## Paired-evidence correction — authoritative addendum

Read directly: `proofs-v6-optimized/shader-ab.json`. Scope: one paired run in the same browser process and host with SwiftShader, injecting the baseline GLSL from `4255ce4e3a2f535ae4846a87380cf8dfd7a27640` into the otherwise current build. This controls more factors than the earlier separate observations, but adaptive quality is still enabled and the desktop variants render different pixel counts. It is not a fixed-resolution benchmark or statistical/device qualification.

| Surface/state | Baseline p50 / p95 | Candidate p50 / p95 | Baseline / candidate pixels |
|---|---|---|---:|
| Desktop idle | 50.0 / 66.4 ms | 50.0 / 66.3 ms | 350,064 / 443,734 |
| Desktop wave | 49.9 / 65.9 ms | 50.0 / 67.6 ms | 350,064 / 443,734 |
| Mobile idle | 33.4 / 50.1 ms | 50.0 / 50.3 ms | 329,160 / 329,160 |
| Mobile wave | 49.9 / 50.2 ms | 50.0 / 52.8 ms | 329,160 / 329,160 |

The paired desktop maintains approximately the same cadence while drawing more pixels. This is compatible with improved rendering headroom, but does not isolate a causal speedup at equal resolution. Mobile shows no uniform gain: its idle p50 worsens at the same pixel count, while wave medians are approximately unchanged and candidate wave p95 is slightly worse. A single order-dependent paired run cannot establish the size or persistence of the mobile regression, but the unfavorable observation must not be omitted.

**Independent decision remains KEEP provisionally in the candidate branch**, because explicit fetch/frontier work is reduced, inspected visual quality is preserved, and desktop retains cadence at a larger adaptive buffer. This is not a performance acceptance or an unconditional rollout recommendation. Before claiming a validated speedup, use repeated order-balanced, fixed-resolution A/B samples and representative hardware; investigate mobile idle behavior rather than selecting the favorable separate run. If that slowdown persists under controlled comparison, isolate the UV/noise/frontier changes and retain only the beneficial subset.

**Correct claim priority:** “Rendering work was simplified; paired cadence results are mixed, with higher desktop detail at similar cadence and no demonstrated mobile speedup.” Do not use “uniformly faster,” “validated cadence gain,” or “60 FPS.” Score and product gate remain **83/100 — HOLD**.
