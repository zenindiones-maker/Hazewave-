# WAVE — HAZEWAVE WORLD BIBLE V1

Status: DEVELOPMENT  
Authority: CANONICAL PROJECT SPEC  
Owner: WAVE  
Project authority: HAZEWAVE_HARNESS  
Scope: Hazewave public interactive music world

## 0. Purpose

This document is the authoritative creative/technical story bible for the Hazewave site.

The site must not be assembled from effects, trendy libraries, or guessed artist lore. It must be authored as one coherent world in which scroll, music objects, player mechanics, artist dossiers, merchandise and network identity all belong to the same narrative.

The site must never invent final artist facts, artwork, music, press proof, audience numbers, merchandise availability, prices, video rights or biography details.

Unknown final content remains explicitly unknown until owner-authorized data/assets arrive.

## 1. Core promise

Hazewave is presented as a living independent sound archive from Santos.

The experience is not a conventional portfolio with a 3D widget added to it.

It is one persistent archive world:

- the owner-supplied lighthouse artwork is the visual ground truth;
- scroll moves the viewer through authored chapters of that same world;
- each artist is represented by a physical music object;
- selecting an object transfers it to the central player through deterministic cinematic motion;
- music changes the atmosphere using HAZE musical semantics plus live signal;
- artist identity, dossier, releases, merch and network remain data-driven surfaces of the same world.

The supplied artwork is not a decorative section image. It is the persistent world substrate.

## 2. Narrative architecture

The public experience follows a linear story rather than a menu hierarchy.

### CHAPTER 00 — THRESHOLD

Goal: establish identity before explanation.

Visual:
- owner-supplied Hazewave lighthouse world fills the viewport;
- logo and one short statement only;
- tape/noise loading texture may appear briefly but cannot delay interaction unnecessarily.

Copy intent:
- HAZEWAVE
- Núcleo Sonoro Independente
- Santos 2021—

Primary action:
- ENTRAR NO ARQUIVO

### CHAPTER 01 — ARCHIVE

Goal: reveal the collection as physical culture.

Visual:
- horizontal artist-object shelf;
- one cassette/artifact per artist identity, not one arbitrary card per album;
- shared mechanical grammar with artist-specific label/material/art direction;
- desktop may use cinematic horizontal travel;
- mobile remains native touch-scrollable and never requires precision drag.

Primary action:
- tap/click artist object.

### CHAPTER 02 — PLAYER TABLE

Goal: turn selection into a memorable physical ritual.

Composition:
- selected music object remains visually present;
- central original Hazewave player;
- artist context beside/around the player on large screens;
- compact integrated composition on mobile.

Player rules:
- inspired by tactile portable music hardware but not a literal Apple iPod copy;
- wheel controls real volume and/or track navigation;
- screen communicates current artist/track/section;
- play/pause/seek remain accessible controls;
- one user gesture is sufficient to unlock audio and begin the authored transfer;
- cassette/object travel is reversible and deterministic.

### CHAPTER 03 — ARTIST DOSSIER

Goal: provide depth after interaction earns attention.

Data surfaces:
- authorized artist photo;
- exact public handle;
- short owner-approved biography/context;
- authorized tracks;
- waveform/section structure derived from real audio;
- authorized clip/embed when available;
- release metadata.

No placeholder may masquerade as final factual content.

### CHAPTER 04 — PROOF / CULTURE

Goal: show cultural reality without fabricated credibility.

Allowed only when owner supplies/verifies:
- press;
- comments;
- audience numbers;
- event/festival history;
- credits;
- collaborators;
- release milestones.

Until then, omit the proof chapter rather than fabricate proof.

### CHAPTER 05 — MERCH BANCA

Goal: feel like a physical street/independent merch stand, not generic ecommerce.

Products:
- cap;
- tee;
- vinyl;
- future objects as typed data.

Each product may have:
- original 3D/product render;
- static poster fallback;
- status;
- price only when authoritative;
- direct-contact CTA.

No Shopify dependency in V1.

Contact CTA:
- prepared message such as "Fala Hazewave, quero o boné Collective";
- destination must be owner-approved Instagram DM or WhatsApp contact;
- no fake availability.

### CHAPTER 06 — NETWORK

Goal: close with people, not platform chrome.

Presentation:
- text handles only;
- no generic social-icon cloud;
- direct links;
- restrained mono typography.

Known current handles:
- @virundun
- @barakozamabeats
- @indionesbala

These handles are navigation data, not permission to invent biographies or artist associations beyond owner-confirmed mapping.

## 3. Persistent world architecture

### Authoritative state

The page has one deterministic story target derived from native scroll position.

Same scroll position must resolve to the same chapter/world target after:
- forward scroll;
- reverse scroll;
- resize refresh;
- reload;
- browser history restoration.

### Render state

Visual motion may damp toward the target for cinematic feel.

The smoothed render state is not application authority.

### Scene Ledger

All chapter world states are declared as data, not scattered magic numbers.

Each chapter can control:
- world crop/scale;
- x/y drift;
- rotation;
- brightness;
- saturation;
- contrast;
- vignette;
- optional foreground intensity;
- optional artist-world emphasis;
- semantic label.

Current implementation:
- `sceneLedger.ts`
- `ScrollConductor.ts`

This pattern is ADOPTED.

## 4. Scroll strategy

### Default authority — native scroll

Native browser scroll remains the product baseline.

Reasons:
- exact URL/history/accessibility behavior;
- keyboard/PageUp/PageDown/space support;
- fewer synchronization layers;
- mobile browser reliability;
- reduced-motion compatibility;
- deterministic `scrollY -> story target` mapping.

### GSAP ScrollTrigger — bounded adoption

ADOPT only where it produces a real authored benefit:
- one desktop-only pinned archive sequence;
- optional horizontal shelf choreography;
- a bounded Show-and-Play chapter;
- one frame-sequence/moviescroller if a final asset justifies it.

Rules:
- do not animate the pinned container itself;
- core selection/audio state cannot depend on a ScrollTrigger;
- mobile below the measured breakpoint returns to normal vertical/native flow;
- use `gsap.matchMedia()`, not deprecated `ScrollTrigger.matchMedia()`;
- every pin receives a no-pin fallback.

### Lenis — SPIKE_ONLY

Lenis is not architecture authority.

It may be tested on desktop if native scroll fails the desired feel.

Admission requires measured improvement with:
- no broken keyboard navigation;
- no find-in-page regression;
- no anchor/history regression;
- no A15 cost;
- no double RAF/ticker drift;
- reduced-motion behavior proven.

Do not add Lenis merely because showcase sites use it.

Do not globally disable GSAP lag smoothing as a prestige/default rule. GSAP's own ticker defaults are retained unless a measured Lenis integration proves another setting necessary.

## 5. Exact owner artwork contract

Source intent:
- owner-supplied Hazewave lighthouse / spiral / ocean artwork.

Rules:
- it remains the persistent visual substrate across the scroll journey;
- it must not be replaced by an AI approximation;
- it must not be recolored into a different identity by default;
- chapter transforms may crop, pan, scale, grade, vignette or reveal portions;
- transformations must preserve recognizability;
- mobile may use different object-position/crop to maintain lighthouse/logo composition;
- a lightweight optimized derivative may be served only if visual comparison proves it preserves the supplied artwork;
- the original source remains provenance evidence outside destructive optimization.

Asset path currently expected by the site:
`/media/hazewave-world.jpg.webp`

Before owner review:
- verify the committed derivative against the supplied source visually;
- verify no accidental low-resolution or over-compressed replacement;
- preserve exact aspect-ratio behavior.

## 6. Physical cassette / music-object system

The long-term production asset is one authored object per final artist.

### Geometry grammar shared across all artists

- consistent cassette/artifact bounding box;
- shared insertion/contact dimensions;
- correct pivot/origin;
- same Deck compatibility;
- real edge bevels;
- readable label surface;
- physical reel/window/contact detail;
- believable thickness.

### Artist-specific differentiation

- label artwork;
- shell plastic/resin/material;
- wear;
- roughness;
- metalness;
- translucency;
- print method;
- typography;
- accent hardware;
- optional geometry trim;
- motion signature.

### Production path — Blender first

Blender is the authoritative zero-cost production DCC.

Pipeline:

```
artist-authorized reference
-> parametric cassette base
-> artist material/label variant
-> UV + PBR authoring
-> pivot/origin validation
-> GLB export
-> glTF-Transform optimization
-> meshopt or Draco evaluation
-> texture compression evaluation
-> visual diff
-> desktop/mobile budget check
-> static poster render
-> ADMIT / REJECT
```

Preferred runtime optimization:
- Meshopt where fast decode and compact repeated geometry win;
- Draco only if measured bytes justify decode tradeoff;
- KTX2/Basis when texture memory/bandwidth savings are meaningful;
- WebP/AVIF poster fallback;
- do not apply all compression technologies simultaneously by habit.

### Meshy / Tripo / Spline

These are concept accelerators, not automatic production dependencies.

Meshy Free:
- commercial use is possible under CC BY 4.0 attribution;
- current free plan can restrict downloads/private ownership;
- therefore not the default source of proprietary Hazewave production assets.

Tripo Free:
- current licensing/help material does not provide the same clean private/commercial ownership as paid plans;
- therefore REJECT as default zero-cost production source until a specific asset's terms are reviewed and acceptable.

Spline:
- optional authoring/prototyping surface;
- never a required hosted runtime;
- exports must remain portable;
- do not upload private final identity assets without an explicit data/terms review.

Default decision:
`BLENDER_PARAMETRIC_FACTORY=ADOPT`
`MESHY_FREE=SPIKE_ONLY_WITH_ATTRIBUTION`
`TRIPO_FREE=REJECT_FOR_FINAL_COMMERCIAL_ASSET`
`SPLINE=OPTIONAL_AUTHORING_ONLY`

## 7. Runtime rendering strategy

### LOW / mobile baseline

- semantic DOM;
- CSS physical product treatment;
- GSAP deterministic choreography;
- static poster fallbacks;
- Web Audio;
- no heavy mandatory WebGL/WebGPU runtime.

### MEDIUM

May add:
- one optimized GLB for the currently focused object;
- lazy load after first interaction-ready state;
- static shelf objects remain cheap if needed.

### HIGH / ULTRA

May add:
- real GLB product assets;
- selective Three.js/WebGPU layer;
- higher-quality lighting/material response;
- bounded atmosphere/post effects.

Rules:
- one renderer only if 3D is admitted;
- no renderer per chapter;
- renderer is enhancement, not application authority;
- business/audio/content state remains renderer-independent;
- bundle and frame budgets decide whether a GPU layer survives.

## 8. Frame-sequence / moviescroller policy

A frame sequence is justified only for a moment that cannot be reproduced more efficiently with the live world.

If used:
- author in Blender/After Effects;
- choose the minimum frame count that survives visual QA;
- prefer AVIF/WebP where decode behavior is proven;
- preload near the chapter, not at page start;
- do not preload 60–120 large frames before allowing the user to enter the site;
- canvas uses cover math and responsive source sizing;
- fallback is a still/poster;
- do not scrub ordinary compressed video as the primary scroll mechanism.

## 9. Audio authority

HAZE owns musical meaning.

WAVE consumes typed:
- BPM;
- sections;
- beat grid;
- energy;
- events;
- motifs where available.

The visual layer may supplement this with real-time Web Audio analysis.

### Core player

Keep the existing Hazewave AudioEngine unless a measured product gap requires replacement.

Howler:
- OPTIONAL;
- do not add only for popularity;
- adopt only if cross-browser media lifecycle problems exceed the value of the current engine.

Spotify:
- OPTIONAL external listening/embed surface;
- never core authority for Hazewave-owned tracks;
- do not assume every embed is always a fixed 30-second preview;
- autoplay/encrypted-media/platform behavior varies;
- final owner-controlled audio should use authorized original files or a storage/CDN path chosen later.

No random web music downloads.

## 10. Original player design

The central player must be recognizable as Hazewave hardware.

Do not reproduce Apple iPod industrial design, trade dress, click-wheel appearance, or UI layout.

Allowed inspiration:
- tactile radial control;
- compact physical screen;
- mechanical docking;
- hierarchy of screen + control surface;
- satisfying volume/track navigation.

Required functions:
- play/pause;
- seek;
- wheel/radial volume;
- previous/next;
- current track/artist;
- semantic section;
- accessible keyboard equivalents;
- mobile touch target correctness.

## 11. Content authority / anti-hallucination rule

Production content is admitted only from owner-authorized data.

Each final Artist record must explicitly provide or mark unknown:

- canonical display name;
- public handle;
- portrait asset;
- biography/context;
- releases;
- track IDs;
- audio files/URLs;
- artwork ownership/provenance;
- video IDs/URLs and embed rights;
- merch associations;
- social links.

Each Track must explicitly provide:
- title;
- artist;
- release;
- duration;
- audio source;
- rights/provenance;
- artwork;
- optional streaming links;
- HAZE analysis manifest.

Unknown fields are `null` / `UNSET`, never guessed.

Demo identities remain clearly non-final until replaced.

## 12. Merch strategy

No ecommerce platform dependency in V1.

Merch is typed content plus direct contact.

Each item:
- id;
- display name;
- category;
- status;
- authorized image/model;
- static poster;
- price if authoritative;
- prepared message;
- destination.

CTA priority:
1. owner-approved WhatsApp deep link if supplied;
2. owner-approved Instagram profile/contact flow;
3. copy prepared message + open destination.

Do not fabricate a WhatsApp number.

## 13. Social strategy

Text handles only.

No decorative icon cloud.

Known handles are rendered in mono typography and linked directly.

Final association between handle and artist must come from owner-authorized content data.

## 14. Deployment strategy

### Current mission boundary

No public production deployment yet.

### Vercel

Vercel Hobby is not the zero-cost answer for a commercial Hazewave site because its Hobby terms are personal/non-commercial.

Do not deploy a commercial Hazewave site to Hobby and call the zero-cost gate satisfied.

### Preferred production shape

Keep the experience statically buildable.

Before deployment:
- evaluate a host whose free terms allow the intended commercial use;
- verify bandwidth/media limits;
- keep large final audio storage abstracted;
- verify custom-domain path;
- verify no paid overflow can surprise the owner.

No billing-capable resource is created without explicit owner authority.

## 15. Performance budgets

Performance is art direction.

Baseline targets:
- LCP <= 2.5 s;
- INP <= 200 ms;
- CLS <= 0.1;
- capable desktop 60 FPS target;
- supported low-tier phone stable ~30 FPS floor during primary transition.

Interaction proof:
- tap feedback immediate;
- selection -> contact measured;
- contact -> audible playback measured;
- track switch/eject state coherent;
- no long task introduced by decorative media.

Loading sequence:

```
HTML / identity
-> owner artwork
-> archive interaction shell
-> critical audio/player runtime
-> first visible artist objects
-> current focused optional assets
-> below-fold dossiers/merch
-> optional HIGH/ULTRA GPU
```

Do not block entry on the full catalog.

## 16. Accessibility and motion

Required:
- semantic content outside visual effects;
- keyboard artifact selection;
- keyboard player controls;
- visible focus;
- no hover-only core action;
- `prefers-reduced-motion`;
- reduced-motion keeps narrative, selection, dock state, playback and content;
- decorative parallax/pins/frame sequences collapse to stable compositions;
- touch is first-class.

## 17. Technology decisions from 2026 research

### KEEP

- Astro static/HTML-first shell;
- GSAP for deterministic physical choreography;
- GSAP MotionPath for cassette/object travel;
- native scroll + current ScrollConductor as story authority;
- progressive View Transitions;
- Web Audio;
- Blender;
- glTF/GLB;
- glTF-Transform;
- optional Three.js only where true 3D earns its cost.

### BOUNDED

- GSAP ScrollTrigger for specific desktop chapters;
- Lenis as an experiment only;
- CSS scroll-driven animation for noncritical editorial enhancement;
- WebGPU on HIGH/ULTRA only;
- Spotify embeds as optional outbound/listening surface;
- Spline as optional authoring.

### REJECT BY DEFAULT

- Next.js/R3F migration for prestige;
- React dependency without a product need;
- mandatory smooth-scroll library;
- literal iPod clone;
- WebGL as mobile correctness dependency;
- physics-driven primary insertion;
- Meshy/Tripo free assets as proprietary final identity without license acceptance;
- Vercel Hobby for a commercial zero-cost launch;
- fake press/social proof;
- unlicensed music/art.

## 18. Why Astro remains

A framework migration does not make the art direction more premium.

Current Next.js 16 is the active supported major in 2026; therefore advice framed around “Next 14/15 as the current pro standard” is already stale.

Hazewave already has:
- static build;
- semantic HTML;
- data model;
- code splitting;
- typed runtime;
- Playwright;
- exact-head A15 artifact proof;
- renderer-independent interaction.

Migration to Next/R3F would add work and client runtime without solving the actual quality bottleneck: final art assets, composition, product modeling and authored motion.

Decision:
`ASTRO=KEEP`
`NEXT_MIGRATION=REJECT_UNLESS_MEASURED_REQUIREMENT`

## 19. Professional review gates

Before owner review:

`OWNER_VISUAL_REVIEW_READY=FALSE`

WAVE must internally prove:

1. owner artwork is visibly preserved;
2. hero feels intentional with no debug/prototype chrome;
3. archive shelf is understandable without instruction paragraphs;
4. cassette/object looks desirable at rest;
5. selected object visibly travels, aligns, docks and stays present;
6. wheel/player behavior is clear and functional;
7. at least desktop and mobile compositions are art-directed separately;
8. no factual final artist content is fabricated;
9. dossier/merch/social sections fit the same world;
10. reduced motion remains complete;
11. Playwright/browser CI is green on exact HEAD;
12. repository contracts are green;
13. bundle budget is green;
14. A15 real-device proof is green after meaningful visual changes;
15. normal-mode screenshots are judged internally as worth showing.

Only then:
`OWNER_VISUAL_REVIEW_READY=TRUE`

## 20. Next production sequence

### P0 — close current CI boundary
- fix any stale test assertions caused by narrative architecture;
- prove exact current HEAD;
- retain owner artwork asset;
- preserve A15 artifact exact-head invariant.

### P1 — background fidelity
- visual-diff committed optimized artwork against owner source;
- tune mobile/desktop object-position and story transforms;
- do not ask owner yet.

### P2 — cassette factory
- create one original parametric Blender cassette base;
- derive artist variants from authorized references;
- export GLB + poster;
- optimize/measure;
- adopt renderer tier only after proof.

### P3 — archive choreography
- desktop bounded cinematic shelf;
- native mobile shelf;
- object-to-player transfer remains deterministic.

### P4 — player table
- finish original Hazewave radial control;
- volume/next/previous/play behavior;
- tactile audio/haptic cues;
- accessible equivalents.

### P5 — dossiers
- replace placeholders only when real artist data/assets arrive;
- waveform/section state from HAZE;
- authorized clip integration.

### P6 — merch/network
- final owner contact target;
- product assets;
- direct-contact CTA;
- final social mappings.

### P7 — deployment readiness
- host/legal/cost review;
- static-media plan;
- custom-domain plan;
- no public production launch until explicitly authorized.

## 21. Success definition

The result succeeds when a first-time visitor does not think:

“this is a website with effects.”

They understand:

“this is Hazewave's world, and the music physically lives inside it.”
