import {
  realArtists,
  getRealArtist,
  type RealArtistId,
} from "../data/realArtists";
import { FieldRenderer } from "./fieldRenderer";

export function bootLivingField(): void {
  const field = document.querySelector<HTMLElement>("#living-field")!;
  const canvas = document.querySelector<HTMLCanvasElement>(
    "#living-field-canvas",
  )!;
  const source = document.querySelector<HTMLImageElement>(
    "#hazewave-world-source",
  )!;
  const status = document.querySelector<HTMLElement>("#field-status")!;
  const search = document.querySelector<HTMLDialogElement>("#artist-search")!;
  const query = document.querySelector<HTMLInputElement>("#artist-query")!;
  const back = document.querySelector<HTMLButtonElement>("#world-back")!;
  const transport = document.querySelector<HTMLElement>(
    "#persistent-transport",
  )!;
  const transportArtist =
    document.querySelector<HTMLElement>("#transport-artist")!;
  const transportState =
    document.querySelector<HTMLElement>("#transport-state")!;
  const transportClose =
    document.querySelector<HTMLButtonElement>("#transport-close")!;
  const signals = Array.from(
    document.querySelectorAll<HTMLButtonElement>("[data-artist-signal]"),
  );
  const worlds = Array.from(
    document.querySelectorAll<HTMLElement>("[data-artist-world]"),
  );
  const searchResults = Array.from(
    search.querySelectorAll<HTMLButtonElement>("[data-search-artist]"),
  );
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  const renderer = new FieldRenderer(field, canvas, motion.matches);
  field.dataset.motion = motion.matches ? "reduced" : "full";
  let current: RealArtistId | null = null;
  let transitionToken = 0;
  let revealTimer = 0,
    waveTimer = 0,
    arrivalTimer = 0;
  let lastPointerWave = 0;
  let lastSelected: HTMLButtonElement | null = null;
  let disposed = false;
  const events = new AbortController();
  const options = { signal: events.signal };
  const clamp = (n: number) => Math.max(0, Math.min(1, n));
  const normalize = (s: string) =>
    s
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  const position = () =>
    signals.forEach((button, index) => {
      const [x, y] =
        innerWidth <= 700
          ? realArtists[index].signal.mobile
          : realArtists[index].signal.desktop;
      button.style.setProperty("--signal-x", `${x * 100}%`);
      button.style.setProperty("--signal-y", `${y * 100}%`);
    });
  const reveal = (button: HTMLButtonElement) => {
    signals.forEach((s) => (s.dataset.revealed = String(s === button)));
    clearTimeout(revealTimer);
    revealTimer = window.setTimeout(
      () => signals.forEach((s) => (s.dataset.revealed = "false")),
      4600,
    );
    status.textContent = `${getRealArtist(button.dataset.artistSignal!)?.name}. Selecione o sinal para entrar.`;
  };
  const wave = (clientX: number, clientY: number) => {
    const rect = field.getBoundingClientRect(),
      x = clamp((clientX - rect.left) / rect.width),
      y = clamp((clientY - rect.top) / rect.height);
    renderer.wave(x, y);
    field.dataset.waveActive = "true";
    clearTimeout(waveTimer);
    waveTimer = window.setTimeout(
      () => (field.dataset.waveActive = "false"),
      3100,
    );
    if (current) return;
    const candidates = signals
      .map((button) => {
        const b = button.getBoundingClientRect();
        return {
          button,
          d: Math.hypot(
            (b.x + b.width / 2 - clientX) / rect.height,
            (b.y + b.height / 2 - clientY) / rect.height,
          ),
        };
      })
      .sort((a, b) => a.d - b.d);
    clearTimeout(arrivalTimer);
    if (candidates[0])
      arrivalTimer = window.setTimeout(
        () => reveal(candidates[0].button),
        motion.matches ? 0 : Math.min(750, (candidates[0].d / 0.55) * 1000),
      );
  };
  const setUrl = (id: RealArtistId | null, mode: "push" | "replace") => {
    const url = new URL(location.href);
    if (id) url.searchParams.set("artist", id);
    else url.searchParams.delete("artist");
    const state = { ...(history.state ?? {}), hazewave: true, artist: id };
    if (mode === "push") history.pushState(state, "", url);
    else history.replaceState(state, "", url);
  };
  const show = (
    id: RealArtistId | null,
    mode: "push" | "replace" | "none" = "none",
    origin: [number, number] = [0.5, 0.5],
    instant = false,
  ) => {
    if (disposed) return;
    const artist = getRealArtist(id);
    id = artist?.materializedWorld ? artist.id : null;
    const token = ++transitionToken;
    current = id;
    field.dataset.worldActive = String(Boolean(id));
    field.dataset.worldReady = "false";
    field.dataset.transitioning = "true";
    const signalField = document.querySelector<HTMLElement>(".signal-field")!;
    signalField.inert = Boolean(id);
    if (id) document.documentElement.dataset.activeArtist = id;
    else delete document.documentElement.dataset.activeArtist;
    worlds.forEach((world) => {
      const active = world.dataset.artistWorld === id;
      world.dataset.active = String(active);
      world.inert = true;
      world.setAttribute("aria-hidden", String(!active));
    });
    back.hidden = !id;
    transportArtist.textContent = artist?.name ?? "HAZEWAVE";
    document.title = artist
      ? `${artist.name} — Hazewave`
      : "Hazewave — Living Resonance Field";
    clearTimeout(arrivalTimer);
    clearTimeout(revealTimer);
    signals.forEach((s) => (s.dataset.revealed = "false"));
    if (mode !== "none") setUrl(id, mode);
    const index = id ? realArtists.findIndex((a) => a.id === id) + 1 : 0;
    renderer.transition(
      index,
      origin[0],
      origin[1],
      () => {
        if (token !== transitionToken || disposed) return;
        field.dataset.worldReady = "true";
        field.dataset.transitioning = "false";
        worlds.forEach(
          (world) => (world.inert = world.dataset.artistWorld !== current),
        );
        status.textContent = artist
          ? `Você entrou no universo de ${artist.name}.`
          : "Você voltou ao campo Hazewave.";
      },
      instant || motion.matches,
    );
    if (id && !instant) back.focus({ preventScroll: true });
  };
  const enter = (button: HTMLButtonElement) => {
    const id = button.dataset.artistSignal as RealArtistId;
    if (!getRealArtist(id)) return;
    lastSelected = button;
    const box = button.getBoundingClientRect(),
      rect = field.getBoundingClientRect();
    const origin: [number, number] = [
      (box.x + box.width / 2 - rect.x) / rect.width,
      (box.y + box.height / 2 - rect.y) / rect.height,
    ];
    renderer.wave(...origin);
    show(id, "push", origin);
  };
  const openSearch = () => {
    query.value = "";
    searchResults.forEach((b) => (b.hidden = false));
    document.querySelector<HTMLElement>("#search-empty")!.hidden = true;
    search.showModal();
    query.focus();
  };
  signals.forEach((button) => {
    button.dataset.revealed = "false";
    button.addEventListener("click", () => enter(button), options);
    button.addEventListener(
      "pointerenter",
      () => {
        if (!current) reveal(button);
      },
      options,
    );
    button.addEventListener(
      "focus",
      () => {
        if (!current) reveal(button);
      },
      options,
    );
  });
  field.addEventListener(
    "pointerdown",
    (event) => {
      if ((event.target as Element).closest("button,dialog,input,a,label"))
        return;
      wave(event.clientX, event.clientY);
    },
    options,
  );
  field.addEventListener(
    "pointermove",
    (event) => {
      const rect = field.getBoundingClientRect();
      renderer.point(
        clamp((event.clientX - rect.x) / rect.width),
        clamp((event.clientY - rect.y) / rect.height),
      );
      if (
        current ||
        (event.target as Element).closest("button,dialog,input,a,label")
      )
        return;
      if (
        (event.pointerType === "mouse" || event.buttons > 0) &&
        performance.now() - lastPointerWave > 1800
      ) {
        wave(event.clientX, event.clientY);
        lastPointerWave = performance.now();
      }
    },
    { ...options, passive: true },
  );
  document.querySelector('[data-primary-action="explore"]')!.addEventListener(
    "click",
    () => {
      const b = signals[3].getBoundingClientRect();
      wave(b.x + b.width / 2, b.y + b.height / 2);
      signals[3].focus({ preventScroll: true });
    },
    options,
  );
  document
    .querySelector('[data-primary-action="search"]')!
    .addEventListener("click", openSearch, options);
  document.querySelector('[data-primary-action="listen"]')!.addEventListener(
    "click",
    () => {
      transport.dataset.expanded = "true";
      transportClose.hidden = false;
      transportState.textContent = "As faixas chegam em breve.";
      status.textContent = "Ainda não há faixas publicadas para reprodução.";
      transport.focus({ preventScroll: true });
    },
    options,
  );
  transportClose.addEventListener(
    "click",
    () => {
      transport.dataset.expanded = "false";
      transportClose.hidden = true;
      transportState.textContent = "Músicas em preparação";
      document
        .querySelector<HTMLButtonElement>('[data-primary-action="listen"]')!
        .focus();
    },
    options,
  );
  document
    .querySelector("[data-search-close]")!
    .addEventListener("click", () => search.close(), options);
  search.addEventListener(
    "click",
    (event) => {
      if (event.target === search) {
        const r = search.getBoundingClientRect();
        if (
          event.clientX < r.left ||
          event.clientX > r.right ||
          event.clientY < r.top ||
          event.clientY > r.bottom
        )
          search.close();
      }
    },
    options,
  );
  query.addEventListener(
    "input",
    () => {
      const term = normalize(query.value);
      let count = 0;
      searchResults.forEach((button) => {
        button.hidden = !normalize(button.textContent ?? "").includes(term);
        if (!button.hidden) count++;
      });
      document.querySelector<HTMLElement>("#search-empty")!.hidden = count > 0;
    },
    options,
  );
  searchResults.forEach((button) =>
    button.addEventListener(
      "click",
      () => {
        search.close();
        const id = button.dataset.searchArtist as RealArtistId;
        const signal = signals.find((s) => s.dataset.artistSignal === id);
        if (signal) enter(signal);
      },
      options,
    ),
  );
  document
    .querySelectorAll("[data-world-switch]")
    .forEach((button) => button.addEventListener("click", openSearch, options));
  // Explicit home navigation works from direct links and never assumes a previous in-app entry.
  back.addEventListener(
    "click",
    () => {
      show(null, "push");
      (
        lastSelected ??
        document.querySelector<HTMLButtonElement>(
          '[data-primary-action="explore"]',
        )
      )?.focus({ preventScroll: true });
    },
    options,
  );
  window.addEventListener(
    "popstate",
    () => {
      if (search.open) search.close();
      const id =
        getRealArtist(new URL(location.href).searchParams.get("artist"))?.id ??
        null;
      show(id, "none");
      (id
        ? back
        : (lastSelected ??
          document.querySelector<HTMLButtonElement>(
            '[data-primary-action="explore"]',
          ))
      )?.focus({ preventScroll: true });
    },
    options,
  );
  window.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Escape" && current && !search.open) {
        show(null, "push");
        lastSelected?.focus({ preventScroll: true });
      }
    },
    options,
  );
  window.addEventListener("resize", position, { ...options, passive: true });
  position();
  const images = [
    source,
    ...worlds.map((w) => w.querySelector<HTMLImageElement>("img")!),
  ];
  motion.addEventListener(
    "change",
    () => {
      field.dataset.motion = motion.matches ? "reduced" : "full";
      void renderer
        .setReduced(motion.matches, images)
        .catch(() => (field.dataset.fieldRuntime = "css-fallback"));
    },
    options,
  );
  const initial =
    getRealArtist(new URL(location.href).searchParams.get("artist"))?.id ??
    null;
  show(initial, "replace", [0.5, 0.5], true);
  void renderer
    .initialize(images)
    .then(() => {
      if (!disposed) show(current, "none", [0.5, 0.5], true);
    })
    .catch((error) => {
      field.dataset.fieldRuntime = "css-fallback";
      field.dataset.worldReady = "true";
      field.dataset.transitioning = "false";
      console.warn("Field fallback:", error);
    });
  // The fallback is retained after a GPU loss. Restored BFCache pages reload to rebind resources.
  window.addEventListener(
    "pagehide",
    () => {
      disposed = true;
      events.abort();
      renderer.dispose();
      [revealTimer, waveTimer, arrivalTimer].forEach(clearTimeout);
    },
    { once: true },
  );
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) location.reload();
  });
}
