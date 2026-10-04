# FreeLLMAPI A15 Runtime Proof — 2026-10-04

## Scope

Observed runtime evidence for the Hazewave-scoped FreeLLMAPI provider gateway on the A15 Termux runtime.

This document records runtime evidence only. It does not grant authority or widen data-egress policy.

## Hazewave runtime

- project: `HAZEWAVE`
- authority: `HAZEWAVE_HARNESS`
- canonical development ref: `work/wave-living-resonance-v1`
- runtime SHA observed before proof: `24acd736524ac5cd54cb5856b4ebec89cb0091f7`
- immutable runtime: PASS

## FreeLLMAPI runtime

- upstream exact SHA: `716948f20b12ec1c9b7c6fcebd22a3e7233cda1b`
- endpoint: `http://127.0.0.1:3001/v1`
- process identity: `MANAGED_DIRECT_NODE`
- loopback only: PASS
- update check: OFF
- unified key: CONFIGURED
- FreeLLMAPI authority: NONE
- Hazewave project authority: HAZEWAVE_HARNESS
- private-media egress: FORBIDDEN

## Persistence installation evidence

Observed:

- `HAZEWAVE_FREELLMAPI_PERSISTENCE=PASS`
- Termux:Boot script executable: PASS
- supervisor process online: PASS

The boot script existing and the supervisor running are not proof that Android has executed the boot path after a real device reboot. Reboot persistence remains unverified until an empirical reboot test is performed.

## Live Harness-to-provider proof

Observed command:

```bash
PYTHONPATH="$HOME/.local/share/hazewave/deploy/current/src" \
python -m hazewave.cli freellmapi probe
```

Observed result:

```text
HAZEWAVE_FREELLMAPI_LIVE_PROBE=PASS
```

Receipt:

```json
{
  "authority": "HAZEWAVE_HARNESS",
  "authorization_id": "2f0106b11132372e7ab438260923f58156ebda1cf60f2b39c019acf8256352b2",
  "capability_id": "audio.analyze",
  "content_sha256": "5bbd29fef683e7588175f4a49a800ca3a339e19642f0be31f1ec9352d7f729ed",
  "data_classification": "INTERNAL_NON_SECRET",
  "domain": "HAZE",
  "project_id": "HAZEWAVE",
  "provider_gateway": "FREELLMAPI",
  "routed_via": "kilo/dots-studio/dots-3-note-preview:free",
  "schema": "HazewaveProviderProbeReceipt/v1",
  "served_model": "dots-studio/dots-3-note-preview:free",
  "status": "PASS",
  "task_id": "hazewave-freellmapi-live-proof",
  "usage": {
    "completion_tokens": 64,
    "cost": 0,
    "is_byok": false,
    "prompt_tokens": 44,
    "total_tokens": 108
  }
}
```

No raw provider key or FreeLLMAPI unified key is recorded here.

## Security interpretation

The runtime proof establishes that a bounded Hazewave Harness authorization reached a real upstream provider through FreeLLMAPI and returned provider/model routing evidence.

The observed route was Kilo's anonymous free route. FreeLLMAPI upstream documentation states that Kilo's anonymous free route logs prompts/outputs for training. The proof prompt was synthetic and contained no private media or credentials.

After this proof, Hazewave tightens generic FreeLLMAPI egress to `PUBLIC` only. The receipt above retains the classification that was actually emitted at proof time; it is historical evidence, not the post-proof policy.

Any future use of internal project context requires a separately reviewed provider/model eligibility policy and pre-egress enforcement.


## Supervisor auto-recovery proof

Observed after Hazewave runtime advanced to:

`9242f8d70bbbae0e55dca1ec644d687607406cdd`

The managed FreeLLMAPI server process was intentionally terminated and the supervisor was allowed one reconciliation interval.

Observed:

- old managed server PID: `7384`;
- old process terminated intentionally;
- wait: 40 seconds;
- replacement managed server PID: `12654`;
- replacement PID was live;
- `HAZEWAVE_FREELLMAPI_AUTO_RECOVERY=PASS`;
- provider status after recovery: `ONLINE`;
- process identity after recovery: `MANAGED_DIRECT_NODE`;
- exact upstream SHA remained `716948f20b12ec1c9b7c6fcebd22a3e7233cda1b`.

This establishes in-session supervisor recovery from managed process death. It does not establish Android reboot persistence.

## Post-policy live proof

After generic FreeLLMAPI egress was tightened to `PUBLIC` only, a second real Harness-to-provider probe was executed.

Observed result:

```text
HAZEWAVE_FREELLMAPI_LIVE_PROBE=PASS
```

Receipt summary:

```json
{
  "authority": "HAZEWAVE_HARNESS",
  "authorization_id": "2f0106b11132372e7ab438260923f58156ebda1cf60f2b39c019acf8256352b2",
  "capability_id": "audio.analyze",
  "content_sha256": "384478d9140c931a616f570bd58192584ea3f1ddfe427e0a8b03636f2301dc5c",
  "data_classification": "PUBLIC",
  "domain": "HAZE",
  "project_id": "HAZEWAVE",
  "provider_gateway": "FREELLMAPI",
  "routed_via": "kilo/dots-studio/dots-3-note-preview:free",
  "schema": "HazewaveProviderProbeReceipt/v1",
  "served_model": "dots-studio/dots-3-note-preview:free",
  "status": "PASS",
  "task_id": "hazewave-freellmapi-live-proof",
  "usage": {
    "completion_tokens": 64,
    "cost": 0,
    "is_byok": false,
    "prompt_tokens": 44,
    "total_tokens": 108
  }
}
```

No raw provider key or FreeLLMAPI unified key is recorded.

## Remaining persistence boundary

The following are now separately proven:

- provider process identity: PASS;
- exact upstream SHA binding: PASS;
- loopback-only runtime: PASS;
- unified key configured: PASS;
- Harness-authorized real provider call: PASS;
- generic egress after policy tightening: PUBLIC-only;
- in-session supervisor recovery after managed process death: PASS;
- Termux:Boot script installed and executable: PASS.

Still not proven:

- execution of the Termux:Boot path after a real Android device reboot.

A real reboot remains the only missing runtime evidence for reboot persistence.
