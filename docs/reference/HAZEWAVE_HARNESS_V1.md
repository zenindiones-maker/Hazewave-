# Hazewave Harness Reference v1

Hazewave Harness is the project-local control plane implemented by `src/hazewave/harness.py`.

## Authority

The Harness may:
- route tasks to HAZE, WAVE or BRIDGE;
- bind a required capability to the matching domain;
- issue project/task/capability-bound authorization;
- reject domain or capability escalation.

The Harness may not derive execution authority from portfolio metadata or expand its own authority.

## Current capability surface

HAZE:
- `audio.generate`
- `audio.separate`
- `audio.analyze`
- `audio.mix`
- `audio.master`
- `audio.voice`

WAVE:
- `visual.render`
- `visual.image`
- `visual.video`
- `visual.site`
- `visual.animate`

BRIDGE:
- `bridge.haze_to_wave`

Cross-domain meta-capabilities, always bound to the requested HAZE/WAVE/BRIDGE domain at authorization time:
- `reason.general`
- `reason.deep`
- `reason.fusion`
- `code.generate`
- `code.review`
- `embedding.create`
- `decision.route`
- `decision.gate`
- `decision.score`

The decision.* capabilities may be executed by a subordinate local provider such as Colibri, but the provider has authority=NONE and cannot expand the Harness authorization.

## Verification

```bash
python -m hazewave.harness doctor
pytest tests/test_hazewave_harness.py
```
