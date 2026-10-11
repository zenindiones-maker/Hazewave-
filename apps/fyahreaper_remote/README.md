# FyahReaper Remote — Hazewave candidate MVP

**Scope:** `zenindiones-maker/Hazewave-`, isolated candidate branch. Workstation is the **existing** Codespace `hazewave-zero-cost-4jxp45676rq6279xx`; the Android phone is a remote touch controller. No changes to BR-no-GTA, Termux processing, original project media, or existing REAPER instances.

## What is implemented

- Authenticated FastAPI REST routes: `/health`, `/api/transport/play`, `/api/transport/stop`, `/api/transport/rec`, `/api/tracks`, `PATCH /api/tracks/{guid}`, `/api/project/create_midi`.
- Authenticated WebSocket `/ws` pushes transport state. Commands execute synchronously through the host `python-reapy` bridge with serialized access to the DAW.
- REC requires a track armed by the owner. Commands are idempotent for the same current transport state. MIDI is created on **new track directly below** the sole selected audio item, with the existing `FyahGrabber 808 Instrument` JSFX, note count readback and rollback if FX/creation fails.
- Android Jetpack Compose source: connect URL + bearer token, big transport buttons, touch mixer, mute/solo/arm, vertical fader, MIDI keyboard painter.
- No persistent credential storage on mobile.

## Explicitly not yet delivered

APK binary, validation against the *actual* REAPER instance, selected-audio waveform PNG, arrange drag, sample upload/import/sonogram, OSC meter feedback, Opus master return/WebRTC, or mobile Wi-Fi/Tailscale E2E. A green local test suite is **not** a real REAPER proof. The human three-note painting stopwatch has not been measured.

## Workstation setup (do not automate restarts)

This feature runs as **external Python service**, not inside a long-running ReaScript. `python-reapy` must first be configured to communicate with the already installed REAPER. It may edit REAPER configuration and require a controlled REAPER restart; do not change a running owner's project or auto-restart REAPER to force readiness. `reapy` uses a REAPER Web Interface and internal port; do not forward or expose internal ports 2306/2307 to the internet.

```bash
# Run ONLY inside the approved existing Hazewave Codespace terminal.
# Never run on A15 or create a second Codespace.
cd /workspaces/Hazewave-
# Review WIP & head before changing anything:
git status --short && git rev-parse HEAD
# Work from checked-out candidate branch or an isolated worktree first.
python3 -m venv "$HOME/.local/share/hazewave/fyahreaper-remote/.venv"
"$HOME/.local/share/hazewave/fyahreaper-remote/.venv/bin/pip" install 'python-reapy==0.10.0' 'fastapi>=0.115,<1' 'uvicorn>=0.30,<1' 'pydantic>=2.8,<3'
# One-time REAPER integration, only after checking config and permission to restart:
# "$HOME/.local/share/hazewave/fyahreaper-remote/.venv/bin/python" -c 'import reapy; reapy.configure_reaper()'
# Set FYAH_REMOTE_TOKEN from local secret storage (minimum 24 chars); never commit it.
# export FYAH_REMOTE_TOKEN='your-unique-random-token'
cd apps/fyahreaper_remote
"$HOME/.local/share/hazewave/fyahreaper-remote/.venv/bin/python" -m uvicorn reahub_server:build_app --factory --host 127.0.0.1 --port 8000
```

**Networking:** the existing Hazewave workstation is a GitHub Codespace, **not** automatically another device on the phone's home Wi-Fi. `192.168.1.10` is only an example for a true local PC. For the Codespace, use an authenticated, tested network path (e.g. Tailscale on both endpoints with firewall restrictions) before remote access. Do not make Codespaces port `8000` public. API bearer over plain HTTP on ordinary Wi-Fi is not encrypted: use a private trusted LAN for initial test, and TLS or WireGuard/Tailscale before using it over untrusted networks.

## Android build

Open `apps/fyahreaper_remote/android/` in an Android SDK 35 + JDK 17 / Android Studio environment. Build the `app` debug variant. A reproducible `gradlew` wrapper and signed APK are not yet present; do not claim APK ready before an actual build and device test.

## Tests and acceptance

```bash
python -m pytest -q apps/fyahreaper_remote/tests
```

1. Backend local negative/contract tests (token, arming, fader, three MIDI notes, rollback) must pass.
2. Connect authorized Samsung device through a **private network**, confirm `REAPER_CONNECTED=true` and current transport state.
3. Arm a disposable test track, press REC on phone; verify REAPER recording via state and host observation; press STOP.
4. Select one test audio item on the host, paint pitches 36, 40, 43; submit; verify **three real notes** in a new MIDI take below source track, with installed 808 JSFX.
5. Do not claim the full project finished without actual host + APK + phone evidence. Never run destructive tests on owner's current project.
