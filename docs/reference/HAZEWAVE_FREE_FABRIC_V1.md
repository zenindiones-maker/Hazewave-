# Hazewave Governed Free Fabric v1

## Status

Repository implementation: GREEN on the active development branch.

Runtime activation: requires immutable Termux sync of the resulting branch SHA before live capability claims are made for the A15.

## Authority

Hazewave Harness remains the sole project-local authority:

`AUTHORITY=HAZEWAVE_HARNESS`

FreeLLMAPI remains a subordinate provider gateway:

`FREELLMAPI_AUTHORITY=NONE`

No provider response, model catalog entry, compatibility surface, or MCP tool grants Hazewave execution authority.

## Core policy

The governed fabric is fail-closed:

```text
PAID_FALLBACK=FORBIDDEN
UNKNOWN_COST=DENY
CREDENTIAL_EGRESS=DENY
PRIVATE_MEDIA_DEFAULT_EGRESS=DENY
UNREVIEWED_PROVIDER=QUARANTINED
```

Provider discovery and FreeLLMAPI signed-catalog membership do not grant Hazewave eligibility.

Execution requires a project-owned policy decision from:

`config/freellmapi-provider-eligibility-v1.json`

validated by:

`schemas/freellmapi-provider-eligibility-v1.schema.json`

and enforced by:

`src/hazewave/provider_policy.py`

## Provider routing

Governed provider execution does not use unrestricted FreeLLMAPI `auto`.

Hazewave discovers routable models, applies its own provider/cost/data policy, then submits an explicit provider-qualified model id such as:

```text
github:gpt-free
kilo:dots-studio/dots-3-note-preview:free
```

The provider reported in `X-Routed-Via` is checked against the selected provider. A provider mismatch fails the request.

## Implemented surfaces

All of the following use the common Hazewave authorization and eligibility boundary where provider execution occurs:

- OpenAI-compatible governed chat;
- streaming chat;
- OpenAI Responses compatibility;
- legacy completions compatibility;
- Anthropic Messages compatibility;
- native Gemini `/v1beta` compatibility;
- Ollama `/api/chat` compatibility;
- tool-call proposal transport;
- vision input;
- embeddings with family/dimension binding;
- image generation;
- video generation;
- text-to-speech;
- transcription;
- Fusion with an explicit eligible panel and judge;
- response-cache/compression/task-type/session controls;
- read-only MCP observability.

## MCP boundary

Hazewave exposes only read-only FreeLLMAPI MCP observability through its client wrapper:

- `healthcheck`
- `list_models`
- `provider_health`
- `usage_summary`
- `routing_info`
- `cache_stats`
- `compression_stats`

The following are deliberately not available through the Hazewave MCP wrapper:

- `ask_freellmapi` — bypasses the Hazewave authorization/routing boundary;
- `set_routing_strategy` — mutates gateway routing state outside Harness governance.

Model execution continues through governed Hazewave methods instead.

## Media boundary

`PRIVATE_MEDIA` remains local-only by default.

Remote private-media egress requires `HazewaveMediaEgressGrant/v1` bound to:

- task;
- authorization;
- asset digest;
- provider;
- model pattern;
- modality;
- purpose;
- rights basis;
- expiration.

A grant for another task, provider, model, asset or modality is rejected.

## Embeddings

Embedding routing is bound to one embedding family.

Hazewave verifies:

- the selected family is eligible;
- every routable family member is policy-compatible;
- the returned provider is one of the eligible family members;
- returned vector dimensions equal the expected family dimensions.

Cross-family failover is not allowed.

## Fusion

Fusion remains opt-in and uses capability:

`reason.fusion`

It is treated as:

```text
MONEY_COST=ZERO
QUOTA_COST=HIGH
```

The panel and judge are explicit policy-eligible models; unrestricted FreeLLMAPI `fusion` auto-routing is not the governed execution path.

## Compatibility surfaces

Native Gemini and Ollama compatibility are convenience wire formats only.

They do not change:

- task authority;
- provider eligibility;
- data classification;
- cost policy;
- model pinning.

Ollama emulation must also be enabled in the local FreeLLMAPI instance before a live Ollama-compatible call can succeed.

## Operational CLI

Available commands:

```bash
hazewave freellmapi inventory
hazewave freellmapi eligible
hazewave freellmapi eligible --data-classification PUBLIC
hazewave freellmapi health
hazewave freellmapi quota
hazewave freellmapi probe
hazewave freellmapi probe-all
```

`inventory` reports the local FreeLLMAPI surface without exposing stored provider credentials.

`eligible` intersects the local catalog with Hazewave policy.

`probe` makes one real, bounded, Harness-authorized zero-cost text request.

`probe-all` deliberately performs only that one live text request and reports eligibility for the other surfaces without spending their finite free quotas.

`quota` uses read-only MCP usage observability and therefore requires the FreeLLMAPI MCP server to be enabled locally.

## Receipts

Governed execution emits `HazewaveProviderExecutionReceipt/v1` or a surface-specific proof envelope containing project/task/capability binding, provider/model route, data classification, trust lane, zero-cost verification and content digests.

Raw provider keys and the local unified FreeLLMAPI key are never included.

## Runtime invariants

The FreeLLMAPI provider runtime remains:

- exact-SHA pinned;
- loopback-only;
- outside the Hazewave source tree;
- stateful data outside immutable releases;
- crash-safe under control/supervisor stale-lock recovery;
- Termux:Boot managed;
- application update checks disabled.

The upstream signed model catalog is a distinct discovery mechanism. Catalog discovery does not override project eligibility.

## Verification

Repository gate:

```bash
python -m compileall -q src
python scripts/validate_repository_contracts.py
pytest
```

Required CI matrix:

- Python 3.12;
- Python 3.14.

Runtime adoption gate after immutable sync:

```bash
hazewave freellmapi inventory
hazewave freellmapi eligible
hazewave freellmapi health
hazewave freellmapi probe
```

Only capabilities that produce real eligible routes may be reported as runtime-available.
