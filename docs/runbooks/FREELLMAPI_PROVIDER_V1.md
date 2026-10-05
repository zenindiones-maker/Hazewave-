# FreeLLMAPI Provider Runtime v1

## Scope

This runbook installs and operates the Hazewave-scoped FreeLLMAPI provider gateway on Termux under the Governed Free Fabric policy.

FreeLLMAPI is a subordinate inference gateway only. Hazewave Harness remains the sole project-local routing and authorization authority.

Provider eligibility, data-class policy and zero-cost policy are project-owned and defined by ADR-0006 plus:

- `config/freellmapi-provider-eligibility-v1.json`;
- `schemas/freellmapi-provider-eligibility-v1.schema.json`;
- `src/hazewave/provider_policy.py`.

## Accepted upstream

- release: `v0.13.4`
- exact commit: `716948f20b12ec1c9b7c6fcebd22a3e7233cda1b`
- license: MIT
- upstream mode: personal experimentation / learning

Do not replace the exact commit with `main` or `latest`.

Application update checking remains disabled. The upstream signed model catalog is a separate discovery mechanism; catalog membership never grants Hazewave provider eligibility.

## Requirements

The upstream Termux path requires Android 7+ and Node.js 22.13 or newer. Node 24 LTS is preferred upstream.

Install prerequisites:

```bash
pkg update
pkg install -y nodejs-lts git
node --version
```

## Install the pinned provider runtime

From the active Hazewave immutable release:

```bash
bash scripts/install_hazewave_freellmapi_termux.sh
```

Expected:

```text
HAZEWAVE_FREELLMAPI_INSTALL=PASS
HAZEWAVE_FREELLMAPI_SHA=716948f20b12ec1c9b7c6fcebd22a3e7233cda1b
```

Provider namespaces remain project-local:

```text
~/.local/share/hazewave/providers/freellmapi/
~/.local/state/hazewave/providers/freellmapi/
~/.config/hazewave/providers/freellmapi/
```

Credentials, database state and generated runtime data do not belong in immutable source releases.

## Security invariants

The control doctor must report the governed fabric invariants without printing credentials:

```text
HAZEWAVE_FREELLMAPI_LOOPBACK_ONLY=PASS
HAZEWAVE_FREELLMAPI_UPDATE_CHECK=OFF
HAZEWAVE_FREELLMAPI_AUTHORITY=NONE
HAZEWAVE_FREELLMAPI_PROJECT_AUTHORITY=HAZEWAVE_HARNESS
HAZEWAVE_FREE_FABRIC=ENFORCED
HAZEWAVE_FREE_FABRIC_ZERO_COST_GUARD=ENFORCED
HAZEWAVE_FREE_FABRIC_PAID_FALLBACK=FORBIDDEN
HAZEWAVE_FREE_FABRIC_UNKNOWN_COST=DENY
HAZEWAVE_FREE_FABRIC_PRIVATE_MEDIA_DEFAULT_EGRESS=DENY
HAZEWAVE_FREE_FABRIC_UNREVIEWED_PROVIDER=QUARANTINED
```

The local API endpoint remains:

`http://127.0.0.1:3001/v1`

Do not expose it directly to the public internet.

## First-run provider configuration

Provider keys belong to FreeLLMAPI's encrypted local store.

Do not place raw provider keys in:

- the Hazewave repository;
- Telegram messages;
- Hazewave logs;
- screenshots or shell history where avoidable.

Store only the local unified FreeLLMAPI bearer key at:

`~/.config/hazewave/providers/freellmapi/unified-api-key`

and apply owner-only permissions:

```bash
chmod 600 ~/.config/hazewave/providers/freellmapi/unified-api-key
```

Do not paste that credential into chat.

## Governed routing

For provider execution Hazewave requires:

1. a valid `HazewaveAuthorization`;
2. capability/domain binding;
3. data classification;
4. zero-cost eligibility;
5. provider trust-lane eligibility;
6. media egress grant when remote private media is involved.

Unrestricted FreeLLMAPI `model=auto` is not the governed path.

Hazewave selects a provider-qualified route after policy filtering and verifies `X-Routed-Via` against that selected provider.

Unknown providers and unknown-cost routes fail closed.

There is no automatic paid fallback when free quota is exhausted.

## Data classes

```text
PUBLIC
  -> reviewed zero-cost remote or local lanes

INTERNAL_NON_SECRET
  -> LOCAL_PRIVATE or REMOTE_INTERNAL_SAFE only

PRIVATE_MEDIA
  -> local by default
  -> remote only with HazewaveMediaEgressGrant/v1

CREDENTIAL
  -> provider egress forbidden
```

A provider/model appearing in the FreeLLMAPI catalog does not alter these rules.

## Operational inspection

After syncing the immutable Hazewave release:

```bash
hazewave freellmapi inventory
hazewave freellmapi eligible
hazewave freellmapi health
```

`inventory` is local and secret-free.

`eligible` intersects the local FreeLLMAPI database with Hazewave's provider registry. It does not consume provider quota.

Example for another data class:

```bash
hazewave freellmapi eligible --data-classification INTERNAL_NON_SECRET
```

A provider that is available upstream but not Hazewave-eligible is not an execution candidate.

## Live bounded proof

Run:

```bash
hazewave freellmapi probe
```

Expected:

```text
HAZEWAVE_FREELLMAPI_LIVE_PROBE=PASS
```

The proof:

- uses synthetic PUBLIC content;
- binds a real Harness authorization;
- selects a provider-qualified eligible route;
- refuses unrestricted `auto`;
- verifies zero-cost policy;
- records route/model evidence;
- emits no raw provider key or unified router key.

For a broader but quota-conservative report:

```bash
hazewave freellmapi probe-all
```

`probe-all` performs one live text proof and reports the other currently eligible surfaces without calling all of them. This prevents a diagnostic from consuming scarce free image/video/audio quotas.

## Quota and MCP observability

Hazewave's client wrapper permits only these FreeLLMAPI MCP tools:

- `healthcheck`;
- `list_models`;
- `provider_health`;
- `usage_summary`;
- `routing_info`;
- `cache_stats`;
- `compression_stats`.

It deliberately rejects:

- `ask_freellmapi`;
- `set_routing_strategy`;
- unknown MCP tools.

Those exclusions prevent provider inference or routing mutation from bypassing the Harness boundary.

When FreeLLMAPI MCP is enabled locally:

```bash
hazewave freellmapi quota --range 24h
```

If MCP is disabled, quota/MCP diagnostics may report a local gateway error; this does not make the inference gateway itself offline.

## Supported governed surfaces

The project client implements policy-bound access to:

- OpenAI-compatible chat;
- streaming chat;
- Responses;
- legacy completions;
- Anthropic Messages;
- native Gemini `/v1beta`;
- Ollama `/api/chat`;
- tool-call proposal transport;
- vision;
- embeddings;
- image generation;
- video generation;
- TTS;
- transcription;
- Fusion;
- cache/compression/session/task-type request controls.

A method existing in source does not prove that a live provider for that modality is configured. Runtime availability is reported only from real local inventory/eligibility evidence.

Ollama compatibility also requires the FreeLLMAPI Ollama emulation surface to be enabled locally.

## Embedding rule

Embedding failover may not cross vector families.

Hazewave verifies the family, eligible provider membership and vector dimensions before accepting an embedding result.

## Media rule

Remote generated media remains auxiliary.

FreeLLMAPI-generated images/videos do not become canonical WAVE engine output automatically.

Private-media remote egress requires a scoped grant; PUBLIC media may use approved public-free providers.

## Efficiency controls

Governed calls may request:

- exact-match response cache;
- prompt compression;
- task-type routing hint;
- session id/context continuity.

These options do not widen the eligible provider pool.

Fusion is not the default route because monetary cost may be zero while free-quota cost is high.

## Persistence

Install/update the project-local supervisor and Termux:Boot entry:

```bash
bash scripts/install_hazewave_freellmapi_persistence.sh
```

The control and supervisor locks carry owner identity and recover stale state left by abrupt process death/reboot.

Expected:

```text
HAZEWAVE_FREELLMAPI_PERSISTENCE=PASS
```

The historical A15 proof has already demonstrated a real Android cold boot for the crash-safe persistence baseline. Any new immutable Hazewave release that changes runtime behavior still requires its own bounded post-sync verification.

## Stop / restart / logs

```bash
bash scripts/hazewave_freellmapi_control.sh stop
bash scripts/hazewave_freellmapi_control.sh restart
bash scripts/hazewave_freellmapi_control.sh logs 100
```

## Upgrade policy

Do not run `git pull` inside an active immutable provider release.

To change the FreeLLMAPI upstream pin:

1. review upstream code/release/security notes;
2. update the exact provider SHA in Hazewave;
3. run repository contracts and tests;
4. install the new provider release beside the old one;
5. verify doctor and governed probes;
6. activate only after validation.

Changing the signed model catalog does not itself change Hazewave provider eligibility.

## Failure policy

Legitimate terminal states include:

```text
ZERO_COST_POOL_UNAVAILABLE
ZERO_COST_POOL_EXHAUSTED
POLICY_DENIED
PRIVATE_MEDIA_GRANT_REQUIRED
```

Do not convert those states into:

- paid inference;
- unreviewed provider fallback;
- private-data downgrade to PUBLIC;
- direct agent-to-FreeLLMAPI bypass.

## Repository validation

Before runtime adoption:

```bash
python -m compileall -q src
python scripts/validate_repository_contracts.py
pytest
```

Both Python 3.12 and 3.14 CI jobs must be green.

The implementation reference is:

`docs/reference/HAZEWAVE_FREE_FABRIC_V1.md`
