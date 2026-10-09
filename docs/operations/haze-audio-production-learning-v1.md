# HAZE — escuta computacional, engenharia reversa de áudio e aprendizado de produtor (V1)

**Status:** Candidate-only / PR draft. NOT deployed to the owner's Codespace; no owner's song has been used for style model fitting yet.
**Owner objective:** eventually compose, arrange, mix and master original works with human-level judgment across all owner music genres. This V1 is the *measurable beginning*, **not** proof of that end state.
**Authority:** HAZEWAVE_HARNESS. HAZE owns audio, WAVE owns visuals, A15 is a control/transport endpoint only.

## Four different accomplishments, not one

1. **Perception / genuine listening:** FFmpeg decodes *real bytes* on the authorized workstation. \`haze_audio_learning.listen_audio\` invokes the existing bounded PCM decoder + full-track \`ReferenceProfile/v1\`: low/mid/high energy, transient activity, stereo correlation/side energy, section loudness profile, crest factor, EBU R128 integrated loudness, LRA, true peak and SHA-256. Treble/bass estimates and the first 30s *middle excerpt* are approximations, not measured individual sources. No genre or musical quality inference from filename.
2. **Learning a style representation:** \`train_style_memory\` learns numerical **centroids and medians** from genuinely analyzed, separately approved, owner-labeled references. It requires >=2 owner-defined styles with >=3 independent digests each. One distinct SHA per style is held out from fitting; the output reports exactly what did and did not generalize. A different title or file path does not make the holdout composition-independent; leave-one-SHA-out is only a preliminary gate. Model output stays private and cannot grant DAW action.
3. **Reverse-engineering investigations (not yet wired):** optional qualified Essentia for tempo/tonal descriptors; LAION CLAP or a music-audio embedding model for perceptual retrieval; Spotify Basic Pitch on isolated instruments to create editable MIDI; Demucs-style stem extraction as an experimental separated approximation, never original multitrack recovery. Identify chords, rhythmic cells, song structure, timbre, effects by *measured evidence* and independent human auditions. Full mixed waveform cannot uniquely reveal source instruments, MIDI, plug-in chain, seeds or human creative process.
4. **Generative producer (not yet qualified):** use approved, creator-owned material as references for a pinned, cost-admitted ACE-Step 1.5 generator, comparing reference-conditioned creation with optional LoRA only on an adequately resourced **approved** GPU. The existing 2-vCPU / ~8GB RAM Codespace has no verified accelerator; do not download multi-GB weights, run open-ended training, start paid infrastructure or route private media to hosted APIs automatically. REAPER's existing controlled bridge may import a synthesized original sketch into a disposable test project only after separate permission; structure, MIDI, stems, mix/master A/B and blind review must pass before owner approval.

Upstream technical background:
- Essentia music extractor: https://essentia.upf.edu/streaming_extractor_music.html
- LAION CLAP: https://github.com/LAION-AI/CLAP
- Spotify Basic Pitch: https://github.com/spotify/basic-pitch
- Demucs v4 (the original Meta repository was archived): https://github.com/facebookresearch/demucs
- ACE-Step 1.5 project and VRAM guidance: https://ace-step.github.io/ACE-Step-1.5/
- REAPER ReaScript/MIDI operations: https://www.reaper.fm/sdk/reascript/reascripthelp.html

## Preserving 435 owner assets

The **separate** A15/Termux discovery receipt \`HazeOwnerDiscovery/v1\` lists 435 found source recordings (423 MP3 and 12 WAV, ~1.572GB metadata-reported total), with one owner's private MP3 proven copied into the existing Codespace and analyzed. That receipt is **NOT** a \`HazePrivateCatalog/v1\` as used by \`haze_catalog.curate\`; do not confuse the two schemas or claim 435 media files have been transferred. Those receipts remain outside Git.

Generated titles frequently collide for **different compositions**. Never automatically delete, move, rename, overwrite, deduplicate, group as the same song, select "Final", or prefer larger WAV. Individual path/asset IDs, hashes, arrangement identities and human style labels remain separate. Even byte-identical copies remain independent source assets; for training, identical source digests are rejected to prevent evaluation leakage, **not deleted from the catalog**.

Treat songs, stems, synthetic vocals, collaborators and rights on a per-recording basis. Human authorization to analyze private owner music does not imply full legal rights for model weights, automated public release, cloud provider egress, or close imitation of third-party samples. No private music to GitHub Actions, public repos, LLM prompts or model hosts.

## CLI usage: private existing workstation only (after authorized code revision is available)

Source code lives on the candidate branch \`work/haze-producer-reaper-qualification-v1\`, not necessarily the deployed worktree. **Do not switch the active Reflex/REAPER worktree, overwrite WIP, or run these commands before the candidate SHA is available in an isolated, approved runtime.**

Example: the one MP3 copied into the private inbox. \`--root\` is the private media directory; its \`--relative-path\` must identify an actual file in that directory. \`--output\` is separately private and **outside Git** and outside original media sources. Mode 0600, atomic exclusive create, no overwrite.

\`\`\`bash
ROOT="$HOME/.local/share/hazewave/private-corpus/inbox"
PRIVATE="$HOME/.local/state/hazewave/owner-audio-learning"
mkdir -p "$PRIVATE"
chmod 700 "$PRIVATE"

PYTHONPATH="/path/to/isolated-approved-Hazewave/src" \
python -m hazewave.haze_audio_learning listen \
  --root "$ROOT" \
  --relative-path "aquaverno-004.mp3" \
  --output "$PRIVATE/aquaverno-004-listen-v1.json" \
  --allow-private-corpus
\`\`\`

The listen receipt records true technical characteristics; it **never labels genre, approves a reference, trains a model, reconstructs content or changes REAPER**.

A later **manually approved and rights-confirmed** set of at least 6 independent songs spanning 2 styles can be characterized with \`haze_catalog inventory/curate\`, producing \`HazeCuratedStyleMemory/v1\`. The next operation actually fits a small, non-neural, style-feature prototype and checks previously excluded audio:

\`\`\`bash
PYTHONPATH="/path/to/isolated-approved-Hazewave/src" \
python -m hazewave.haze_audio_learning learn \
  --root "$ROOT" \
  --input "$PRIVATE/curated-style-memory-v1.json" \
  --output "$PRIVATE/learned-style-centroids-v1.json" \
  --allow-private-corpus --allow-feature-learning
\`\`\`

The explicit feature-learning flag is for this non-neural training only; it is **not** authorization for ACE-Step LoRA, remote models, sharing data, copying songs or production actions. Do not label a held-out SHA as an unseen *composition* until a human verifies it is not a variation of a train track.


## Immediate owner training from four already-listened private MP3s

**Decision:** User explicitly requested to begin learning immediately, not to wait until the whole library is ingested. Use the already-private four \`HazeAudioListenReceipt/v1\` records as **cold-start, unsupervised acoustic feature fitting**. This mode does not require manually assigned genres, but cannot assert a genre or produce music. One unique SHA-256 per example must match its current physical source bytes, and each asset remains independent.

New CLI mode: \`python -m hazewave.haze_audio_learning bootstrap\`. Specify the actual private media \`--root\`, \`--output\` outside Git/media, \`--allow-private-corpus\`, \`--allow-feature-learning\`, and repeat \`--receipt\` for each exact path:
- \`$HOME/.local/state/hazewave/owner-audio-learning/aquaverno-004-listen-v1.json\`
- \`$HOME/.local/state/hazewave/owner-audio-learning/haze-hemorragia-cosmica-001.mp3.listen-v1.json\`
- \`$HOME/.local/state/hazewave/owner-audio-learning/haze-afro-samba-drift.mp3.listen-v1.json\`
- \`$HOME/.local/state/hazewave/owner-audio-learning/haze-iron-murk.mp3.listen-v1.json\`

Requires **2–64** independent audio SHA-256 values, exact path-to-receipt identity, declared FFmpeg reference-profile analyzer, intact audio files, and valid finite acoustic metrics. Returns \`HazeEarlyAudioLearning/v1\` with actually fitted feature centering/scaling coefficients and one prototype per source; nearest neighbours are **acoustic proximity only**, not same composition/genre. No labels or held-out performance are claimed from four examples: \`heldout_examples=0\`, \`evaluation_status=NO_INDEPENDENT_HOLDOUT_YET\`. The training is CPU-light and replayable; new examples require a new versioned receipt and refit on all valid prior receipts, with no overwrite of historical artifacts.

This is a **real non-neural fitted model** for the earliest auditory memory, not a foundation-model/LoRA fine-tune, music reconstruction, quality measure, or autonomous producer. A future generator may consult the learned representations only after an independent, owner-approved, per-style music benchmark. Never export private receipts or audio into CI or Git history.

## Incremental V2: prova com um quinto áudio e crescimento imutável

**No novo módulo** \`haze_incremental_learning.py\`, o HAZE usa os coeficientes e quatro protótipos já ajustados, sem reaprender ou modificar o modelo V1, para medir a distância da nova gravação. É uma **prova de generalização acústica por SHA-distinto**, *não* demonstra classificação de estilo nem independência de composição (regravações da mesma obra podem ter SHA diferente).

Com \`probe\`: raiz de áudio privado existente, \`--prior\` apontando para o checkpoint de quatro músicas, \`--receipt\` apontando para o relatório da música realmente nova, \`--allow-private-corpus\` e \`--output\` novo fora de Git e fora do diretório de mídias. Essa ação **não treina**, apenas compara com modelo congelado, com relatório \`HazeAcousticHoldoutProbe/v1\`.

Com \`grow\`: mesmos \`--root\` e \`--prior\`; passar \`--receipt\` **de cada um dos quatro registros históricos** e do(s) novo(s) áudio(s), \`--allow-private-corpus --allow-feature-learning\`, e um novo \`--output\`. O Harness:
1. relê hash e identidade de todos os arquivos originais, rejeitando alteração ou ausência;
2. reconstrói independentemente os parâmetros históricos dos quatro exemplos e reconcilia exatamente com o checkpoint anterior;
3. compara o novo áudio contra o **modelo congelado antes do ajuste**;
4. refaz o ajuste de coeficientes e protótipos sobre todos os exemplos autorizados, sem perda, deixando intactos áudios, recibos e modelos anteriores;
5. grava \`HazeEarlyAudioLearning/v2\` com SHA-256 do modelo ancestral, contagem antiga/nova, revisão, prova pré-ajuste e os novos parâmetros.

O output é privado e exclusivo (não sobrescreve). Crescimento V2→V3 também é permitido com novos recibos, exigindo replay completo da memória. Ao aumentar o acervo, agrupar famílias de versões por **curadoria humana de composição**, e reservá-las inteiramente fora de treino, conforme boas práticas de separação por grupo; identidade do título ou SHA diferente sozinhas não resolvem vazamento entre versões. Sem validação humana, \`style_prediction=null\`, \`heldout_examples=0\` no novo modelo de produção e \`generator_weights_updated=false\`.

Não transferir ou treinar automaticamente a coleção inteira de 435 arquivos; a quinta gravação deve ter cópia privada com autorização, SHA de transporte validado e relatório \`HazeAudioListenReceipt/v1\` antes de \`probe\`. REAPER/Reflex e A15 continuam intocados.

## Research and producer-competence roadmap with measurable gates

- **Corpus read:** bounded, resumable transfer by owner-approved subsets; SHA end-to-end; transport original names/path mapping, harden filenames, finite quotas; no bulk copy without confirmed quota. Catalog all without deletions. Audit true rights/labels and family boundaries.
- **Listening:** real decode on real privately copied tracks; verify technical reproducibility; estimate beat/tempo, tonal/harmony, sections, perceptual semantics with separate benchmark evidence. Separate music identity from duplicate title or reference stems.
- **Learning:** label owner styles and human preferences, train retrieval/ranking or adapters with held-out composition **families**, adversarially test style collisions, compare against simplistic filename/LUFS baseline; report per-style precision/recall and confidence/abstention.
- **Generative training:** only after GPU cost/rights approval; frozen base vs reference conditioning vs LoRA A/B with seed recording, held-out compositions, musical originality/plagiarism review, ablation, hours/cost and checkpoints. Running ACE-Step on this Codespace is **not approved** by this design.
- **REAPER autonomy:** owner-approved isolated sessions; safe arrangement/MIDI/render, stems and effects through typed commands; checkpoints, receipts, rollbacks and explicit human listening before final master/publication. Live session undo and publication gates continue to apply.

**Success criterion:** The user blind-auditions *new*, demonstrably original songs and confirms musical identity, arrangement, expressive quality and mix/master consistency, on multiple styles, with an evaluation against human-produced references. Until then, \`PRODUCER_COMPETENCE_PROVEN=FALSE\`.
