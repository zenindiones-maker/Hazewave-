# Hazewave Always-Ready Codespace V1

Status: DEVELOPMENT  
Scope: existing Hazewave Codespace, Termux control plane, Reflex/Laya runtime  
Authority: operational only. Hazewave Harness remains the sole execution authority.

## Goal

Make the existing zero-cost Codespace behave as an always-ready workstation without
trying to keep GitHub Codespaces compute alive continuously.

The design is **lazy wake + deterministic reconcile**, not keepalive.

- The A15/Termux control plane is persistent.
- The existing Codespace is allowed to stop normally.
- A remote-capability request starts the same existing Codespace when necessary.
- After it becomes Available, the controller attests repository and Codespace identity.
- Reflex/Laya is reconciled as a detached loopback-only service.
- Repeated startup failures are bounded and fail closed.
- No new Codespace is created and no paid fallback is enabled.

## Normal Termux entry

After the candidate controller is installed:

```bash
hazewave-reflex ready
```

This performs:

```text
GitHub auth
  -> locate the existing Hazewave Codespace
  -> start it only when not Available
  -> wait for Available
  -> attest Codespace + repository
  -> sync the isolated candidate worktree
  -> verify model/source/secret/runtime material
  -> reuse a healthy tracked Reflex service, or start one detached
  -> health check
  -> HAZEWAVE_WORKSTATION_READY=PASS
```

The command must not contain a keepalive loop and must not create another Codespace.

## Runtime reconciliation

The remote reconciler is:

```text
scripts/codespaces/reflex-shadow-control.sh reconcile
```

Safety properties:

- `flock` serializes concurrent reconcile attempts;
- bind remains `127.0.0.1:28080`;
- existing healthy runtime is reused only when tracked metadata matches current candidate HEAD;
- a tracked healthy runtime from an older HEAD is stopped through the pinned Colibri launcher and restarted;
- an untracked service on the Reflex port is not killed automatically;
- startup uses `nohup` and is detached from the SSH/Termux session;
- no `pkill`, `killall`, blind process sweep, or unrelated-process termination is allowed;
- restart failures are bounded to 3 within 15 minutes;
- restart-budget exhaustion reports DEGRADED and stops retrying;
- model/source preparation is not performed implicitly during reconcile.

## Codespace lifecycle

`.devcontainer/devcontainer.json` points `postStartCommand` at:

```text
scripts/codespaces/start-always-ready.sh
```

That hook starts/reconciles the professional desktop and then reconciles Reflex.

Changing a devcontainer lifecycle command may require a container rebuild before an
already-created Codespace uses the new hook. A rebuild is **not** part of this candidate's
automatic rollout because Hazewave model/runtime material currently lives under the user
home and must not be risked merely to activate the hook. The Termux lazy-wake path works
without a rebuild.

## Zero-cost boundary

This design intentionally lets the Codespace become idle and stop. It does not:

- increase machine size;
- create a second Codespace;
- run artificial activity to defeat idle timeout;
- enable paid fallback;
- enable unknown-cost providers.

## Initial material

Always-ready reconciliation assumes the pinned Colibri source, Laya model and secret
were already prepared and verified. If they are absent, reconciliation fails closed with
a preparation-required condition instead of downloading or installing silently.

## Status and recovery

Read state without intentionally keeping compute alive longer than required:

```bash
hazewave-reflex status
hazewave-reflex runtime-status
```

Explicit stop remains available:

```bash
hazewave-reflex serve-stop
hazewave-reflex stop
```

The service receipt is written outside the repository under the Reflex state root and
contains no credential or raw media.

## Truth boundaries

`HAZEWAVE_WORKSTATION_READY=PASS` proves runtime readiness only. It does not prove:

- Reflex production calibration;
- model correctness on unlabeled traffic;
- canonical promotion;
- publication approval.

The current Reflex provider remains `authority=NONE` and
`production_calibrated=false`.
