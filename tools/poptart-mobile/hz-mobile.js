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
  ]);
  const KEY = 'hazewave.poptart.mobile.steps.v1';
  const NOTE_KEY = 'hazewave.poptart.mobile.notes.v1';
  const MIX_KEY = 'hazewave.poptart.mobile.controls.v1';
  const limits = (n, low, high, fallback) => Number.isFinite(n) ? Math.max(low, Math.min(high, n)) : fallback;
  let storedNotes = null, storedMix = null;
  try { storedNotes = JSON.parse(W.localStorage.getItem(NOTE_KEY)); } catch {}
  try { storedMix = JSON.parse(W.localStorage.getItem(MIX_KEY)); } catch {}
  const noteSteps = Array.from({ length: 16 }, (_, i) => {
    const n = storedNotes?.[i];
    const defaults = [0, -1, 2, -1, 3, -1, 4, -1, 5, -1, 4, -1, 2, -1, 1, -1];
    return Number.isInteger(n) && n >= -1 && n <= 7 ? n : defaults[i];
  });
  const mix = {
    bpm: Math.round(limits(Number(storedMix?.bpm), 60, 200, 120)) || 120,
    cutoff: limits(Number(storedMix?.cutoff), 0.05, 0.95, 0.45),
    gain: limits(Number(storedMix?.gain), 0.05, 0.9, 0.35),
  };
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
      W.localStorage.setItem(NOTE_KEY, JSON.stringify(noteSteps));
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
    return [MARK_A,
      '// Padrões produzidos no sequenciador touch do Hazewave.',
      'setbpm(' + mix.bpm + ')',
      ...KIT.map(lane => {
        const notes = state[lane.id].map(v => v ? 'pt_kit:' + lane.sample : '~');
        return 'hz_' + lane.id + ': s("' + notes.join(' ') + '").postgain(0.45)';
      }),
      'hz_melody: n("' + noteSteps.map(n => n < 0 ? '~' : n).join(' ') +
        '").scale("F minor").synth("Wavetable").fx("Filter").param("Cutoff", ' +
        mix.cutoff.toFixed(2) + ').postgain(' + mix.gain.toFixed(2) + ')',
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
      schema: 'HazewavePoptartMobileBackup/v1',
      exported_at: new Date().toISOString(),
      source, steps: state, notes: noteSteps, mix: mix,
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
      if (data.schema !== 'HazewavePoptartMobileBackup/v1' ||
          typeof data.source !== 'string') throw new Error('Backup inválido');
      if (!W.confirm('Substituir o código atual pelo backup? Exporte seu trabalho antes.')) return;
      getEditor().set(data.source);
      for (const lane of KIT) {
        if (Array.isArray(data.steps?.[lane.id]) && data.steps[lane.id].length === 16)
          state[lane.id] = data.steps[lane.id].map(x => x === true);
      }
      if (Array.isArray(data.notes) && data.notes.length === 16) {
        for (let i = 0; i < 16; i++)
          noteSteps[i] = Number.isInteger(data.notes[i]) && data.notes[i] >= -1 &&
            data.notes[i] <= 7 ? data.notes[i] : -1;
      }
      for (const key of ['bpm', 'cutoff', 'gain'])
        if (Number.isFinite(data.mix?.[key])) mix[key] = data.mix[key];
      mix.bpm = Math.round(limits(mix.bpm, 60, 200, 120));
      mix.cutoff = limits(mix.cutoff, 0.05, 0.95, 0.45);
      mix.gain = limits(mix.gain, 0.05, 0.9, 0.35);
      const bpm = D.getElementById('hz-bpm');
      const cutoff = D.getElementById('hz-cutoff');
      const gain = D.getElementById('hz-gain');
      if (bpm) bpm.value = mix.bpm;
      if (cutoff) cutoff.value = mix.cutoff;
      if (gain) gain.value = mix.gain;
      saveSteps(); repaint();
      report('Backup restaurado. Pressione Play para ouvir.');
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
      ? 'HAZE / piano roll · F menor'
      : 'HAZE / bateria · 16 passos';
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
    for (let pitch = 7; pitch >= 0; pitch--) {
      const label = D.createElement('div');
      label.className = 'hz-lane-name';
      label.textContent = 'Grau ' + (pitch + 1);
      keys.append(label);
      for (let beat = 0; beat < 16; beat++) {
        const b = D.createElement('button');
        b.type = 'button';
        b.dataset.hzNote = String(pitch);
        b.dataset.hzBeat = String(beat);
        b.textContent = String(beat + 1);
        b.setAttribute('aria-label', 'Grau ' + (pitch + 1) + ', passo ' + (beat + 1));
        if (beat % 4 === 0) b.classList.add('bar-start');
        keys.append(b);
      }
    }
    piano.append(keys); board.append(piano);
    const controls = D.createElement('div');
    controls.className = 'hz-music-controls';
    controls.innerHTML = '<label>BPM <input id="hz-bpm" type="number" min="60" max="200" step="1" value="' + mix.bpm + '"></label>' +
      '<label>Filtro <input id="hz-cutoff" type="range" min="0.05" max="0.95" step="0.05" value="' + mix.cutoff + '"></label>' +
      '<label>Volume <input id="hz-gain" type="range" min="0.05" max="0.9" step="0.05" value="' + mix.gain + '"></label>';
    board.append(controls);
    let pendingUpdate = null;
    controls.addEventListener('input', event => {
      const id = event.target.id;
      const value = Number(event.target.value);
      if (id === 'hz-bpm') mix.bpm = Math.round(limits(value, 60, 200, 120));
      if (id === 'hz-cutoff') mix.cutoff = limits(value, 0.05, 0.95, 0.45);
      if (id === 'hz-gain') mix.gain = limits(value, 0.05, 0.9, 0.35);
      saveSteps();
      if (pendingUpdate) W.clearTimeout(pendingUpdate);
      pendingUpdate = W.setTimeout(() => {
        try {
          const e = getEditor();
          if (!e.get()?.includes(MARK_A)) return;
          e.set(mergeManagedBlock(e.get(), generatePattern()));
          D.getElementById('updateBtn')?.click();
          report('Parâmetro atualizado. Confirme a resposta sonora.');
        } catch (error) { report(error.message); }
      }, 130);
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
    repaint();
    D.documentElement.classList.add('hz-mobile-active');
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
