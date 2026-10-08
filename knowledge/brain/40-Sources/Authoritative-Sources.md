---
project: HAZEWAVE
type: source-map
authority: KNOWLEDGE_ONLY
status: VERIFIED_SEED
updated: 2026-10-08
---

# Authoritative Sources

This note is a human-readable map. The machine source registry remains `config/daily-intelligence-sources-v1.json`.

## HAZE — Tier A

### Cockos / REAPER
- User Guide: https://www.reaper.fm/userguide.php
- Official videos: https://www.reaper.fm/videos.php
- ReaScript: https://www.cockos.com/reaper/sdk/reascript/reascript.php
- Generated ReaScript API: https://www.cockos.com/reaper/sdk/reascript/reascripthelp.html
- JSFX: https://www.reaper.fm/sdk/js/js.php

Current observed documentation on 2026-10-08:
- User Guide page references REAPER 7.81.
- generated ReaScript API page identifies REAPER 7.82.

Treat exact installed/runtime version separately from documentation version.

### Audio standards
- ITU-R BS.1770-5: https://www.itu.int/rec/R-REC-BS.1770-5-202311-I
- EBU R 128: https://tech.ebu.ch/publications/r128
- EBU Tech 3343 practical R128 guidance: https://tech.ebu.ch/publications/tech3343
- AES Loudness topic/standards map: https://aes.org/audio-topics/loudness/

Important:
- ITU-R BS.1770-5 defines programme loudness and true-peak measurement algorithms.
- EBU R 128 v5 uses -23 LUFS as its programme loudness target for its broadcast workflow; this is not a universal music-mastering target.
- AES guidance includes Internet/online delivery recommendations and must be applied by delivery profile.

### FFmpeg
- Filters: https://ffmpeg.org/ffmpeg-filters.html

Use official filter documentation for analysis/render commands such as loudness measurement and deterministic media transforms.

## WAVE — Tier A

### Blender
- Current manual: https://docs.blender.org/manual/en/latest/
- Python API: https://docs.blender.org/api/current/

The current manual is Blender 5.2 LTS and covers Grease Pencil, animation/rigging, rendering, compositing, video editing and Geometry Nodes.

### Web platform
- WebGPU: https://www.w3.org/TR/webgpu/
- WGSL: https://www.w3.org/TR/WGSL/
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
- Web Audio specification: https://www.w3.org/TR/webaudio/
- WebCodecs: https://www.w3.org/TR/webcodecs/

As of 2026-10-08, WebGPU and WGSL remain active Candidate Recommendation Drafts. Treat them as current standards work requiring feature detection/progressive enhancement.

### Implementation references
- Three.js WebGPU docs: https://threejs.org/docs/pages/WebGPU.html
- GSAP ScrollTrigger: https://gsap.com/docs/v3/Plugins/ScrollTrigger/
- MDN Web Audio: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API
- MDN WebCodecs: https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API

## Source admission rule

A source being authoritative permits knowledge verification. It does not grant runtime adoption.

Any new tool/version/plugin still follows:

`DISCOVER -> VERIFY -> SECURITY_REVIEW -> COMPATIBILITY -> BENCHMARK -> RUNTIME_PROOF -> PRODUCTION_APPROVED`
