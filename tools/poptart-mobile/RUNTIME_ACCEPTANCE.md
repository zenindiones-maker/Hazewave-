# Hazewave Poptart Mobile V1 — private runtime acceptance

Use only the existing GitHub Codespace:
hazewave-zero-cost-4jxp45676rq6279xx.

This branch has a static build artifact, not an approved Android release.
Do not change the active worktree, reset WIP, create a Codespace, or install
runtime packages on the A15 / Termux.

1. In Work's authentic Codespace integrated terminal, verify CODESPACE_NAME,
   CODESPACES=true, the remote origin, and preserve any dirty worktree.
2. Retrieve the latest HAZE Poptart Mobile Candidate workflow artifact
   for the exact candidate SHA. Verify its SHA-256 against the GitHub Actions
   artifact digest. An old archive hash is not valid for a new archive.
3. Fetch this branch in an isolated Git worktree if needed; never check out
   another branch over dirty work.
4. From the candidate source, run:
   bash tools/poptart-mobile/codespace-preview.sh start /path/to/artifact.zip <verified-sha256>
   bash tools/poptart-mobile/codespace-preview.sh status
5. The script uses ONLY Python stdlib, curl, and the existing Codespace on
   127.0.0.1:8777. It makes no machine or billing changes. It does not
   publish the service or make a GitHub port public.
6. Check the Codespaces Ports panel: port 8777 must be PRIVATE. Capture its
   *actual* HTTPS forwarded URL only after verifying the GitHub session.
   Do not guess the URL from the Codespace name.
7. Open the private preview in Chrome Android on the Samsung A15:
   - touch the 16-step kit and confirm audible non-silent kick/snare/hat;
   - edit the melodic grid and hear the WebAudio Wavetable synth;
   - check BPM, cutoff, gain, play and update;
   - export JSON, reload and import; separately verify WAV export;
   - wait for Service Worker installation, then turn off Wi-Fi/mobile data
     and relaunch to measure actual offline readiness;
   - measure CPU, memory, underruns, keyboard handling and touch latency.
8. Record exact artifact digest, release SHA, browser/device versions, logs,
   run ID, screenshot/video, and explicit human audio judgement. Keep
   AUDIO_PASS, OFFLINE_PASS and WAV_EXPORT_PASS pending until actually tested.
9. Stop privately using:
   bash tools/poptart-mobile/codespace-preview.sh stop

Never promote or publish to production without owner's authorization.
Upstream suite failures remain a separate, blocking quality gate.
