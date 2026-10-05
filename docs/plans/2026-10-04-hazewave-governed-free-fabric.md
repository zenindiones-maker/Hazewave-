# Hazewave Governed Free Fabric Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Harness-authorized, zero-cost-only FreeLLMAPI provider fabric with provider-qualified routing, typed receipts and fail-closed media/data policy.

**Architecture:** A pure project-owned policy engine evaluates provider eligibility before any provider request. The FreeLLMAPI client discovers ready catalog rows, binds a request to an explicit provider-qualified model, executes only after Harness authorization and emits a secret-free typed receipt. Multimodal and agent surfaces reuse the same gate rather than implementing separate trust logic.

**Tech Stack:** Python 3.12/3.14, dataclasses, enum, JSON/JSON Schema Draft 2020-12, httpx, pytest, GitHub Actions, immutable Termux releases.

## Global Constraints

- `HAZEWAVE_HARNESS` remains sole project authority.
- FreeLLMAPI remains `authority=NONE`.
- Paid fallback is forbidden.
- Unknown cost/provider policy is denied before egress.
- `CREDENTIAL` egress is always denied.
- `PRIVATE_MEDIA` remote egress requires a task/asset/provider-bound grant.
- Governed requests may not use unrestricted FreeLLMAPI `auto`.
- Provider/model discovery does not grant eligibility.
- Existing immutable/persistence/cold-boot behavior must not regress.

---

### Task 1: Governance contracts and provider eligibility registry

**Files:**
- Create: `schemas/freellmapi-provider-eligibility-v1.schema.json`
- Create: `config/freellmapi-provider-eligibility-v1.json`
- Modify: `docs/DOCUMENTATION_REGISTRY_V2.json`
- Modify: `scripts/validate_repository_contracts.py`
- Test: `tests/test_freellmapi_governed_fabric.py`

**Interfaces:**
- Consumes: ProjectProfile/v2 data classes and Harness authority.
- Produces: `HazewaveProviderEligibilityRegistry/v1` validated at repository gate.

- [ ] Add failing tests that require a registered, schema-valid eligibility registry and ADR-0006 registration.
- [ ] Run `pytest -q tests/test_freellmapi_governed_fabric.py tests/test_documentation_governance_v2.py`; expect missing artifacts/registry assertions.
- [ ] Add schema, initial conservative registry and repository validation.
- [ ] Re-run focused tests; expect pass.
- [ ] Run `python scripts/validate_repository_contracts.py`; expect `HAZEWAVE_REPOSITORY_CONTRACTS=PASS`.
- [ ] Commit the passing governance contract.

### Task 2: Pure zero-cost eligibility engine

**Files:**
- Create: `src/hazewave/provider_policy.py`
- Test: `tests/test_freellmapi_governed_fabric.py`

**Interfaces:**
- Consumes: registry entry, capability, modality, data classification and optional MediaEgressGrant.
- Produces: `ProviderEligibilityDecision` with `ALLOW` or stable denial reason.

- [ ] Add failing tests for unknown provider, paid/unknown cost, credential egress, internal/public lane boundaries and private-media grant mismatch.
- [ ] Run focused test; expect import/missing behavior failures.
- [ ] Implement trust lanes, cost states, grant validation and deterministic decision reasons.
- [ ] Re-run focused tests; expect pass.
- [ ] Run `pytest -q tests/test_hazewave_harness.py tests/test_freellmapi_integration.py tests/test_freellmapi_governed_fabric.py`.
- [ ] Commit the policy engine.

### Task 3: Governed model discovery and provider-qualified chat

**Files:**
- Modify: `src/hazewave/freellmapi.py`
- Test: `tests/test_freellmapi_integration.py`
- Test: `tests/test_freellmapi_governed_fabric.py`

**Interfaces:**
- Consumes: `GET /v1/models?execution_status=ready`, registry/policy decision and Harness authorization.
- Produces: explicit `platform:model_id` request plus `HazewaveProviderExecutionReceipt/v1`.

- [ ] Add failing tests proving unrestricted `auto` is rejected for governed calls, a provider-qualified id is emitted, unreviewed routes are skipped and receipts omit secrets.
- [ ] Run focused tests and record relevant failure.
- [ ] Implement ready-model normalization, policy filtering, deterministic model selection and governed chat execution.
- [ ] Re-run focused tests; expect pass.
- [ ] Run existing FreeLLMAPI integration and persistence tests.
- [ ] Commit governed chat/discovery.

### Task 4: Reasoning, tools, Fusion and embeddings

**Files:**
- Modify: `src/hazewave/harness.py`
- Modify: `src/hazewave/freellmapi.py`
- Modify: `src/hazewave/cli.py`
- Test: `tests/test_hazewave_harness.py`
- Test: `tests/test_freellmapi_governed_fabric.py`

**Interfaces:**
- Adds capabilities: `reason.general`, `reason.deep`, `reason.fusion`, `code.generate`, `code.review`, `embedding.create`, `visual.analyze`, `audio.transcribe`.
- Tool requests remain proposals; execution requires separate Harness authorization.
- Embedding receipts bind family and dimensions; cross-family failover is rejected.

- [ ] Add failing capability/domain and provider-surface tests.
- [ ] Implement minimal Harness mappings and generic JSON/binary request helpers under the common policy gate.
- [ ] Add Fusion quota-cost metadata and explicit capability requirement.
- [ ] Add embeddings family/dimension validation.
- [ ] Run affected Harness/FreeLLMAPI tests.
- [ ] Commit the reasoning/knowledge surfaces.

### Task 5: Governed multimodal surfaces

**Files:**
- Modify: `src/hazewave/freellmapi.py`
- Modify: `src/hazewave/cli.py`
- Test: `tests/test_freellmapi_governed_fabric.py`

**Interfaces:**
- Produces governed requests for vision, transcription, TTS, image generation and video generation.
- PRIVATE_MEDIA requires `HazewaveMediaEgressGrant/v1`; PUBLIC media may use approved public-free lanes.
- Generated media results carry provider/model/content digest provenance.

- [ ] Add failing tests for media egress, grant binding, binary response handling and no remote private-media default.
- [ ] Implement the minimum multimodal methods under the shared eligibility engine.
- [ ] Add bounded CLI inventory/probe commands without exposing keys.
- [ ] Run focused tests.
- [ ] Run full `pytest`.
- [ ] Commit multimodal surfaces.

### Task 6: Runtime and documentation closure

**Files:**
- Modify: `docs/runbooks/FREELLMAPI_PROVIDER_V1.md`
- Create: `docs/reference/HAZEWAVE_FREE_FABRIC_V1.md`
- Modify: `docs/DOCUMENTATION_REGISTRY_V2.json`
- Modify as needed: `scripts/hazewave_freellmapi_control.sh`

**Interfaces:**
- Runtime doctor reports policy/zero-cost fabric status without reading secrets.
- Runtime probe emits secret-free execution receipts.

- [ ] Add/extend contract tests for runtime diagnostics and documentation registration.
- [ ] Run `python -m compileall -q src`.
- [ ] Run `python scripts/validate_repository_contracts.py`.
- [ ] Run `pytest` and require zero failures on Python 3.12/3.14 CI.
- [ ] Sync immutable Termux release and perform bounded A15 probes on available zero-cost surfaces; do not fabricate unavailable provider evidence.
- [ ] Preserve the existing cold-boot/persistence proof and report any capability that remains unavailable because no eligible free provider/key is configured.

## Externally observable decisions

The specification settles the policy decisions required for implementation: unknown cost is denied, paid fallback is forbidden, unrestricted `auto` is forbidden for governed calls, private-media remote egress requires a scoped grant, and unavailable free capability is reported rather than silently widened. There are no unresolved product decisions blocking implementation.
