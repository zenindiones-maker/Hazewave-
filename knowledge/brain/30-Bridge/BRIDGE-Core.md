---
project: HAZEWAVE
domain: BRIDGE
type: competency-map
authority: KNOWLEDGE_ONLY
execution_authority: false
status: DEVELOPMENT
updated: 2026-10-08
---

# BRIDGE — Typed Audiovisual Translation

BRIDGE does not own audio or visuals. It translates typed state between HAZE and WAVE without transferring authority.

## Allowed knowledge

- section/marker timelines;
- beats, onsets and tempo grids;
- amplitude/envelope summaries;
- spectral/energy bands when explicitly approved;
- dialogue/phoneme timing;
- scene/shot boundaries;
- motion cues;
- transition timing;
- render/timebase metadata;
- synchronization tolerances.

## Core contract

`HAZE_STATE -> typed translation -> WAVE_STATE`

Examples:

- approved music section markers -> scene transition markers;
- amplitude envelope -> bounded visual intensity parameter;
- onset timestamps -> animation trigger timestamps;
- phoneme timing -> lip-sync cue sequence;
- approved tempo map -> editor/motion time grid.

## Forbidden behavior

BRIDGE must not:
- master audio;
- choose visual art direction;
- rewrite HAZE or WAVE policy;
- infer authority from a model confidence value;
- move raw private media into an unapproved provider;
- publish or promote output;
- convert correlation into an artistic decision without the owning domain.

## Quality evidence

- timebase and units explicit;
- deterministic mapping;
- source/target hashes;
- synchronization error measured;
- no hidden resampling or frame-rate conversion;
- owner domains retain final judgement.
