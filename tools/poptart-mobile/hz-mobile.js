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
    try { W.localStorage.setItem(KEY, JSON.stringify(state)); }
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
      ...KIT.map(lane => {
        const notes = state[lane.id].map(v => v ? 'pt_kit:' + lane.sample : '~');
        return 'hz_' + lane.id + ': s("' + notes.join(' ') + '")';
      }),
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
      report('Padrão enviado ao motor do Poptart. Confirme o som no aparelho.');
    } catch (error) { report(error.message); }
  }
  function downloadBackup() {
    const source = getEditor().get();
    if (source == null) return report('Editor ainda não disponível');
    const data = JSON.stringify({
      schema: 'HazewavePoptartMobileBackup/v1',
      exported_at: new Date().toISOString(),
      source, steps: state, attribution: 'Poptart by Glossing, AGPL-3.0-only',
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
  }
  function show(panel) {
    const board = D.getElementById('hz-mobile-board');
    D.documentElement.classList.toggle('hz-mobile-tools', panel === 'tools');
    board.hidden = panel !== 'pads';
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
      const open = !board.hidden && tab === 'pads' ? 'code' : tab;
      show(open);
    });
    board.addEventListener('click', e => {
      const step = e.target.closest('[data-hz-lane][data-hz-step]');
      if (step) {
        const lane = step.dataset.hzLane, index = Number(step.dataset.hzStep);
        state[lane][index] = !state[lane][index];
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
    if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost'))
      navigator.serviceWorker.register('./hz-sw.js', { scope: './' }).catch(() => {});
  }
  if (D.readyState === 'loading') D.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
