# FreeLLMAPI A15 Runtime Proof — 2026-10-04

## Scope

Observed runtime evidence for the Hazewave-scoped FreeLLMAPI provider gateway on the Samsung A15 Termux runtime.

This document is historical runtime evidence. It does not grant authority, widen provider eligibility or prove later source revisions that were not yet synced to the device.

## Authority and provider boundary

Observed throughout the proof:

```text
PROJECT_ID=HAZEWAVE
AUTHORITY=HAZEWAVE_HARNESS
FREELLMAPI_AUTHORITY=NONE
FREELLMAPI_ENDPOINT=http://127.0.0.1:3001/v1
FREELLMAPI_UPSTREAM_SHA=716948f20b12ec1c9b7c6fcebd22a3e7233cda1b
```

The provider runtime remained loopback-only and the unified key remained local/configured without being printed into evidence.

## Early live provider proof

A bounded Harness-authorized provider call succeeded through Kilo with monetary cost reported as zero.

That early proof originally used `INTERNAL_NON_SECRET`. Subsequent review found that Kilo's anonymous free route can log prompts/outputs for training, so generic FreeLLMAPI egress was tightened to `PUBLIC` before further live proof.

The historical receipt is retained as evidence of what actually happened at that time, not as the current policy.

## Post-policy live proof

After tightening generic egress to `PUBLIC`, the same bounded synthetic connectivity proof passed again.

Observed:

```text
HAZEWAVE_FREELLMAPI_LIVE_PROBE=PASS
routed_via=kilo/dots-studio/dots-3-note-preview:free
reported_cost=0
```

No private audio/media, project secret or credential was used in that proof.

## Supervisor auto-recovery

At runtime SHA:

`9242f8d70bbbae0e55dca1ec644d687607406cdd`

the managed FreeLLMAPI server was intentionally terminated.

Observed:

- old server PID: `7384`;
- supervisor remained alive;
- replacement server PID: `12654`;
- replacement process identity: `MANAGED_DIRECT_NODE`;
- exact FreeLLMAPI upstream SHA unchanged;
- `HAZEWAVE_FREELLMAPI_AUTO_RECOVERY=PASS`.

This proved in-session recovery, but not yet Android reboot persistence.

## Cold-boot incident

The first real Android reboot exposed a persistent-lock defect.

Observed after reboot:

- supervisor process existed;
- recorded server PID was stale;
- `control.lock` remained present after the process that owned the critical section no longer existed;
- supervisor reconciliation repeatedly returned `HAZEWAVE_FREELLMAPI_CONTROL=BUSY`;
- provider remained `OFFLINE`;
- live probe failed with connection refused.

The evidence established a causal failure chain:

```text
server process death
 -> stale control.lock
 -> supervisor RECONCILING
 -> CONTROL=BUSY
 -> no server restart
 -> provider OFFLINE
```

A secondary inconsistent state was also observed during recovery: a live supervisor could become detached from its `supervisor.pid` / lock metadata.

## Crash-safe persistence fix

The Hazewave source was changed so both control and supervisor locks carry owner identity and can safely reclaim stale state after non-graceful process death.

The corrected Hazewave runtime release was:

`e100c63e2d3ab60ad0b7718647a93b7e80c19099`

Repository CI for that source revision was GREEN before deployment.

The A15 then materialized that exact immutable release.

Observed immediately after installation:

```text
DEPLOY_EXACT_HEAD=PASS
HAZEWAVE_FREELLMAPI_PERSISTENCE=PASS
SUPERVISOR_LIVENESS=PASS
SERVER_LIVENESS=PASS
HAZEWAVE_FREELLMAPI=ONLINE
HAZEWAVE_FREELLMAPI_LIVE_PROBE=PASS
CONTROL_LOCK_IDLE=PASS
SUPERVISOR_LOCK_OWNERSHIP=PASS
```

Observed process state before final reboot proof:

- supervisor PID: `26952`;
- server PID: `26783`;
- supervisor lock owner: `26952`.

## Final real Android cold-boot proof

The A15 was then rebooted again.

No manual FreeLLMAPI `restart`, persistence reinstall, control-lock deletion or boot-script invocation was performed before the proof.

Observed after automatic Termux:Boot recovery:

```text
SUPERVISOR_PID=23409
SERVER_PID=24648
LOCK_OWNER=23409

HAZEWAVE_FREELLMAPI_COLD_BOOT=PASS
COLD_BOOT_RUNTIME_SHA=PASS
HAZEWAVE_FREELLMAPI=ONLINE
HAZEWAVE_FREELLMAPI_PROCESS_IDENTITY=MANAGED_DIRECT_NODE
CONTROL_LOCK_IDLE=PASS
SUPERVISOR_LOCK_OWNERSHIP=PASS
HAZEWAVE_FREELLMAPI_LIVE_PROBE=PASS
```

Exact runtime SHA after the reboot:

`e100c63e2d3ab60ad0b7718647a93b7e80c19099`

The live proof again routed through the configured zero-dollar Kilo route and reported `cost=0`.

## Persistence conclusion

For runtime SHA `e100c63e2d3ab60ad0b7718647a93b7e80c19099`, the following are empirically proven:

- exact immutable Hazewave release binding: PASS;
- exact FreeLLMAPI upstream SHA binding: PASS;
- loopback-only provider runtime: PASS;
- managed direct Node process identity: PASS;
- unified key configured locally: PASS;
- bounded Harness-to-provider live request: PASS;
- supervisor recovery after process death: PASS;
- stale control-lock recovery: PASS;
- supervisor-lock ownership consistency: PASS;
- Termux:Boot automatic execution after real Android reboot: PASS;
- provider ONLINE after cold boot: PASS;
- live provider proof after cold boot: PASS.

Therefore the crash-safe FreeLLMAPI persistence baseline is closed for that release.

## Relationship to Governed Free Fabric

The later Governed Free Fabric expands provider policy and client surfaces beyond this historical runtime SHA.

This proof must not be reused to claim that later source revisions or new modalities are already active on the A15.

For a later Free Fabric release, required runtime adoption is:

1. immutable Hazewave sync to the new exact SHA;
2. doctor;
3. inventory/eligibility report;
4. bounded zero-cost live probe;
5. modality claims only where a real eligible provider/key is configured.

The implementation reference for the expanded fabric is:

`docs/reference/HAZEWAVE_FREE_FABRIC_V1.md`
