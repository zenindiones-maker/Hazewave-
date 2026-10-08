# HAZEWAVE — AUDIOVISUAL REVERSE ENGINEERING LAB V1

**Status:** development candidate, not a live Codespace deployment and not production approved.
**Authority:** HAZEWAVE_HARNESS. **Workstation:** existing Hazewave Codespace only; no new compute allocation.
**Scope:** original analysis of *authorized* images, sound, video and scripts, never unconditional recreation of third-party protected works.

## Separate tools by what they really measure

| Domain / kind | Existing or added analyzer | Evidence | Unproven by that analyzer |
|---|---|---|---|
| HAZE / AUDIO_QC | `src/hazewave/audio_qc.py` FFmpeg ebur128/astats | integrated loudness, LUFS, true peak, sample/RMS, clipping, dynamic range | mix quality or emotional impact |
| HAZE / AUDIO_MUSIC | `audio_analysis.py` Essentia and PCM analyses | BPM, onsets, transient density, key confidence, stereo, spectral energy, sections | artistic style/identity of original producer |
| WAVE / VIDEO_QC | `video_qc.py` FFprobe/FFmpeg | frame/timebase, color, black/frozen segments, A/V delta, codec and integrity | cinematic merit |
| WAVE / SCENE_DETECTION | `scene_detection.py` PySceneDetect | cut boundaries and scene durations | why editor chose a shot |
| WAVE / IMAGE_METRICS | `av_research_lab.py` Pillow bounded thumbnail | size, alpha, luma average/stddev/entropy | full-res photometry, composition quality |
| WAVE / EDITORIAL_SCRIPT | `av_research_lab.py` source-owned structured JSON | segment timing, word density, gaps and overlaps | argument truthfulness, narrative quality |
| SOFTWARE / REA6 | `rea6_integration.py` REA 6.0.0 + Ghidra | native Evidence bound to digest/provider | audio/visual quality or original creative intent |

## License and install choice

The system contains only governed open-source research tools; **the REAPER DAW already used in Hazewave is not an open-source application** and is not installed by this lab. FFmpeg's effective distribution obligations depend on its actual build configuration. Essentia is **AGPL-3.0-only** and is explicitly opt-in, especially if any service distributing functionality is ever contemplated. WhisperX code may be open source but downstream alignment/diarization models need independent license approval. Production use requires separate legal review.

Run in the **existing Codespace** `hazewave-zero-cost-4jxp45676rq6279xx` on the reviewed candidate worktree, not in the active Laya/reflex worktree. Confirm `git rev-parse HEAD`, `git status --porcelain`, free disk, available RAM, no concurrent high-RAM audio job, and the exact remote. Do not switch branches or overwrite WIP.

```bash
# On the candidate worktree *within the existing Codespace*:
bash scripts/codespaces/install-av-research-open-tools.sh --preflight

# Optional explicit install of bounded FOSS image/video/editorial core:
bash scripts/codespaces/install-av-research-open-tools.sh --core
bash scripts/codespaces/install-av-research-open-tools.sh --doctor

# Music extensions, ONLY after AGPL-3 review and resource admission:
# HAZEWAVE_ACCEPT_AGPL3=yes bash scripts/codespaces/install-av-research-open-tools.sh --music
```

Installation uses a **separate venv**, strict direct-package pins, wheel-only installs, no privileged apt/npm process and zero automatic GPU/model downloads. It does not modify Reflex or install new Codespaces. `--doctor` verifies pinned Python packages/import/owned image fixture, **not full runtime QA or agent connectivity**. Log the pip install reports and version receipts. Review transitive dependency versions/metadata before promoting to any canonical runtime; these pip reports alone are not a comprehensive, hash-locked supply-chain guarantee.

## Real evidence production

The analysis CLI cannot be invoked with an unverified `--authorized` boolean. For each input, the owner/Harness creates and signs `HazewaveReverseEngineeringTargetGrant/v1` containing the exact input's SHA-256, `domain`, `target_kind` (audio_asset, video_asset, image_asset, editorial_script), purpose `AUTHORIZED_FEATURE_STUDY`, an expiry <=24h and owner identity. Sign unchanged JSON with OpenSSH `ssh-keygen -Y sign -n hazewave-research-grant`. Keep the signing PRIVATE key entirely outside the Codespace; configure only the approved public signer as `~/.config/hazewave/reverse-engineering/allowed_signers` (0600).

Use the **same Python venv into which the analyzers are installed**:

```bash
"$HOME/.local/share/hazewave/av-research/av-research-venv/bin/python" \
  -m hazewave.av_research_lab \
  --kind EDITORIAL_SCRIPT \
  --source /absolute/path/to/authorized-script.json \
  --case-id owner-script-case-001 \
  --grant-file /absolute/path/to/owner-grant.json \
  --signature-file /absolute/path/to/owner-grant.json.sig
```

For `EDITORIAL_SCRIPT`, the source file must be a bounded JSON object:

```json
{
  "schema": "HazewaveEditorialReference/v1",
  "segments": [
    {"id": "intro001", "start_seconds": 0, "duration_seconds": 12, "narration": "Seu roteiro original."},
    {"id": "part001", "start_seconds": 12, "duration_seconds": 18, "narration": "Trecho seguinte do texto original."}
  ]
}
```

`run_authorized_study` checks exact signature/subject/domain, routes an explicit Harness capability, measures with the specialized tool, re-hashes the source to detect changes during analysis and writes a mode-0600 receipt under `~/.local/state/hazewave/av-research/receipts`. It strips raw narration, paths and private source content. A typed `OBSERVATION_ONLY` outcome can be fed into HAZE/WAVE knowledge only as **technical evidence**, never as an automatically learned style rule or authorized production.

## Scientific closed loop

1. **Observe**: gather signed target identity, codec/file structure, acoustic/visual/editorial measurements and tool/version.
2. **Hypothesize**: describe ONE causal mechanism with expected effect and conditions that would refute it.
3. **Reconstruct originally**: implement owned audio effects, score, storyboard, Blender rig or timeline with a reproducible seed/parameters.
4. **Compare**: technical A/B controlling level, timing, color space and resolution. Include uncertainty and counterexamples.
5. **Critique**: human editor, sound engineer and visual reviewer rate naturalness, artistic quality, coherence and originality separately.
6. **Learn carefully**: store only hash-linked summaries and negative outcomes; no automatic merge, publication, reference ingestion into model training or promotion.

## Future optional capabilities, not automatically installed

- **Acoustics & speech**: librosa and Essentia enabled only after core; WhisperX requires compatible licensed ASR/alignment assets and a separate resource plan; REAPER's own licenses are outside the open-source-only laboratory.
- **Graphics/animation**: Blender Python headless for synthetic animation experiments and OpenCV image/flow features when needed. RenderDoc requires a suitable graphics host/context; simply installing it onto the headless 2-vCPU Codespace does not constitute proof.
- **Visual similarity**: VMAF/SSIM/PSNR only when identical licensed reference inputs, aligned timebases and matching colorspaces exist. None of these is a creativity score.
- **Sound perceptual similarity**: repeated listening, level-match checks and bounded CPU-dependent metrics; do not assert model-identity equivalence from wave/spectral similarity alone.
- **Software**: REA6 in its separate capability lane; never put binary decompilation in place of audio/music analysis.

## Minimum acceptance

GitHub CI proves code contracts; separate disposable runner smoke proves **one** real Pillow image decode and structured editorial extraction. A Codespace `--preflight` confirms admission only. A Codespace `--doctor` proves imports in the dedicated venv, not a complete song/video study. Full sign-and-execute tests require at least one real HAZE audio, WAVE video, still image and original editorial case on the owner's actual workstation with CPU/RAM/elapsed receipts, independent human review and failure evidence. No fake PASS. Current stock Colibri remains unchanged.

Sources:
- https://ffmpeg.org/ffmpeg-filters.html
- https://github.com/MTG/essentia
- https://www.scenedetect.com/docs/latest/
- https://github.com/AcademySoftwareFoundation/OpenTimelineIO
- https://pypi.org/project/pillow/
- https://pypi.org/project/librosa/
- https://github.com/m-bain/whisperX
