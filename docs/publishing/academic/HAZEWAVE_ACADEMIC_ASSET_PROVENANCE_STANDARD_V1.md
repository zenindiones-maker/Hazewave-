# HAZEWAVE Academic Asset Provenance & Rights Standard v1

## 1. Purpose

Every image, diagram, map, audio example, recording, score, transcription, dataset and generated asset used in a Hazewave academic publication must have traceable origin and rights status.

A visually convincing asset is not acceptable evidence unless its provenance is known.

## 2. Asset classes

### Documentary
- artifact photograph;
- site photograph;
- archival photograph;
- manuscript scan;
- map;
- primary-source document;
- historical recording;
- field recording.

### Scholarly derivative
- archaeological drawing;
- transcription;
- chart;
- diagram;
- map derived from research data;
- acoustic model;
- spectral analysis;
- statistical visualization.

### Reconstruction
- reconstructed instrument;
- reconstructed site;
- reconstructed sound;
- experimental archaeology recording.

### Interpretive
- HAZE interpretation;
- WAVE illustration;
- speculative soundscape;
- conceptual scene.

### AI-assisted/generated
- generated image;
- generated texture;
- generated audio;
- AI-assisted diagram;
- AI-assisted restoration draft.

The final publication must never blur these classes.

## 3. Provenance record

Every asset should have:

```text
ASSET_ID
BOOK_ID
CHAPTER_ID
ASSET_TYPE
TITLE
CREATOR
SOURCE
SOURCE_ID
DATE
LOCATION
INSTITUTION
OBJECT / CALL / CATALOGUE NUMBER
RIGHTS_HOLDER
LICENSE
PERMISSION_ID
TRANSFORMATIONS
AI_INVOLVEMENT
EVIDENCE_CLASS
CAPTION
ALT_TEXT
PUBLIC_LINK
CHECKSUM
VERSION
```

## 4. Documentary integrity

Do not:
- crop away information that changes interpretation without disclosure;
- colorize a source image and present it as original;
- clean a recording so aggressively that analytical features change without disclosure;
- remove context from an artifact photograph;
- relabel a reconstruction as a historical original.

## 5. AI image policy

AI-generated visual material:
- is never labeled as documentary evidence;
- is clearly captioned as reconstruction/concept visualization;
- has model/tool/version recorded when materially relevant;
- does not fabricate a specific archaeological artifact and imply authenticity;
- does not replace an available licensed documentary image merely for aesthetics when the documentary object is central to the claim.

## 6. Audio provenance

For every audio object:

```text
AUDIO_ASSET_ID
PERFORMER
RECORDER / ENGINEER
DATE
LOCATION
SOURCE CARRIER
ARCHIVE / LABEL
CATALOGUE / MATRIX
TRANSFER
RESTORATION
EDIT
SPEED / PITCH ASSUMPTIONS
RIGHTS
HAZE_TRANSFORMATIONS
EVIDENCE_TYPE
```

## 7. Historical recording restoration

Restoration may include:
- de-click;
- noise reduction;
- EQ;
- speed correction;
- channel repair.

Analytical editions should preserve:
- raw/reference copy where lawful;
- restoration notes;
- original carrier metadata;
- uncertainty about speed/pitch.

## 8. Reconstruction audio

A reconstructed sound is not the past itself.

Record:
- source evidence;
- instrument reconstruction;
- materials;
- performer;
- technique assumptions;
- tuning assumptions;
- room;
- microphones;
- processing;
- known deviations.

## 9. HAZE interpretation

HAZE may create artistic music inspired by scholarship.

It is classified as **HAZE_INTERPRETATION**.

This category permits creativity precisely because it does not claim historical authenticity.

## 10. Maps

Map record includes:
- base map source;
- projection;
- modern vs historical boundary status;
- uncertainty;
- coordinate source;
- dating layer;
- toponym policy.

## 11. Diagrams

Diagrams distinguish:
- measured;
- observed;
- inferred;
- modeled;
- hypothetical.

Visual certainty must match evidentiary certainty.

## 12. Musical transcription

Record:
- source recording/performance;
- transcriber;
- notation system;
- tempo;
- tuning reference;
- analytical purpose;
- uncertainties;
- transformations.

## 13. Rights states

Possible internal states:

- PUBLIC_DOMAIN_CONFIRMED
- OPEN_LICENSE
- LICENSED
- PERMISSION_GRANTED
- FAIR_USE / QUOTATION_REVIEW_REQUIRED
- RESTRICTED
- SACRED_OR_SENSITIVE
- UNKNOWN
- DO_NOT_PUBLISH

UNKNOWN never silently becomes publishable.

## 14. Cultural restrictions

Technical access does not equal ethical permission.

For culturally restricted material:
- identify community protocols;
- consult appropriate rights holders/custodians;
- restrict public companion assets when required;
- document why an asset is omitted or described instead.

## 15. Version binding

Every published figure/audio item binds to:
- edition;
- asset version;
- rights state at publication;
- checksum where practical.

## 16. Corrections

If provenance is challenged:
- freeze questionable asset distribution where warranted;
- investigate;
- publish correction;
- replace/remove in future editions;
- preserve correction history.

## 17. Final rule

If Hazewave cannot answer:

> What is this, where did it come from, who owns it, what did we change, and what evidentiary role does it play?

the asset is not ready for an academic publication.
