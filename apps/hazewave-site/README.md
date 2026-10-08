# Hazewave — Living Resonance Field

**Owner rejected V3 as a final product (2026-10-08).** The [V4 critical audit](review/creative-audit-v4.md) supersedes the earlier readiness assessment. The current corrections address three reproduced defects only; spatial art direction, traversal interruption, adaptive quality and authorized audio remain open. Do not treat passing tests as creative approval.

Candidate creative reset, based on site HEAD `9873973e79df670ff29e31fff08b1cc38c41c3ee`.

The first screen samples the owner's lighthouse artwork as an interactive WebGL2 field. Contact emits a radial refraction through the image; signal selection replaces the material with the selected artist artwork using the same spatial aperture that revealed it. EXPLORE starts a short optional native-scroll journey into Aquaverno: advance, pause and reverse the texture takeover before entering its world. Direct artist selection and SEARCH remain available without the journey. Aquaverno uses tidal displacement and close ocean framing on mobile. Hemorragia Cósmica uses asymmetric compression, skeletal texture and wire tension. The original five artists are searchable and have direct `?artist=` links.

The six image files are byte-identical to the owner submissions. `owner-art-provenance.json` records their SHA-256 values. Older infrastructure and historical art derivatives remain in the repository, but the cassette/player wheel and synthetic demo catalog are absent from the entry point's dependency graph.

## Run

Node 24:

```sh
npm ci --ignore-scripts
npm run build
npm run preview -- --host 127.0.0.1 --port 4321
```

Open the reported preview URL. A standard static HTTP server can serve `dist/` as well.

## Verify

```sh
npx tsc --noEmit
node scripts/check-bundle-budget.mjs
npx playwright install chromium
npm test -- --workers=1
```

If a compatible Chromium is already installed, set `PLAYWRIGHT_EXECUTABLE_PATH` to its executable. This disables Playwright's optional video recording; tests still produce screenshots and failure traces. Desktop and Pixel 7 projects cover source-image decoding, actual canvas changes, transitions, URL/history navigation, accent-insensitive search, direct entry/return, disabled audio, reduced motion changes, GPU loss, keyboard focus, no-JavaScript access and a 360×640 layout, scroll reversal and journey teardown after motion/GPU changes. Draws are gated by a non-blocking GPU fence and settled scenes sample only their active texture.

## Scope and limitations

- This is a visual/interaction candidate, not a production publication or owner approval.
- No authorized tracks were supplied: LISTEN presents an explicit unavailable state. There is no invented track, synthetic replacement, autoplay or playback-success claim. The prior internal audio infrastructure is preserved for later authorized integration.
- Tested with headless Chromium and software WebGL. Physical A15, Safari and hardware frame-rate/power profiling are not yet proven.
- Static fallback retains the source artwork and artist navigation. Without JavaScript an accessible original-art gallery replaces inactive controls.
- The repository-wide Python suite has an unchanged supervisor process-recovery failure in this execution environment (`test_boot_recovers_after_supervisor_sigkill_with_stale_pid_and_lock`, installer exit 3). Repository contracts pass. No HAZE/Termux runtime code was modified for this WAVE task.
