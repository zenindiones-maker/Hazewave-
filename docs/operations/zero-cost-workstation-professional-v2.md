# Hazewave Professional Zero-Cost Workstation v2

## Objective

Provide a professional browser-accessible audio workstation while keeping the
GitHub Codespaces machine on the smallest supported 2-core / 8 GB / 32 GB tier
and preserving a fail-closed zero-cost operating model.

## Runtime architecture

A15/Termux is the control plane. The Codespace is an interactive workstation.
Xpra HTML5 on port 14500 is the primary remote transport. noVNC on port 6080 is
retained only as a fallback. Both services bind to loopback inside the
Codespace, and the A15 controller requires GitHub port visibility to be
`private` before opening a browser.

The professional audio surface contains Ardour, LSP LV2, x42 plugins,
Dragonfly Reverb and Rubber Band. Xpra installs its X11, HTML5 and audio-server
packages explicitly so `start-desktop` and browser speaker forwarding are
not dependent on optional package recommendations.

Microphone forwarding, webcam access, file transfer, remote printing, mDNS,
session sharing and client-triggered command execution are disabled. Browser
speaker forwarding is configured for review/mixing convenience; final
reference listening remains local on the A15.

## Storage and compute policy

Transient render/cache/scratch data lives under `/tmp`, not `/workspaces`.
Pip caching is disabled during bootstrap and apt package archives are cleaned.
Do not keep large media masters in the Codespace.

No Codespaces prebuild is required by this design. Batch validation and audio
QC belong on the repository's standard public GitHub-hosted Actions runner.
The workflow intentionally does not upload large media artifacts.

## Required proof

A professional runtime is not READY until all of these are true:

- `HAZEWAVE_PRO_WORKSTATION=PASS`
- `XPRA_HTML5=PASS`
- `XPRA_X11=PASS`
- `XPRA_AUDIO_SERVER=PASS`
- `XPRA_BIND=LOOPBACK_ONLY`
- `ARDOUR=PASS`
- LSP, x42, Dragonfly and Rubber Band checks pass
- GitHub forwarded desktop port is `private`
- `PAID_FALLBACK=FALSE`
- `UNKNOWN_COST_FALLBACK=FALSE`

The noVNC fallback is not evidence that the Xpra professional gate passed.
