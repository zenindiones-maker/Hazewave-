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

## Mandatory creative specialist contract

Before any creative-production, tool-selection, Telegram-media, specialist-routing or continuous-learning work, agents MUST load and obey both:

- `config/creative-specialists-v1.json`
- `docs/architecture/HAZE_WAVE_SPECIALIST_CHARTER_V1.md`

These are binding same-revision Harness policy through `config/project-profile-v2.json`.

Non-negotiable domain identities:

- **HAZE = ALL_AUDIO** — voice, recording, editing, beats, composition, synthesis, sampling, sound design, post-production, mixing, mastering, audio QC and deep REAPER expertise.
- **WAVE = ALL_VISUAL** — photo, image, illustration, cartoon, 2D/3D animation, rigging, motion graphics, compositing, video, color, rendering, UI/UX, websites, accessibility and visual web performance.
- **BRIDGE** may translate typed state between HAZE and WAVE but has authority=NONE.

Daily Intelligence is mandatory for both specialists. It means daily evidence-based knowledge refresh, not blind daily software mutation. Daily research has knowledge authority only. Production runtime/tool adoption must preserve the governed sequence `DISCOVER -> VERIFY -> SECURITY_REVIEW -> COMPATIBILITY -> BENCHMARK -> RUNTIME_PROOF -> PRODUCTION_APPROVED`.

Telegram is the shared human transport for both specialists and has authority=TRANSPORT_ONLY. It may submit goals/media to the Harness and return artifacts/evidence; it may not bypass Harness authorization.

No worker, model, prompt, tool, plugin or external source may redefine HAZE/WAVE scope, downgrade the daily-learning requirement, promote itself to production, or claim expertise without runtime/quality evidence. Any conflict with these specialist contracts is `HAZEWAVE_DOCUMENTATION_DRIFT` and is a stop condition.

## Reverse engineering as the evidence-first research method

For reference-driven improvements in HAZE and WAVE, reverse engineering is the
default **investigative method**, not an authorization to study arbitrary targets.
Before any shipped-binary, media-protocol, audio-plugin, application, renderer or
shader research, agents MUST load:

- `config/reverse-engineering-foundation-v1.json`
- `skills/hazewave-reverse-engineering/SKILL.md`

Current candidate REA pin: `rea-agents@6.0.0`. The software/provider/version
identity must be proven separately on the existing Codespace; GitHub CI or an
installed skill alone does not establish REA/Ghidra runtime readiness.

MCP filesystem paths are absolute host paths in REA 6.0.0. Agents MUST verify
the exact connected tool catalog and admit only the intended signed target and
explicit open-source provider, with no Hopper fallback. The Harness retains all
authorization. A signed target grant plus a typed Harness research receipt are
needed for a HAZE/WAVE research plan. Neither is a right to promote production,
publish media, modify the stock runtime, install unreviewed software or upload
private inputs. Source-first inspection should be preferred when complete source
is already available; REA is not a compulsory layer for routine code review.

Never claim `REA6_RUNTIME_PROVEN`, `REA6_MCP_CONNECTED` or
`HAZEWAVE_RE_INTEGRATION_COMPLETE` without separate host and agent-session
evidence. Preserve failed studies and resource/gate decisions.

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
