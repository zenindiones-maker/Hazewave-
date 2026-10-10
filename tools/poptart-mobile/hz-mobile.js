/* Hazewave Mobile Music Lab: isolated touch adapter for Poptart web-engine.
   Poptart copyright Glossing, AGPL-3.0-only; see upstream source and license. */
(() => {
  'use strict';
  const W = window, D = document;
  const MARK_A = '// HAZEWAVE_MOBILE_BEGIN';
  const MARK_B = '// HAZEWAVE_MOBILE_END';
  const KIT = Object.freeze([
    { id: 'kick', label: 'Kick', sample: 0, defaults: [0, 4, 8, 12] },
    { id: 'snare', label: 'Snare', sample: 1, defaults: [4, 12] },
    { id: 'hat', label: 'Hat', sample: 4, defaults: [0, 2, 4, 6, 8, 10, 12, 14] },
    { id: 'rim', label: 'Rim', sample: 2, defaults: [] },
    { id: 'clap', label: 'Clap', sample: 3, defaults: [] },
    { id: 'openhat', label: 'Hat aberto', sample: 5, defaults: [] },
    { id: 'tomlo', label: 'Tom grave', sample: 6, defaults: [] },
    { id: 'tomhi', label: 'Tom agudo', sample: 7, defaults: [] },
  ]);
  const KEY = 'hazewave.poptart.mobile.steps.v1';
  const NOTE_KEY = 'hazewave.poptart.mobile.notes.v1'; // legacy scale degrees
  const MIDI_KEY = 'hazewave.poptart.mobile.midi.v2';
  const ROOTS = Object.freeze(['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']);
  const MODES = Object.freeze({ major: [0, 2, 4, 5, 7, 9, 11], minor: [0, 2, 3, 5, 7, 8, 10] });
  const SYNTHS = Object.freeze(['Wavetable', 'FM', 'Plaits', 'Braids', 'Rings', 'Elements', 'Granular', 'Sampler']);
  const SOUND_VARIANTS = Object.freeze({"Wavetable":{"parameter":"Osc 1 Table","options":["Basic","Harmonics","Odd","PWM","Sync","Fold","FM","Organ","Vocal"]},"Plaits":{"parameter":"Engine","options":["VA VCF","Phase Distortion","FM 6-op A","FM 6-op B","FM 6-op C","Wave Terrain","String Machine","Chiptune","Virtual Analog","Waveshaping","FM","Grain","Additive","Wavetable","Chord","Speech","Swarm","Noise","Particle","String","Modal","Bass Drum","Snare Drum","Hi-Hat"]},"Braids":{"parameter":"Shape","options":["CSaw","Morph","Saw Square","Sine Triangle","Buzz","Square Sub","Saw Sub","Square Sync","Saw Sync","Triple Saw","Triple Square","Triple Triangle","Triple Sine","Triple Ring Mod","Saw Swarm","Saw Comb","Toy","Filter LP","Filter Peak","Filter BP","Filter HP","VOSIM","Vowel","Vowel FOF","Harmonics","FM","Feedback FM","Chaotic FM","Plucked","Bowed","Blown","Fluted","Struck Bell","Struck Drum","Kick","Cymbal","Snare","Wavetables","Wave Map","Wave Line","Wave Paraphonic","Filtered Noise","Twin Peaks Noise","Clocked Noise","Granular Cloud","Particle Noise","Digital Modulation","Question Mark"]},"Rings":{"parameter":"Model","options":["Modal","Sympathetic String","String","FM Voice","Quantised Sympathetic","String and Reverb"]}});
  const FX_CHOICES = Object.freeze(['Nenhum','Reverb','Delay','Chorus','Phaser','Flanger','Distort','Overdrive','Crush','GrainEcho','Stutter','CloudSeed','Galactic','Clouds','Shift','FreqShift','EQ','Compressor','Multiband','Limiter','Ducker','Convolver']);
  const TIMBRE_PARAMS = Object.freeze({Wavetable:['Osc 1 Position','Osc 1 Warp'],FM:['Op 2 Level','Mod 2 to 1'],Plaits:['Timbre','Morph'],Braids:['Timbre','Color'],Rings:['Brightness','Damping'],Elements:['Brightness','Space'],Granular:['Spray','Reverse']});
  const LOCAL_PACKS = Object.freeze([{"id":"pt_keys","title":"Poptart Keys","kind":"melodic","files":[{"name":"Pluck","number":0,"license":"CC0-1.0"},{"name":"Bell","number":1,"license":"CC0-1.0"},{"name":"Bass","number":2,"license":"CC0-1.0"},{"name":"Pad","number":3,"license":"CC0-1.0"},{"name":"Stab","number":4,"license":"CC0-1.0"}]},{"id":"pt_kit","title":"Poptart Kit","kind":"drums","files":[{"name":"Kick","number":0,"license":"CC0-1.0"},{"name":"Snare","number":1,"license":"CC0-1.0"},{"name":"Rim","number":2,"license":"CC0-1.0"},{"name":"Clap","number":3,"license":"CC0-1.0"},{"name":"Hat","number":4,"license":"CC0-1.0"},{"name":"Hat aberto","number":5,"license":"CC0-1.0"},{"name":"Tom grave","number":6,"license":"CC0-1.0"},{"name":"Tom agudo","number":7,"license":"CC0-1.0"}]}]);
  let remotePacks = [];
  const soundPacks = kind => [...LOCAL_PACKS.filter(p=>p.kind===kind),...remotePacks.filter(p=>p.kind===kind)];
  const packOf = (id,kind) => soundPacks(kind).find(p=>p.id===id);
  const audioFiles = (id,kind) => packOf(id,kind)?.files ?? [];

  const DRUM_SAMPLES = Object.freeze(['Kick', 'Snare', 'Rim', 'Clap', 'Hat', 'Hat aberto', 'Tom grave', 'Tom agudo']);
  const NOTE_NAMES = Object.freeze(['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']);
  const noteName = midi => NOTE_NAMES[midi % 12].toLowerCase() + (Math.floor(midi / 12) - 2);
  const tonicMidi = (root, octave) => 60 + ROOTS.indexOf(root) + 12 * (octave - 3);
  const degreeMidi = (degree, root, mode, octave) =>
    tonicMidi(root, octave) + MODES[mode][degree % 7] + 12 * Math.floor(degree / 7);
  const boundedMidi = n => Number.isInteger(n) && n >= 36 && n <= 108 ? n : -1;
  const MIX_KEY = 'hazewave.poptart.mobile.controls.v1';
  // Budget the COMBINED voices, not just each slider: peaks from tracks add up.
  // Full keeps all eight lanes but never restores V3's unsafe 0.42 per lane.
  const AUDIO_PROFILES = Object.freeze({
    stable: {maxLanes:4, drumBudget:0.42, maxDrumGain:0.14, maxMelodyGain:0.22},
    full: {maxLanes:8, drumBudget:0.48, maxDrumGain:0.14, maxMelodyGain:0.34},
  });
  const HEAVY_FX = Object.freeze(['CloudSeed','Galactic','Clouds','Shift','Convolver','GrainEcho','Multiband']);

  const limits = (n, low, high, fallback) => Number.isFinite(n) ? Math.max(low, Math.min(high, n)) : fallback;
  let storedNotes = null, storedMidi = null, storedMix = null;
  try { storedNotes = JSON.parse(W.localStorage.getItem(NOTE_KEY)); } catch {}
  try { storedMidi = JSON.parse(W.localStorage.getItem(MIDI_KEY)); } catch {}
  try { storedMix = JSON.parse(W.localStorage.getItem(MIX_KEY)); } catch {}
  const mix = {
    bpm: Math.round(limits(Number(storedMix?.bpm), 60, 200, 120)),
    cutoff: limits(Number(storedMix?.cutoff), 0.05, 0.95, 0.45),
    // Clamp imported V1-V3 mixer state before it touches the audio engine.
    gain: limits(Number(storedMix?.gain), 0.05,
      AUDIO_PROFILES[storedMix?.audioMode === 'full' ? 'full' : 'stable'].maxMelodyGain, 0.16),
    audioMode: storedMix?.audioMode === 'full' ? 'full' : 'stable',
    root: ROOTS.includes(storedMix?.root) ? storedMix.root : 'F',
    mode: Object.hasOwn(MODES, storedMix?.mode) ? storedMix.mode : 'minor',
    octave: Number.isInteger(storedMix?.octave) ? limits(storedMix.octave, 2, 5, 3) : 3,
    synth: SYNTHS.includes(storedMix?.synth) ? storedMix.synth : 'Wavetable',
    fx: FX_CHOICES.includes(storedMix?.fx) ? storedMix.fx : 'Nenhum',
    samplePack: 'pt_keys',
    sampleIndex: 0,
    drumPacks: KIT.map((lane, i) => typeof storedMix?.drumPacks?.[i] === 'string'
      && /^pt_[a-z0-9_]+$/.test(storedMix.drumPacks[i])
      ? storedMix.drumPacks[i] : 'pt_kit'),
    kit: KIT.map((lane, i) => {
      const n = storedMix?.kit?.[i];
      return Number.isInteger(n) && n >= 0 && n <= 4999 ? n : lane.sample;
    }),
    soundVariant: storedMix?.soundVariant && typeof storedMix.soundVariant === 'object'
      ? {...storedMix.soundVariant} : {},
    tones: storedMix?.tones && typeof storedMix.tones === 'object'
      ? {...storedMix.tones} : {},
  };
  // Sound picks are kept as data, never executed as JavaScript.
  if (typeof storedMix?.samplePack === 'string' && /^pt_[a-z0-9_]+$/.test(storedMix.samplePack))
    mix.samplePack = storedMix.samplePack;
  if (Number.isInteger(storedMix?.sampleIndex) && storedMix.sampleIndex >= 0 && storedMix.sampleIndex <= 4999)
    mix.sampleIndex = storedMix.sampleIndex;
  const defaultDegrees = [0, -1, 2, -1, 3, -1, 4, -1, 5, -1, 4, -1, 2, -1, 1, -1];
  // Import the existing user's V1 steps without shifting their audible pitches.
  const noteSteps = Array.from({ length: 16 }, (_, i) => {
    if (Array.isArray(storedMidi) && storedMidi.length === 16)
      return boundedMidi(storedMidi[i]);
    const n = Array.isArray(storedNotes) && Number.isInteger(storedNotes[i]) &&
      storedNotes[i] >= -1 && storedNotes[i] <= 7 ? storedNotes[i] : defaultDegrees[i];
    return n < 0 ? -1 : degreeMidi(n, 'F', 'minor', 3);
  });
  const isMobile = () => W.matchMedia('(max-width: 800px)').matches;
  const report = (message) => {
    const status = D.getElementById('hz-mobile-status');
    if (status) status.textContent = message;
  };
  function storedSteps() {
    let incoming = null;
    try { incoming = JSON.parse(W.localStorage.getItem(KEY)); } catch {}
    return Object.fromEntries(KIT.map(lane => [
      lane.id, Array.from({ length: 16 }, (_, i) =>
        Array.isArray(incoming?.[lane.id]) ? incoming[lane.id][i] === true : lane.defaults.includes(i)
      ),
    ]));
  }
  const state = storedSteps();
  function saveSteps() {
    try {
      W.localStorage.setItem(KEY, JSON.stringify(state));
      W.localStorage.setItem(MIDI_KEY, JSON.stringify(noteSteps));
      W.localStorage.setItem(MIX_KEY, JSON.stringify(mix));
    }
    catch { report('Armazenamento indisponível. Exporte o projeto para não perder as alterações.'); }
  }
  function getEditor() {
    const cm = D.querySelector('.CodeMirror')?.CodeMirror;
    const textarea = D.getElementById('editor');
    return {
      get: () => cm?.getValue?.() ?? textarea?.value ?? null,
      set: (value) => {
        if (cm?.setValue) cm.setValue(value);
        else if (textarea) {
          textarea.value = value;
          textarea.dispatchEvent(new Event('input', { bubbles: true }));
        } else throw new Error('Editor do Poptart não encontrado');
      },
      focus: () => cm?.focus?.() ?? textarea?.focus(),
    };
  }
  function generatePattern() {
    const activeKit = KIT.map((lane, i) => ({lane, i}))
      .filter(({lane}) => state[lane.id].some(Boolean));
    const profile = AUDIO_PROFILES[mix.audioMode] ?? AUDIO_PROFILES.stable;
    if (activeKit.length > profile.maxLanes)
      throw new Error('Modo estável: no máximo '+profile.maxLanes+
        ' pistas de bateria ativas. Desative outras pistas ou escolha Completo.');
    if (mix.audioMode === 'stable' && HEAVY_FX.includes(mix.fx))
      throw new Error('Efeito pesado para o A15. Mude para Completo ou escolha um efeito leve.');
    const drumLevel = Math.min(profile.maxDrumGain,
      profile.drumBudget / Math.max(1, activeKit.length));
    const melodyLevel = Math.min(profile.maxMelodyGain, mix.gain);
    const notes = noteSteps.map(n => n < 0 ? '~' : noteName(n)).join(' ');
    const isSample = mix.synth === 'Sampler';
    const isGrain = mix.synth === 'Granular';
    const sample = mix.samplePack + ':' + mix.sampleIndex;
    if ((isSample || isGrain) && (!packOf(mix.samplePack,'melodic') ||
      !audioFiles(mix.samplePack,'melodic')[mix.sampleIndex]))
      throw new Error('Sample melódico ainda não disponível no catálogo local; tente novamente após carregar.');
    for (let i=0;i<KIT.length;i++) {
      if (state[KIT[i].id].some(Boolean) &&
        (!packOf(mix.drumPacks[i],'drums') || !audioFiles(mix.drumPacks[i],'drums')[mix.kit[i]]))
        throw new Error('Banco de bateria '+KIT[i].label+' não disponível; carregue o catálogo.');
    }
    let melody = isSample ? 's("' + sample + '").note("' + notes + '")'
      : 'note("' + notes + '").synth("' + mix.synth + '")';
    if (isGrain) melody += '.param("Sample", "' + sample + '")';
    const v = SOUND_VARIANTS[mix.synth];
    const option = v && v.options.includes(mix.soundVariant[mix.synth]) ? mix.soundVariant[mix.synth] : null;
    if (option) melody += '.param("' + v.parameter + '", "' + option + '")';
    const controls = TIMBRE_PARAMS[mix.synth] || [];
    const tone = mix.tones[mix.synth];
    if (tone && typeof tone === 'object') for (let n = 0; n < controls.length; n++) {
      const value = tone[n];
      if (typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1)
        melody += '.param("' + controls[n] + '", ' + value.toFixed(2) + ')';
    }
    melody += '.fx("Filter").param("Cutoff", ' + mix.cutoff.toFixed(2) + ')';
    if (mix.fx !== 'Nenhum') melody += '.fx("' + mix.fx + '")';
    melody += '.postgain(' + melodyLevel.toFixed(2) + ')';
    return [MARK_A,
      '// Catálogo oficial Poptart: sintetizadores, presets e samples licenciados.',
      'setbpm(' + mix.bpm + ')',
      // Do not instantiate six extra silent sample tracks on a small CPU.
      ...activeKit.map(({lane,i}) => {
        const sample = mix.drumPacks[i] + ':' + mix.kit[i];
        const steps = state[lane.id].map(v => v ? sample : '~');
        return 'hz_' + lane.id + ': s("' + steps.join(' ') +
          '").postgain(' + drumLevel.toFixed(3) + ')';
      }),
      'hz_melody: ' + melody,
      MARK_B].join('\n');
  }
  function mergeManagedBlock(source, managed) {
    if (source == null) throw new Error('Editor não inicializado');
    const start = source.indexOf(MARK_A), end = source.indexOf(MARK_B);
    if ((start >= 0) !== (end >= 0) || (start >= 0 && end < start))
      throw new Error('Bloco musical gerenciado está incompleto: não sobrescrito');
    if (start < 0) return source.trimEnd() + '\n\n' + managed + '\n';
    if (source.indexOf(MARK_A, start + MARK_A.length) >= 0 ||
        source.indexOf(MARK_B, end + MARK_B.length) >= 0)
      throw new Error('Blocos gerenciados duplicados: edição suspensa');
    return source.slice(0, start) + managed + source.slice(end + MARK_B.length);
  }
  function playFromTouch() {
    try {
      const e = getEditor();
      const next = mergeManagedBlock(e.get(), generatePattern());
      e.set(next);
      const update = D.getElementById('updateBtn');
      const play = D.getElementById('playBtn');
      const playing = /\bstop\b/i.test(play?.textContent ?? '');
      const target = playing ? update : play;
      if (!target) throw new Error('Controle de reprodução não encontrado');
      target.click();
      report('Padrão atualizado no editor. Confirme a reprodução e o som no aparelho.');
    } catch (error) { report(error.message); }
  }
  function downloadBackup() {
    const source = getEditor().get();
    if (source == null) return report('Editor ainda não disponível');
    const data = JSON.stringify({
      schema: 'HazewavePoptartMobileBackup/v4',
      exported_at: new Date().toISOString(),
      source, steps: state, midi_notes: noteSteps, mix,
      attribution: 'Poptart by Glossing, AGPL-3.0-only',
    }, null, 2);
    const url = URL.createObjectURL(new Blob([data], { type: 'application/json' }));
    const a = D.createElement('a');
    a.href = url;
    a.download = 'hazewave-poptart-' + new Date().toISOString().slice(0, 10) + '.json';
    D.body.append(a);
    a.click(); a.remove();
    W.setTimeout(() => URL.revokeObjectURL(url), 1000);
    report('Backup exportado. Confira o arquivo baixado.');
  }
  function restoreBackup(file) {
    if (!file || file.size > 2 * 1024 * 1024) return report('Backup ausente ou maior que 2 MB');
    file.text().then(text => {
      const data = JSON.parse(text);
      if (!['HazewavePoptartMobileBackup/v1', 'HazewavePoptartMobileBackup/v2',
        'HazewavePoptartMobileBackup/v3', 'HazewavePoptartMobileBackup/v4'].includes(data.schema) ||
          typeof data.source !== 'string') throw new Error('Backup inválido');
      if (!W.confirm('Substituir o código atual pelo backup? Exporte seu trabalho antes.')) return;
      getEditor().set(data.source);
      for (const lane of KIT) {
        if (Array.isArray(data.steps?.[lane.id]) && data.steps[lane.id].length === 16)
          state[lane.id] = data.steps[lane.id].map(x => x === true);
      }
      if (Array.isArray(data.midi_notes) && data.midi_notes.length === 16) {
        for (let i = 0; i < 16; i++) noteSteps[i] = boundedMidi(data.midi_notes[i]);
      } else if (Array.isArray(data.notes) && data.notes.length === 16) {
        // Backward-compatible V1 backup: degrees always belonged to F minor at octave 3.
        for (let i = 0; i < 16; i++) {
          const degree = data.notes[i];
          noteSteps[i] = Number.isInteger(degree) && degree >= 0 && degree <= 7
            ? degreeMidi(degree, 'F', 'minor', 3) : -1;
        }
      }
      for (const key of ['bpm', 'cutoff', 'gain'])
        if (Number.isFinite(data.mix?.[key])) mix[key] = data.mix[key];
      if (ROOTS.includes(data.mix?.root)) mix.root = data.mix.root;
      if (Object.hasOwn(MODES, data.mix?.mode)) mix.mode = data.mix.mode;
      if (Number.isInteger(data.mix?.octave)) mix.octave = limits(data.mix.octave, 2, 5, 3);
      if (SYNTHS.includes(data.mix?.synth)) mix.synth = data.mix.synth;
      if (FX_CHOICES.includes(data.mix?.fx)) mix.fx=data.mix.fx;
      mix.audioMode = data.mix?.audioMode === 'full' ? 'full' : 'stable';
      if (Array.isArray(data.mix?.drumPacks))
        mix.drumPacks=KIT.map((lane,i)=>typeof data.mix.drumPacks[i]==='string' &&
          /^pt_[a-z0-9_]+$/.test(data.mix.drumPacks[i]) ? data.mix.drumPacks[i] : 'pt_kit');
      if (Array.isArray(data.mix?.kit))
        mix.kit=KIT.map((lane,i)=>Number.isInteger(data.mix.kit[i]) &&
          data.mix.kit[i]>=0 && data.mix.kit[i]<=4999 ? data.mix.kit[i] : lane.sample);
      if (typeof data.mix?.samplePack==='string' && /^pt_[a-z0-9_]+$/.test(data.mix.samplePack))
        mix.samplePack=data.mix.samplePack;
      if (Number.isInteger(data.mix?.sampleIndex) && data.mix.sampleIndex>=0 &&
        data.mix.sampleIndex<=4999) mix.sampleIndex=data.mix.sampleIndex;
      if (data.mix?.soundVariant && typeof data.mix.soundVariant==='object')
        for (const [name,choice] of Object.entries(data.mix.soundVariant))
          if (SOUND_VARIANTS[name] && SOUND_VARIANTS[name].options.includes(choice))
            mix.soundVariant[name]=choice;
      if (data.mix?.tones && typeof data.mix.tones==='object')
        for(const [name,settings] of Object.entries(data.mix.tones)){
          if (!TIMBRE_PARAMS[name] || !settings || typeof settings!=='object') continue;
          mix.tones[name]={};
          for(const n of [0,1]){
            const v=settings[n];
            if (typeof v==='number' && Number.isFinite(v) && v>=0 && v<=1)
              mix.tones[name][n]=v;
          }
        }
      mix.bpm = Math.round(limits(mix.bpm, 60, 200, 120));
      mix.cutoff = limits(mix.cutoff, 0.05, 0.95, 0.45);
      mix.gain = limits(mix.gain, 0.05, AUDIO_PROFILES[mix.audioMode].maxMelodyGain, 0.16);
      const bpm = D.getElementById('hz-bpm');
      const cutoff = D.getElementById('hz-cutoff');
      const gain = D.getElementById('hz-gain');
      if (bpm) bpm.value = mix.bpm;
      if (cutoff) cutoff.value = mix.cutoff;
      if (gain) gain.value = mix.gain;
      for (const [key, value] of [['hz-key', mix.root], ['hz-mode', mix.mode],
        ['hz-octave', mix.octave], ['hz-synth', mix.synth]])
        { const select = D.getElementById(key); if (select) select.value = String(value); }
      for (let i = 0; i < KIT.length; i++) {
        const select = D.getElementById('hz-kit-' + i);
        if (select) select.value = String(mix.kit[i]);
      }
      syncSoundUI(); syncAudioProfileUI(); refreshPitchGrid(); saveSteps(); repaint();
      report('Backup restaurado (V1–V4). Pressione Aplicar e ouvir.');
    }).catch(error => report('Falha ao importar: ' + error.message));
  }
  function repaint() {
    for (const b of D.querySelectorAll('[data-hz-lane][data-hz-step]')) {
      const active = !!state[b.dataset.hzLane]?.[Number(b.dataset.hzStep)];
      b.setAttribute('aria-pressed', String(active));
      b.classList.toggle('on', active);
    }
    for (const b of D.querySelectorAll('[data-hz-note][data-hz-beat]')) {
      const active = noteSteps[Number(b.dataset.hzBeat)] === Number(b.dataset.hzNote);
      b.setAttribute('aria-pressed', String(active));
      b.classList.toggle('on', active);
    }
  }
  function refreshPitchGrid() {
    const heading = D.querySelector('#hz-mobile-board .hz-board-heading strong');
    if (heading && !D.getElementById('hz-melody-scroll')?.hidden)
      heading.textContent = 'HAZE / notas cromáticas · ' + mix.root + mix.octave;
    const base = tonicMidi(mix.root, mix.octave);
    const canvas = D.getElementById('hz-note-grid');
    if (!canvas) return;
    canvas.replaceChildren();
    const inScale = MODES[mix.mode];
    for (let semitone = 11; semitone >= 0; semitone--) {
      const midi = base + semitone;
      const name = noteName(midi);
      const label = D.createElement('div');
      label.className = 'hz-lane-name';
      label.textContent = name.toUpperCase();
      if (inScale.includes(semitone)) label.classList.add('hz-in-scale');
      canvas.append(label);
      for (let step = 0; step < 16; step++) {
        const b = D.createElement('button');
        b.type = 'button';
        b.dataset.hzNote = String(midi);
        b.dataset.hzBeat = String(step);
        b.textContent = String(step + 1);
        b.setAttribute('aria-label', name + ', passo ' + (step + 1));
        if (step % 4 === 0) b.classList.add('bar-start');
        canvas.append(b);
      }
    }
    repaint();
  }
  function shiftPitch(semitones) {
    if (!semitones) return;
    // Never silently discard user notes on a shift outside the supported MIDI range.
    if (noteSteps.some(n => n >= 0 && (n + semitones < 36 || n + semitones > 108)))
      throw new Error('Transposição fora do alcance: mantenha as notas entre MIDI 36 e 108');
    for (let i = 0; i < noteSteps.length; i++)
      if (noteSteps[i] >= 0) noteSteps[i] += semitones;
  }
  // This is a pinned on-disk catalog, not a network search in a remote repository.
  // Poptart's own engine fetches external sound bytes only when a pack is used.
  function optionsFor(select,values,selected) {
    if (!select) return;
    select.replaceChildren();
    for (const [value,label] of values) {
      const option = D.createElement('option');
      option.value = String(value); option.textContent = String(label); select.append(option);
    }
    select.value = String(selected);
  }
  function soundChoices(pack,kind) {
    const files = audioFiles(pack,kind);
    return files.map((f,i)=>[i, f.name + ' · ' + String(i + 1) + '/' + files.length]);
  }
  function packChoices(kind) {
    return soundPacks(kind).map(p=>[p.id,p.title+' ('+p.files.length+')'+
      (p.id==='pt_kit'||p.id==='pt_keys'?' · local':' · externo')]);
  }
  function syncSoundUI() {
    const synth = D.getElementById('hz-synth');
    if (!synth) return;
    const variantRow = D.getElementById('hz-variant-row');
    const sampleRows = D.getElementById('hz-sampler-controls');
    const timbreRows = D.getElementById('hz-character-controls');
    const variants = SOUND_VARIANTS[mix.synth];
    if (variantRow) variantRow.hidden = !variants;
    if (variants) {
      optionsFor(D.getElementById('hz-variant'),
        [['','Padrão original'],...variants.options.map(t=>[t,t])],
        variants.options.includes(mix.soundVariant[mix.synth])?mix.soundVariant[mix.synth]:'');
    }
    if (sampleRows) sampleRows.hidden = mix.synth !== 'Sampler' && mix.synth !== 'Granular';
    const pack = packOf(mix.samplePack,'melodic');
    if (!pack && soundPacks('melodic').length) {
      mix.samplePack = 'pt_keys'; mix.sampleIndex = 0;
    }
    optionsFor(D.getElementById('hz-sample-pack'),packChoices('melodic'),mix.samplePack);
    const samples = soundChoices(mix.samplePack,'melodic');
    if (mix.sampleIndex >= samples.length) mix.sampleIndex = 0;
    optionsFor(D.getElementById('hz-sample-file'),samples,mix.sampleIndex);
    if (timbreRows) timbreRows.hidden = !TIMBRE_PARAMS[mix.synth];
    const names = TIMBRE_PARAMS[mix.synth] || [];
    const settings = mix.tones[mix.synth] || {};
    names.forEach((name,i)=>{
      const label=D.getElementById('hz-tone-label-'+i);
      const slider=D.getElementById('hz-tone-'+i);
      if (label) label.firstChild.textContent=name;
      if (slider) slider.value=typeof settings[i]==='number'?settings[i]:0.5;
    });
    for (let i=0; i<KIT.length; i++) {
      const pack=packOf(mix.drumPacks[i],'drums');
      if (!pack && soundPacks('drums').length) {
        mix.drumPacks[i]='pt_kit';mix.kit[i]=KIT[i].sample;
      }
      optionsFor(D.getElementById('hz-pack-'+i),packChoices('drums'),mix.drumPacks[i]);
      const sounds=soundChoices(mix.drumPacks[i],'drums');
      if (mix.kit[i]>=sounds.length) mix.kit[i]=0;
      optionsFor(D.getElementById('hz-kit-'+i),sounds,mix.kit[i]);
    }
    const count = D.getElementById('hz-catalog-summary');
    if (count) count.textContent='Biblioteca oficial: 13 locais + '+remotePacks.reduce((n,p)=>n+p.files.length,0)+
      ' externos catalogados. Os externos precisam de rede no primeiro uso.';
  }
  async function loadCatalog() {
    try {
      const response=await W.fetch('./hz-sound-catalog.json',{cache:'force-cache'});
      if (!response.ok) throw new Error('catálogo HTTP '+response.status);
      const data=await response.json();
      const expected='6e19b90a4f07a1c863fc1272a41800934d7c6530';
      if (data.schema!=='HazewavePoptartSoundCatalog/v1' ||
        data.origin_commit!==expected || data.origin_files!==182 || data.local_files!==13 ||
        !Array.isArray(data.packs) || data.packs.length!==15)
        throw new Error('identidade ou contagem de catálogo divergente');
      const packs=data.packs.map(p=>{
        if (!/^pt_[a-z0-9_]+$/.test(p.id) || !['drums','melodic'].includes(p.kind) ||
          !Array.isArray(p.files) || !p.files.length ||
          !p.files.every((f,i)=> f.number===i && f.license==='CC0-1.0' &&
             typeof f.name==='string' && typeof f.file==='string' &&
             /^[a-z0-9_.-]+$/i.test(f.file)))
          throw new Error('catálogo contém pack inválido');
        return p;
      });
      if (packs.reduce((n,p)=>n+p.files.length,0)!==182)
        throw new Error('contagem de arquivos divergente');
      remotePacks=packs;
      syncSoundUI();saveSteps();
    } catch (error) {
      report('Biblioteca remota indisponível: '+error.message+'. 13 samples locais permanecem.');
    }
  }
  function syncAudioProfileUI() {
    const profile=AUDIO_PROFILES[mix.audioMode] ?? AUDIO_PROFILES.stable;
    mix.gain=limits(mix.gain,0.05,profile.maxMelodyGain,0.16);
    const selector=D.getElementById('hz-audio-profile');
    if(selector) selector.value=mix.audioMode;
    const gain=D.getElementById('hz-gain');
    if(gain) {
      gain.max=String(profile.maxMelodyGain);
      gain.value=String(mix.gain);
    }
  }
  function show(panel) {
    const board = D.getElementById('hz-mobile-board');
    D.documentElement.classList.toggle('hz-mobile-tools', panel === 'tools');
    board.hidden = panel !== 'pads' && panel !== 'notes';
    const drum = D.getElementById('hz-drum-scroll');
    const melody = D.getElementById('hz-melody-scroll');
    if (drum) drum.hidden = panel !== 'pads';
    if (melody) melody.hidden = panel !== 'notes';
    const heading = board.querySelector('.hz-board-heading strong');
    if (heading) heading.textContent = panel === 'notes'
      ? 'HAZE / notas cromáticas · ' + mix.root + mix.octave
      : 'HAZE / bateria · 16 passos';
    const tone = D.getElementById('hz-tone-controls');
    const kit = D.getElementById('hz-kit-controls');
    if (tone) tone.hidden = panel !== 'notes';
    if (kit) kit.hidden = panel !== 'pads';
    for (const b of D.querySelectorAll('[data-hz-tab]'))
      b.setAttribute('aria-pressed', String(b.dataset.hzTab === panel));
    if (panel === 'code') getEditor().focus();
  }
  function createUI() {
    if (D.getElementById('hz-mobile-dock')) return;
    const dock = D.createElement('nav');
    dock.id = 'hz-mobile-dock';
    dock.setAttribute('aria-label', 'Controles musicais Hazewave');
    dock.innerHTML = '<button type="button" data-hz-tab="code">Código</button>' +
      '<button type="button" data-hz-tab="pads">Bateria</button>' +
      '<button type="button" data-hz-tab="notes">Melodia</button>' +
      '<button type="button" data-hz-tab="tools">Painéis</button>' +
      '<button type="button" data-hz-tab="backup">Backup</button>';
    const board = D.createElement('section');
    board.id = 'hz-mobile-board';
    board.hidden = true;
    board.setAttribute('aria-label', 'Sequenciador touch de 16 passos');
    const heading = D.createElement('div');
    heading.className = 'hz-board-heading';
    heading.innerHTML = '<strong>HAZE / sequenciador 16 passos</strong>' +
      '<button type="button" id="hz-mobile-close" aria-label="Fechar bateria">×</button>';
    board.append(heading);
    const scroller = D.createElement('div');
    scroller.className = 'hz-grid-scroll';
    scroller.id = 'hz-drum-scroll';
    const grid = D.createElement('div');
    grid.className = 'hz-sequencer-grid';
    for (const lane of KIT) {
      const label = D.createElement('div');
      label.className = 'hz-lane-name'; label.textContent = lane.label; grid.append(label);
      for (let i = 0; i < 16; i++) {
        const b = D.createElement('button');
        b.type = 'button'; b.dataset.hzLane = lane.id; b.dataset.hzStep = String(i);
        b.setAttribute('aria-label', lane.label + ' tempo ' + (i + 1));
        b.textContent = String(i + 1);
        if (i % 4 === 0) b.classList.add('bar-start');
        grid.append(b);
      }
    }
    scroller.append(grid); board.append(scroller);
    const piano = D.createElement('div');
    piano.className = 'hz-grid-scroll';
    piano.id = 'hz-melody-scroll';
    piano.hidden = true;
    const keys = D.createElement('div');
    keys.className = 'hz-sequencer-grid';
    keys.id = 'hz-note-grid';
    piano.append(keys); board.append(piano);
    const tone = D.createElement('div');
    tone.id = 'hz-tone-controls';
    tone.className = 'hz-tone-controls';
    tone.hidden = true;
    const makeSelect = (id, title, options, selected) => {
      const label = D.createElement('label');
      label.textContent = title;
      const select = D.createElement('select');
      select.id = id;
      for (const [value, name] of options) {
        const option = D.createElement('option');
        option.value = String(value);
        option.textContent = name;
        select.append(option);
      }
      select.value = String(selected);
      label.append(select);
      return label;
    };
    tone.append(
      makeSelect('hz-key', 'Tonalidade', ROOTS.map(k => [k, k]), mix.root),
      makeSelect('hz-mode', 'Escala', [['minor', 'Menor'], ['major', 'Maior']], mix.mode),
      makeSelect('hz-octave', 'Oitava', [2, 3, 4, 5].map(n => [n, String(n)]), mix.octave),
      makeSelect('hz-synth', 'Instrumento', SYNTHS.map(n => [n, n]), mix.synth),
    );
    board.append(tone);
    const kitControls = D.createElement('div');
    kitControls.id = 'hz-kit-controls';
    kitControls.className = 'hz-kit-controls';
    kitControls.hidden = true;
    KIT.forEach((lane,i)=>{
      kitControls.append(makeSelect('hz-pack-'+i,'Banco '+lane.label,
        [['pt_kit','Poptart Kit · local']],mix.drumPacks[i]));
      kitControls.append(makeSelect('hz-kit-'+i,'Som '+lane.label,
        DRUM_SAMPLES.map((name,n)=>[n,name]),mix.kit[i]));
    });
    board.append(kitControls);
    const variantRow=D.createElement('div');
    variantRow.id='hz-variant-row';
    variantRow.className='hz-extra-sound-controls';
    variantRow.append(makeSelect('hz-variant','Modelo / wavetable',
      [['','Padrão original']],mix.soundVariant[mix.synth]||''));
    tone.append(variantRow);
    const sampleRows=D.createElement('div');
    sampleRows.id='hz-sampler-controls';
    sampleRows.className='hz-extra-sound-controls';
    sampleRows.append(
      makeSelect('hz-sample-pack','Banco melódico',[['pt_keys','Poptart Keys · local']],mix.samplePack),
      makeSelect('hz-sample-file','Sample',[['0','Pluck']],mix.sampleIndex));
    tone.append(sampleRows);
    const timbreRows=D.createElement('div');
    timbreRows.id='hz-character-controls';
    timbreRows.className='hz-extra-sound-controls';
    for(let i=0;i<2;i++){
      const lab=D.createElement('label');
      lab.id='hz-tone-label-'+i;
      lab.append(D.createTextNode('Timbre '+(i+1)));
      const slider=D.createElement('input');
      slider.id='hz-tone-'+i;
      slider.type='range';slider.min='0';slider.max='1';slider.step='0.05';slider.value='0.5';
      lab.append(slider);timbreRows.append(lab);
    }
    tone.append(timbreRows);
    const extra=makeSelect('hz-fx','Efeito adicional',
      FX_CHOICES.map(name=>[name,name]),mix.fx);
    tone.append(extra);
    const summary=D.createElement('p');
    summary.id='hz-catalog-summary';
    summary.setAttribute('role','status');
    tone.append(summary);
    syncSoundUI();
    const controls = D.createElement('div');
    controls.className = 'hz-music-controls';
    controls.innerHTML = '<label>BPM <input id="hz-bpm" type="number" min="60" max="200" step="1" value="' + mix.bpm + '"></label>' +
      '<label>Filtro <input id="hz-cutoff" type="range" min="0.05" max="0.95" step="0.05" value="' + mix.cutoff + '"></label>' +
      '<label>Volume da melodia <input id="hz-gain" type="range" min="0.05" max="0.22" step="0.01" value="' + mix.gain + '"></label>' +
      '<label>Áudio <select id="hz-audio-profile"><option value="stable">Estável (A15)</option>' +
      '<option value="full">Completo (experimental)</option></select></label>';
    board.append(controls);
    syncAudioProfileUI();
    tone.addEventListener('change', event => {
      const input = event.target;
      try {
        if (input.id === 'hz-key' && ROOTS.includes(input.value)) {
          shiftPitch(ROOTS.indexOf(input.value) - ROOTS.indexOf(mix.root));
          mix.root = input.value;
        } else if (input.id === 'hz-octave') {
          const next = Number(input.value);
          if (!Number.isInteger(next) || next < 2 || next > 5) return;
          shiftPitch(12 * (next - mix.octave));
          mix.octave = next;
        } else if (input.id === 'hz-mode' && Object.hasOwn(MODES, input.value))
          mix.mode = input.value;
        else if (input.id === 'hz-synth' && SYNTHS.includes(input.value))
          mix.synth = input.value;
        else if (input.id === 'hz-fx' && FX_CHOICES.includes(input.value))
          mix.fx = input.value;
        else if (input.id === 'hz-variant' &&
          SOUND_VARIANTS[mix.synth]?.options.includes(input.value) || 
          (input.id === 'hz-variant' && input.value === ''))
          mix.soundVariant[mix.synth] = input.value;
        else if (input.id === 'hz-sample-pack' && packOf(input.value,'melodic')) {
          mix.samplePack=input.value;mix.sampleIndex=0;
        } else if (input.id === 'hz-sample-file') {
          const number=Number(input.value);
          if (!Number.isInteger(number) || number<0 ||
            number>=audioFiles(mix.samplePack,'melodic').length) return;
          mix.sampleIndex=number;
        }
        else return;
        syncSoundUI();saveSteps(); refreshPitchGrid();
        report('Timbre selecionado. Pressione Aplicar e ouvir; confirme o som real no aparelho.');
      } catch (error) {
        input.value = input.id === 'hz-key' ? mix.root : String(mix.octave);
        report(error.message);
      }
    });
    tone.addEventListener('input',event=>{
      if (!/^hz-tone-[01]$/.test(event.target.id)) return;
      const index=Number(event.target.id.slice(-1));
      const n=Number(event.target.value);
      if (!TIMBRE_PARAMS[mix.synth] || !Number.isFinite(n) || n<0 || n>1) return;
      if (!mix.tones[mix.synth] || typeof mix.tones[mix.synth]!=='object')
        mix.tones[mix.synth]={};
      mix.tones[mix.synth][index]=n;
      saveSteps();
      report('Parâmetro do instrumento ajustado. Pressione Aplicar e ouvir.');
    });
    kitControls.addEventListener('change', event => {
      const input=event.target;
      const id=input.id;
      if (/^hz-pack-[0-7]$/.test(id)) {
        const i=Number(id.slice(-1));
        if (!packOf(input.value,'drums')) return;
        mix.drumPacks[i]=input.value;mix.kit[i]=0;
      } else if (/^hz-kit-[0-7]$/.test(id)) {
        const i=Number(id.slice(-1));
        const n=Number(input.value);
        if (!Number.isInteger(n) || n<0 ||
          n>=audioFiles(mix.drumPacks[i],'drums').length) return;
        mix.kit[i]=n;
      } else return;
      syncSoundUI();saveSteps();
      report('Banco/peça alterado. Pressione Aplicar e ouvir; confirme o som real.');
    });
    controls.addEventListener('input', event => {
      const id=event.target.id;
      if (!['hz-bpm','hz-cutoff','hz-gain'].includes(id)) return;
      const value=Number(event.target.value);
      if (id==='hz-bpm') mix.bpm=Math.round(limits(value,60,200,120));
      if (id==='hz-cutoff') mix.cutoff=limits(value,0.05,0.95,0.45);
      if (id==='hz-gain') mix.gain=limits(value,0.05,
        AUDIO_PROFILES[mix.audioMode].maxMelodyGain,0.16);
      saveSteps();
      // V3 rebuilt the entire audio graph after 130ms while sliding:
      // stop that update storm on Chrome Android; apply once, on user request.
      report('Ajuste guardado. Pressione Aplicar e ouvir (sem reiniciar áudio durante o gesto).');
    });
    controls.addEventListener('change', event => {
      if (event.target.id!=='hz-audio-profile') return;
      if (!Object.hasOwn(AUDIO_PROFILES,event.target.value)) return;
      mix.audioMode=event.target.value;
      syncAudioProfileUI();saveSteps();
      report(mix.audioMode==='stable'
        ? 'Modo estável: no máximo 4 pistas, efeitos leves e volume protegido.'
        : 'Modo completo: até 8 pistas; teste em volume baixo e pare se houver estalos.');
    });
    const actions = D.createElement('div');
    actions.className = 'hz-actions';
    actions.innerHTML = '<button type="button" id="hz-mobile-apply">Aplicar e ouvir</button>' +
      '<button type="button" id="hz-mobile-export">Exportar projeto</button>';
    board.append(actions);
    const status = D.createElement('p');
    status.id = 'hz-mobile-status';
    status.setAttribute('role', 'status');
    status.textContent = 'Toque nos passos e pressione Aplicar e ouvir.';
    board.append(status);
    D.body.append(board, dock);
    dock.addEventListener('click', (e) => {
      const button = e.target.closest('[data-hz-tab]');
      if (!button) return;
      const tab = button.dataset.hzTab;
      if (tab === 'backup') { downloadBackup(); return; }
      const open = !board.hidden && (tab === 'pads' || tab === 'notes') &&
        D.querySelector('[data-hz-tab="' + tab + '"]')?.getAttribute('aria-pressed') === 'true'
        ? 'code' : tab;
      show(open);
    });
    board.addEventListener('click', e => {
      const step = e.target.closest('[data-hz-lane][data-hz-step]');
      if (step) {
        const lane = step.dataset.hzLane, index = Number(step.dataset.hzStep);
        state[lane][index] = !state[lane][index];
        saveSteps(); repaint();
      }
      const note = e.target.closest('[data-hz-note][data-hz-beat]');
      if (note) {
        const index = Number(note.dataset.hzBeat);
        const pitch = Number(note.dataset.hzNote);
        noteSteps[index] = noteSteps[index] === pitch ? -1 : pitch;
        saveSteps(); repaint();
      }
    });
    D.getElementById('hz-mobile-close').addEventListener('click', () => show('code'));
    D.getElementById('hz-mobile-apply').addEventListener('click', playFromTouch);
    D.getElementById('hz-mobile-export').addEventListener('click', downloadBackup);
    const file = D.createElement('input');
    file.type = 'file'; file.accept = 'application/json,.json';
    file.id = 'hz-mobile-import'; file.hidden = true;
    file.addEventListener('change', () => { restoreBackup(file.files?.[0]); file.value = ''; });
    board.append(file);
    const importButton = D.createElement('button');
    importButton.type = 'button';
    importButton.id = 'hz-mobile-import-btn';
    importButton.textContent = 'Importar backup';
    importButton.addEventListener('click', () => file.click());
    actions.append(importButton);
    refreshPitchGrid();syncAudioProfileUI();
    D.documentElement.classList.add('hz-mobile-active');
    loadCatalog();
  }
  function start() {
    if (isMobile()) createUI();
    W.matchMedia('(max-width: 800px)').addEventListener?.('change', e => {
      if (e.matches) createUI();
      D.documentElement.classList.toggle('hz-mobile-active', e.matches);
      if (!e.matches) D.documentElement.classList.remove('hz-mobile-tools');
    });
    // Treat the browser's own trust decision as authoritative: secure
    // loopback URLs (127.0.0.1/::1) support Service Workers even over HTTP.
    // Do not request offline caching on untrusted origins.
    if ('serviceWorker' in navigator && W.isSecureContext) {
      navigator.serviceWorker.register('./hz-sw.js', { scope: './' })
        .catch(error => console.warn('HAZE_OFFLINE_SERVICE_WORKER_FAILED', error));
    }
  }
  if (D.readyState === 'loading') D.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
