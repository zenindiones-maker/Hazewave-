/* Motor de scrub próprio (MIT): o progresso de cada cena = posição do scroll dentro da cena (0..1).
   Escreve somente transform / stroke-dashoffset / opacity. Um rAF por evento de scroll. */
(() => {
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const scenes = [...document.querySelectorAll('.scene')];
  scenes.forEach(s => s.style.height = (Number(s.dataset.len) * 100) + 'vh');
  const prog = s => { const r = s.getBoundingClientRect(), span = r.height - innerHeight; return Math.min(1, Math.max(0, -r.top / Math.max(1, span))); };
  const clamp = v => Math.min(1, Math.max(0, v));
  // Cena 1: traço
  const strokes = [...document.querySelectorAll('#s1 .stroke')];
  const L = strokes.map(p => { const l = p.getTotalLength(); p.style.strokeDasharray = l + ' ' + l; p.style.strokeDashoffset = l; return l; });
  const raster = document.querySelector('.logo-raster');
  const n = strokes.length, overlap = 2.5;
  function s1(t) {
    const draw = clamp(t / 0.75);                // 75% da cena desenha, 25% pinta
    strokes.forEach((p, i) => {
      const a = i / (n + overlap), b = (i + 1 + overlap) / (n + overlap);
      const k = RM ? 1 : clamp((draw - a) / (b - a));
      p.style.strokeDashoffset = L[i] * (1 - k);
    });
    const fill = RM ? 1 : clamp((t - 0.75) / 0.2);
    strokes.forEach(p => p.style.fillOpacity = fill);
    raster.style.opacity = RM ? 0 : clamp((t - 0.9) / 0.1);
  }
  // Cena 2: personagem (ciclo de passada amarrado ao scroll: 6 passos por cena)
  const w = document.querySelector('.walker');
  const parts = ['legA','legB','armA','armB'].map(c => w.querySelector('.' + c));
  function s2(t) {
    const x = t * (innerWidth - w.getBoundingClientRect().width);
    const ph = t * Math.PI * 2 * 6, sw = RM ? 0 : Math.sin(ph) * 28, bob = RM ? 0 : Math.abs(Math.sin(ph)) * -6;
    w.style.transform = `translate3d(${x}px,${bob}px,0)`;
    parts[0].style.transform = `rotate(${sw}deg)`; parts[1].style.transform = `rotate(${-sw}deg)`;
    parts[2].style.transform = `rotate(${-sw * .8}deg)`; parts[3].style.transform = `rotate(${sw * .8}deg)`;
  }
  // Cena 3: pan & zoom do mundo
  const img = document.querySelector('.world');
  function s3(t) {
    const z = 1 + (RM ? 0 : 0.18 * t), iw = img.getBoundingClientRect().width / (img._z || 1);
    const maxX = Math.max(0, iw * z - innerWidth);
    img._z = z; img.style.transformOrigin = '0 50%';
    img.style.transform = `translate3d(${-maxX * t}px,0,0) scale(${z})`;
  }
  const fns = [s1, s2, s3];
  let q = 0;
  const frame = () => { q = 0; scenes.forEach((s, i) => { const t = prog(s); fns[i](t); s.dataset.p = t.toFixed(3); }); };
  addEventListener('scroll', () => { if (!q) q = requestAnimationFrame(frame); }, { passive: true });
  addEventListener('resize', frame); frame();
})();
