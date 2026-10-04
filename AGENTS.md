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
