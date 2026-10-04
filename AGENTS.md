# HAZEWAVE — agent contract

Hazewave is one project with two primary creative domains and one explicit bridge.

- **HAZE** owns sound: music, voice, audio, rhythm, timbre, composition, synthesis, sound design, mixing, mastering and sonic analysis.
- **WAVE** owns image: photos, sites, video, images, animation, visual design, generative visuals and interactive visual media.
- **BRIDGE** owns only the typed translation boundary `HAZE_STATE -> WAVE_STATE`.

## Project authority

**Hazewave Harness** is the project-local control plane for task-domain routing, capability authorization and project-local execution policy.

The portfolio layer has authority=NONE over Hazewave execution. Shared portfolio knowledge may inform decisions, but it may not route, authorize, promote, publish or mutate Hazewave state.

BR-no-GTA is a separate project. Its Harness, runtime, secrets, state, deployment model and policies must not be imported automatically into Hazewave. Reuse across projects requires an explicit target-project decision.

## Stable execution direction

Human goal
→ Hazewave Harness
→ explicit HAZE / WAVE / BRIDGE domain
→ required capability
→ bounded worker/provider/tool
→ typed result/evidence
→ review when required
→ project-local state.

Routing is capability-first. Worker or model names are implementation details.

## Development and runtime isolation

A development checkout is not a production/runtime deployment.

Termux runtime for Hazewave uses its own namespace:

- config: `~/.config/hazewave`
- state/logs: `~/.local/state/hazewave`
- deployment store: `~/.local/share/hazewave/deploy`

Hazewave must never depend on the BR-no-GTA checkout or state directories.

Runtime-generated data, credentials, models and private media must remain outside immutable source releases.

## Cross-project safety

Never expose or copy credentials, private media, biometric material, databases or runtime state from another project into Hazewave.

External bots receive no secrets and no private media by default.

## Canonical references

- `config/project-profile-v1.json`
- `canon/hazewave-domain-v1.json`
- `docs/HAZEWAVE_SYSTEM_INDEX.md`
- `apps/neandercaus/README.md`

When repository reality conflicts with prose, report the drift instead of silently inventing a resolution.
