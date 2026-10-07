# ADR-0007 — Colibri Local Decision Plane

- Status: ACTIVE / DEVELOPMENT IMPLEMENTATION
- Date: 2026-10-06
- Authority: HAZEWAVE_HARNESS
- Supersedes: none
- Extends: ADR-0006 governed zero-cost provider fabric

## Context

Hazewave needs more local intelligence without turning an external runtime into project authority or consuming paid API capacity. Colibri v2.0.0 provides a local HTTP server and a System One endpoint for typed closed-set decisions. Its decision engines are materially smaller than its chat/creative models.

The current GitHub workstation lane is intentionally resource-constrained. The useful target is therefore not the 419–429 GB GLM class and not an 8 GB-minimum chat model that would consume essentially all workstation RAM. The useful first target is a decision model that can remain subordinate to the Harness.

## Decision

Hazewave adopts Colibri as a subordinate local execution provider with provider_authority=NONE.

Flow:

HAZEWAVE_HARNESS -> decision.route | decision.gate | decision.score -> Colibri /v1/systemone -> typed probabilities -> existing Harness policy

Colibri never grants an authorization and never expands a capability. A Colibri answer may rank or classify choices that are already legal under Hazewave policy. It cannot override static deny rules, publication gates, security review, promotion review, human approval requirements, or project boundaries.

### Current admitted model

Laya is the only execution-enabled model in V1.

Reasons:

- Colibri documents about 0.85 GB download and about 1.7 GB resident RAM for its Laya decision engine.
- It returns choice, score and noul answers with probabilities rather than generating prose.
- The model is Apache-2.0.
- The repository policy keeps 3 GB of system RAM and 6 GB of disk as Hazewave reserve instead of treating upstream minimum hardware as a production budget.
- The exact upstream model revision and primary safetensors SHA-256 are pinned.

GLiNER2.5-Decide is catalogued but disabled until its pin and Hazewave benchmark are promoted. Clef is not a current-workstation candidate: Colibri documents roughly 52–55 GB on disk and at least about 19 GB RAM.

### Language boundary

Colibri v2.0.0 supports the root Laya checkpoint, which its engine documentation describes as English-only. The Laya repository also contains a multilingual checkpoint, but Colibri v2.0.0 states that its multilingual Laya checkpoint is not supported by the engine yet.

Therefore V1 admits only state_language=en. Direct classification of the owner's PT-BR messages is not qualified. V1 is intended first for normalized internal state, stable enums, compact English machine summaries and closed operational questions. A future multilingual lane requires runtime proof before admission.

### Runtime and security boundary

- Colibri is pinned to release v2.0.0, source commit bf2442915d6e3dd4cdfd2eb9c2a3d2aa44a25850.
- The Linux x86_64 release checksum is pinned in config/colibri-local-provider-v1.json.
- The server is permitted only at http://127.0.0.1:28080.
- A bearer API key is required even on loopback.
- Auto-install and auto-download are forbidden.
- Colibri MCP is not granted install or execution authority.
- Credentials are forbidden input.
- Raw audio, image and video ingress is not part of this decision lane.
- Model files are treated as untrusted executable-adjacent input because Colibri has published memory-safety advisories involving crafted model/config data. Only allowlisted revisions/checksums may become runtime candidates.
- Health must return status=ok before a System One request is accepted.
- A response must report provider=colibri, the expected model id and usage.cost=0.

### Confidence boundary

The default choice confidence threshold is 0.80. Below threshold the adapter fails closed or hands control back to an existing deterministic Harness rule. Confidence is not authorization. Even a high-confidence answer cannot self-approve security, promotion or publication.

## Where Colibri helps Hazewave

The high-value V1 uses are:

1. HAZE/WAVE/BRIDGE classification after deterministic prechecks.
2. Selecting among already-authorized execution lanes.
3. Triage of QC evidence into review buckets without changing underlying QC thresholds.
4. Daily-intelligence prioritization and contradiction triage.
5. Incident severity and retry/defer/escalate classification.
6. Human-review routing where the model may recommend automatic, review, or block while the Harness enforces final policy.

The decision plane should reduce generative-model calls for closed questions. It must not be used where deterministic code already has the exact answer.

## Deferred lanes

### Local chat/code

Qwen3-Coder-30B-A3B and Qwen3.6-35B-A3B are supported by Colibri but are not admitted on the current small GitHub workstation. Colibri publishes about 8 GB minimum RAM / 19.4 GB disk for Qwen3-Coder and 10 GB minimum RAM / 23.1 GB disk for Qwen3.6. Hazewave requires additional workstation reserve, so an upstream minimum is not sufficient.

A future larger workstation can qualify these models for reason or code work only after measured latency, memory, disk, coexistence with REAPER/FFmpeg and zero-cost quota evidence.

### Image generation

Qwen-Image-2.1 is not admitted. Colibri lists about 33 GB disk and 12 GB minimum RAM, and the upstream catalog identifies a research/non-commercial license. Hazewave must not place it in a commercial production lane without a separate license basis.

### Giant MoE

GLM-5.2/5.3, DeepSeek V4, Kimi K3 and similar models remain discovery candidates for future larger local machines. They are not a GitHub Codespaces V1 target.

## Proof states

Repository implementation can reach COMPATIBLE through CI. It does not reach RUNTIME_PROVEN until the real Hazewave workstation demonstrates exact source/model identity, loopback-only binding, API-key enforcement, real health and System One calls, resource headroom, zero paid egress, representative Hazewave benchmarks, and restart/recovery behavior.

PRODUCTION_APPROVED requires those proofs plus human/security review where applicable.
