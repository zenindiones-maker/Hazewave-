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
