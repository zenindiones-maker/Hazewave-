# FYAHGRABBER OPEN — REAPER-first

**Status: candidate code, not deployed to the actual HAZE workstation.** This original MIT-licensed program emulates a workflow, **not** Navie D's commercial noteGRABBER2 code, branding, or visual assets. No third-party DSP code or model weights are vendored.

## Target / preservation

- Existing Codespace only: `hazewave-zero-cost-4jxp45676rq6279xx`
- Existing REAPER 7.82: `/home/vscode/.local/opt/reaper/7.82/REAPER/reaper`
- Existing checkout: `/workspaces/Hazewave-`. Preserve its checkout/HEAD/WIP.
- The A15 is a control terminal only: Python/audio processing runs on the Codespace.
- No new machine, repo, Sprite, paid resource, or change to BR-no-GTA.

## Install — only through the existing Codespace

The installer is deliberately fail-closed and checks the existing REAPER and Codespace. On the **Codespace terminal**, with the current Hazewave repo available:

```bash
git -C /workspaces/Hazewave- fetch --no-tags origin refs/heads/work/fyahgrabber-reaper-native-v1
git -C /workspaces/Hazewave- show FETCH_HEAD:scripts/fyahgrabber-install-existing-haze-workstation.sh | bash -s -- --with-cqt
```

It archives the candidate without changing the checkout, copies the JSFX to the **existing** REAPER Effects directory, places versioned ReaScripts in the REAPER Scripts directory and creates a dedicated Python venv with pinned `librosa==0.11.0`, `Pillow==11.3.0`. It does **not** launch, restart, or override the running REAPER. It never overwrites an existing `FyahGrabber_808.jsfx`; conflicting state blocks installation.

Before executing, ensure any client is connected to that **same** Codespace; don't run these commands on the A15 processor, another repo, or a GitHub Actions runner and call it live REAPER proof. Installed dependencies may take time; do not assume the 10-second UI target includes first-time dependency setup.

In REAPER, open the Action List, **Load ReaScript**, and select the versioned `FyahGrabber_Analyze_Selected_Item.lua` under the resource directory's Scripts folder. The 808 is a JSFX in Effects. Run once with an existing selected item, draw notes in the piano roll, then click **CREATE MIDI BELOW**. If REAPER has not scanned a newly installed JSFX, refresh it using the DAW's FX browser at a safe point without interrupting any active session.

For CQT, when prompted, point REAPER at the installed dedicated Python:
`/home/vscode/.local/share/hazewave/fyahgrabber-open/.venv/bin/python`.
The source can be MP3/FLAC/other audio REAPER decodes: the script extracts only the selected *pre-FX* take for offline analysis, with size/duration bounds. Sample content never leaves the Codespace.

## Exact live runtime acceptance — not a mock

Perform this only in a disposable REAPER project with a **selected audio item at least 0.75 seconds**:

1. Run `FyahGrabber_Live_Proof_3_Notes.lua` through the real REAPER Action List. It should create a MIDI item containing MIDI note pitches 36/40/43 and attach the open 808 JSFX. It writes `FyahGrabber-live-proof.json` in `reaper.GetResourcePath()`, including REAPER version, operating system, note count, FX evidence, API timing and `human_paint_under_10s=NOT_MEASURED`.
2. For the actual user-facing criterion, run `FyahGrabber_Analyze_Selected_Item.lua`, click or paint **three notes**, then **CREATE MIDI BELOW**. The UI records first-paint → MIDI-creation wall time in the REAPER Console, with explicit `PASS` only if under 10 seconds. Inspect the MIDI item and hear the 808 through the REAPER audio output. A screenshot/live recording and exact local timestamp are required to claim the 10-second goal.
3. Verify the project retains its original source item and that the output MIDI sits on a newly inserted track below it. Close the disposable project without copying test changes into an owner's active arrangement.

**CI is a source gate only**: Lua syntax, pure logic and mocked audio-accessor WAV extraction. It is not proof of REAPER GUI integration, JSFX audio, CQT performance, or a 10-second human workflow.

## Known limits

- Native CQT spectrogram is a visual guide, not automatic MIDI transcription. It requires an optional local Python runtime.
- CQT extracts only pre-FX audio, not effects rendered after the take; 20 s max per item.
- Paint/edit currently supports single-gesture creation, undo-last and clear. Full note move/resize, snap options, multiple gestures and saved project state need human QA.
- No automatic Basic Pitch inference, VST3, ReaPack release, or published beta is claimed here. Those require separate build/licensing and actual workstation E2E.
- Source JSFX is a simple one-voice synthesized 808; acoustic validation must happen in REAPER.

## Governing sources

- https://www.reaper.fm/sdk/reascript/reascripthelp.html — REAPER Lua APIs for MIDI item, item selection, audio accessor and JSFX insertion
- https://librosa.org/doc/main/generated/librosa.cqt.html — CQT reference
- https://github.com/spotify/basic-pitch — potential optional inference, Apache-2.0, **not installed by this REAPER-first installer**

Every capability is subordinate to `HAZEWAVE_HARNESS`. Publication and production promotion require separate human approval.


## Isolated host proof without modifying the current music project

A separate, guarded host E2E action is now available as
\`FyahGrabber_Disposable_Host_E2E.lua\`. It generates its **own** test WAV,
starts from an empty project in a **separate REAPER instance**,
verifies true REAPER pre-FX accessor output, inserts a track directly
below the audio, checks 3 MIDI pitches, and verifies the bundled JSFX.

Do **not** pass \`-nonewinst\`. Do **not** run this E2E action inside the
owner's active session. Use only
\`scripts/fyahgrabber-reaper-host-e2e-existing-workstation.sh\`, which
requires \`FYAH_E2E_ISOLATED=1\`, checks the existing Xpra DISPLAY,
generates a private run-specific evidence directory, bounds execution
time and verifies JSON/byte hashes. It never approves human timing.

After updating the versioned installation using the normal installer
(without \`--with-cqt\` when CQT is already available), the Codespace
may execute the checked-out runner script from the exact remote Git
SHA through an SSH command. The proof file remains under
\`~/.local/state/hazewave/fyahgrabber/proofs/reaper-host-*/reaper-host-proof.json\`.

Proof states:
- \`FYAH_REAL_REAPER_HOST_E2E=PASS\`: REAPER host API, original synthetic
  WAV accessor, 3 MIDI notes, JSFX plug-in presence and track geometry.
- \`FYAH_HUMAN_3_NOTES_UNDER_10S=NOT_MEASURED\`: requires a separate
  live GUI interaction test; API execution time is not a UX benchmark.
- \`BLOCKED:*\`: do not promote; investigate exact error, do not restart
  the workstation or use an unrelated remote REAPER.

A static Lua unit test is not a valid substitute for the real host proof.
