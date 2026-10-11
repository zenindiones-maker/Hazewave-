# HAZE — Sample Note Map / MIDI Export v1

State: DEVELOPMENT_CANDIDATE. Harness domain: HAZE. Capability: `audio.sample_to_midi`. This is original Hazewave software, **not** noteGRABBER, its installation, its proprietary model or a VST3 plugin. The Beat Builder 3000 graphic in the reference video is not proof of a distributable separate program.

## Feature scope
- Accept existing local, uncompressed PCM16 WAV (mono or stereo, 8–48 kHz, up to 20 s / 10 MiB).
- Mandatory source inspector `codec_stream_analyzer` **before** analysis, with a separate task-bound Harness authorization and SHA check.
- Windowed Hann FFT (4096 samples, hop 2048), local spectral peaks and basic harmonic-suppression heuristic, yields an editable time/pitch map.
- Output standard MIDI Type 0; tempo 120 BPM; separate JSON containing note map, spectral frames and evidence-bound receipts.
- Mono and simple chords may work; **polyphonic note extraction is NOT guaranteed**. Transients, drums, phase cancellation, sustained chords and complex mixtures can create spurious or missing notes. Manual note correction should be required for professional production.
- No external model, plugin binary, license key, cloud, network I/O or resource provisioning. Tests create their own clean tones, never use copyrighted media.

## Guardrails
- Scope HAZE only; WAVE/BRIDGE may not route this capability.
- No nested repositories, untrusted program execution, production publishing, external account changes, private-media upload or payment.
- Inspect first; reject symlinks, truncated PCM, corrupt/oversized files and authorization mismatches.
- MIDI write is local, fails closed if destination exists and emits SHA-256 of original and output. Receipts are **audit hashes, not cryptographically signed approvals**.

## Usage (checkout of this candidate branch)

```bash
python -m hazewave.sample_note_map ./sample.wav \
  --out ./sample.mid \
  --task-id haze-local-audio-to-midi-001 \
  --json-out ./sample-note-map.json
```

The output can be opened in compatible DAW piano rolls for manual correction. For MP3/FLAC/etc, separately convert to PCM16 WAV using an approved offline decoder and verify both provenance and audio rights.

## Sources and alternatives
- noteGRABBER2 official commercial Windows/macOS plugin: https://notegrabber.com/products/notegrabber
- Workflow reference: https://notegrabber.com/pages/howto
- Open-source future alternative for more complex polyphonic transcription: https://github.com/spotify/basic-pitch (Apache-2.0). **Not installed or verified**; would require compatible Python/model runtime and explicit scope.
- Baseline technique is independently implemented Python stdlib code, no upstream protected source copied.

## Acceptance evidence
`pytest tests/test_haze_sample_note_map.py`; full Hazewave CI; a fresh exact-SHA GitHub Actions E2E using generated WAV with nonempty MIDI output and inspectable receipt. **A green unit test does not establish quality for real mixed samples.**

Upstream proprietary noteGRABBER2 installation: NOT_ATTEMPTED (no license, no compatible Linux build).
