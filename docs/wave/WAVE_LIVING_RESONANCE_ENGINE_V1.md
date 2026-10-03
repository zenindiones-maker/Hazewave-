# WAVE — Living Resonance Engine v1

## Purpose

WAVE is the visual half of HAZEWAVE.

HAZE owns sound. WAVE owns image, motion, light, geometry, simulation and visual memory. WAVE is not a skin around HAZE and it is not a conventional music visualizer. It is a generative material system whose state is driven by structured sonic information.

The first WAVE project is the **Living Resonance Engine**.

## Core thesis

> Sound reveals the hidden geometry of matter.

The engine should make music appear to reorganize a synthetic world. The visual grammar is informed by real resonance phenomena — Chladni figures, Faraday waves, nodal modes, interference, non-Newtonian responses and ferrofluid-like field behavior — but the final form must be original to Hazewave.

The goal is not to simulate one laboratory experiment forever.

The goal is to build an impossible digital material whose physics can evolve with the music.

## Signature behavior

The world begins close to nothing.

Audio introduces energy. Energy creates resonance. Resonance organizes matter. Organized matter accumulates memory.

The canonical state chain is:

```text
HAZE SIGNAL
  ↓
RESONANCE FIELD
  ↓
VECTOR / POTENTIAL FIELD
  ↓
MATERIAL ORGANIZATION
  ↓
TOPOLOGY CHANGE
  ↓
SCAR MEMORY
  ↓
WAVE
```

The simulation must support real mobility. The subject is not a static plate in the center of the screen.

Resonant structures may:

- migrate through the viewport;
- split and merge;
- attach to boundaries;
- orbit energetic regions;
- fracture under transients;
- condense from haze into nodal structures;
- dissolve back into particles;
- move from line to membrane to volume;
- leave durable scars behind;
- alter their own boundary conditions.

The matter itself moves. Camera movement must never be used as a substitute for weak simulation.

## HazeMatter

**HazeMatter** is the canonical visual material of Hazewave.

It can exist in several regimes without becoming unrelated presets:

1. **DORMANT HAZE** — latent particles, low-energy field, almost invisible.
2. **NODAL DUST** — matter migrates toward resonant nulls and exposes geometry.
3. **RESONANT MEMBRANE** — the field becomes a continuous deforming surface.
4. **FRACTURE** — transients break continuity and redirect energy.
5. **SWARM** — coherent material decomposes into mobile agents/particles.
6. **FLUID** — matter behaves like a driven liquid or ferrofluid-inspired field.
7. **CRYSTAL** — stable modes harden into persistent structure.
8. **SCAR** — history remains after the instantaneous sound has gone.

These are material states of one world, not visual themes.

## Audio-to-form contract

WAVE must not reduce music to bass = size and treble = particles.

The Hazewave Translation Layer receives a structured HAZE state. Fast features control immediate physical response; slower features control structural evolution.

### Micro timescale

Milliseconds to hundreds of milliseconds.

Examples:

- onset → impulse;
- transient strength → fracture;
- high-frequency flux → filament detail;
- instantaneous energy → local displacement.

### Meso timescale

Seconds.

Examples:

- phrase contour → locomotion;
- harmonic stability → symmetry persistence;
- timbre → material regime;
- groove → repeated field deformation;
- stereo field → spatial attraction/repulsion.

### Macro timescale

Sections and whole-track structure.

Examples:

- section change → topology transition;
- recurring motif → recurring geometric family;
- long-term intensity → scar depth;
- track arc → material-state narrative;
- final accumulated state → sonic fingerprint.

## Physically inspired foundation

Scientific phenomena are constraints and references, not claims that the engine is a laboratory simulator.

Useful families include:

- Chladni nodal modes;
- Faraday surface instabilities;
- Lissajous/phase relationships;
- reaction-diffusion;
- vector fields;
- fluid advection;
- particle migration;
- signed distance fields;
- morphing boundaries;
- persistent state accumulation.

The important lesson from real Chladni systems is that **boundary geometry changes the family of possible modes**.

Hazewave extends that idea:

```text
fixed boundary
→ deforming boundary
→ broken boundary
→ learned / audio-grown boundary
```

## Mobility

Mobility is a first-class requirement.

Introduce one or more **Resonance Walkers**: special field seeds that move through the world according to energy, phase and structural opportunity.

A walker can:

```text
move
→ deposit energy
→ create a node
→ connect nodes
→ grow a resonant structure
→ detach
→ continue elsewhere
```

These are not narrative characters and not autonomous software agents. They are visual dynamics.

The result should evoke a living system without turning into a literal animal or creature.

## Matrix-adjacent system language

The project may evoke the feeling that reality contains a hidden computational layer, but must not imitate Matrix code rain.

Use sparse, meaningful diagnostics such as:

```text
ƒ 218.4 Hz
MODE 07
PHASE +0.31π
NODE 18
ΔE 0.73
COHERENCE 0.91
```

Rules:

- overlays are secondary;
- diagnostics appear only when they communicate real state;
- no decorative fake terminal spam;
- no falling glyph wall;
- no green-neon dependency for identity.

## Rendering architecture

Preferred direction:

```text
TypeScript
├── Web Audio API
├── AudioWorklet
├── feature extraction
├── WebGPU compute
│   ├── particle state
│   ├── velocity field
│   ├── resonance field
│   ├── pressure / fluid state
│   ├── scar field
│   └── material phase
├── Three.js WebGPURenderer
│   ├── TSL / WGSL
│   ├── SDF / raymarching where justified
│   ├── volumetric haze
│   └── post-processing
└── deterministic state recorder
```

Compatibility:

- WebGPU-first;
- WebGL2 fallback;
- same state model across quality tiers;
- adaptive particle density;
- reduced-motion mode;
- export mode may increase quality but must not silently change simulation semantics.

## Deterministic signature

A track should be able to leave a reproducible artifact.

```text
audio digest
+ engine version
+ seed
+ simulation parameters
= Hazewave visual signature
```

Possible outputs:

- still scar map;
- full motion render;
- loop;
- state snapshot;
- later: 3D mesh / GLB;
- later: comparison/morph between two track signatures.

## Site invariant

The Neandercaus website must not use an unrelated decorative WebGL background.

The same WAVE engine powers both the musical visualizer and the site.

```text
WEBSITE_VISUAL_ENGINE == MUSIC_VISUAL_ENGINE
```

The site may use different scenes and quality profiles, but HazeMatter, resonance rules, scar memory and transition grammar must be shared.

## First prototype

Build the phenomenon before the spectacle.

Start with:

- one square field;
- one monochrome material;
- one nodal-mode solver;
- one GPU particle population;
- one scar-memory buffer;
- file audio input;
- microphone input;
- deterministic seed;
- no account system;
- no preset marketplace;
- no decorative UI.

Success criterion:

A restrained black/white prototype with almost no bloom must already look alive and musically causal.

If the prototype only becomes impressive after glow, camera motion and huge particle counts, the core engine is not ready.

## Relationship to Neandercaus

**NEANDERCAUS** is the first canonical work built on WAVE.

Its visual history evolves through the same matter:

```text
dust
→ pigment
→ bone
→ metal
→ groove
→ electricity
→ tape
→ sample
→ pixel
→ data
→ latent matter
```

The matter never resets between eras. It transforms.

That continuity is the central visual storytelling mechanism.
