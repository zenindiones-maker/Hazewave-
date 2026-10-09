# Hazewave — Cosmic Interference (candidate)

**Status: technical candidate implemented; not owner-approved or published.**

This is a creative rebuild from the interrupted Grok Build worktree, not a continuation of the former cassette/player direction. [The Boat (SBS)](https://www.sbs.com.au/theboat/) is a conceptual interaction reference; its proprietary source and visual assets were not copied.

## Implemented

- Native-scroll, reversible three-act journey: birth, traversal and identity reveal.
- Original procedural WebGL2 interference field with nebula, depth layers and optional pointer motion.
- The owner-supplied original Hazewave art is not modified; interference masks reveal its original texture.
- The film completes before the artist directory to keep the final reveal unobscured.
- Five static routes use owner-supplied artist images: Indionesbala, Barak Ozama Beats, Baazü, Aquaverno and Hemorragia Cósmica.
- Optional opt-in synthetic interference audio. No published track, release or artist biography is invented.
- Accessible semantic navigation and non-JavaScript/non-WebGL artwork fallback.

## Run and verify (Node 24)

From apps/hazewave-site, run:

    npm ci --ignore-scripts --no-audit --no-fund
    node scripts/verify-owner-art.mjs
    npx tsc --noEmit
    npm run build
    node scripts/verify-owner-art.mjs --dist
    node scripts/check-bundle-budget.mjs
    npx playwright install chromium
    npm test -- --workers=1

Preview the built site:

    npm run preview -- --host 0.0.0.0 --port 4321

WAVE Site CI runs repository contracts, Python suite, TypeScript, Astro build, bundle budget and desktop/Pixel 7 Playwright. Verified runs retain the static dist and visual proof as artifacts.

## Still not proven

This is analytic **2.5D WebGL2**, not a geometric 3D reconstruction, nor a completed illustrated production comparable in artistic sophistication to The Boat. Automated screenshots prove browser execution, not final creative quality. Real Android/Safari hardware tests, frame-time profiling, comprehensive accessibility review and authorized artist tracks remain pending. The site has no owner approval and must not be published or merged into main.

Historical WAVE reviews remain evidence, not current design authority. Respect repository AGENTS.md and owner-art-provenance.json; preserve all original artwork.
