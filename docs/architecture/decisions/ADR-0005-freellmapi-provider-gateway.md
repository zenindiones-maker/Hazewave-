# ADR-0005 — FreeLLMAPI as a subordinate provider gateway

- Status: Accepted for development
- Date: 2026-10-04
- Owner: Hazewave

## Context

Hazewave needs a low-cost model execution substrate for project-local reasoning and experimentation without turning any third-party router into a control plane.

FreeLLMAPI aggregates multiple upstream model providers behind an OpenAI-compatible API and supports Android/Termux. Upstream explicitly describes the project as suitable for personal experimentation and learning rather than a stable production inference substrate.

Hazewave already defines a project-local authority model: the Hazewave Harness routes and authorizes work. Providers and tools are subordinate executors only.

## Decision

FreeLLMAPI is integrated as an **optional subordinate provider gateway**, never as Hazewave authority.

The accepted upstream baseline is:

- repository: `https://github.com/tashfeenahmed/freellmapi.git`;
- release: `v0.13.4`;
- exact commit: `716948f20b12ec1c9b7c6fcebd22a3e7233cda1b`;
- upstream license: MIT.

Hazewave does not vendor the FreeLLMAPI source tree into the Hazewave repository. The upstream runtime is materialized separately, pinned to the exact commit and activated through a project-local provider deployment pointer.

Runtime namespaces:

- provider deploy: `~/.local/share/hazewave/providers/freellmapi/`;
- provider state: `~/.local/state/hazewave/providers/freellmapi/`;
- provider config/credentials: `~/.config/hazewave/providers/freellmapi/`.

The local API is loopback-only by default:

`http://127.0.0.1:3001/v1`

Hazewave disables FreeLLMAPI update checks in the managed runtime. Upstream changes are adopted only by an explicit pin update reviewed in Hazewave.

## Authority boundary

FreeLLMAPI has:

`authority=NONE`

It may select/fail over among provider/model routes only after a Hazewave Harness authorization already exists for the Hazewave task and capability.

The provider gateway may not:

- create or widen Hazewave task authority;
- route across HAZE/WAVE/BRIDGE domains;
- promote project state;
- publish;
- mutate canonical Hazewave configuration;
- read another project's secrets or state.

Hazewave Harness remains:

`authority=HAZEWAVE_HARNESS`

## Data boundary

Initial integration is **text-only provider egress**.

Allowed classes:

- `PUBLIC`;
- `INTERNAL_NON_SECRET`.

Fail closed:

- `PRIVATE_MEDIA`;
- `CREDENTIAL`.

This deliberately does not activate FreeLLMAPI image, audio or video routing for Hazewave. Those surfaces require a separate provider-by-provider privacy, rights and data-handling review before private or rights-bearing media can leave the project boundary.

Provider API keys remain owned by the FreeLLMAPI local data store. Hazewave source code never receives or persists those raw upstream provider keys.

Hazewave may store only the local unified FreeLLMAPI bearer key in:

`~/.config/hazewave/providers/freellmapi/unified-api-key`

with local credential protections.

## Runtime security

The managed runtime:

- binds to `127.0.0.1`;
- uses an explicit AES-256-GCM encryption key stored outside source control;
- stores the SQLite database under Hazewave provider state, not under an immutable source release;
- keeps update checks disabled to prevent unreviewed code/catalog behavior changes from mutating the pinned runtime contract;
- is not exposed directly to the public internet.

The upstream project's own signed model catalog may still change model availability according to FreeLLMAPI policy. Such model catalog changes do not grant Hazewave authority and must not be treated as project policy changes.

## Terms and production boundary

FreeLLMAPI's upstream documentation states that free provider tiers are for personal experimentation and learning and are not a stable production inference substrate. Each upstream provider's terms continue to apply.

Therefore:

- FreeLLMAPI is acceptable for Hazewave development, evaluation and non-production experimentation;
- production/publication-critical Hazewave workflows must not depend solely on free-tier availability;
- a future production provider path requires an explicit reliability and provider-terms decision.

## Consequences

Benefits:

- one project-local OpenAI-compatible endpoint;
- provider failover and quota-aware routing delegated to a specialized gateway;
- no cross-project provider state;
- no provider router authority expansion.

Costs:

- another credential-bearing runtime to patch and monitor;
- upstream provider terms and free-tier stability remain external dependencies;
- Android/Termux support is upstream-labeled experimental.

## Verification

Repository-level controls are exercised by:

- `tests/test_freellmapi_integration.py`;
- `scripts/validate_repository_contracts.py`.

Runtime verification is defined in:

`docs/runbooks/FREELLMAPI_PROVIDER_V1.md`.
