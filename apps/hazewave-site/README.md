# Hazewave — WAVE site (review candidate)

**One artist only: Indionesbala.** HAZEWAVE is the master brand; Indionesbala appears as a smaller supporting signature. No other artist routes/media, experimental HUDs or private imagery are authorized for publication. This WAVE candidate is **not** approved for public deployment or merge.

## Run the real site with one command

Prerequisites: clone this repository, Node.js **24+**, Bash, Git and a browser-capable system. Install scripts run in the checkout, never on the A15. No Codespace, machine or paid provider is created.

From the **repository root**:

```bash
bash scripts/run_hazewave_site.sh
```

The command verifies original owner artwork, performs a frozen `npm ci` from the committed lockfile, checks JavaScript and TypeScript, builds Astro, verifies the two approved images in `dist/`, enforces JS bundle limits, installs Chromium, runs real Playwright desktop/mobile E2E against a local preview server, and then serves `http://127.0.0.1:4321` until stopped with Ctrl+C. **Failures stop the process with a nonzero code**; no pretend fallback.

For CI/auditors, run the exact same path without leaving the server open:

```bash
bash scripts/run_hazewave_site.sh verify
```

The [WAVE Site CI](../../.github/workflows/wave-site-ci.yml) runs `verify` in a fresh GitHub Actions checkout. It first exercises all historical prototype regressions in a temporary QA build, **then rebuilds a strict five-file production distribution** and runs the real site E2E again against that clean output. Only the second `dist/` is preserved; it has no experimental routes, prototype vendor chunks, or unauthorised artwork. Source media provenance remains versioned; the public build removes the other four historical artist images. The image verification uses all six preserved originals **for source provenance**, but only the approved HAZEWAVE and Indionesbala images **for the distribution**.

## Scope and limits

The Python/Haze audio engine and GPU-dependent generation are a **different runtime domain** governed by the same Hazewave Harness. The WAVE site launcher does not install ACE-Step model weights, pretend to exercise GPU hardware, export private audio, deploy to public HTTPS or touch Termux/A15. The root `AGENTS.md` governs all phases and promotion.

**Site artistic approval remains pending.** Passing Astro/Playwright confirms the implementation works, not that it reaches a cinematic 10/10. The SBS *The Boat* reference guides the interaction concept; no copyrighted source code or imagery is copied.
