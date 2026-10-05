# ADR-0006 — Governed zero-cost provider fabric

- Status: Accepted for development
- Date: 2026-10-04
- Owner: Hazewave
- Supersedes: ADR-0005 for provider eligibility and FreeLLMAPI routing policy

## Context

ADR-0005 established FreeLLMAPI as a pinned, loopback-only subordinate provider gateway. Runtime proof subsequently established immutable deployment, crash-safe persistence and cold-boot recovery.

Hazewave now requires a broader FreeLLMAPI surface: reasoning, tools, embeddings, vision, transcription, speech, image/video generation, Fusion and agent compatibility. A single unrestricted FreeLLMAPI `auto` pool is insufficient because free providers differ in billing overflow behavior, data handling, modality, rights constraints and terms.

FreeLLMAPI model unification may route one logical model across multiple providers. Therefore filtering only after FreeLLMAPI chooses a provider does not enforce Hazewave policy.

## Decision

Hazewave adopts a project-owned **Governed Free Fabric**.

Hazewave Harness remains the sole project-local authority. FreeLLMAPI remains `authority=NONE`.

Every provider execution must pass, before egress:

1. exact task/capability authorization;
2. domain match;
3. data-class policy;
4. media-rights grant where required;
5. provider eligibility;
6. zero-monetary-cost eligibility.

Unknown cost or provider policy fails closed.

For governed requests Hazewave selects an explicit provider-qualified model (`platform:model_id`) or a Hazewave-managed profile composed only of policy-equivalent eligible members. Unrestricted `auto` is not an authorized governed route.

## Trust lanes

- `LOCAL_PRIVATE`
- `REMOTE_INTERNAL_SAFE`
- `REMOTE_PUBLIC_FREE`
- `QUARANTINED`

New provider identities default to `QUARANTINED`.

## Cost boundary

Paid fallback is forbidden. Eligibility must distinguish verified zero-cost execution from free credits or routes that can overflow into paid billing. If a route cannot prove a fail-closed zero-cost policy, Hazewave does not automatically execute it.

## Data boundary

`CREDENTIAL` never leaves the project through a provider.

`PRIVATE_MEDIA` is local-only by default. Remote private-media egress requires a task-scoped `HazewaveMediaEgressGrant/v1` bound to the asset, provider and purpose.

`INTERNAL_NON_SECRET` requires `LOCAL_PRIVATE` or `REMOTE_INTERNAL_SAFE`.

`PUBLIC` may use approved zero-cost remote routes.

## Catalog boundary

FreeLLMAPI application code remains pinned to the exact reviewed SHA. Application update checking remains disabled.

The upstream signed catalog is a distinct discovery mechanism and may refresh. A catalog signature proves catalog origin/integrity, not Hazewave eligibility. Hazewave's project-owned eligibility registry is authoritative for execution policy.

## Media and WAVE boundary

Remote image/video generation is auxiliary and does not become canonical WAVE output. The Living Resonance Engine remains the canonical WAVE rendering path.

## Consequences

Benefits:

- maximum useful free-provider capacity without paid fallback;
- dynamic model discovery without dynamic authority expansion;
- one policy boundary for text, agents and multimodal surfaces;
- explicit private-media rights boundary;
- provider-qualified routing prevents unapproved cross-provider failover.

Costs:

- Hazewave must maintain provider policy evidence;
- some available FreeLLMAPI routes remain quarantined;
- private-media remote execution is intentionally more restrictive;
- Fusion and multimodal probes consume finite free quota even when monetary cost is zero.

## Verification

Implementation is accepted only with RED/GREEN tests for unknown provider denial, paid/unknown-cost denial, data-class restrictions, media-grant binding, provider-qualified model selection, receipt redaction and no paid fallback.

Runtime acceptance additionally requires immutable Termux deployment and live receipts showing zero-cost execution on selected eligible surfaces.
