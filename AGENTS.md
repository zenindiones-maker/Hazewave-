# HAZEWAVE — Agent Operating Contract v2

Hazewave is a project-local creative engineering system with two primary domains and one typed bridge.

- **HAZE** owns sound: music, voice, audio, rhythm, timbre, composition, synthesis, sound design, mixing, mastering, analysis and sonic memory.
- **WAVE** owns image: photography, websites, video, animation, visual design, generative visuals, publishing and interactive visual media.
- **BRIDGE** owns only the typed translation boundary `HAZE_STATE -> WAVE_STATE`.

## Authority

**Hazewave Harness** is the project-local control plane for task-domain routing, capability authorization and project-local execution policy.

The portfolio layer has authority=NONE over Hazewave execution. Shared knowledge may be considered as evidence, but it cannot route, authorize, promote, publish or mutate Hazewave state.

Workers, models, providers, tools and skills are subordinate executors. They may not expand their own authority.

## Source-of-truth precedence

For project authority, security and runtime rules:

1. `config/project-profile-v2.json`
2. this `AGENTS.md`
3. machine-readable schemas under `schemas/`
4. accepted architecture decisions under `docs/architecture/decisions/`
5. operational references and runbooks
6. explanatory/design documents
7. generated publication artifacts

Creative canon under `canon/` is authoritative for creative identity and domain invariants. It does not grant execution authority.

If two normative sources conflict, stop and report `HAZEWAVE_DOCUMENTATION_DRIFT`. Do not silently choose the more convenient rule.

## Setup

Development checkout:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Optional audio separation dependencies:

```bash
python -m pip install -e ".[separation,dev]"
```

Do not place credentials, private media, model caches or generated runtime state inside source-controlled paths.

## Test and validation commands

Before claiming a repository change is ready:

```bash
python -m compileall -q src
python scripts/validate_repository_contracts.py
pytest
```

On a configured Termux runtime:

```bash
bash scripts/hazewave_termux_control.sh doctor
```

A green unit suite does not replace runtime evidence when the change affects runtime behavior.

## Domain routing

Route by required capability, not by worker or model name.

- HAZE capabilities operate on sound/music/voice/audio.
- WAVE capabilities operate on images/sites/video/animation/visual systems.
- BRIDGE capabilities translate typed HAZE state into typed WAVE state.

A task requesting one domain may not silently mutate another domain. Cross-domain work must declare BRIDGE or an explicitly authorized multi-domain task.

## Data classification

Classes:

- `PUBLIC`
- `INTERNAL_NON_SECRET`
- `PRIVATE_MEDIA`
- `CREDENTIAL`

External bots are limited to `INTERNAL_NON_SECRET` or lower unless a future project-local security policy explicitly establishes a stronger isolated execution boundary.

Private voice, private media and credentials require explicit task-scoped authorization and must not be committed to the repository.

## Write rules

- Bind work to the exact repository/ref supplied by the task.
- Use candidate branches for material changes.
- Do not push directly to the canonical branch without explicit authorization.
- Do not modify promotion, publication, security or authority policy as a side effect of an unrelated task.
- Machine-readable contracts must be validated against their schemas.
- New normative documents must be registered in `docs/DOCUMENTATION_REGISTRY_V2.json`.
- When changing an accepted architecture decision, create a superseding ADR rather than rewriting history without explanation.

## Runtime isolation

A development checkout is not a runtime deployment.

Hazewave Termux namespaces are:

- config: `~/.config/hazewave`
- state: `~/.local/state/hazewave`
- immutable deployments: `~/.local/share/hazewave/deploy`

Runtime-generated data, models, credentials and private media live outside immutable source releases.

### Dedicated Telegram runtime

Hazewave Telegram uses the dedicated bot identity `@HazewaveAgentBot`.

Its boundaries are:

- code: immutable `~/.local/share/hazewave/deploy/current`;
- config: `~/.config/hazewave/telegram/`;
- state: `~/.local/state/hazewave/telegram/`;
- token: local credential only, never committed;
- access: explicitly paired private user;
- authority: Telegram is transport only; Hazewave Harness remains the project authority.

Do not reuse another project's bot token, state, supervisor, gateway, runtime checkout, or credential material.

## Path-specific expectations

### `src/hazewave/`

Behavior changes require tests. Capability routing and authorization changes require explicit negative tests for authority/domain escalation.

### `docs/wave/`

Separate design explanation from machine-executable contracts. If prose describes a required state shape, update the corresponding schema/reference when the requirement becomes normative.

### `docs/publishing/academic/`

Do not fabricate citations, evidence, provenance, reviewer identity or rights status. Consequential claims remain traceable to human-readable sources.

### `apps/neandercaus/`

Respect the project canon, including music-as-dialogue and the explicitly governed human vocal identity and rights model.

## Stop conditions

Stop and report instead of improvising when:

- the ProjectProfile is missing, invalid or superseded without a replacement;
- a normative document conflicts with repository/runtime evidence;
- task scope is insufficient for a required side effect;
- required private-data authorization is absent;
- an operation would cross project boundaries;
- a requested capability is unknown or mismatched to its domain;
- a critical provenance or rights link is unresolved.

## Handoff contract

Every material handoff must state:

- repository and branch/ref;
- base SHA and resulting HEAD SHA when mutation occurred;
- task/capability scope;
- files materially changed;
- validation commands and results;
- runtime evidence when applicable;
- unresolved risks/blockers;
- whether canonical promotion or publication was attempted.

Do not report success from intention, local-only state or unverified prose.

## Mandatory principal-engineer audit and real-execution protocol

This section is an **additional execution and verification contract**, not a new control plane. The Hazewave Harness, `config/project-profile-v2.json`, data classifications, canonical promotion gates, and the HAZE / WAVE / BRIDGE separation defined above retain precedence. It applies to work in this repository, including the WAVE site, HAZE audio system and infrastructure. It cannot authorize publication, private-media egress, remote provisioning, spending, secrets access or writes to the canonical branch.

### Non-negotiable quality bar

1. **Observed behavior wins over promises.** No fabricated evidence, success receipts, screenshots, logs, runtime claims, tests that only return `true`, TODO/placeholder counted as complete, or synthetic/mock/fake behavior passed off as real end-to-end proof. Where an isolated synthetic test is necessary, label it clearly; it never substitutes for real execution.
2. **One governed system.** Never nest another repository, shadow authority, duplicate a deployment control plane, or introduce independent nested package trees merely to make tests pass. The existing root Python project and single `apps/hazewave-site` Astro package are acknowledged as distinct real runtime domains, not competing authorities. Adding another package/runtime requires an explicit design decision and evidence.
3. **One documented entrypoint per supported runnable surface.** A developer must be able to invoke one command to install/check/build/serve that surface. It must fail with a meaningful nonzero exit code if prerequisites are unavailable. Do not describe unavailable GPU/models or private data as automatically installed or tested; disclose those separately.
4. **No simulated production claim.** Mocked dependencies, stubs, fixtures, catalogs, green workflow names, static source inspection, and self-reported PASS are insufficient to claim a capability is operational. Require actual executable artifacts, checks of external responses where authorized, and real Chromium for the site.
5. **Fix root causes without erasing work.** Preserve verified sources, current WIP, immutable checkpoints, deletion intent, and evidence. Do not blind-rerun, silently resurrect deleted architecture, relax failed gates, edit secrets into versioned files, deploy, merge, or provision paid resources.
6. **Site identity boundary.** Current reviewed WAVE experience has one artist: Indionesbala. HAZEWAVE is the dominant ornamental master brand; Indionesbala is a subordinate signature. Do not reactivate other artists, unauthorised images, chapter-number HUD or private artwork publication without owner approval.

### Ordered five-phase workflow — required for material changes

**PHASE 1 — Reverse engineer before modifying.** Pin repository/ref and exact HEAD; inventory current routes, workers, commands, env *names* (never secret values), scripts, dependencies, schemas, CI and deployment boundaries. Compare what the system promises to what it actually does. Start the real supported runtime or cite an exact-SHA real CI execution; record failures, restrictions, and artifacts. **Do not fix yet.**

**PHASE 2 — Adversarial GAP MAP.** Write `| GAP | Impact | Problem evidence |` with severity and ownership. Assess architecture, functionality, engineering quality, performance/security, developer experience/operations, and visual/artistic finish. Every critical/high gap needs reproducible evidence and a precise acceptance condition. A green unit test is not a cinematic approval.

**PHASE 3 — Current primary-source research.** For each critical/high gap, check current authoritative standards and provider documentation; normally compare 2–3 sources or clearly record why fewer are available. Record the chosen technical solution, alternatives, compatibility and provenance. Research does not grant authority to access remote private state.

**PHASE 4 — Correct and harden, one verified gap at a time.** RED: first reproduce the failure with a real test or exact readback. GREEN: apply the minimal correction within the authorized scope. Verify actual test/build/browser/runtime proof against the **new exact SHA**, then proceed to the next priority. No pass-by-assertion, speculative success, fabricated fixtures or CI-green-for-art-quality equivalence. Keep the original policy, ownership, branch and human approval gates intact.

**PHASE 5 — Clean end-to-end verification.** From a fresh clone/checkout, do clean dependency installation, typecheck/contracts, full build, local start/preview and real E2E tests with a **single documented entrypoint** where that surface supports it. Reconcile generated artifacts, locked dependencies, routes, security, error logs, ownership and responsive screenshots. A critical/high failure returns to PHASE 2 for remediation. Explicitly distinguish exercised capabilities from blocked GPU/model/external-provider/private-media/human-approval operations.

### Required handoff and no-false-closure gate

Every audit or implementation handoff MUST include **(1) initial GAP MAP, (2) gap-by-gap research + decision + code + evidence, (3) final GAP MAP with each status and remaining blockers, (4) the exact single launch/check command**, plus repository, branch, before/after SHA, changed files and exact tests/runs. Use `OPEN`, `BLOCKED`, `FIXED_VERIFIED`; never call open gaps resolved. Do not certify overall production readiness, "10/10" creative quality, or zero high-priority gaps without their corresponding independent proof and human approval where required.

A task's "continue until no critical/high gaps remain" means **work forward within a single authorized execution and real resource limits**, not an unsupervised infinite loop, a permission to violate the Harness, or a promise of background execution. On an external blocker, fail closed and preserve the exact restart point.

