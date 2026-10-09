import {
  realArtists,
  getRealArtist,
  type RealArtistId,
} from "../data/realArtists";
import { FieldRenderer, FIELD_WAVE_SPEED } from "./fieldRenderer";
import { bootAuthorizedTransport } from "./audio/AuthorizedTransport";

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
  const audioTransport = bootAuthorizedTransport();
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
  const motionToggle =
    document.querySelector<HTMLButtonElement>("#motion-toggle");
  let manualReduced = false;
  const reduced = () => motion.matches || manualReduced;
  const renderer = new FieldRenderer(field, canvas, reduced());
  field.dataset.motion = reduced() ? "reduced" : "full";
  const descentOrder = [2, 0, 1, 3, 4];
  let discoveredIndex = descentOrder[0];
  let journeyIndex = discoveredIndex;
  let journeySequence = [...descentOrder];
  let current: RealArtistId | null = null;
  let journey = false;
  let journeyFrame = 0;
  let journeyHistoryOwned = false;
  const journeyControls =
    document.querySelector<HTMLElement>(".journey-controls")!;
  const journeyDistance =
    document.querySelector<HTMLElement>("#journey-distance")!;
  const journeyStage = document.querySelector<HTMLElement>("#journey-stage")!;
  const journeyArtist = document.querySelector<HTMLElement>("#journey-artist");
  // Keep a short native-scroll runway armed at the origin, before any interaction.
  // Reduced motion, direct artist routes and dialogs retain a single viewport.
  const syncScrollSurface = () => {
    const armed =
      journey ||
      (!current &&
        !reduced() &&
        !search.open &&
        field.dataset.fieldRuntime === "webgl2");
    journeyDistance.hidden = !armed;
    journeyDistance.style.height = `${Math.max(180, journeySequence.length * 130)}svh`;
    field.dataset.scrollReady = String(armed);
    field.style.position = armed ? "sticky" : "";
    field.style.top = armed ? "0px" : "";
    field.style.touchAction = armed ? "pan-y" : "";
  };
  const stopJourney = () => {
    if (!journey) return;
    journey = false;
    cancelAnimationFrame(journeyFrame);
    journeyFrame = 0;
    clearTimeout(arrivalTimer);
    clearTimeout(revealTimer);
    journeyControls.hidden = true;
    journeyDistance.hidden = true;
    field.dataset.journey = "false";
    delete field.dataset.journeyAct;
    delete field.dataset.journeyChapter;
    delete field.dataset.journeyPhase;
    syncScrollSurface();
    document.querySelector<HTMLElement>(".signal-field")!.inert =
      Boolean(current);
    window.scrollTo({ top: 0, behavior: "instant" });
  };
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
    discoveredIndex = signals.indexOf(button);
    if (journey && field.dataset.journeyAct === "discover") {
      journeyIndex = discoveredIndex;
      journeySequence = descentOrder.slice(
        descentOrder.indexOf(discoveredIndex),
      );
      syncScrollSurface();
      if (journeyArtist)
        journeyArtist.textContent = realArtists[journeyIndex].name;
    }
    signals.forEach((s) => (s.dataset.revealed = String(s === button)));
    const r = field.getBoundingClientRect(),
      b = button.getBoundingClientRect();
    renderer.preview(
      signals.indexOf(button) + 1,
      (b.x + b.width / 2 - r.x) / r.width,
      (b.y + b.height / 2 - r.y) / r.height,
    );
    field.dataset.signalDiscovered = "true";
    clearTimeout(revealTimer);
    revealTimer = journey
      ? 0
      : window.setTimeout(() => {
          signals.forEach((s) => (s.dataset.revealed = "false"));
          renderer.clearPreview();
          field.dataset.signalDiscovered = "false";
        }, 8000);
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
      renderer.prepare(signals.indexOf(candidates[0].button) + 1);
    if (candidates[0])
      arrivalTimer = window.setTimeout(
        () => reveal(candidates[0].button),
        reduced() ? 0 : (candidates[0].d / FIELD_WAVE_SPEED) * 1000,
      );
  };
  const setUrl = (id: RealArtistId | null, mode: "push" | "replace") => {
    const url = new URL(location.href);
    url.pathname = url.pathname.includes("/artists/") ? "/" : url.pathname;
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
    syncScrollSurface();
    field.dataset.signalDiscovered = "false";
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
    audioTransport.selectArtist(id);
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
          (world) => (world.inert = world.dataset.artistWorld !== current || (journey && field.dataset.journeyPhase !== "hold")),
        );
        status.textContent = artist
          ? `Você entrou no universo de ${artist.name}.`
          : "Você voltou ao campo Hazewave.";
        if (!id && !instant) {
          (
            lastSelected ??
            document.querySelector<HTMLButtonElement>(
              '[data-primary-action="explore"]',
            )
          )?.focus({ preventScroll: true });
        }
      },
      instant || reduced(),
    );
    if (id && !instant) back.focus({ preventScroll: true });
    else if (!id && !instant)
      document
        .querySelector<HTMLButtonElement>('[data-primary-action="explore"]')!
        .focus({ preventScroll: true });
  };
  const enter = (button: HTMLButtonElement) => {
    stopJourney();
    const id = button.dataset.artistSignal as RealArtistId;
    if (!getRealArtist(id)) return;
    lastSelected = button;
    discoveredIndex = signals.indexOf(button);
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
    if (journey) {
      stopJourney();
      show(current, "none", [0.5, 0.5], true);
    }
    query.value = "";
    searchResults.forEach((b) => (b.hidden = false));
    document.querySelector<HTMLElement>("#search-empty")!.hidden = true;
    search.showModal();
    syncScrollSurface();
    query.focus();
  };
  signals.forEach((button) => {
    button.dataset.revealed = "false";
    button.addEventListener("click", () => enter(button), options);
    button.addEventListener(
      "pointerenter",
      () => {
        if (!current && (!journey || field.dataset.journeyAct === "discover"))
          reveal(button);
      },
      options,
    );
    button.addEventListener(
      "focus",
      () => {
        if (!current && (!journey || field.dataset.journeyAct === "discover"))
          reveal(button);
      },
      options,
    );
  });
  field.addEventListener(
    "pointerdown",
    (event) => {
      if (
        journey ||
        (event.target as Element).closest("button,dialog,input,a,label")
      )
        return;
      wave(event.clientX, event.clientY);
    },
    options,
  );
  field.addEventListener(
    "pointermove",
    (event) => {
      if (journey) return;
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
  const startJourney = (deliberate: boolean) => {
    if (journey || current || disposed) return;
    journeyIndex = discoveredIndex;
    journeySequence = descentOrder.slice(descentOrder.indexOf(discoveredIndex));
    if (reduced() || field.dataset.fieldRuntime !== "webgl2") {
      if (deliberate) signals[journeyIndex].focus({ preventScroll: true });
      return;
    }
    journey = true;
    journeyHistoryOwned = false;
    journeyControls.hidden = false;
    field.dataset.journey = "true";
    field.dataset.journeyAct = "discover";
    syncScrollSurface();
    field.style.setProperty("--journey-progress", "0");
    if (journeyArtist)
      journeyArtist.textContent = realArtists[journeyIndex].name;
    const b = signals[journeyIndex].getBoundingClientRect();
    wave(b.x + b.width / 2, b.y + b.height / 2);
    clearTimeout(arrivalTimer);
    reveal(signals[journeyIndex]);
    clearTimeout(revealTimer);
    journeyStage.textContent = "01 / ENCONTRE O SINAL";
    // Native scrolling never steals focus from the visitor's current control.
    if (deliberate)
      document
        .querySelector<HTMLButtonElement>("#journey-exit")!
        .focus({ preventScroll: true });
  };
  document
    .querySelector('[data-primary-action="explore"]')!
    .addEventListener("click", () => startJourney(true), options);
  const updateJourney = () => {
    journeyFrame = 0;
    if (!journey) return;
    const progress = clamp(scrollY / Math.max(1, journeyDistance.offsetHeight));
    const discovering = progress <= 0.045;
    // Equal chapter lengths, each with a real arrival hold. The scene is a pure
    // function of native scroll, so reversing never depends on animation history.
    const chapterPosition =
      clamp((progress - 0.045) / 0.955) * journeySequence.length;
    const chapter = Math.min(
      journeySequence.length - 1,
      Math.floor(chapterPosition),
    );
    const local = clamp(chapterPosition - chapter);
    const p = discovering ? 0 : clamp(local / 0.68);
    journeyIndex = journeySequence[chapter];
    const fromIndex = chapter === 0 ? 0 : journeySequence[chapter - 1] + 1;
    const toIndex = journeyIndex + 1;
    const arrival = !discovering && p >= 1;
    const displayId = discovering
      ? null
      : arrival
        ? realArtists[journeyIndex].id
        : fromIndex
          ? realArtists[fromIndex - 1].id
          : null;
    if (current !== displayId) {
      show(
        displayId,
        displayId && !journeyHistoryOwned
          ? "push"
          : journeyHistoryOwned
            ? "replace"
            : "none",
        [0.5, 0.5],
        true,
      );
      if (displayId) journeyHistoryOwned = true;
    }
    document.querySelector<HTMLElement>(".signal-field")!.inert = !discovering;
    const [x, y] =
      innerWidth <= 700
        ? realArtists[journeyIndex].signal.mobile
        : realArtists[journeyIndex].signal.desktop;
    if (discovering) {
      renderer.transition(0, x, y, () => {}, true);
      renderer.preview(toIndex, x, y);
      signals.forEach(
        (s, i) => (s.dataset.revealed = String(i === journeyIndex)),
      );
    } else {
      renderer.scrubBetween(fromIndex, toIndex, x, y, p);
      signals.forEach((s) => (s.dataset.revealed = "false"));
    }
    field.style.setProperty("--journey-progress", String(progress));
    field.style.setProperty("--chapter-progress", String(local));
    field.style.setProperty("--world-takeover", arrival ? "1" : "0");
    if (journeyArtist)
      journeyArtist.textContent = realArtists[journeyIndex].name;
    const chapterLabel = `${String(chapter + 1).padStart(2, "0")} / ${String(journeySequence.length).padStart(2, "0")}`;
    journeyStage.textContent = discovering
      ? "ORIGEM / ROLE PARA DESCER"
      : arrival
        ? `${chapterLabel} / ${chapter === journeySequence.length - 1 ? "NÚCLEO PROFUNDO" : "PERMANEÇA · CONTINUE DESCENDO"}`
        : `${chapterLabel} / ATRAVESSE A RESSONÂNCIA`;
    field.dataset.journeyAct = discovering
      ? "discover"
      : arrival
        ? "arrival"
        : "traverse";
    field.dataset.journeyChapter = String(chapter + 1);
    field.dataset.journeyPhase = discovering
      ? "origin"
      : arrival
        ? "hold"
        : "transition";
    field.dataset.signalDiscovered = String(discovering);
    // CSS also uses visibility:hidden during crossing. Keep semantic interactivity
    // aligned so a previous world's controls never remain keyboard destinations.
    const focusedWorld = worlds.find((world) => world.contains(document.activeElement));
    worlds.forEach((world) => (world.inert = !arrival || world.dataset.artistWorld !== current));
    if (!arrival && focusedWorld) document.querySelector<HTMLButtonElement>("#journey-exit")!.focus({ preventScroll: true });
  };
  window.addEventListener(
    "scroll",
    () => {
      if (
        !journey &&
        scrollY > 2 &&
        field.dataset.scrollReady === "true" &&
        !search.open
      )
        startJourney(false);
      if (journey && !journeyFrame)
        journeyFrame = requestAnimationFrame(updateJourney);
    },
    { ...options, passive: true },
  );
  document.querySelector("#journey-exit")!.addEventListener(
    "click",
    () => {
      stopJourney();
      show(null, "replace", [0.5, 0.5], true);
      document
        .querySelector<HTMLButtonElement>('[data-primary-action="explore"]')!
        .focus();
    },
    options,
  );
  document
    .querySelector('[data-primary-action="search"]')!
    .addEventListener("click", openSearch, options);
  document
    .querySelector('[data-primary-action="listen"]')!
    .addEventListener("click", () => audioTransport.open(), options);
  document
    .querySelectorAll<HTMLButtonElement>("[data-world-listen]")
    .forEach((button) =>
      button.addEventListener("click", () => audioTransport.open(), options),
    );
  document
    .querySelector("[data-search-close]")!
    .addEventListener("click", () => search.close(), options);
  search.addEventListener("close", syncScrollSurface, options);
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
      stopJourney();
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
      stopJourney();
      if (search.open) search.close();
      const id =
        getRealArtist(new URL(location.href).searchParams.get("artist") ?? location.pathname.split("/artists/")[1]?.split("/")[0])?.id ??
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
      if (event.key === "Escape" && journey && !search.open) {
        stopJourney();
        show(null, "replace", [0.5, 0.5], true);
        document
          .querySelector<HTMLButtonElement>('[data-primary-action="explore"]')!
          .focus();
        return;
      }
      if (event.key === "Escape" && current && !search.open) {
        show(null, "push");
        lastSelected?.focus({ preventScroll: true });
      }
    },
    options,
  );
  window.addEventListener(
    "resize",
    () => {
      position();
      if (journey) updateJourney();
    },
    { ...options, passive: true },
  );
  field.addEventListener(
    "fieldfallback",
    () => {
      syncScrollSurface();
      if (journey) {
        stopJourney();
        show(current, "none", [0.5, 0.5], true);
        (current
          ? back
          : document.querySelector<HTMLButtonElement>(
              '[data-primary-action="explore"]',
            ))!.focus();
      }
    },
    options,
  );
  position();
  const images = [
    source,
    ...worlds.map((w) => w.querySelector<HTMLImageElement>("img")!),
  ];
  const applyMotion = () => {
    if (journey && reduced()) {
      stopJourney();
      show(current, "none", [0.5, 0.5], true);
      (current
        ? back
        : document.querySelector<HTMLButtonElement>(
            '[data-primary-action="explore"]',
          ))!.focus();
    }
    field.dataset.motion = reduced() ? "reduced" : "full";
    syncScrollSurface();
    if (motionToggle) {
      motionToggle.setAttribute("aria-pressed", String(reduced()));
      motionToggle.textContent = reduced()
        ? "MOVIMENTO REDUZIDO"
        : "PAUSAR MOVIMENTO";
      motionToggle.setAttribute(
        "aria-label",
        motion.matches
          ? "Movimento reduzido pela preferência do sistema"
          : manualReduced
            ? "Retomar movimento"
            : "Pausar movimento",
      );
    }
    void renderer
      .setReduced(reduced(), images)
      .then(syncScrollSurface)
      .catch(() => (field.dataset.fieldRuntime = "css-fallback"));
  };
  motion.addEventListener("change", applyMotion, options);
  motionToggle?.addEventListener(
    "click",
    () => {
      manualReduced = !manualReduced;
      applyMotion();
    },
    options,
  );
  if (motionToggle) {
    motionToggle.setAttribute("aria-pressed", String(reduced()));
    motionToggle.textContent = reduced()
      ? "MOVIMENTO REDUZIDO"
      : "PAUSAR MOVIMENTO";
  }
  const initial =
    getRealArtist(new URL(location.href).searchParams.get("artist") ?? location.pathname.split("/artists/")[1]?.split("/")[0])?.id ??
    null;
  if (initial)
    discoveredIndex = realArtists.findIndex((artist) => artist.id === initial);
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
      syncScrollSurface();
      console.warn("Field fallback:", error);
    });
  // The fallback is retained after a GPU loss. Restored BFCache pages reload to rebind resources.
  window.addEventListener(
    "pagehide",
    () => {
      disposed = true;
      events.abort();
      cancelAnimationFrame(journeyFrame);
      renderer.dispose();
      audioTransport.dispose();
      [revealTimer, waveTimer, arrivalTimer].forEach(clearTimeout);
    },
    { once: true },
  );
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) location.reload();
  });
}
