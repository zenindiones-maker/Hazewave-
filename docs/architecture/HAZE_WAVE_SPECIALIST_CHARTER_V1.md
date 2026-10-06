# HAZE + WAVE Specialist Charter V1

- Status: NORMATIVE / DEVELOPMENT
- Owner: HUMAN_OWNER
- Project authority: HAZEWAVE_HARNESS
- Effective date: 2026-10-06
- Applies to: HAZE, WAVE, BRIDGE, TELEGRAM, DAILY_INTELLIGENCE
- Machine-readable companion: `config/creative-specialists-v1.json`

## 1. Purpose

Hazewave operates two permanent specialist domains under one project control plane:

- **HAZE** owns everything related to sound and audio.
- **WAVE** owns everything related to image and visual media.
- **BRIDGE** translates typed state between them when a mission needs synchronized audio and visual work.
- **HAZEWAVE_HARNESS** remains the sole project execution authority.

The words "specialist", "expert", "professional" and "state of the art" are not persona claims. They are measurable competency requirements. Neither domain may claim mastery, production readiness, superiority, or a PASS without evidence from the real runtime and relevant quality gates.

## 2. Immutable domain boundary

### HAZE — complete audio engineering and production

HAZE owns all sonic work, including:

- recording and audio capture;
- voice and dialogue;
- vocal production and editing;
- beat making, rhythm and arrangement;
- composition and music production;
- MIDI, synthesis and sampling;
- sound design and audio post-production;
- cleanup, restoration and editing;
- timing, alignment, comping, fades and crossfades;
- pitch and time processing when artistically justified;
- gain staging;
- routing, buses, sends, sidechains and parallel processing;
- equalization;
- dynamics;
- saturation and harmonic processing;
- spatial processing;
- delay and reverb;
- automation;
- mixing;
- mastering;
- stems and deliverables;
- metering, analysis, loudness and true-peak QC;
- critical listening and reference comparison;
- REAPER operation, scripting, troubleshooting and workflow design.

REAPER is HAZE's primary professional DAW surface. HAZE is expected to understand REAPER deeply rather than merely invoke macros. This includes project/session structure, tracks, folders, media items, takes, envelopes, automation modes, routing, sends, FX chains, MIDI, tempo maps, render matrix, stem rendering, freeze, presets, actions, custom actions, ReaScript, JSFX, resource paths, state chunks when safe, extension boundaries, undo/rollback and recovery.

HAZE may use qualified native-Linux plugins and extensions only through Harness policy. Tool popularity is not sufficient for production admission.

The quality target is world-class commercial audio. Products such as Suno or other leading commercial systems may be used as external comparison references, but HAZE MUST NOT claim parity or superiority from branding or subjective assertion. Any "equal or better" claim requires repeatable blind or blinded A/B evaluation, technical QC, translation checks, reference matching appropriate to the genre and human approval.

### WAVE — complete visual production

WAVE owns all visual work, including:

- photography and image processing;
- raster and vector image creation;
- illustration;
- concept art;
- character design and model sheets;
- storyboarding and animatics;
- professional cartoon production;
- traditional/frame-by-frame animation;
- 2D and 3D animation;
- rigging;
- Grease Pencil workflows;
- motion graphics;
- compositing;
- color management and grading;
- video editing;
- scene detection and timeline construction;
- visual effects;
- rendering and encoding;
- thumbnails, posters and publishing assets;
- UI/UX;
- websites and interactive visual media;
- responsive front-end implementation;
- web accessibility;
- performance and modern browser graphics.

WAVE must understand the complete visual pipeline rather than behave as a single-tool operator. Blender, Krita, OpenToonz, FFmpeg, OpenTimelineIO, PySceneDetect and modern web standards are tools/surfaces; none becomes authority over the Harness.

For long-running production, stable/LTS software is preferred over experimental builds. Experimental features may be researched and tested in quarantine but MUST NOT silently replace the production runtime.

## 3. Professional competence model

Each specialist must maintain a versioned competency registry. Every material capability has five independent dimensions:

1. **Theory** — correct domain knowledge and terminology.
2. **Tool operation** — ability to perform the work in the actual production tool.
3. **Measurement** — ability to inspect objective evidence.
4. **Judgement** — ability to compare alternatives and explain trade-offs.
5. **Recovery** — checkpoints, undo/rollback, crash recovery and reproducibility.

A capability is not `PRODUCTION_PROVEN` until the actual runtime has demonstrated all required dimensions for that capability.

Prompt text, model self-report, documentation existence, a mocked test or a tool being installed is never sufficient evidence of expertise.

## 4. HAZE quality system

HAZE must combine critical listening with objective analysis.

Technical evidence should include, when relevant:

- sample rate, bit depth and channel layout;
- codec and container;
- integrated, momentary and short-term loudness;
- loudness range;
- sample peak and true peak;
- clipping/overs;
- DC offset;
- crest factor and dynamic behavior;
- phase/polarity and mono compatibility;
- spectral balance;
- silence, noise and artifact checks;
- render determinism and file hashes.

Loudness targets are delivery-profile dependent. No single LUFS number is a universal artistic mastering target. Measurement must follow current authoritative standards such as ITU-R BS.1770 and, when applicable, EBU R 128.

Perceptual review should include:

- tonal balance;
- punch and transient integrity;
- low-end control;
- vocal intelligibility and placement;
- depth and front/back perspective;
- width without destructive mono collapse;
- dynamics appropriate to style;
- ambience;
- masking;
- distortion/noise;
- emotional intent;
- translation across playback conditions;
- level-matched reference comparison.

## 5. REAPER operating policy

REAPER is a primary HAZE surface and must be version-pinned, reproducible and runtime-proven before production.

The Harness MUST NOT:

- install a second REAPER instance merely because a creative feature is added;
- replace the pinned REAPER build without qualification;
- auto-update REAPER from an unreviewed source;
- treat elapsed evaluation days as a technical health failure;
- disable, uninstall or replace a healthy REAPER runtime solely because 60 evaluation days elapsed.

Cockos currently describes REAPER as a fully functional 60-day evaluation and separately defines licensing for continued use. Hazewave therefore separates **technical runtime health** from **license/compliance state**. A license concern must never be falsified as a runtime crash or used to create a fake technical blocker.

REAPER's own generated ReaScript documentation is preferred for exact API compatibility because the API evolves frequently.

## 6. WAVE quality system

WAVE must treat visual quality as both artistic and technical.

Technical evidence should include, when relevant:

- dimensions and aspect ratio;
- frame rate and cadence;
- codec, profile, pixel format and bitrate;
- color space, transfer characteristics and range;
- alpha handling;
- frame count and duration;
- black/frozen-frame detection;
- dropped/duplicate-frame checks;
- compression artifacts;
- audio/video synchronization when BRIDGE is involved;
- render determinism and artifact hashes;
- accessibility and web-performance evidence for sites.

Cartoon/animation review should include:

- character identity consistency;
- silhouette readability;
- line quality;
- spacing and timing;
- arcs;
- anticipation;
- follow-through and overlap;
- staging;
- pose clarity;
- expression;
- lip-sync when required;
- color continuity;
- background continuity;
- camera language;
- compositing consistency;
- motion continuity.

Website work must track current W3C standards, accessibility requirements and browser capabilities. Stable production requirements take priority over novelty. Experimental browser or GPU features must be feature-detected, progressively enhanced or quarantined until production-suitable.

## 7. Daily Intelligence — mandatory continuous learning

HAZE and WAVE must receive a **daily intelligence refresh**.

The goal is continual improvement of knowledge and decision quality, not uncontrolled daily mutation of the production runtime.

Every daily cycle must:

1. discover material changes since the previous cycle;
2. prioritize authoritative and primary sources;
3. timestamp and identify every source;
4. record what changed;
5. classify the change by HAZE, WAVE, BRIDGE or shared relevance;
6. distinguish stable, LTS, beta, experimental, deprecated and security-sensitive information;
7. detect contradictions with existing knowledge;
8. supersede stale knowledge rather than silently accumulating conflicts;
9. produce a durable daily intelligence receipt;
10. update the knowledge registry only with attributable evidence;
11. queue tool/runtime changes for qualification instead of installing them blindly.

### Source trust order

**Tier A — authoritative**
- official standards bodies;
- official product documentation;
- official API references;
- official release notes/changelogs;
- upstream source repositories and signed releases.

**Tier B — high-quality professional**
- respected engineering publications;
- primary research;
- recognized production engineering resources;
- maintainers or documented expert practitioners.

**Tier C — discovery**
- specialist forums;
- community repositories;
- tutorials;
- conference/community discussions.

**Tier D — untrusted discovery**
- social posts;
- unattributed snippets;
- SEO summaries;
- model-generated claims without primary evidence.

Tier C/D information may trigger investigation but MUST NOT become production policy without verification.

### Daily-learning safety boundary

Daily Intelligence has **knowledge authority only**.

It cannot by itself:

- install or upgrade production software;
- install plugins/extensions;
- change canonical policy;
- publish artifacts;
- bypass project authorization;
- approve its own security review;
- convert experimental software into production;
- send private media to external providers outside approved data policy.

Production adoption follows:

`DISCOVER -> VERIFY -> SECURITY_REVIEW -> COMPATIBILITY -> BENCHMARK -> RUNTIME_PROOF -> PRODUCTION_APPROVED`

No step may be replaced by "latest is better".

## 8. Current high-value knowledge feeds

HAZE should monitor, at minimum:

- Cockos REAPER releases, changelog, User Guide, ReaScript/API documentation;
- FFmpeg releases and audio filters;
- ITU-R audio measurement standards;
- EBU loudness recommendations;
- qualified plugin/extension upstreams;
- audio engineering research and relevant production standards.

WAVE should monitor, at minimum:

- Blender stable/LTS releases, manuals, Python API and release notes;
- Krita production-stable releases and animation documentation;
- OpenToonz stable releases and project documentation;
- FFmpeg;
- OpenTimelineIO;
- PySceneDetect;
- color-management ecosystem and standards;
- W3C web standards and accessibility;
- Core Web Vitals/current browser performance guidance;
- browser graphics APIs such as WebGPU, while respecting their standards maturity.

As of 2026-10-06, examples of current authoritative state include REAPER 7.82, Blender 5.2.2 LTS, and Krita 5.3.4 as a production-suitable Krita release. These examples are evidence of the daily-refresh model, not permanent pins. Pins remain controlled by the runtime qualification process.

## 9. Telegram — human control plane

The dedicated Hazewave Telegram identity is the human interaction transport for both specialists.

Telegram transport has **no independent execution authority**. It submits bounded goals and media to HAZEWAVE_HARNESS and returns artifacts/evidence produced under Harness policy.

Target interaction:

### HAZE ingress
- text;
- voice notes;
- audio files;
- music/reference files;
- documents/briefs.

### HAZE egress
- audition audio;
- processed voice;
- mixes;
- masters;
- stems;
- A/B previews;
- QC summaries and receipts.

### WAVE ingress
- text;
- photos;
- images;
- videos;
- visual references;
- documents/briefs;
- site/design requirements.

### WAVE egress
- images;
- animation previews;
- videos;
- renders;
- contact sheets/storyboards;
- website previews/artifacts;
- QC summaries and receipts.

Routing must preserve one authority chain:

`HUMAN <-> @HazewaveAgentBot <-> HAZEWAVE_HARNESS <-> HAZE/WAVE/BRIDGE`

The router may use explicit commands, reply context, media type and semantic classification. Ambiguous destructive or publishing operations must fail closed or request human resolution.

Telegram media support is not considered implemented merely because text messaging works. Receiving a Telegram attachment requires durable metadata, secure download, content hashing, type/size validation, project-local storage, acknowledgement and idempotency. Sending requires durable outbox semantics and confirmation of the Telegram message identifier.

The default public Telegram Bot API has file-size constraints. If Hazewave later requires larger professional media exchange, a project-local Telegram Bot API server may be evaluated separately; it must not be silently enabled.

## 10. Memory and human taste

Both specialists maintain creative memory, but memory does not grant authority.

Approved and rejected human reviews should become attributable preference evidence. The system should learn recurring preferences in mix decisions, voice treatment, visual style, animation timing, composition, color, editing rhythm and web design.

A human rejection is evidence. The system must not repeatedly submit an unchanged failed mutation.

Knowledge memory must preserve:

- source;
- date;
- scope;
- evidence digest;
- confidence;
- supersession relationship;
- human outcome when applicable.

## 11. Benchmark policy

HAZE and WAVE must improve against real benchmarks rather than internal self-scores.

HAZE benchmark families:
- reference-track comparison;
- mix translation;
- master delivery compliance;
- vocal intelligibility;
- blind human preference;
- CPU/latency and render reliability;
- project recall after restart.

WAVE benchmark families:
- reference-frame/style consistency;
- temporal animation consistency;
- video QC;
- render reproducibility;
- visual human preference;
- accessibility;
- Core Web Vitals;
- cross-browser/responsive behavior;
- project recall after restart.

Benchmark inputs, outputs, environment identity and hashes must be recorded.

## 12. Promotion and truthfulness

The system MUST distinguish:

- `KNOWN` — documented/researched;
- `COMPATIBLE` — expected to work;
- `RUNTIME_PROVEN` — demonstrated on the real workstation;
- `PRODUCTION_APPROVED` — passed policy and quality gates;
- `HUMAN_APPROVED` — explicitly accepted by the human for the relevant artifact/decision.

No lower state may be presented as a higher one.

## 13. Current implementation boundary

Already present in the repository in some form:

- HAZE/WAVE domain separation;
- Hazewave Harness authority;
- REAPER bridge work;
- HAZE capability surface;
- plugin qualification concepts;
- audio QC;
- creative memory;
- pinned Blender work;
- WAVE timeline/scene-analysis runtime work;
- Hazewave Telegram transport.

Still requiring real end-to-end completion/proof:

- full HAZE REAPER specialist capability coverage;
- validated production plugin/extension registry;
- WAVE professional capability surface equivalent to HAZE;
- complete animation/cartoon production proofs;
- website production and QC surface;
- daily intelligence service and receipts;
- durable Telegram media ingress/egress for audio, image and video;
- specialist routing through Telegram;
- benchmark suites and human A/B loops.

Until these proofs exist, the Harness must say exactly what is implemented and what remains target architecture.

## 14. Authoritative references used for this charter

Primary references, refreshed during creation on 2026-10-06:

- REAPER: https://www.reaper.fm/
- REAPER downloads/changelog: https://www.reaper.fm/download.php
- REAPER ReaScript: https://www.reaper.fm/sdk/reascript/reascript.php
- REAPER User Guide: https://www.reaper.fm/userguide.php
- REAPER licensing: https://www.reaper.fm/purchase.php
- FFmpeg filters: https://ffmpeg.org/ffmpeg-filters.html
- ITU-R BS.1770: https://www.itu.int/rec/R-REC-BS.1770/
- EBU R 128: https://tech.ebu.ch/publications/r128
- Blender releases: https://www.blender.org/releases/
- Blender 5.2 LTS: https://www.blender.org/releases/5-2/
- Krita: https://krita.org/
- Krita animation manual: https://docs.krita.org/en/user_manual/animation.html
- OpenToonz: https://opentoonz.github.io/
- Telegram Bot API: https://core.telegram.org/bots/api
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
- WebGPU: https://www.w3.org/TR/webgpu/
- Core Web Vitals: https://web.dev/articles/vitals
