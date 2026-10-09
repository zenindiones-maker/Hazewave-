/**
 * Single-source native scroll conductor for the hand-illustrated Hazewave film.
 * WAVE controls image only. No HAZE audio, tracking, scroll-jacking, or autoplay.
 * Timeline is reversible and deterministic, including touch and reduced motion.
 */
const clamp = (v: number) => Math.min(1, Math.max(0, v));
const smooth = (a: number, b: number, x: number) => {
  const t = clamp((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};

export function mountStorybook(): void {
  const film = document.getElementById("film");
  const reel = document.querySelector<HTMLElement>(".film-reel");
  const rail = document.querySelector<HTMLElement>(".progress-line");
  const art = document.querySelector<SVGElement>("#interference-art");
  if (!film || !reel || !rail || !art) return;

  const reducedQuery = matchMedia("(prefers-reduced-motion: reduce)");
  const lines = [
    document.querySelector<HTMLElement>(".line-origin"),
    document.querySelector<HTMLElement>(".line-crossing"),
    document.querySelector<HTMLElement>(".line-rupture"),
    document.querySelector<HTMLElement>(".line-reveal"),
  ];
  const root = document.documentElement;
  const abort = new AbortController();
  const { signal } = abort;
  let waiting = false;
  let progress = -1;

  function render(): void {
    waiting = false;
    const length = Math.max(1, film!.getBoundingClientRect().height - innerHeight);
    const current = clamp(-film!.getBoundingClientRect().top / length);
    if (current === progress) return;
    progress = current;

    const origin = 1 - smooth(.11, .3, current);
    const crossing = smooth(.12, .29, current) * (1 - smooth(.48, .65, current));
    const rupture = smooth(.47, .63, current) * (1 - smooth(.75, .89, current));
    const reveal = smooth(.77, .94, current);
    const signal = smooth(.025, .13, current) * (1 - smooth(.87, .98, current));
    const drawn = clamp((current - .035) / .7);
    const phase = current < .25 ? "origin" : current < .56 ? "crossing" : current < .83 ? "rupture" : "reveal";

    root.style.setProperty("--origin", origin.toFixed(4));
    root.style.setProperty("--crossing", crossing.toFixed(4));
    root.style.setProperty("--rupture", rupture.toFixed(4));
    root.style.setProperty("--reveal", reveal.toFixed(4));
    root.style.setProperty("--signal", signal.toFixed(4));
    root.style.setProperty("--dash", (100 - drawn * 100).toFixed(3));
    root.style.setProperty("--shift", reducedQuery.matches ? "0" : (current * 85).toFixed(2));
    root.style.setProperty("--parallax", reducedQuery.matches ? "0" : ((current - .5) * 35).toFixed(2));
    root.style.setProperty("--line-width", (current * 100).toFixed(2) + "%");
    document.body.dataset.phase = phase;
    document.body.dataset.progress = current.toFixed(3);
    document.body.dataset.motion = reducedQuery.matches ? "reduced" : "full";

    const opacity = [origin, crossing, rupture, reveal];
    lines.forEach((line, i) => {
      if (!line) return;
      line.setAttribute("aria-hidden", String(opacity[i]! < .2));
    });
  }

  function schedule(): void {
    if (waiting) return;
    waiting = true;
    requestAnimationFrame(render);
  }
  render();
  window.addEventListener("scroll", schedule, { signal, passive: true });
  window.addEventListener("resize", schedule, { signal });
  reducedQuery.addEventListener("change", () => {
    progress = -1;
    schedule();
  }, { signal });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) schedule();
  }, { signal });

  // Re-entrant hot-reload or client-side navigation must not install extra handlers.
  const globalState = window as Window & { __hazewaveStoryStop?: () => void };
  const old = globalState.__hazewaveStoryStop;
  if (old) old();
  globalState.__hazewaveStoryStop = () => {
    abort.abort();
    globalState.__hazewaveStoryStop = undefined;
  };
}
