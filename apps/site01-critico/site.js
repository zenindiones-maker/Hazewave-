/* HAZEWAVE SITE 01 v4 — o scroll é o pincel. Motor próprio (MIT), sem bibliotecas.
   Traços em binário HZS1 (delta int8), decodificados sob demanda; tinta em <canvas> incremental. */
(async () => {
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const C = await (await fetch('site.json')).json();
  const ease3 = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const clamp = v => Math.min(1, Math.max(0, v)), seg = (t, a, b) => clamp((t - a) / (b - a)), ease = t => t * t * (3 - 2 * t);
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs = {}, parent) => { const e = tag.startsWith('svg:') ? document.createElementNS(NS, tag.slice(4)) : document.createElement(tag); for (const k in attrs) e.setAttribute(k, attrs[k]); parent && parent.appendChild(e); return e; };
  const INKC = getComputedStyle(document.documentElement).getPropertyValue('--ink').trim() || '#1d1b1a';
  const idle = f => (window.requestIdleCallback || (g => setTimeout(g, 1)))(f);

  /* ---------- HZS1: decodificação preguiçosa ---------- */
  const bufs = new Map(); const fetchBuf = src => bufs.get(src) || (bufs.set(src, fetch(src).then(r => r.arrayBuffer())), bufs.get(src));
  function decode(ab) {
    const dv = new DataView(ab), W = dv.getUint16(4, true), H = dv.getUint16(6, true), N = dv.getUint32(8, true); let o = 12; const S = [];
    for (let s = 0; s < N; s++) {
      const g = dv.getUint8(o), n = dv.getUint16(o + 2, true); let x = dv.getInt16(o + 4, true), y = dv.getInt16(o + 6, true); o += 8;
      const P = new Float32Array(n * 2), cum = new Float32Array(n); P[0] = x; P[1] = y;
      for (let i = 1; i < n; i++) { x += dv.getInt8(o); y += dv.getInt8(o + 1); o += 2; P[i * 2] = x; P[i * 2 + 1] = y; cum[i] = cum[i - 1] + Math.hypot(P[i * 2] - P[i * 2 - 2], P[i * 2 + 1] - P[i * 2 - 1]); }
      let hs = (s * 2654435761) >>> 0; const rnd = () => (hs = (hs * 1664525 + 1013904223) >>> 0) / 4294967296;
      for (let i = 1; i < n - 1; i++) { P[i * 2] += (rnd() - .5) * 1.1; P[i * 2 + 1] += (rnd() - .5) * 1.1; } /* tremor de mão, determinístico */
      S.push({ g, P, cum, len: cum[n - 1] || 1, f: 0, w: [1.45, 1, .7][g] * (.8 + .4 * rnd()) });
    }
    return { W, H, S };
  }

  /* ---------- camada de tinta em canvas, incremental e reversível ---------- */
  function InkLayer(parent, src, { w, h, lw = 1.7, groups = [.25, .12, .04], label = '' }) {
    const cv = el('canvas', { role: 'img', 'aria-label': label, class: 'inkcv' }, parent); cv.width = w; cv.height = h;
    const cx = cv.getContext('2d'); cx.lineCap = 'round'; cx.lineJoin = 'round'; cx.strokeStyle = INKC;
    let data = null, byG = null, st = null, pending = null, decoding = false, LW = lw;
    const ready = () => !!data;
    function load() { if (decoding) return; decoding = true; fetchBuf(src).then(ab => idle(() => { data = decode(ab); cv.width = data.W; cv.height = data.H; cx.lineCap = 'round'; cx.lineJoin = 'round'; cx.strokeStyle = INKC; cx.lineWidth = lw; LW = lw; byG = [0, 1, 2].map(g => data.S.filter(s => s.g === g)); st = byG.map(() => 0); if (pending) draw(pending); })); }
    function piece(s, a, b) { const T = .14;
      if (a < T) { seg1(s, a, Math.min(b, T), .45); if (b <= T) return; a = T; }
      if (b > 1 - T) { if (a < 1 - T) seg1(s, a, 1 - T, 1); seg1(s, Math.max(a, 1 - T), b, .45); return; }
      seg1(s, a, b, 1); }
    function seg1(s, a, b, wm) { const A = a * s.len, B = b * s.len, P = s.P, Cm = s.cum; cx.beginPath(); let on = false;
      for (let i = 1; i < Cm.length; i++) { if (Cm[i] < A) continue; const s0 = Math.max(A, Cm[i - 1]), s1 = Math.min(B, Cm[i]); if (s1 < s0) break; const L = Cm[i] - Cm[i - 1] || 1, u0 = (s0 - Cm[i - 1]) / L, u1 = (s1 - Cm[i - 1]) / L, x0 = P[i * 2 - 2], y0 = P[i * 2 - 1], dx = P[i * 2] - x0, dy = P[i * 2 + 1] - y0;
        if (!on) { cx.moveTo(x0 + dx * u0, y0 + dy * u0); on = true; } cx.lineTo(x0 + dx * u1, y0 + dy * u1); if (Cm[i] >= B) break; }
      if (on) { cx.lineWidth = LW * s.w * wm; cx.stroke(); } }
    function draw(ks) {
      if (!data) { pending = ks; load(); return; }
      ks = ks.map(k => RM ? 1 : k);
      let back = false; byG.forEach((arr, g) => { const ov = Math.max(1, arr.length * groups[g]); if (ks[g] * (arr.length + ov) < st[g] - 1e-6) back = true; });
      if (back) { cx.clearRect(0, 0, data.W, data.H); data.S.forEach(s => s.f = 0); st = st.map(() => 0); }
      byG.forEach((arr, g) => { const n = arr.length, ov = Math.max(1, n * groups[g]), head = ks[g] * (n + ov); if (head <= st[g]) return;
        const a = Math.max(0, Math.floor(st[g] - ov) - 1), b = Math.min(n, Math.ceil(head) + 1);
        for (let i = a; i < b; i++) { const s = arr[i], f = clamp((head - i) / ov); if (f > s.f + 1e-4) { piece(s, Math.max(0, s.f - .002), f); s.f = f; } }
        st[g] = head; });
    }
    return { cv, draw, load, ready };
  }

  /* revelação da cor por "pincelada": duas camadas em contra-translação (só compositor, sem repaint) + borda de tinta */
  function Wipe(img) { const w = el('div', { class: 'wipe' }); img.parentNode.insertBefore(w, img); w.appendChild(img); el('i', { class: 'edge' }, w); w._f = -1;
    return f => { f = RM ? 1 : f; if (f === w._f) return; w._f = f; const d = ((1 - f) * 100).toFixed(2); w.style.transform = `translate3d(0,-${d}%,0)`; img.style.transform = `translate3d(0,${d}%,0)`; w.classList.toggle('mid', f > 0 && f < 1); w.style.visibility = f ? 'visible' : 'hidden'; }; }
  /* toque: anel de tinta + retraçado rápido */
  function ripple(host, ev) { const r = host.getBoundingClientRect(), d = el('i', { class: 'ripple' }, host); d.style.left = (ev.clientX - r.left) + 'px'; d.style.top = (ev.clientY - r.top) + 'px'; setTimeout(() => d.remove(), 700); }
  function retrace(ink, ks) { if (RM || !ink.ready()) return; const t0 = performance.now(); const go = t => { const u = Math.min(1, (t - t0) / 650); ink.draw(ks.map(k => k * ease(u))); if (u < 1) requestAnimationFrame(go); }; ink.draw([0, 0, 0]); requestAnimationFrame(go); }

  /* cabo desenhado à mão (determinístico) para planos de primeiro plano */
  function cable(x0, y0, y1, amp, seed) { let d = `M${x0} ${y0}`, y = y0, i = 0, h = seed; const r = () => (h = (h * 9301 + 49297) % 233280) / 233280;
    while (y < y1) { const ny = Math.min(y1, y + 60 + r() * 50); d += ` Q ${(x0 + (i++ % 2 ? amp : -amp) * (.6 + r() * .6)).toFixed(1)} ${((y + ny) / 2).toFixed(1)} ${(x0 + (r() - .5) * amp * .3).toFixed(1)} ${ny.toFixed(1)}`; y = ny; } return d; }
  function inkPath(svg, d, cls) { const p = el('svg:path', { d, class: cls || '' }, svg); const L = p.getTotalLength(); p.style.strokeDasharray = L; p.style.strokeDashoffset = L; p._L = L; p._k = -1;
    return k => { k = RM ? 1 : Math.round(k * 160) / 160; if (k === p._k) return; p._k = k; p.style.strokeDashoffset = (p._L * (1 - k)).toFixed(1); }; }

  /* ================= JORNADA ================= */
  const W = C.world, pin = document.querySelector('#journey .pin'), world = document.getElementById('world');
  // céu: camada de profundidade atrás do mundo (parallax), galáxia e luas desenhadas pelo scroll
  const K = C.sky, sky = el('div', { class: 'sky', 'aria-hidden': 'true' }); pin.insertBefore(sky, world);
  el('img', { src: K.far, alt: '', width: K.w, height: K.h, decoding: 'async' }, sky);
  const skyTop = InkLayer(el('div', { class: 'skytop', style: `height:${(K.topH / K.h * 100).toFixed(2)}%` }, sky), K.top, { w: K.w, h: K.topH, lw: 1.4, groups: [.3, .2, .08] });
  world.style.width = W.width + 'px'; world.style.height = W.height + 'px';
  [W.tiles[2], ...W.tiles].forEach((src, i) => el('img', { class: 'tile', src, alt: '', width: 1000, height: W.tileHeight, decoding: 'async', loading: i > 1 ? 'lazy' : 'eager', style: `top:${(i - 1) * W.tileHeight}px` }, world));
  const T = await (await fetch(W.title.src)).json();
  const tsvg = el('svg:svg', { class: 'ink title', viewBox: T.viewBox, role: 'img', 'aria-label': 'HAZEWAVE', style: `left:${W.title.x}px;top:${W.title.y}px;width:${W.title.w}px;height:${W.title.h}px` }, world);
  const tg = el('svg:g', { transform: T.transform }, tsvg); const tp = T.paths.map(d => el('svg:path', { d, 'vector-effect': 'non-scaling-stroke' }, tg));
  const TL = tp.map(p => { const l = p.getTotalLength() + 1; p.style.strokeDasharray = l; p.style.strokeDashoffset = l; return l; });
  const drawTitle = k => tp.forEach((p, i) => { const n = tp.length, ov = 4, v = clamp((k * (n + ov) - i) / ov); p.style.strokeDashoffset = TL[i] * (1 - (RM ? 1 : v)); });
  const rsvg = el('svg:svg', { class: 'ink road', viewBox: `0 0 ${W.width} ${W.height}`, style: `left:0;top:0;width:${W.width}px;height:${W.height}px`, 'aria-hidden': 'true' }, world);
  const rw = el('svg:path', { d: W.road, class: 'wash' }, rsvg), rp = el('svg:path', { d: W.road }, rsvg);
  const RL = W.roadLen; /* pré-calculado no build: evita getPointAtLength no carregamento */ [rw, rp].forEach(p => { p.style.strokeDasharray = RL; p.style.strokeDashoffset = RL; });
  const RPTS = W.roadPts, RS = RPTS.length - 1;
  const tickG = el('svg:g', { class: 'ticks' }, rsvg), ticks = [];
  for (let i = 1; i < RS - 1; i++) { const [x0, y0] = RPTS[i - 1], [x1, y1] = RPTS[i + 1], dx = x1 - x0, dy = y1 - y0, l = Math.hypot(dx, dy) || 1, nx = -dy / l, ny = dx / l, [x, y] = RPTS[i], amp = 8 + 16 * Math.abs(Math.sin(i * 1.48) * Math.cos(i * .44));
    const p = el('svg:path', { d: `M${(x - nx * amp).toFixed(1)} ${(y - ny * amp).toFixed(1)} L${(x + nx * amp).toFixed(1)} ${(y + ny * amp).toFixed(1)}`, style: 'stroke-width:3' }, tickG); p._at = i / RS; p.style.opacity = 0; ticks.push(p); }
  const lockedEls = []; (C.lockedSlots || []).forEach(L => { const im = el('img', { class: 'locked', src: L.src, alt: 'Ilha livre, ainda sem artista', width: 640, height: 360, loading: 'lazy', style: `left:${L.x}px;top:${L.y}px;width:${L.w}px;opacity:0` }, world); const tag = el('span', { class: 'locked-tag', style: `left:${L.x}px;top:${L.y + L.w * .56}px;width:${L.w}px;opacity:0` }, world); tag.textContent = 'ILHA LIVRE';
    const at = RPTS.reduce((b, q, i) => { const d = Math.hypot(q[0] - (L.x + L.w / 2), q[1] - (L.y + L.w * .28)); return d < b[0] ? [d, i / RS] : b; }, [1e9, 0])[1]; lockedEls.push({ im, tag, at }); });
  const I = C.islands.find(i => i.status === 'active'), P = I.art.placement, ih = P.w * I.art.h / I.art.w;
  const ibox = el('div', { class: 'island', style: `left:${P.x}px;top:${P.y}px;width:${P.w}px;height:${ih}px` }, world);
  const flat = el('img', { src: I.art.flat, alt: `Ilha-MPC de ${I.name}, colorida`, width: I.art.w, height: I.art.h, decoding: 'async' }, ibox); const flatWipe = Wipe(flat);
  let islandKs = [1, 1, 1]; ibox.addEventListener('click', ev => { ripple(ibox, ev); ibox.classList.remove('wig'); void ibox.offsetWidth; ibox.classList.add('wig'); });
  const islandInk = InkLayer(ibox, I.art.ink, { w: I.art.w, h: I.art.h, label: `Ilha-MPC de ${I.name} sendo desenhada` });
  const fgJ = el('div', { class: 'fg', 'aria-hidden': 'true' }, pin), fgS = el('svg:svg', { viewBox: '0 0 100 1000', preserveAspectRatio: 'none' }, fgJ);
  const fgL = inkPath(fgS, cable(3, -20, 1020, 4, 7), 'c1'), fgR = inkPath(fgS, cable(97, -20, 1020, 4, 11), 'c2');
  const card = document.getElementById('card'); const capEl = el('p', { class: 'cap', id: 'cap' }, pin);
  card.innerHTML = `<h2>${I.name}</h2><div class="btns">` + I.actions.map((a, i) => a.url ? `<a class="btn${i ? '' : ' main'}" href="${a.url}">${a.label}</a>` : `<button class="btn${i ? '' : ' main'}" aria-disabled="true" title="em breve">${a.label}</button>`).join('') + `</div><p class="prov">PROVISÓRIO — clipe, faixa e arquivo para download a fornecer.</p>`;
  const roadPt = k => { const f = k * RS, i = Math.floor(f), j = Math.min(RS, i + 1), u = f - i; return { x: RPTS[i][0] + (RPTS[j][0] - RPTS[i][0]) * u, y: RPTS[i][1] + (RPTS[j][1] - RPTS[i][1]) * u }; };
  let lastTick = -1;
  function camera(t) {
    const vw = VW, vh = VH, land = vw > vh;
    const sRoad = Math.min(vw / W.width, vh / 760), s0 = Math.min(vw / (W.title.w * 1.1), vh / 500);
    const sIsl = land ? Math.min(vw * .56 / P.w, vh * .9 / ih) : Math.min(vw / (P.w * .98), (vh * .62) / ih);
    let fx, fy, s, ay = .45; const tRoad = seg(t, .12, .5), tZoom = ease3(seg(t, .45, .58)), tour = RM ? 0 : Math.sin(Math.PI * seg(t, .6, .84));
    if (t < .12) { fx = 500; fy = W.title.y + W.title.h / 2; s = s0; }
    else { const p = roadPt(tRoad), kx = seg(t, .16, .24); fx = 500 + (p.x - 500) * .35 * kx; fy = p.y; s = s0 + (sRoad - s0) * ease(seg(t, .12, .2)); }
    const iCX = P.x + P.w / 2, iCY = P.y + ih / 2, tgX = land ? iCX + (vw * .2) / sIsl : iCX;
    fx += (tgX - fx) * tZoom; fy += (iCY - fy) * tZoom; s += (sIsl - s) * tZoom; ay += ((land ? .5 : .36) - ay) * tZoom;
    /* passeio de câmera (NASA Prospect): aproxima dos pads enquanto a tinta corre e recua para a cor */
    const tx = P.x + P.w * (.42 + .16 * seg(t, .6, .84)), ty = P.y + ih * .4;
    fx += (tx - fx) * .55 * tour; fy += (ty - fy) * .55 * tour; s *= 1 + .38 * tour;
    const x = vw / 2 - fx * s, y = vh * ay - fy * s;
    world.style.transform = `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0) scale(${s.toFixed(4)})`;
    // parallax do céu: anda uma fração do deslocamento vertical e some quando a câmera mergulha
    const skyY = (y - vh * .45 + (W.title.y + W.title.h / 2) * s) * K.parallax;
    const sy = Math.round(skyY), so = tZoom > .98 ? 0 : +(1 - .75 * tZoom).toFixed(2);
    if (sy !== sky._y) { sky._y = sy; sky.style.transform = `translate3d(-50%,${sy}px,0)`; }
    if (so !== sky._o) { sky._o = so; sky.style.opacity = so; sky.style.visibility = so ? 'visible' : 'hidden'; }
  }
  function journey(t) {
    document.getElementById('hint').style.opacity = 1 - seg(t, 0, .04);
    skyTop.draw([seg(t, 0, .1), seg(t, .02, .14), seg(t, .04, .18)]);
    drawTitle(seg(t, .01, .1)); const fo = RM ? 1 : seg(t, .08, .13); tp.forEach(p => p.style.fillOpacity = fo);
    const kr = RM ? 1 : seg(t, .12, .5); rp.style.strokeDashoffset = rw.style.strokeDashoffset = RL * (1 - kr);
    if (kr !== lastTick) { lastTick = kr; ticks.forEach(p => { const v = p._at <= kr ? 1 : 0; if (p._v !== v) { p._v = v; p.style.opacity = v; } }); }
    lockedEls.forEach(o => { const v = RM ? 1 : seg(kr, o.at - .08, o.at); o.im.style.opacity = .32 * v; o.tag.style.opacity = .6 * v; });
    if (t > .25) islandInk.load();
    islandInk.draw([seg(t, .5, .6), seg(t, .56, .7), seg(t, .62, .8)]);
    const f = RM ? 1 : seg(t, .78, .88); flatWipe(f);
    const c = RM ? 1 : ease(seg(t, .88, .96)); card.style.opacity = c; card.style.transform = `translateY(${24 * (1 - c)}px)`; card.classList.toggle('on', c > .5);
    const ci = C.captions.reduce((b, c, i) => t >= c[0] ? i : b, 0);
    if (ci !== capEl._i) { capEl._i = ci; capEl.textContent = C.captions[ci][1]; }
    const co = (t < .04 || t > .87) ? '0' : '1'; if (capEl._o !== co) { capEl._o = co; capEl.style.opacity = co; }
    fgL(seg(t, .1, .55)); fgR(seg(t, .2, .7));
    const fy = Math.round(-t * VH * 1.1); if (fy !== fgJ._y) { fgJ._y = fy; fgJ.style.transform = `translate3d(0,${fy}px,0)`; }
    camera(t);
  }

  /* ================= SEÇÕES 3–6 + FINAL (cidade) ================= */
  const secRoot = document.getElementById('sections'), secs = [];
  function makeSection(S, { len = 1.7, big = false } = {}) {
    const sec = el('section', { id: S.id, class: 'scene sec' + (big ? ' big' : ''), 'data-len': String(len), 'aria-labelledby': S.id + '-h' }, secRoot);
    const pinS = el('div', { class: 'pin' }, sec), box = el('div', { class: 'box' }, pinS);
    const back = el('div', { class: 'back', 'aria-hidden': 'true' }, pinS); el('img', { src: C.sky.far, alt: '', loading: 'lazy', decoding: 'async' }, back);
    const fg = el('div', { class: 'fg sfg', 'aria-hidden': 'true' }, pinS), fs = el('svg:svg', { viewBox: '0 0 100 1000', preserveAspectRatio: 'none' }, fg);
    const fgd = inkPath(fs, cable(3.5, -20, 1020, 2, 3 + secs.length * 5), 'c1');
    const art = el('div', { class: 'art', tabindex: '-1' }, box);
    art.addEventListener('click', ev => { ripple(art, ev); art.classList.remove('wig'); void art.offsetWidth; art.classList.add('wig'); const o = secs.find(o => o.art === art); o && retrace(o.ink, o.ks || [1, 1, 1]); });
    const fl = el('img', { src: S.flat || S.icon.flat, alt: '', decoding: 'async', loading: 'lazy' }, art);
    const ink = InkLayer(art, S.ink || S.icon.ink, { w: big ? 1280 : 560, h: big ? 720 : 360, lw: big ? 3.2 : 2.6, label: S.title });
    const flW = Wipe(fl);
    fl.onload = () => { art.style.aspectRatio = `${fl.naturalWidth}/${fl.naturalHeight}`; };
    const dv = el('svg:svg', { class: 'divider', viewBox: '0 0 300 24', 'aria-hidden': 'true' }); box.insertBefore(dv, art);
    const dp = el('svg:path', { d: 'M4 14 C 30 2, 50 22, 76 12 S 120 4, 150 13 S 200 22, 226 11 S 272 6, 296 13' }, dv); const DL = 300; dp.style.strokeDasharray = DL; dp.style.strokeDashoffset = DL;
    const kk = el('p', { class: 'kicker' }, box); kk.textContent = S.kicker || '';
    const h = el('h2', { id: S.id + '-h' }, box); h.textContent = S.title;
    const p = el('p', {}, box); p.textContent = S.text;
    if (S.cta) { const b = S.cta.url ? el('a', { class: 'btn main', href: S.cta.url }, box) : el('button', { class: 'btn main', 'aria-disabled': 'true', title: 'em breve' }, box); b.textContent = S.cta.url ? S.cta.label : S.cta.label + ' — em breve'; }
    if (S.provisional) { const q = el('p', { class: 'prov' }, box); q.textContent = S.provisional; }
    secs.push({ sec, ink, fl, flW, big, dp, DL, back, art, fg, fgd });
  }
  C.sections.forEach(S => makeSection(S));
  makeSection(C.finale, { len: 2.6, big: true });
  /* fio contínuo: a estrada de onda continua da ilha, atravessa todas as seções e termina na cidade */
  /* fio contínuo: cada seção continua o cabo da borda esquerda (camada pequena por cena, sem SVG gigante) */

  /* ---------- som opcional: só liga por toque; sem arquivo ainda ---------- */
  const sb = el('button', { class: 'sound', 'aria-pressed': 'false', title: 'Som opcional' }, document.body); sb.textContent = '♪ Som: desligado';
  let actx = null, audioEl = null;
  sb.addEventListener('click', async () => {
    const on = sb.getAttribute('aria-pressed') !== 'true'; sb.setAttribute('aria-pressed', String(on)); sb.textContent = on ? '♪ Som: ligado' : '♪ Som: desligado';
    if (on) { actx = actx || new (window.AudioContext || window.webkitAudioContext)(); await actx.resume();
      if (C.sound.src) { audioEl = audioEl || Object.assign(new Audio(C.sound.src), { loop: true }); audioEl.play().catch(() => {}); } else sb.title = 'Som pronto — faixa ainda não fornecida'; }
    else { audioEl && audioEl.pause(); actx && actx.suspend(); }
    document.documentElement.dataset.sound = on ? 'on' : 'off';
  });

  /* ================= laço ================= */
  const scenes = [...document.querySelectorAll('.scene')];
  scenes.forEach(s => s.style.height = (+s.dataset.len * 100) + 'vh');
  /* posições cacheadas no resize: nenhum getBoundingClientRect por quadro (evitava layout forçado entre escritas) */
  const POS = new Map(); const measure = () => { const y = scrollY; scenes.forEach(s => { const r = s.getBoundingClientRect(); POS.set(s, [r.top + y, r.height]); }); };
  let SY = 0, VW = innerWidth; const prog = s => { const [t, h] = POS.get(s); return clamp((SY - t) / Math.max(1, h - VH)); };
  const secProg = s => { const [t, h] = POS.get(s); return clamp((VH - (t - SY)) / h); }; let VH = innerHeight;
  measure();
  const journeyEl = document.getElementById('journey'); let q = 0;
  const frame = () => {
    q = 0; SY = scrollY; const t = prog(journeyEl); journeyEl.dataset.p = t.toFixed(3); journey(t);
    secs.forEach(o => { const k = secProg(o.sec); o.sec.dataset.p = k.toFixed(3); if (k > 0 && k < 1.01 || o.ink.ready()) { if (k > 0) o.ink.draw(o.ks = o.big ? [seg(k, .12, .3), seg(k, .2, .45), seg(k, .28, .62)] : [seg(k, .1, .25), seg(k, .15, .38), seg(k, .2, .5)]); }
      const f = RM ? 1 : (o.big ? seg(k, .6, .75) : seg(k, .45, .6)); o.flW(f); o.fgd(seg(k, 0, .7)); if (!RM && k > 0 && k < 1) o.fg.style.transform = `translate3d(0,${((.5 - k) * VH * 1.1).toFixed(1)}px,0)`;
      if (!RM && k > 0 && k < 1) { const z = ease3(seg(k, .05, .55)); o.back.style.transform = `translate3d(-50%,${((.5 - k) * 120).toFixed(1)}px,0)`; o.art.style.transform = `translate3d(0,${((.5 - k) * 36).toFixed(1)}px,0) scale(${(1.14 - .14 * z).toFixed(4)})`; } o.dp.style.strokeDashoffset = o.DL * (1 - (RM ? 1 : seg(k, .05, .3))); });
  };
  addEventListener('scroll', () => { if (!q) q = requestAnimationFrame(frame); }, { passive: true });
  addEventListener('resize', () => { VW = innerWidth; VH = innerHeight; measure(); frame(); }); addEventListener('load', () => { measure(); frame(); }); frame();
  if (RM) { islandInk.load(); secs.forEach(o => o.ink.load()); }
  idle(() => islandInk.load());
  document.documentElement.dataset.ready = '1'; const ld = document.getElementById('loader'); if (ld) { ld.classList.add('done'); setTimeout(() => ld.remove(), 600); }
})();
