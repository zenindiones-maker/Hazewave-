# WAVE V11 — ArtCraft external production pipeline (seven tools)

Status: **CANDIDATE / NOT PRODUCTION APPROVED**. Repository: `zenindiones-maker/Hazewave-` ONLY.
Authority: **Hazewave Harness** only; each upstream `storytold/*` executable has `authority=NONE`.
This integration deliberately does **not** vendor upstream repositories, register global agents, install apps
on A15 or mutate BR-no-GTA. No private owner artwork is sent to GitHub Actions.

## Investigated boundaries

The ArtCraft Launcher is a desktop installer/catalogue, not an unattended WAVE composition API.
Use upstream *real CLI commands* for offline reproducible rendering instead of installing GUI
packages or claiming that opening the launcher constitutes pipeline integration. The upstream
applications are early-stage projects; having a README command does not prove a specific release
performs it on our art. Versions are pinned in `scripts/wave_artcraft-seven-lock.json`.

| App | WAVE permission / expected artistic output | Proof boundary |
| --- | --- | --- |
| PhotoCraft | ORIGINAL artwork masks, layers, matte preparation | Linux CLI on synthetic input -> image bytes; owner layers pending |
| LightCraft | Non-destructive color development / print tonal consistency | Linux CLI synthetic PNG -> image bytes; owner grade pending |
| VectorCraft | First-party SVG signal trajectories | Already executed in `wave-vectorcraft-real-cli-proof.yml` at v0.7.0 |
| EffectCraft | Scroll sample / motion keyframes | Already executed in `wave-effectcraft-filmcraft-portal-proof.yml` at v0.6.0 |
| FilmCraft | Decode/QC EffectCraft-generated reference media | Already executed in the same workflow at v0.4.0; not a video editor claim |
| DesignCraft | Layout/print editorial frames and future art bible | Linux CLI sample -> PDF; no owner publication |
| PdfCraft | Check exported PDF and rasterize a page for review | Linux CLI -> PDF metadata and PNG |

## Required integration invariants

1. First-party lockfile is exactly seven entries, one per expected upstream app, with official
   GitHub release URL, **whole-archive SHA-256**, only a matching named CLI executable,
   `PUBLIC` data classification, zero app authority, no auto-install, and publication forbidden.
2. New four executables are downloaded only by the explicit bounded GitHub Actions job,
   verified before extraction, and extracted without following archive links or traversal.
3. Run their genuine CLIs in a disposable Docker mount: **no network, read-only filesystem,
   no Linux capabilities, no new privileges, bounded CPU/memory/PIDs**; WAVE sources read-only.
4. The fixture is an explicitly synthetic first-party HAZEWAVE drawn PNG and DesignCraft
   bundled sample; **neither proves quality of the five original owner paintings**.
5. PhotoCraft and LightCraft must actually alter pixels and produce valid distinct outputs;
   DesignCraft must create a valid PDF and PdfCraft must inspect that PDF and render page 1.
   Fail if the executable is absent, an archive changes or a command exits unsuccessfully.
6. The three old exact-pinned CLI proofs remain valid; do not upgrade their releases as a
   side-effect or duplicate that runtime architecture in this PR.
7. A command changing owner media or attaching unreviewed artifacts to the production
   `apps/hazewave-site/public/` is **not** authorized here. The five originals remain private;
   approval of output art still requires real Chromium screenshots, review and explicit owner assent.

## GAP MAP and decision

| Gap | Severity | Resolution in this candidate |
| --- | --- | --- |
| Four missing tools treated as integrated | P0 | Four SHA-pinned CLI bridges, synthetic real E2E proof in dedicated Actions |
| Seven tools have no shared provenance boundary | P0 | Lockfile / validation and destructive negative tests; only one HAZEWAVE identity |
| ArtCraft app output not wired into approved original five-art traversal | P0 | OPEN — first prove safe WAVE tool capability, then authorize private local art-stage adaptor |
| Independent artistic inspection still missing | P0 | OPEN — no 10/10 claim until owner approves a real-media mobile traversal |
| Proprietary Adobe or licensing confusion | HIGH | Use open-source clean-room apps; no Adobe proprietary binaries / plug-in loading |
| 7 full desktop GUIs installed in environment | NOT REQUESTED | Toolchain does not launch GUI or create a new machine |

## Tests / handoff

Run deterministic negative tests:
```bash
python3 -m unittest discover -s tests -p 'test_wave_artcraft_external_tools.py' -v
python3 scripts/wave_artcraft_external_tools.py validate
```

GitHub Actions: `.github/workflows/wave-artcraft-four-real-bridge.yml`.
This workflow is the runtime gate for the four new tools. It must complete on the exact
candidate commit; green unit tests or scripts without the genuine CLI **do not count**.

The original three tools are already covered by their separately pinned proven workflows,
each of which must remain green on the final exact SHA. The current V11 branch is an
experimental candidate, not canonical. No automatic upstream artifact sync,
publishing, promotion, local machine provisioning or background agents are permitted.

Upstream technical references:
- https://github.com/storytold/photocraft/blob/main/book/src/automation/cli.md
- https://github.com/storytold/lightcraft/tree/main/apps/lightcraft-cli
- https://github.com/storytold/designcraft/tree/main/apps/designcraft-cli
- https://github.com/storytold/pdfcraft/tree/main/apps/pdfcraft-cli
- https://github.com/storytold/craft-launcher
