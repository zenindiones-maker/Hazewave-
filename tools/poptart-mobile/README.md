# HAZE / Poptart Mobile Music Lab — candidate V1

This is a reproducible build adapter, not a rewritten engine. The Poptart
browser source remains pinned upstream; this directory overlays a touch
sequencer and offline-capable PWA packaging onto the upstream Web Audio build.

## Source and boundaries

- Upstream repository: https://github.com/glossings/poptart
- Exact source commit: 1310635d3a306a46544773bfc77720ce123ede75
- License: AGPL-3.0-only, including modified network versions.
- Architecture: pattern-core, web-engine, web-app.
- Hazewave target: HAZE audio; no Harness/control-plane authority.
- No mutation to WAVE, BRIDGE, A15/Termux runtime, site or artists.
- No native VST, native SuperCollider, or remote server required for browser sound.

## Reproduce inside the EXISTING Codespace only

Do not create another Codespace or disturb the working checkout. Use isolated
directories/worktrees and preserve WIP.

1. Check out Hazewave candidate work/haze-poptart-integration-v1.
2. Clone upstream into a separate directory at the SHA above; verify HEAD.
3. With Node.js >=20 run npm ci --ignore-scripts, npm test, npm run build:web.
4. In the Hazewave checkout run:
   node tools/poptart-mobile/build.mjs /path/to/poptart/dist/web
5. Run node --test tools/poptart-mobile/build.test.mjs.
6. Serve the static dist/web behind a private HTTPS preview. Do NOT publicly
   expose the upstream Node evaluation server or grant access to Hazewave secrets.

The candidate branch workflow builds a static candidate artifact. This artifact
is NOT deployed to a HTTPS URL. A private preview still must be configured and
verified inside the existing Codespace.

## Mobile controls

On viewports <=800px: Código, Bateria (16 steps), Painéis and Backup.
The integrated pattern targets Poptart built-in synthesized drum kit samples
0 kick, 1 snare and 4 closed hi-hat. Aplicar e ouvir updates only the bounded
HAZEWAVE_MOBILE_BEGIN / END block in the upstream music code editor and activates
the existing Poptart controls.

JSON backup preserves editor text and drum state; it does NOT export WAV.
Import requires an explicit confirmation before overwriting the song.
Poptart IndexedDB retains its own song persistence. Browsers may clear data,
so exported backups remain important.

## Honest quality gates

CI unit tests and static validation are not proof of physical Android audio,
recording/export, reliable offline cache, MIDI, Bluetooth or CPU performance.
No test can be marked PASS without evidence.

Android owner test must demonstrate taps -> real sound, piano roll interaction,
saving/reopening, offline relaunch, WAV export where supported, and performance
on Samsung A15 before promotion. The mobile Panel button exposes upstream
panels; this alone does not prove a touch-first mixer or piano roll.

## Security and license

Browser livecoding evaluates user code. Keep the app on a dedicated origin
without privileged Hazewave credentials. Keep upstream AGPL copyright, license,
third-party notices and complete corresponding source links when distributing.
Do not treat an Actions artifact as permission to publish the site.
