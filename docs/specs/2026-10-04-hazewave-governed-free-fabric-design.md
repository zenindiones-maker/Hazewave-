# Hazewave Governed Free Fabric — Design v1

- Status: Approved for implementation
- Date: 2026-10-04
- Owner: HAZEWAVE
- Authority: HAZEWAVE_HARNESS
- Provider gateway authority: NONE

## Goal

Use the maximum practical zero-monetary-cost FreeLLMAPI surface for Hazewave without allowing a provider router to widen project authority, leak private media by default, or fall through to paid inference.

## Architecture

```text
Goal
 -> HAZEWAVE_HARNESS
 -> HazewaveAuthorization
 -> capability/domain
 -> data classification
 -> rights/media policy
 -> ZeroCostEligibility
 -> ProviderTrustLane
 -> explicit eligible provider/model
 -> FreeLLMAPI
 -> subordinate provider
 -> HazewaveProviderExecutionReceipt
```

FreeLLMAPI owns provider availability, quota/cooldown tracking, model adapters and failover inside an already-authorized pool. Hazewave owns eligibility, cost, privacy, rights and capability authority.

## Core invariants

```text
HAZEWAVE_HARNESS_AUTHORITY=PASS
FREELLMAPI_AUTHORITY=NONE
PAID_FALLBACK=FORBIDDEN
UNKNOWN_COST=DENY
CREDENTIAL_EGRESS=DENY
PRIVATE_MEDIA_DEFAULT_EGRESS=DENY
UNREVIEWED_PROVIDER=QUARANTINED
```

## Zero-cost policy

A route is executable only when its registry entry proves:

- monetary policy permits zero-cost execution;
- billing overflow cannot silently widen to paid for the selected policy;
- provider policy is approved;
- capability and modality are allowed;
- data classification is allowed;
- media rights/egress gate passes when applicable.

Unknown cost, unknown terms, or unknown privacy behavior is fail-closed.

## Trust lanes

- `LOCAL_PRIVATE`: local or explicitly attested project-controlled execution. May handle approved private media.
- `REMOTE_INTERNAL_SAFE`: remote route reviewed for internal non-secret data. Private media still requires a scoped grant.
- `REMOTE_PUBLIC_FREE`: free/keyless/experimental routes suitable only for PUBLIC data.
- `QUARANTINED`: not automatically executable.

## Model selection

Hazewave must not use unrestricted `model=auto` for governed requests because FreeLLMAPI model unification can fail over across several providers. Governed calls select a provider-qualified model identifier (`platform:model_id`) or a Hazewave-created profile whose members are all eligible under the same policy.

The signed upstream catalog is discovery evidence, not authorization.

## Data classes

- `PUBLIC`: eligible remote or local lanes.
- `INTERNAL_NON_SECRET`: local or approved internal-safe routes.
- `PRIVATE_MEDIA`: local by default; remote only with `HazewaveMediaEgressGrant/v1`.
- `CREDENTIAL`: provider egress forbidden.

## HAZE

Prefer local extraction of BPM, onsets, section boundaries, spectral flux, harmonic stability, timbre, stereo field, motif identity and energy curves. Send structured `HAZE_STATE` for remote reasoning when possible instead of raw private audio.

FreeLLMAPI augments HAZE with reasoning, transcription, scratch TTS and audio description. It does not replace ACE-Step, Demucs or the canonical production pipeline.

## WAVE

Free provider image/video output is auxiliary: concept art, storyboard, previs, ideation and reference material. Canonical WAVE output remains the Living Resonance Engine:

```text
HAZE_STATE -> Translation Layer -> WAVE_STATE -> HazeMatter -> Living Resonance Engine
```

## BRIDGE

BRIDGE translates structured HAZE state into WAVE state. It should not export raw audio merely to derive parameters that can be computed locally.

## Supported fabric surfaces

The implementation may expose, when eligible and available:

- chat and streaming;
- OpenAI Responses-compatible reasoning;
- legacy completions for compatible agents;
- tool calling and structured outputs;
- Fusion multi-model synthesis;
- embeddings with family/dimension binding;
- vision;
- transcription;
- TTS;
- image generation;
- video generation;
- health/quota/cache/compression/routing introspection;
- MCP observability;
- agent-provider bridges.

## Fusion

Fusion is `MONEY_COST=ZERO` but `QUOTA_COST=HIGH`. It requires its own capability and is not the default route for ordinary requests.

## Tool authority

A model may propose a tool call. Only Hazewave Harness may authorize execution of the tool. Provider output never grants tool authority.

## Catalog/update boundary

- FreeLLMAPI code remains pinned to an exact reviewed SHA.
- Application update checking remains disabled.
- The upstream signed model catalog may refresh independently.
- An unsigned catalog is not trusted.
- A signed catalog entry does not become Hazewave-eligible automatically.

## Registry

`config/freellmapi-provider-eligibility-v1.json` is the project-owned policy registry. It records provider trust lane, zero-cost/billing policy, allowed data classes/modalities/capabilities, review state and evidence URLs. New providers enter as quarantined until reviewed.

## Media egress grants

A remote private-media request requires a task-scoped `HazewaveMediaEgressGrant/v1` bound to:

- task authorization;
- asset digest;
- provider;
- model or model pattern;
- purpose;
- modality;
- rights basis;
- expiration.

A grant for another asset/provider/task is invalid.

## Receipts

Provider execution returns `HazewaveProviderExecutionReceipt/v1` with:

- project/authority/task/authorization;
- capability/domain/classification;
- provider gateway/provider/model/trust lane;
- zero-cost verification state;
- route and usage;
- input/output digests;
- optional media grant id;
- terminal status.

Credentials and raw provider keys are never recorded.

## Failure semantics

- No eligible route: `ZERO_COST_POOL_UNAVAILABLE`.
- Eligible routes exhausted: `ZERO_COST_POOL_EXHAUSTED`.
- Unknown/paid route: denied before egress.
- No automatic paid fallback.
- No silent data-class downgrade.
- No cross-model embedding-family fallback.

## Rollout

1. Governance core: registry, schema, zero-cost guard, trust lanes, grants and receipts.
2. Text intelligence: provider-qualified discovery, chat/reasoning/tools/Fusion.
3. Knowledge: embeddings, quota/health/cache/compression.
4. Multimodal: vision, transcription, TTS, image and video with provenance.
5. Agent fabric: governed adapters/MCP observability.
6. Runtime proof: CI, immutable sync, A15 live zero-cost probes and cold-boot regression.

## Completion criteria

Repository and runtime must prove that all provider execution is Harness-authorized, zero-cost-only, policy-filtered, secret-free in receipts, and fail-closed for private media and unknown providers.
