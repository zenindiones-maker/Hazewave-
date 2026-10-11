/* HAZEWAVE SITE 01 v3 — o scroll é o pincel. Motor próprio (MIT), sem bibliotecas.
   Cada efeito é função pura do progresso t (0..1) da cena ⇒ reversível. Só transform/opacity/dashoffset/clip-path. */
(async () => {
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const C = await (await fetch('site.json')).json();
  const clamp = v => Math.min(1, Math.max(0, v)), seg = (t, a, b) => clamp((t - a) / (b - a));
  const ease = t => t * t * (3 - 2 * t);
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs = {}, parent) => { const e = tag.includes(':') ? document.createElementNS(NS, tag.split(':')[1]) : document.createElement(tag); for (const k in attrs) e.setAttribute(k, attrs[k]); parent && parent.appendChild(e); return e; };

  /* Desenhador de traços: só toca nos paths cujo estado mudou desde o último frame. */
  function strokeSet(paths, overlapFrac = .06) {
    const L = paths.map(p => { const l = p.getTotalLength() + 1; p.style.strokeDasharray = l + ' ' + l; p.style.strokeDashoffset = l; p._o = l; return l; });
    const n = paths.length, ov = Math.max(1, n * overlapFrac); let last = -1, pLo = 0, pHi = 0;
    return k => {
      if (RM) k = 1; if (k === last) return; last = k;
      const head = k * (n + ov);
      const lo = Math.max(0, Math.floor(head - ov) - 1), hi = Math.min(n, Math.ceil(head) + 1);
      const a = Math.min(lo, pLo), b = Math.max(hi, pHi); pLo = lo; pHi = hi;
      for (let i = a; i < b; i++) {
        const v = i < lo ? 0 : i >= hi ? 1 : 1 - clamp((head - i) / ov), off = L[i] * v;
        if (paths[i]._o !== off) { paths[i]._o = off; paths[i].style.strokeDashoffset = off; }
      }
    };
  }

  /* ================= JORNADA: abertura → estrada → ilha (uma câmera contínua) ================= */
  const W = C.world, world = document.getElementById('world');
  world.style.width = W.width + 'px'; world.style.height = W.height + 'px';
  [W.tiles[2], ...W.tiles].forEach((src, i) => el('img', { class: 'tile', src, alt: '', width: 1000, height: W.tileHeight, decoding: 'async', loading: i > 1 ? 'lazy' : 'eager', style: `top:${(i - 1) * W.tileHeight}px` }, world));
  // título
  const T = await (await fetch(W.title.src)).json();
  const tsvg = el('svg:svg', { class: 'ink title', viewBox: T.viewBox, role: 'img', 'aria-label': 'HAZEWAVE', style: `left:${W.title.x}px;top:${W.title.y}px;width:${W.title.w}px;height:${W.title.h}px` }, world);
  const tg = el('svg:g', { transform: T.transform }, tsvg); const tp = T.paths.map(d => el('svg:path', { d, 'vector-effect': 'non-scaling-stroke' }, tg));
  const drawTitle = strokeSet(tp, .5);
  // estrada (tinta + aguada pré-renderizada como traço largo translúcido, sem filter:blur)
  const rsvg = el('svg:svg', { class: 'ink road', viewBox: `0 0 ${W.width} ${W.height}`, style: `left:0;top:0;width:${W.width}px;height:${W.height}px`, 'aria-hidden': 'true' }, world);
  const rw = el('svg:path', { d: W.road, class: 'wash' }, rsvg), rp = el('svg:path', { d: W.road }, rsvg);
  const RL = rp.getTotalLength(); [rw, rp].forEach(p => { p.style.strokeDasharray = RL; p.style.strokeDashoffset = RL; });
  const RS = 600, RPTS = Array.from({ length: RS + 1 }, (_, i) => { const q = rp.getPointAtLength(RL * i / RS); return [q.x, q.y]; });
  // barras de forma de onda ao longo da estrada (a "estrada de onda"), desenhadas junto com ela
  const tg2 = el('svg:g', { class: 'ticks' }, rsvg), ticks = [];
  for (let i = 4; i < RS - 2; i += 4) { const [x0, y0] = RPTS[i - 1], [x1, y1] = RPTS[i + 1], dx = x1 - x0, dy = y1 - y0, l = Math.hypot(dx, dy) || 1, nx = -dy / l, ny = dx / l;
    const [x, y] = RPTS[i], amp = 10 + 22 * Math.abs(Math.sin(i * .37) * Math.cos(i * .11));
    ticks.push(el('svg:path', { d: `M${(x - nx * amp).toFixed(1)} ${(y - ny * amp).toFixed(1)} L${(x + nx * amp).toFixed(1)} ${(y + ny * amp).toFixed(1)}`, style: 'stroke-width:3' }, tg2)); }
  const drawTicks = strokeSet(ticks, .02);
  // ilhas livres (sem artista): só esboço apagado, sem cor, sem nome inventado
  const lockedEls = []; (C.lockedSlots || []).forEach(L => { const im = el('img', { class: 'locked', src: L.src, alt: 'Ilha livre, ainda sem artista', width: 640, height: 360, loading: 'lazy', style: `left:${L.x}px;top:${L.y}px;width:${L.w}px` }, world); const tag = el('span', { class: 'locked-tag', style: `left:${L.x}px;top:${L.y + L.w * .56}px;width:${L.w}px` }, world); tag.textContent = 'ILHA LIVRE'; const near = RPTS.reduce((b, q, i) => { const d = Math.hypot(q[0] - (L.x + L.w / 2), q[1] - (L.y + L.w * .28)); return d < b[0] ? [d, i / RS] : b; }, [1e9, 0])[1]; lockedEls.push({ im, tag, at: near }); });
  // ilha
  const I = C.islands.find(i => i.status === 'active'), P = I.art.placement, ih = P.w * I.art.h / I.art.w;
  const ibox = el('div', { class: 'island', style: `left:${P.x}px;top:${P.y}px;width:${P.w}px;height:${ih}px` }, world);
  const flat = el('img', { src: I.art.flat, alt: `Ilha-MPC de ${I.name}, colorida`, width: I.art.w, height: I.art.h, decoding: 'async' }, ibox);
  const INK = await (await fetch(I.art.ink)).json();
  // tinta da ilha em <canvas>: desenho incremental (só o trecho novo do pincel); redesenho completo só ao voltar o scroll
  const cv = el('canvas', { role: 'img', 'aria-label': `Ilha-MPC de ${I.name} sendo desenhada` }, ibox);
  const DPR = Math.min(2, devicePixelRatio || 1), CW = INK.w, CH = INK.h;
  cv.width = CW; cv.height = CH; const cx = cv.getContext('2d'), sc = CW / INK.w;
  cx.lineCap = 'round'; cx.lineJoin = 'round'; cx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--ink').trim() || '#1d1b1a'; cx.lineWidth = 1.7 * sc;
  const polys = INK.paths.map(p => { const pts = p.d.slice(1).split('L').map(q => q.trim().split(' ').map(Number)); const cum = [0]; for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])); return { g: p.g, pts, cum, len: cum[cum.length - 1] || 1, f: 0 }; });
  const byG = [0, 1, 2].map(g => polys.filter(p => p.g === g)), OVG = [.25, .12, .04];
  function seg2(p, a, b) { // desenha o trecho [a,b] (frações) do polilinha p
    const A = a * p.len, B = b * p.len, P = p.pts, C = p.cum; cx.beginPath(); let started = false;
    for (let i = 1; i < P.length; i++) { if (C[i] < A) continue; const s0 = Math.max(A, C[i - 1]), s1 = Math.min(B, C[i]); if (s1 < s0) break;
      const L = C[i] - C[i - 1] || 1, u0 = (s0 - C[i - 1]) / L, u1 = (s1 - C[i - 1]) / L, x0 = P[i - 1][0] + (P[i][0] - P[i - 1][0]) * u0, y0 = P[i - 1][1] + (P[i][1] - P[i - 1][1]) * u0;
      if (!started) { cx.moveTo(x0 * sc, y0 * sc); started = true; } cx.lineTo((P[i - 1][0] + (P[i][0] - P[i - 1][0]) * u1) * sc, (P[i - 1][1] + (P[i][1] - P[i - 1][1]) * u1) * sc); if (C[i] >= B) break; }
    if (started) cx.stroke(); }
  const gState = byG.map(() => ({ head: 0 }));
  function inkDraw(ks) {
    let back = false;
    byG.forEach((arr, g) => { const n = arr.length, ov = Math.max(1, n * OVG[g]), head = (RM ? 1 : ks[g]) * (n + ov); if (head < gState[g].head - 1e-6) back = true; });
    if (back) { cx.clearRect(0, 0, CW, CH); polys.forEach(p => p.f = 0); gState.forEach(s => s.head = 0); }
    byG.forEach((arr, g) => {
      const n = arr.length, ov = Math.max(1, n * OVG[g]), head = (RM ? 1 : ks[g]) * (n + ov), st = gState[g];
      if (head <= st.head) return;
      const a = Math.max(0, Math.floor(st.head - ov) - 1), b = Math.min(n, Math.ceil(head) + 1);
      for (let i = a; i < b; i++) { const p = arr[i], f = clamp((head - i) / ov); if (f > p.f + 1e-4) { seg2(p, Math.max(0, p.f - .002), f); p.f = f; } }
      st.head = head;
    });
  }
  cv.dataset.undrawn = '0';
  // cartão da ilha
  const card = document.getElementById('card');
  card.innerHTML = `<h2>${I.name}</h2><div class="btns">` + I.actions.map((a, i) => a.url ? `<a class="btn${i ? '' : ' main'}" href="${a.url}">${a.label}</a>` : `<button class="btn${i ? '' : ' main'}" aria-disabled="true" title="em breve">${a.label}</button>`).join('') + `</div><p class="prov">PROVISÓRIO — clipe, faixa e arquivo para download a fornecer.</p>`;
  // câmera
  const roadPt = k => { const f = k * RS, i = Math.floor(f), j = Math.min(RS, i + 1), u = f - i; return { x: RPTS[i][0] + (RPTS[j][0] - RPTS[i][0]) * u, y: RPTS[i][1] + (RPTS[j][1] - RPTS[i][1]) * u }; };
  function camera(t) {
    const vw = innerWidth, vh = innerHeight;
    const sRoad = Math.min(vw / W.width, vh / 760);                 // enquadramento da estrada
    const land = vw > vh; const sIsl = land ? Math.min(vw * .56 / P.w, vh * .9 / ih) : Math.min(vw / (P.w * .98), (vh * .62) / ih);
    let focusX, focusY, s, anchorY = .45;
    const tTitle = seg(t, 0, .14), tRoad = seg(t, .12, .5), tZoom = ease(seg(t, .46, .58));
    if (t < .12) { const k = W.title.y + W.title.h / 2; focusX = 500; focusY = k; s = Math.min(vw / (W.title.w * 1.05), vh / 500); }
    else { const p = roadPt(tRoad); const kx = seg(t, .16, .24); focusX = 500 + (p.x - 500) * .35 * kx; focusY = p.y; s = sRoad; }
    if (t >= .12 && t < .2) { const k = seg(t, .12, .2), s0 = Math.min(vw / (W.title.w * 1.05), vh / 500); s = s0 + (sRoad - s0) * ease(k); }
    // aproximação contínua estrada → ilha
    const iCX = P.x + P.w / 2, iCY = P.y + ih / 2;
    const tgtX = land ? iCX + (vw * .2) / sIsl : iCX; focusX += (tgtX - focusX) * tZoom; focusY += (iCY - focusY) * tZoom; s += (sIsl - s) * tZoom; anchorY += ((land ? .5 : .36) - anchorY) * tZoom;
    let x = vw / 2 - focusX * s; const y = vh * anchorY - focusY * s;
    world.style.transform = `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0) scale(${s.toFixed(4)})`;
  }
  function journey(t) {
    drawTitle(seg(t, .01, .1));
    tp.forEach(p => p.style.fillOpacity = RM ? 1 : seg(t, .08, .13));
    const kr = RM ? 1 : seg(t, .12, .5); document.getElementById('hint').style.opacity = 1 - seg(t, 0, .04); rp.style.strokeDashoffset = rw.style.strokeDashoffset = RL * (1 - kr); drawTicks(kr); lockedEls.forEach(o => { const v = RM ? 1 : seg(kr, o.at - .08, o.at); o.im.style.opacity = .32 * v; o.tag.style.opacity = .6 * v; });
    inkDraw([seg(t, .5, .6), seg(t, .56, .7), seg(t, .62, .8)]);
    const f = RM ? 1 : seg(t, .78, .88);             // tinta lavando de cima para baixo
    flat.style.opacity = f ? 1 : 0; flat.style.clipPath = `inset(0 0 ${(100 * (1 - f)).toFixed(1)}% 0)`;
    const c = RM ? 1 : ease(seg(t, .88, .96)); card.style.opacity = c; card.style.transform = `translateY(${24 * (1 - c)}px)`; card.classList.toggle('on', c > .5);
    camera(RM ? Math.max(t, 0) : t);
  }

  /* ================= SEÇÕES 3–6: cada ícone nasce em tinta e depois ganha cor ================= */
  const ICONS = {
    phone: { fill: [['M62 22 h76 a12 12 0 0 1 12 12 v132 a12 12 0 0 1 -12 12 h-76 a12 12 0 0 1 -12 -12 v-132 a12 12 0 0 1 12 -12z', 'light'], ['M62 44 h76 v108 h-76z', 'slate'], ['M78 92 h44 v18 h-44z', 'accent']],
             ink: ['M62 22 h76 a12 12 0 0 1 12 12 v132 a12 12 0 0 1 -12 12 h-76 a12 12 0 0 1 -12 -12 v-132 a12 12 0 0 1 12 -12z', 'M62 44 h76 v108 h-76z', 'M90 33 h20', 'M100 166 m-6 0 a6 6 0 1 0 12 0 a6 6 0 1 0 -12 0', 'M70 60 h60 M70 72 h60', 'M78 92 h44 v18 h-44z', 'M74 128 l10 -10 l10 10 l10 -14 l10 14 l10 -8'] },
    rack: { fill: [['M20 58 h160 v84 h-160z', 'light'], ['M46 100 m-20 0 a20 20 0 1 0 40 0 a20 20 0 1 0 -40 0', 'mid'], ['M100 100 m-20 0 a20 20 0 1 0 40 0 a20 20 0 1 0 -40 0', 'mid'], ['M150 76 h18 v48 h-18z', 'accent']],
             ink: ['M20 58 h160 v84 h-160z', 'M46 100 m-20 0 a20 20 0 1 0 40 0 a20 20 0 1 0 -40 0', 'M46 100 l10 -14', 'M100 100 m-20 0 a20 20 0 1 0 40 0 a20 20 0 1 0 -40 0', 'M100 100 l-12 -12', 'M150 76 h18 v48 h-18z', 'M150 92 h18 M150 108 h18', 'M30 150 h140', 'M30 66 h6 M164 66 h6'] },
    shirt: { fill: [['M70 30 l-44 22 l14 34 l18 -8 v92 h84 v-92 l18 8 l14 -34 l-44 -22 q-30 22 -60 0z', 'light'], ['M84 96 h32 v32 h-32z', 'accent']],
             ink: ['M70 30 l-44 22 l14 34 l18 -8 v92 h84 v-92 l18 8 l14 -34 l-44 -22', 'M70 30 q30 22 60 0', 'M84 96 h32 v32 h-32z', 'M92 112 l8 -8 l8 8 l8 -8'] },
    heart: { fill: [['M100 168 C40 128 22 98 30 70 C38 42 76 36 100 64 C124 36 162 42 170 70 C178 98 160 128 100 168z', 'accent']],
             ink: ['M100 168 C40 128 22 98 30 70 C38 42 76 36 100 64 C124 36 162 42 170 70 C178 98 160 128 100 168z', 'M56 76 q6 -16 22 -16', 'M100 168 v10 M88 186 h24'] }
  };
  const secRoot = document.getElementById('sections'), secs = [];
  C.sections.forEach(S => {
    const sec = el('section', { id: S.id, class: 'scene sec', 'data-len': '1.7', 'aria-labelledby': S.id + '-h' }, secRoot);
    const pin = el('div', { class: 'pin' }, sec), box = el('div', { class: 'box' }, pin);
    const svg = el('svg:svg', { viewBox: '0 0 200 200', class: 'ink', 'aria-hidden': 'true' }, box);
    const fills = ICONS[S.icon].fill.map(([d, c]) => el('svg:path', { d, class: 'fill', style: `fill:var(--${c});stroke:none` }, svg));
    const inks = ICONS[S.icon].ink.map(d => el('svg:path', { d, style: 'stroke-width:5' }, svg));
    const h = el('h2', { id: S.id + '-h' }, box); h.textContent = S.title;
    const p = el('p', {}, box); p.textContent = S.text;
    const b = S.cta.url ? el('a', { class: 'btn main', href: S.cta.url }, box) : el('button', { class: 'btn main', 'aria-disabled': 'true', title: 'em breve' }, box);
    b.textContent = S.cta.url ? S.cta.label : S.cta.label + ' — em breve';
    if (S.provisional) { const q = el('p', { class: 'prov' }, box); q.textContent = S.provisional; }
    secs.push({ sec, draw: strokeSet(inks, .5), fills });
  });

  /* ================= laço ================= */
  const scenes = [...document.querySelectorAll('.scene')];
  scenes.forEach(s => s.style.height = (+s.dataset.len * 100) + 'vh');
  const prog = s => { const r = s.getBoundingClientRect(); return clamp(-r.top / Math.max(1, r.height - innerHeight)); };
  const secProg = s => { const r = s.getBoundingClientRect(); return clamp((innerHeight - r.top) / (r.height)); }; // começa ao entrar
  const journeyEl = document.getElementById('journey');
  let q = 0;
  const frame = () => {
    q = 0; const t = prog(journeyEl); journeyEl.dataset.p = t.toFixed(3); journey(t);
    secs.forEach(o => { const k = secProg(o.sec); o.sec.dataset.p = k.toFixed(3); o.draw(seg(k, .1, .5)); const f = RM ? 1 : seg(k, .45, .6); o.fills.forEach(x => x.style.opacity = f); });
  };
  addEventListener('scroll', () => { if (!q) q = requestAnimationFrame(frame); }, { passive: true });
  addEventListener('resize', frame); frame(); document.documentElement.dataset.ready = '1';
})();
