# ADR-0009 — Codespace Reflex Shadow Runtime

Status: DEVELOPMENT IMPLEMENTED / LIVE CODESPACE PROOF PENDING
Date: 2026-10-07
Authority: HAZEWAVE_HARNESS
Extends: ADR-0007 / ADR-0008

## Owner boundary

Use only existing Hazewave Codespace `redesigned-space-bassoon-gxp67g5g7r739w59`.
Do not create another Codespace, increase VM size, attach paid storage or switch/reset its active branch.
Do not kill other services, interrupt REAPER or FFmpeg, or overwrite an existing worktree.

## Runtime placement

The existing Codespace's active Git worktree is preserved. Runtime runs in a separate detached worktree under `~/.local/share/hazewave/reflex-shadow-runtime/checkout`, bound to the current remote SHA of `work/reflex-shadow-runtime-v1`. The doctor requires the exact current remote head and the original reflex-governor base as ancestor.

The Colibri v2.0.0 source and Laya checkpoint live under private local model/provider directories; no weights or API keys go into Git.

The command controller is `scripts/codespaces/reflex-shadow-control.sh`. It has no implicit background services, no unattended install, no auto-update and no silent branch switching.

## Runtime transitions

1. `PRECHECK`: validate the existing Codespace identity and hardware resource budget.
2. `PREPARE`: explicit download/build only after resource admission. Verify Colibri source SHA and Laya weight SHA.
3. `SERVE`: operator starts foreground loopback-only authenticated process. No process manager auto-respawn or kill.
4. `SMOKE`: one real authenticated `/v1/systemone` inference, durable minimal receipt.
5. `OBSERVE`: handle explicit normalized internal decision events in shadow-only mode, with optional post-hoc ground truth.
6. `REPORT`: calculate separately identified calibration cohorts from durable labeled outcomes.

Only steps 4 and 5 involve real local inference. CI stubs do not count.

## Evidence truthfulness

The smoke proof uses a synthetic operational state and proves only that the installed runtime answered; it does not prove model accuracy, representative p95 latency, production readiness, Codespaces remaining quota or restart/recovery.

Shadow observations use an explicit `HazewaveReflexShadowEvent/v1` contract: task id, prechecked ambiguity marker, requested domain, English machine-state dictionary, and optional later QC/human evidence. Raw private media, secrets and raw PT-BR messages are forbidden.

Observations never override an existing task route and never mutate a REAPER/FFmpeg/animation project. Responses do not grant execution authority.

Repeated identical events return the existing receipt without invoking the model twice. A local filesystem lock protects the event/ledger write. Persist only event SHA-256, model response digest, typed probabilities, labels and receipt metadata. Do not persist raw event state.

## Caveats

A label-evidence SHA digest is a content-integrity reference, not a cryptographic identity signature or proof that a claimed human approved a decision. Human labels should not be treated as independently authenticated until bound to a trusted human-review producer. Any future automatic training must independently validate the evidence origin.

The current Codespaces billing/quota cannot be proven from an on-disk model and must not be marked PASS merely because `usage.cost=0`. Preserve ZERO_COST by using only the existing quota and never enabling paid fallback.

The local resource audit proves capacity at sample time only. During REAPER/FFmpeg peak load the governor must abstain or stop serving if resource headroom is insufficient.

No canonical promotion, model specialization, production calibration or delegated authority is attempted.
