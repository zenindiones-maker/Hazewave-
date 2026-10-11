/* Ilhas Hazewave — template reutilizável (MIT). Cada ilha-MPC = um artista, descrito em islands.json.
   Progresso t de cada cena = função pura do scroll ⇒ reversível. Escreve só transform/opacity/dashoffset/filter. */
(async () => {
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cfg = await (await fetch('islands.json')).json();
  const clamp = v => Math.min(1, Math.max(0, v)), seg = (t, a, b) => clamp((t - a) / (b - a));
  const scenes = [...document.querySelectorAll('.scene')];
  scenes.forEach(s => s.style.height = (+s.dataset.len * 100) + 'vh');
  const prog = s => { const r = s.getBoundingClientRect(); return clamp(-r.top / Math.max(1, r.height - innerHeight)); };

  /* ---- Cena 1: estrada de onda desenhada pelo scroll, câmera desce do logo à ilha ---- */
  const W = cfg.world, world = document.getElementById('world'), img = document.getElementById('worldImg');
  img.src = W.image; img.width = W.width; img.height = W.height;
  const svg = document.getElementById('roadSvg'); svg.setAttribute('viewBox', `0 0 ${W.width} ${W.height}`);
  const road = document.getElementById('roadPath'), glow = document.getElementById('roadGlow');
  road.setAttribute('d', W.road); glow.setAttribute('d', W.road);
  const RL = road.getTotalLength(); [road, glow].forEach(p => { p.style.strokeDasharray = RL; p.style.strokeDashoffset = RL; });
  const slots = document.getElementById('slots');
  const slotEls = cfg.islands.map(is => {
    const pt = road.getPointAtLength(RL * is.roadT), d = document.createElement('div');
    d.className = 'slot ' + is.status; d.style.left = (pt.x / W.width * 100) + '%'; d.style.top = (pt.y / W.height * 100) + '%';
    if (is.status === 'locked') { d.innerHTML = `<img src="${is.layers.color}" alt="Ilha ainda sem artista (bloqueada)" width="${is.layers.width}" height="${is.layers.height}"><span>ILHA LIVRE</span>`; }
    else { d.style.width = '0'; }
    slots.appendChild(d); return { is, d };
  });
  const cap = document.getElementById('roadCap');
  const caps = [[0, 'A onda nasce do HAZEWAVE…'], [.35, 'Cada ilha-MPC é um artista.'], [.7, 'Ilhas apagadas esperam seus artistas.'], [.9, 'A primeira ilha acende: Indionesbala.']];
  function sRoad(t) {
    const scale = Math.max(innerWidth / W.width, innerHeight * 1.9 / W.height), ww = W.width * scale, wh = W.height * scale;
    world.style.width = ww + 'px';
    const k0 = RM ? 1 : seg(t, .05, .95), pt = road.getPointAtLength(RL * k0);
    const x = Math.min(0, Math.max(innerWidth - ww, innerWidth / 2 - pt.x * scale));
    const y = Math.min(0, Math.max(innerHeight - wh, innerHeight * .5 - pt.y * scale));
    world.style.transform = `translate3d(${x}px,${y}px,0)`;
    const k = RM ? 1 : seg(t, .05, .95);
    road.style.strokeDashoffset = glow.style.strokeDashoffset = RL * (1 - k);
    slotEls.forEach(({ is, d }) => { if (is.status === 'locked') d.style.opacity = k >= is.roadT ? .9 : 0; });
    cap.textContent = caps.filter(c => t >= c[0]).pop()[1];
  }

  /* ---- Cena 2: a ilha do artista — traço nasce, depois cor, depois neon e cartão ---- */
  const A = cfg.islands.find(i => i.status === 'active');
  document.documentElement.style.setProperty('--neon', A.colors.neon); document.documentElement.style.setProperty('--ink', A.colors.ink);
  const line = await (await fetch(A.layers.line)).json();
  const ls = document.getElementById('islandLine'); ls.setAttribute('viewBox', line.viewBox); ls.setAttribute('aria-label', `Ilha-MPC de ${A.name} desenhada pelo scroll`);
  ls.innerHTML = `<g transform="${line.transform}">` + line.paths.map(d => `<path d="${d}"/>`).join('') + '</g>';
  const P = [...ls.querySelectorAll('path')], PL = P.map(p => { const l = p.getTotalLength(); p.style.strokeDasharray = l; p.style.strokeDashoffset = l; return l; });
  const col = document.getElementById('islandColor'); col.src = A.layers.color; col.width = A.layers.width; col.height = A.layers.height;
  col.alt = `Ilha-MPC de ${A.name} acesa`;
  const card = document.getElementById('islandCard');
  card.innerHTML = `<h2>${A.name.toUpperCase()}</h2>` + [...A.clips, ...A.music].map(x => x.url ? `<p><a href="${x.url}">${x.title}</a></p>` : `<p class="prov">${x.title}</p>`).join('');
  const N = P.length, OV = N * .08;
  function sIsland(t) {
    const draw = RM ? 1 : seg(t, 0, .55);
    for (let i = 0; i < N; i++) { const a = i / (N + OV), b = (i + OV) / (N + OV); P[i].style.strokeDashoffset = PL[i] * (1 - clamp((draw - a) / (b - a))); }
    const c = RM ? 1 : seg(t, .5, .75), lit = RM ? 1 : seg(t, .72, .85);
    col.style.opacity = c; col.style.filter = `saturate(${lit}) brightness(${.4 + .6 * c + .15 * lit})`;
    ls.style.opacity = 1 - .85 * lit;
    const cd = RM ? 1 : seg(t, .82, .95); card.style.opacity = cd; card.style.transform = `translateY(${20 * (1 - cd)}px)`;
  }
  const fns = [sRoad, sIsland]; let q = 0;
  const frame = () => { q = 0; scenes.forEach((s, i) => { const t = prog(s); fns[i](t); s.dataset.p = t.toFixed(3); }); };
  addEventListener('scroll', () => { if (!q) q = requestAnimationFrame(frame); }, { passive: true });
  addEventListener('resize', frame);
  img.decode?.().catch(() => {}).finally(frame); frame(); document.documentElement.dataset.ready = '1';
})();
