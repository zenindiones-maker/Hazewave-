# HAZEWAVE — Brand Platform / Site Concept v1

## Role

The Hazewave site is the **canonical public home of the entire Hazewave universe**.

It must function simultaneously as:

- brand experience;
- interactive artwork;
- artist/collective portal;
- music platform;
- video and film hub;
- photography/archive;
- project showcase;
- home for original works such as NEANDERCAUS;
- free music download destination;
- merchandise store.

It is not a landing page with a WebGL background.

The site itself is a HAZEWAVE product.

## Brand architecture

```text
HAZE = SOUND
WAVE = IMAGE
HAZEWAVE = THE WORLD WHERE THEY BECOME ONE
```

### HAZE surfaces

- music player;
- releases;
- artists;
- soundtrack projects;
- Haze Studio;
- stems / sonic experiments where published;
- free downloads;
- sonic fingerprints;
- audio-reactive state.

### WAVE surfaces

- visual world;
- films;
- animated works;
- photography;
- interactive scenes;
- project identities;
- Wave Studio;
- generative art;
- HazeMatter;
- Living Resonance Engine.

## Core site invariant

```text
WEBSITE_VISUAL_ENGINE == MUSIC_VISUAL_ENGINE
```

The site and the visual works share WAVE primitives and HazeMatter.

The website must not ship an unrelated decorative visual engine.

## Content architecture

Primary public areas:

```text
HOME
HAZE
WAVE
MUSIC
RELEASES
ARTISTS
FILMS / VIDEOS
PHOTOS
PROJECTS
WORKS
  └── NEANDERCAUS
DOWNLOADS
SHOP
ARCHIVE
ABOUT / MANIFESTO
```

The exact navigation presentation may be unconventional, but every destination must remain directly addressable, accessible and indexable.

## Home experience

The home page should feel alive before the visitor reads anything.

However, the first render must still provide meaningful content quickly.

Concept:

1. minimal Hazewave mark / identity;
2. HazeMatter dormant field;
3. first user interaction activates audio capability;
4. current release / artist / work changes the world state;
5. navigation emerges from the same material system;
6. browsing preserves global player and WAVE world state.

The user should feel that they are entering a system rather than opening a portfolio.

## Persistent global audio

HAZE should remain present while browsing.

Global player requirements:

- persistent playback across internal navigation;
- queue;
- release/artist metadata;
- artwork;
- play/pause/seek;
- volume;
- track progress;
- Media Session integration where supported;
- optional audio-reactive WAVE state;
- no forced autoplay with sound.

## Music and releases

Each release page should support:

- cover/artwork;
- artist;
- release notes;
- credits;
- track list;
- streaming player;
- lyrics when appropriate;
- project association;
- videos/visuals;
- downloadable formats;
- license/usage information;
- provenance/credits where AI systems contributed.

## Free downloads

Hazewave will allow people to download selected music **directly from the Hazewave website for free**.

Requirements:

- Hazewave-controlled URL;
- no mandatory external music-service account;
- explicit file format;
- file size;
- license/allowed use;
- artist and credits;
- version;
- SHA-256 checksum where practical;
- stable release identifier.

Candidate formats:

- MP3 320 kbps for universal use;
- FLAC for lossless distribution;
- WAV for selected masters/stems where intentionally published.

The download layer must not expose private masters, working stems or restricted model/reference material.

## Artists

Each artist receives a living identity inside the same universe.

Artist pages can include:

- biography;
- portrait/photography;
- releases;
- songs;
- videos;
- projects;
- character/series associations;
- visual signature;
- upcoming work;
- social/contact links where desired;
- merchandise.

Artist identity can influence HazeMatter through a defined visual signature rather than an arbitrary page theme.

## Films / animated works

The video area should support:

- music videos;
- short films;
- animated series;
- behind-the-scenes;
- experiments;
- trailers;
- project films.

NEANDERCAUS should have its own richer interactive experience rather than being reduced to an embedded video.

## Photography

Photography should be treated as authored work, not a generic gallery grid.

Support:

- photo essays;
- series;
- artist portraits;
- project documentation;
- studio/process photography;
- editorial sequences.

WAVE may create transitions and spatial layouts, but image viewing must remain fast and high quality.

## Projects

Project pages explain major Hazewave works.

A project can join multiple content types:

```text
PROJECT
├── artists
├── music
├── film
├── photos
├── interactive work
├── research
└── merchandise
```

This is important because Hazewave works are cross-media by design.

## Shop / merchandise

The shop belongs to the visual world but commerce logic remains isolated from the rendering engine.

Possible merchandise:

- clothing;
- prints;
- physical music;
- limited objects;
- series/project artifacts;
- artist merchandise;
- conventional brand merchandise.

The product page may be visually rich, but:

- price;
- variant;
- inventory;
- shipping;
- checkout;
- order state

must remain conventional, reliable and accessible.

A headless commerce backend is preferred so Hazewave controls the experience without implementing payment infrastructure itself.

## HAZE Studio

The site should present HAZE Studio as the music-production side of Hazewave.

Capabilities may include:

- composition;
- AI-assisted instrumental production;
- human vocals;
- authorized RVC/voice conversion;
- arrangement;
- stems;
- editing;
- sound design;
- mixing;
- mastering;
- soundtrack production.

The public site describes finished capability and work; sensitive internal production tooling stays private.

## WAVE Studio

The site should present WAVE Studio as the visual-production side.

Capabilities may include:

- concept art;
- screenwriting;
- storyboards;
- animatics;
- character/world design;
- animation;
- generative visuals;
- WebGPU experiences;
- film/video;
- photography;
- interactive sites;
- compositing;
- visual identity.

## Modern interaction principles

The target is not maximum animation. It is **maximum coherence**.

Rules:

- motion explains relationships;
- transitions preserve world continuity;
- the persistent visual state reacts to HAZE;
- interaction has consequence;
- no gratuitous scroll-jacking;
- no navigation hidden behind GPU-only interfaces;
- reduced-motion is a first-class mode;
- mobile is a designed experience, not a fallback;
- content remains usable if WebGPU is unavailable;
- performance budgets are part of art direction.

## Experience layers

```text
CONTENT LAYER
semantic HTML / media / metadata
        ↓
INTERACTION LAYER
navigation / player / gestures
        ↓
WAVE LAYER
HazeMatter / particles / fields / transitions
        ↓
HAZE COUPLING
music state drives visual state
```

If the WAVE layer fails, the content layer survives.

## Relationship to NEANDERCAUS

The website is the house.

NEANDERCAUS is the first flagship original animated series inside the house.

The same HAZE/WAVE infrastructure should later support additional:

- series;
- albums;
- artists;
- interactive films;
- installations;
- visual albums;
- games/experiments if created;
- merchandise worlds.

## Current site status

```text
BRAND_PLATFORM_CONCEPT=DEFINED
INFORMATION_ARCHITECTURE=V1
FREE_DOWNLOAD_REQUIREMENT=DEFINED
MERCH_REQUIREMENT=DEFINED
ARTIST_PLATFORM_REQUIREMENT=DEFINED
WAVE_SHARED_ENGINE_REQUIREMENT=DEFINED
SITE_IMPLEMENTATION=NOT_STARTED
```
