import { createInterferenceVoice } from "./audio";
import { mountCosmos, type CosmosEngine } from "./engine";
import { actFor, lineFor, scrollProgress } from "./story";

const PRIOR = "__hazewaveCosmosStop";

export function bootCosmos(): void {
  const previous = (window as unknown as Record<string, (() => void) | undefined>)[PRIOR];
  previous?.();

  const canvas = document.querySelector<HTMLCanvasElement>("#cosmos");
  const line = document.querySelector<HTMLElement>("#line");
  const invitation = document.querySelector<HTMLElement>("#invitation");
  const network = document.querySelector<HTMLElement>("#network");
  const listen = document.querySelector<HTMLButtonElement>("#listen");
  if (!canvas || !line || !invitation || !network || !listen) return;

  const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  if (coarse) invitation.textContent = "Deslize para atravessar";
  document.body.dataset.reduced = reducedQuery.matches ? "yes" : "no";

  let engine: CosmosEngine | null = null;
  try {
    engine = mountCosmos(canvas, reducedQuery.matches);
    document.body.dataset.gl = "live";
  } catch (error) {
    console.error(error);
    document.body.dataset.gl = "unavailable";
    document.getElementById("logo-plate")?.removeAttribute("hidden");
  }

  const voice = createInterferenceVoice();
  const abort = new AbortController();
  const { signal } = abort;
  let pointerX = 0;
  let pointerY = 0;
  let targetX = 0;
  let targetY = 0;
  let shown = "";

  const paint = () => {
    const progress = scrollProgress();
    const act = actFor(progress);
    document.body.dataset.progress = progress.toFixed(3);
    document.body.dataset.act = act;
    document.body.dataset.logo = progress >= 0.96 ? "revealed" : "hidden";
    engine?.setProgress(progress);
    voice.follow(progress);
    const text = lineFor(progress);
    if (text !== shown) {
      shown = text;
      line.textContent = text;
    }
    invitation.hidden = progress > 0.08;
    network.hidden = progress < 0.83;
  };

  const fadePointer = () => {
    if (reducedQuery.matches) {
      pointerX = 0;
      pointerY = 0;
    } else {
      pointerX += (targetX - pointerX) * 0.08;
      pointerY += (targetY - pointerY) * 0.08;
    }
    engine?.setPointer(pointerX, pointerY);
    if (!signal.aborted) requestAnimationFrame(fadePointer);
  };

  paint();
  requestAnimationFrame(fadePointer);

  window.addEventListener("scroll", paint, { passive: true, signal });
  window.addEventListener("resize", paint, { signal });
  window.addEventListener(
    "pointermove",
    (event) => {
      targetX = (event.clientX / Math.max(window.innerWidth, 1)) * 2 - 1;
      targetY = -((event.clientY / Math.max(window.innerHeight, 1)) * 2 - 1);
    },
    { signal },
  );
  reducedQuery.addEventListener(
    "change",
    () => {
      document.body.dataset.reduced = reducedQuery.matches ? "yes" : "no";
      engine?.setReduced(reducedQuery.matches);
    },
    { signal },
  );

  listen.addEventListener(
    "click",
    () => {
      const enabled = voice.toggle();
      document.body.dataset.audio = enabled ? "on" : "off";
      listen.setAttribute("aria-pressed", String(enabled));
      listen.setAttribute("aria-label", enabled ? "Silenciar demonstração sonora sintetizada" : "Ativar demonstração sonora sintetizada da interferência");
      listen.textContent = enabled ? "Silenciar" : "Ouvir a onda";
    },
    { signal },
  );

  canvas.addEventListener(
    "webglcontextlost",
    (event) => {
      event.preventDefault();
      document.body.dataset.gl = "lost";
      engine?.destroy();
      engine = null;
      document.getElementById("logo-plate")?.removeAttribute("hidden");
    },
    { signal },
  );

  canvas.addEventListener(
    "webglcontextrestored",
    () => {
      if (signal.aborted) return;
      try {
        engine = mountCosmos(canvas, reducedQuery.matches);
        document.body.dataset.gl = "live";
        paint();
      } catch (error) {
        console.error(error);
        document.body.dataset.gl = "unavailable";
      }
    },
    { signal },
  );

  (window as unknown as Record<string, () => void>)[PRIOR] = () => {
    abort.abort();
    engine?.destroy();
    voice.destroy();
  };
}
