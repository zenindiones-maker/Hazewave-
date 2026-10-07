import { artistChapters, type ArtistChapterWorld } from "../data/artistChapters";
import { getArtist, getTrack, tracks, type ArtistId } from "../data/catalog";
import { HazewaveAudioEngine } from "./audio/SyntheticAudioEngine";
import { bridgeFixtureManifest } from "./bridge/visualManifest";
import { detectQuality } from "./quality/quality";
import { PlayerMachine, type PlayerPhase } from "./state/playerMachine";
import { ScrollConductor, type StoryRuntimeState } from "./story/ScrollConductor";
import {
  ArtistJourneyConductor,
  type ArtistJourneyPhase
} from "./story/ArtistJourneyConductor";

interface StageController {
  select(trackId: string): Promise<void>;
  setPlaying(playing: boolean): void;
  setSection(section: "intro" | "verse" | "break" | "chorus" | "outro"): void;
  setBeatPulse(value: number): void;
  setSignalEnergy(value: number): void;
  setSpectrum(values: readonly number[]): void;
  setTrackProgress(value: number): void;
  dispose(): void;
}

interface AtmosphereController {
  setArtist(artist: ArtistId): void;
  setEnergy(value: number): void;
  setProgress(value: number): void;
  setPlaying(playing: boolean): void;
  dispose(): void;
}

interface LivingWorldController {
  setStoryState(state: StoryRuntimeState): void;
  setArtistWorld(
    world: ArtistChapterWorld,
    progress: number,
    phase?: ArtistJourneyPhase
  ): void;
  setArtistFocus(active: boolean): void;
  setAudioEnergy(value: number): void;
  setSpectrum(values: readonly number[]): void;
  dispose(): void;
}

export function bootHazewaveSite(): void {
  const stageHost = document.querySelector<HTMLElement>("#premium-stage");
  const player = document.querySelector<HTMLElement>(".player");
  const runtimeLabel = document.querySelector<HTMLElement>("#runtime-label");
  const stateLabel = document.querySelector<HTMLElement>("#state-label");
  const title = document.querySelector<HTMLElement>("#player-title");
  const artistLabel = document.querySelector<HTMLElement>("#player-artist");
  const toggle = document.querySelector<HTMLButtonElement>("#toggle-play");
  const seek = document.querySelector<HTMLInputElement>("#player-seek");
  const sectionMap = document.querySelector<HTMLElement>("#player-sections");
  const sectionLabel = document.querySelector<HTMLElement>("#player-section-label");
  const timeCurrent = document.querySelector<HTMLElement>("#player-time-current");
  const timeTotal = document.querySelector<HTMLElement>("#player-time-total");
  const worldArtistName = document.querySelector<HTMLElement>("#world-artist-name");
  const worldRelease = document.querySelector<HTMLElement>("#world-release");
  const worldTrack = document.querySelector<HTMLElement>("#world-track");
  const deckBeacon = document.querySelector<HTMLElement>(".deck-beacon");
  const deckBeaconTrack = document.querySelector<HTMLElement>("#deck-beacon-track");
  const deckBeaconArtist = document.querySelector<HTMLElement>("#deck-beacon-artist");
  const deckBeaconSection = document.querySelector<HTMLElement>("#deck-beacon-section");
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-track-id]"));
  const archiveButtons = Array.from(
    document.querySelectorAll<HTMLButtonElement>("[data-archive-track-id]")
  );
  const enterArchive = document.querySelector<HTMLButtonElement>("#enter-archive");
  const loader = document.querySelector<HTMLElement>("#site-loader");
  const backdropHost = document.querySelector<HTMLElement>(".site-backdrop");
  const backdropImage = document.querySelector<HTMLImageElement>(".site-backdrop img");
  const wheel = document.querySelector<HTMLElement>("#player-wheel");
  const wheelControl = document.querySelector<HTMLElement>("#wheel-ring-control");
  const wheelVolume = document.querySelector<HTMLElement>("#wheel-volume");
  const deckScreen = document.querySelector<HTMLElement>("#deck-screen");
  const deckTracklist = document.querySelector<HTMLOListElement>("#deck-tracklist");
  const wheelActions = Array.from(
    document.querySelectorAll<HTMLButtonElement>("[data-wheel-action]")
  );
  const merchButtons = Array.from(
    document.querySelectorAll<HTMLButtonElement>("[data-merch-message]")
  );
  const worldFocusControls = Array.from(
    document.querySelectorAll<HTMLButtonElement>("[data-world-focus-control]")
  );
  const artistJourneyRoot = document.querySelector<HTMLElement>("#artist-worlds");

  if (!stageHost || !player || !runtimeLabel || !stateLabel || !title || !artistLabel || !toggle || !seek || !sectionMap || !sectionLabel || !timeCurrent || !timeTotal) return;

  const quality = detectQuality();
  document.documentElement.dataset.qualityTier = quality.tier;
  document.documentElement.dataset.reducedMotion = String(quality.reducedMotion);

  let livingWorld: LivingWorldController | null = null;
  let pendingStoryState: StoryRuntimeState | null = null;

  const artistChapterById = new Map(
    artistChapters.map((chapter) => [chapter.id, chapter] as const)
  );
  const firstArtistChapter = artistChapters[0]!;
  let pendingArtistWorld: {
    world: ArtistChapterWorld;
    progress: number;
    phase: ArtistJourneyPhase;
  } = {
    world: firstArtistChapter.world,
    progress: 0,
    phase: "EMERGE"
  };

  const conductor = new ScrollConductor(
    quality.reducedMotion,
    (state) => {
      pendingStoryState = state;
      livingWorld?.setStoryState(state);
    }
  );

  const artistJourney = new ArtistJourneyConductor(({ artistId, progress, phase }) => {
    const chapter = artistChapterById.get(artistId);
    if (!chapter) return;

    pendingArtistWorld = {
      world: chapter.world,
      progress,
      phase
    };
    livingWorld?.setArtistWorld(chapter.world, progress, phase);
  });

  const livingWorldEligible =
    !quality.reducedMotion &&
    quality.tier !== "LOW" &&
    Boolean(backdropHost && backdropImage);

  if (livingWorldEligible && backdropHost && backdropImage) {
    void import("./world/LivingWorldStage")
      .then(({ LivingWorldStage }) =>
        LivingWorldStage.create(backdropHost, backdropImage, quality)
      )
      .then((created) => {
        livingWorld = created;
        if (pendingStoryState) created.setStoryState(pendingStoryState);
        created.setArtistWorld(
          pendingArtistWorld.world,
          pendingArtistWorld.progress,
          pendingArtistWorld.phase
        );
        created.setArtistFocus(Boolean(focusedArtist));
      })
      .catch((error) => {
        backdropHost.dataset.worldRuntime = "fallback";
        console.warn("Hazewave living-world WebGL2 fallback:", error);
      });
  } else if (backdropHost) {
    backdropHost.dataset.worldRuntime = "css-fallback";
  }

  if (enterArchive) {
    enterArchive.addEventListener("click", () => conductor.scrollTo("#archive"));
  }

  player.dataset.context = "journey";
  const archiveSection = document.querySelector<HTMLElement>("#archive");
  const archivePlayerObserver =
    archiveSection && "IntersectionObserver" in window
      ? new IntersectionObserver(
          ([entry]) => {
            player.dataset.context =
              entry?.isIntersecting && entry.intersectionRatio >= 0.28
                ? "archive"
                : "journey";
          },
          { threshold: [0, 0.28, 0.55] }
        )
      : null;

  if (archiveSection) archivePlayerObserver?.observe(archiveSection);

  let focusedArtist: ArtistId | null = null;

  const unmountAuthorizedVideo = (artistId: ArtistId) => {
    const mount = document.querySelector<HTMLElement>(`[data-video-mount="${artistId}"]`);
    if (!mount) return;

    mount.querySelectorAll("video").forEach((video) => {
      video.pause();
      video.removeAttribute("src");
      video.load();
    });

    mount.replaceChildren();
    delete mount.dataset.loaded;

    const openButton = document.querySelector<HTMLButtonElement>(
      `[data-video-source][data-video-artist="${artistId}"]`
    );
    if (openButton) {
      openButton.disabled = false;
      openButton.textContent = "OPEN VISUAL";
    }

    document
      .querySelector<HTMLButtonElement>(`[data-video-close="${artistId}"]`)
      ?.remove();
  };

  const setArtistFocus = (artistId: ArtistId | null, restoreFocus = false) => {
    const previous = focusedArtist;
    focusedArtist = artistId;

    if (previous && previous !== artistId) {
      unmountAuthorizedVideo(previous);
    }

    document.querySelectorAll<HTMLButtonElement>("[data-artist-focus]").forEach((button) => {
      const active = button.dataset.artistFocus === artistId;
      button.setAttribute("aria-expanded", String(active));
    });

    worldFocusControls.forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.worldFocusControl === artistId)
      );
    });

    document.querySelectorAll<HTMLElement>("[data-artist-focus-panel]").forEach((panel) => {
      panel.dataset.open = String(panel.dataset.artistFocusPanel === artistId);
    });

    document.querySelectorAll<HTMLElement>("[data-artist-chapter]").forEach((chapter) => {
      chapter.dataset.focused = String(chapter.dataset.artistChapter === artistId);
    });

    if (artistId) {
      document.documentElement.dataset.focusedArtist = artistId;
      const focusedChapter = artistChapterById.get(artistId);
      if (focusedChapter) {
        document.documentElement.style.setProperty(
          "--focused-artist-accent",
          focusedChapter.world.accent
        );
      }
    } else {
      delete document.documentElement.dataset.focusedArtist;
      document.documentElement.style.removeProperty("--focused-artist-accent");
    }

    livingWorld?.setArtistFocus(Boolean(artistId));

    if (restoreFocus && previous) {
      document
        .querySelector<HTMLButtonElement>(`[data-artist-focus="${previous}"]`)
        ?.focus({ preventScroll: true });
    }
  };

  const mountAuthorizedVideo = (button: HTMLButtonElement) => {
    const source = button.dataset.videoSource?.trim();
    const artistId = button.dataset.videoArtist as ArtistId | undefined;
    if (!source || !artistId) return;

    const mount = document.querySelector<HTMLElement>(`[data-video-mount="${artistId}"]`);
    if (!mount || mount.dataset.loaded === "true") return;

    let url: URL;
    try {
      url = new URL(source, window.location.origin);
    } catch {
      button.textContent = "INVALID VIDEO SOURCE";
      return;
    }

    const isLocal = url.origin === window.location.origin;
    const isYouTube =
      url.origin === "https://www.youtube.com" ||
      url.origin === "https://www.youtube-nocookie.com";
    const isVimeo = url.origin === "https://player.vimeo.com";

    if (isLocal) {
      const video = document.createElement("video");
      video.controls = true;
      video.preload = "metadata";
      video.playsInline = true;
      video.src = url.pathname + url.search;
      video.setAttribute("aria-label", "Clipe autorizado");
      mount.append(video);
    } else if (isYouTube || isVimeo) {
      const iframe = document.createElement("iframe");
      iframe.src = url.toString();
      iframe.loading = "lazy";
      iframe.allow = "accelerometer; autoplay; encrypted-media; picture-in-picture";
      iframe.allowFullscreen = true;
      iframe.referrerPolicy = "strict-origin-when-cross-origin";
      iframe.title = "Clipe autorizado";
      mount.append(iframe);
    } else {
      button.textContent = "VIDEO SOURCE BLOCKED";
      return;
    }

    mount.dataset.loaded = "true";
    button.textContent = "VISUAL LOADED";
    button.disabled = true;

    const close = document.createElement("button");
    close.type = "button";
    close.className = "artist-video-close";
    close.dataset.videoClose = artistId;
    close.textContent = "CLOSE VISUAL";
    close.setAttribute("aria-label", "Fechar clipe autorizado");
    close.addEventListener(
      "click",
      () => {
        unmountAuthorizedVideo(artistId);
        button.focus({ preventScroll: true });
      },
      { once: true }
    );
    mount.parentElement?.append(close);
  };

  const onArtistJourneyClick = (event: MouseEvent) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const videoButton = target.closest<HTMLButtonElement>("[data-video-source]");
    if (videoButton) {
      mountAuthorizedVideo(videoButton);
      return;
    }

    const focusButton = target.closest<HTMLButtonElement>("[data-artist-focus]");
    const artistId = focusButton?.dataset.artistFocus as ArtistId | undefined;
    if (!focusButton || !artistId) return;

    const next = focusedArtist === artistId ? null : artistId;
    setArtistFocus(next);
  };

  const onArtistJourneyKeydown = (event: KeyboardEvent) => {
    if (event.key !== "Escape" || !focusedArtist) return;
    event.preventDefault();
    setArtistFocus(null, true);
  };

  const onWorldFocusControlClick = (event: Event) => {
    const button = event.currentTarget;
    if (!(button instanceof HTMLButtonElement)) return;

    const artistId = button.dataset.worldFocusControl as ArtistId | undefined;
    if (!artistId) return;

    const next = focusedArtist === artistId ? null : artistId;
    setArtistFocus(next);

    if (next) {
      conductor.scrollTo(`[data-artist-chapter="${next}"]`);
    }
  };

  worldFocusControls.forEach((button) =>
    button.addEventListener("click", onWorldFocusControlClick)
  );

  artistJourneyRoot?.addEventListener("click", onArtistJourneyClick);
  document.addEventListener("keydown", onArtistJourneyKeydown);

  if (loader) {
    let loaderSettled = false;
    const releaseLoader = () => {
      if (loaderSettled) return;
      loaderSettled = true;
      loader.dataset.state = "ready";
      window.setTimeout(() => loader.remove(), 520);
    };

    if (!backdropImage || backdropImage.complete) {
      window.setTimeout(releaseLoader, 260);
    } else {
      backdropImage.addEventListener("load", releaseLoader, { once: true });
      backdropImage.addEventListener("error", releaseLoader, { once: true });
      window.setTimeout(releaseLoader, 1400);
    }
  }

  merchButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const message = button.dataset.merchMessage?.trim();
      const href = button.dataset.merchHref?.trim();
      if (!message || !href) return;

      void navigator.clipboard?.writeText(message).catch(() => undefined);
      button.textContent = "MENSAGEM COPIADA · ABRINDO DM";
      window.open(href, "_blank", "noopener,noreferrer");
      window.setTimeout(() => {
        button.textContent = "COMPRAR VIA DM";
      }, 1800);
    });
  });

  const machine = new PlayerMachine();
  const audio = new HazewaveAudioEngine();
  const mediaSession = "mediaSession" in navigator ? navigator.mediaSession : null;

  const setMediaPlaybackState = (state: "none" | "paused" | "playing") => {
    if (!mediaSession) return;
    try {
      mediaSession.playbackState = state;
    } catch {
      // Progressive enhancement only.
    }
  };

  const formatTime = (seconds: number) => {
    const safe = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
    const minutes = Math.floor(safe / 60);
    const remainder = Math.floor(safe % 60).toString().padStart(2, "0");
    return `${minutes}:${remainder}`;
  };

  const renderSectionMap = (track: ReturnType<typeof getTrack>) => {
    sectionMap.replaceChildren();
    for (const [index, section] of track.visual.sections.entries()) {
      const marker = document.createElement("span");
      marker.className = "player-section-marker";
      marker.dataset.sectionKind = section.kind;
      marker.dataset.sectionIndex = String(index);
      marker.style.left = `${Math.min(100, Math.max(0, (section.at / track.durationSeconds) * 100)).toFixed(2)}%`;
      marker.title = section.kind.toUpperCase();
      sectionMap.append(marker);
    }
    sectionLabel.textContent = "INTRO";
  };

  type WheelMode = "volume" | "tracks";
  let wheelMode: WheelMode = "volume";

  const renderDeckTracklist = (artistId: ArtistId, activeTrackId: string) => {
    if (!deckTracklist) return;

    const artist = getArtist(artistId);
    deckTracklist.replaceChildren();

    artist.tracks.forEach((track, index) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.deckTrackId = track.id;
      button.dataset.active = String(track.id === activeTrackId);
      button.setAttribute("aria-current", track.id === activeTrackId ? "true" : "false");
      button.innerHTML =
        `<span>${String(index + 1).padStart(2, "0")} · ${track.title}</span><small>${track.visual.bpm} BPM</small>`;
      button.addEventListener("click", () => void selectTrack(track.id));
      item.append(button);
      deckTracklist.append(item);
    });
  };

  const setWheelMode = (mode: WheelMode) => {
    wheelMode = mode;
    if (wheel) wheel.dataset.mode = mode;
    if (deckScreen) deckScreen.dataset.view = mode === "tracks" ? "list" : "now";
    if (wheelControl) {
      wheelControl.setAttribute(
        "aria-label",
        mode === "tracks" ? "Selecionar faixa da fita" : "Volume do player"
      );
    }

    if (wheelVolume) {
      if (mode === "volume") {
        wheelVolume.textContent = String(Math.round(audio.volume * 100));
      } else if (machine.activeTrackId) {
        const track = getTrack(machine.activeTrackId);
        const artist = getArtist(track.artistId);
        const index = artist.tracks.findIndex((candidate) => candidate.id === track.id);
        wheelVolume.textContent = `${Math.max(1, index + 1)}/${artist.tracks.length}`;
      } else {
        wheelVolume.textContent = "--";
      }
    }

    wheel?.querySelector<HTMLElement>(".wheel-center small")?.replaceChildren(
      document.createTextNode(mode === "tracks" ? "TRACK" : "VOL")
    );
  };
  let experience: StageController | null = null;
  let atmosphere: AtmosphereController | null = null;
  let atmosphereLoad: Promise<AtmosphereController | null> | null = null;
  let pendingAtmosphereArtist: ArtistId = "aether";
  let pendingAtmosphereProgress = 0;
  let atmosphereShouldPlay = false;
  let selectionToken = 0;
  let selectionInFlight = false;
  let queuedTrackId: string | null = null;
  let selectionStartedAt = 0;
  let contactReachedAt = 0;
  let lastSelectionToContactMs: number | null = null;
  let lastContactToAudioMs: number | null = null;
  let lastSelectionToPlayingMs: number | null = null;

  const commitUiState = (update: () => void, transitionType?: string) => {
    const transitionDocument = document as Document & {
      startViewTransition?: (
        input:
          | (() => void)
          | { update: () => void; types?: string[] }
      ) => { finished: Promise<void> };
    };

    if (quality.reducedMotion || !transitionDocument.startViewTransition) {
      update();
      return;
    }

    if (transitionType) {
      try {
        transitionDocument.startViewTransition({
          update,
          types: [transitionType]
        });
        return;
      } catch {
        // Older implementations may expose startViewTransition() without
        // supporting the 2026 typed options object yet.
      }
    }

    transitionDocument.startViewTransition(update);
  };

  const cuePanForActiveObject = (): number => {
    const trackId = machine.activeTrackId;
    if (!trackId) return 0;

    const track = getTrack(trackId);
    const source = buttons.find((button) => button.dataset.artist === track.artistId);
    if (!source) return 0;

    const rect = source.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const normalized = (centerX / Math.max(window.innerWidth, 1) - 0.5) * 2;
    return Math.max(-0.72, Math.min(0.72, normalized * 0.72));
  };

  const showPhase = (phase: PlayerPhase) => {
    try {
      if (machine.phase !== phase) machine.transition(phase);
    } catch {
      return;
    }
    stateLabel.textContent = phase;

    if (phase === "CONTACT") {
      contactReachedAt = performance.now();
      if (selectionStartedAt > 0) {
        lastSelectionToContactMs = contactReachedAt - selectionStartedAt;
        stageHost.dataset.selectionToContactMs = lastSelectionToContactMs.toFixed(1);
      }
    }

    if (phase === "SELECTED" || phase === "CONTACT" || phase === "EJECT") {
      const cuePan = phase === "SELECTED" ? cuePanForActiveObject() : 0;
      const activeTrack = machine.activeTrackId ? getTrack(machine.activeTrackId) : null;
      const motion = activeTrack
        ? getArtist(activeTrack.artistId).identity.world.motionSignature
        : "FLOAT";
      audio.cue(phase, cuePan, motion);
    }

    if ("vibrate" in navigator) {
      if (phase === "SELECTED") navigator.vibrate(4);
      if (phase === "CONTACT") navigator.vibrate([12, 18, 7]);
    }
  };

  let selectTrack: (trackId: string) => Promise<void>;

  const stageReady = import("./dom/PremiumResonanceStage")
    .then(({ PremiumResonanceStage }) => {
      experience = new PremiumResonanceStage(stageHost, quality, showPhase);
      runtimeLabel.textContent = `CINEMATIC DOM / ${quality.tier}`;
      return experience;
    })
    .catch((error) => {
      experience = null;
      runtimeLabel.textContent = "SEMANTIC AUDIO MODE";
      console.warn("Hazewave cinematic stage fallback:", error);
      return null;
    });

  const gpuEligible =
    !quality.reducedMotion &&
    (quality.tier === "HIGH" || quality.tier === "ULTRA") &&
    "gpu" in navigator;

  const ensureAtmosphere = (): Promise<AtmosphereController | null> => {
    if (!gpuEligible) return Promise.resolve(null);
    if (atmosphereLoad) return atmosphereLoad;

    atmosphereLoad = import("./gpu/HighTierAtmosphere")
      .then(({ HighTierAtmosphere }) => HighTierAtmosphere.create(stageHost, quality))
      .then((created) => {
        atmosphere = created;
        atmosphere.setArtist(pendingAtmosphereArtist);
        atmosphere.setProgress(pendingAtmosphereProgress);
        atmosphere.setPlaying(atmosphereShouldPlay);
        return atmosphere;
      })
      .catch((error) => {
        atmosphere = null;
        stageHost.dataset.gpuAtmosphere = "fallback";
        console.warn("Hazewave WebGPU atmosphere fallback:", error);
        return null;
      });

    return atmosphereLoad;
  };

  if (gpuEligible) {
    const scheduleGpu = () => void ensureAtmosphere();
    const idleWindow = window as Window & {
      requestIdleCallback?: (
        callback: () => void,
        options?: { timeout?: number }
      ) => number;
    };

    if (idleWindow.requestIdleCallback) {
      idleWindow.requestIdleCallback(scheduleGpu, { timeout: 1800 });
    } else {
      window.setTimeout(scheduleGpu, 1100);
    }
  }

  selectTrack = async (trackId: string) => {
    if (selectionInFlight) {
      queuedTrackId = trackId;
      stageHost.dataset.queuedTrackId = trackId;
      return;
    }

    selectionInFlight = true;
    const token = ++selectionToken;
    selectionStartedAt = performance.now();
    contactReachedAt = 0;

    try {
      machine.select(trackId);
      stateLabel.textContent = machine.phase;

      const track = getTrack(trackId);
      const artist = getArtist(track.artistId);
      const manifest = bridgeFixtureManifest(track);

      commitUiState(() => {
        document.documentElement.style.setProperty("--active-accent", artist.identity.accent);
        document.documentElement.style.setProperty("--active-secondary", artist.identity.secondary);
        document.documentElement.dataset.activeArtist = artist.id;

        const theme = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
        if (theme) theme.content = artist.identity.background;

        buttons.forEach((button) =>
          button.setAttribute("aria-pressed", String(button.dataset.artist === artist.id))
        );

        player.dataset.active = "true";
        title.textContent = track.title;
        artistLabel.textContent = `${artist.name.replace(" / DEMO", "")} · ${artist.releaseTitle} · ${manifest.bpm} BPM`;
        seek.max = String(track.durationSeconds);
        seek.value = "0";
        seek.disabled = false;
        renderSectionMap(track);
        timeCurrent.textContent = "0:00";
        timeTotal.textContent = formatTime(track.durationSeconds);
        if (worldArtistName) worldArtistName.textContent = artist.name.replace(" / DEMO", "").toUpperCase();
        if (worldRelease) worldRelease.textContent = artist.releaseTitle.toUpperCase();
        if (worldTrack) worldTrack.textContent = track.title.toUpperCase();
        if (deckBeacon) deckBeacon.dataset.active = "true";
        if (deckBeaconTrack) deckBeaconTrack.textContent = track.title.toUpperCase();
        if (deckBeaconArtist) deckBeaconArtist.textContent = artist.name.replace(" / DEMO", "").toUpperCase();
        if (deckBeaconSection) deckBeaconSection.textContent = "INTRO";
        renderDeckTracklist(artist.id, track.id);
        if (wheelMode === "tracks") setWheelMode("tracks");
      }, `artist-${artist.id}`);

      if (mediaSession && "MediaMetadata" in window) {
        try {
          mediaSession.metadata = new MediaMetadata({
            title: track.title,
            artist: artist.name.replace(" / DEMO", ""),
            album: artist.releaseTitle
          });
        } catch {
          // Metadata support varies independently from navigator.mediaSession.
        }
      }

      pendingAtmosphereArtist = artist.id;
      atmosphere?.setArtist(artist.id);
      await audio.prepare(track);

      const stage = await stageReady;
      if (stage) {
        await stage.select(trackId);
      } else {
        // Semantic fallback settles on actual paint boundaries. Do not guess
        // that a wall-clock delay means the UI has reached a valid state.
        await new Promise<void>((resolve) => {
          requestAnimationFrame(() => {
            if (quality.reducedMotion) {
              resolve();
              return;
            }
            requestAnimationFrame(() => resolve());
          });
        });
      }

      if (token !== selectionToken) return;

      if (machine.phase === "CONTACT") machine.transition("ACTIVATING");
      if (machine.phase === "ACTIVATING" || machine.phase === "SELECTED") {
        await audio.play(track);
        machine.transition("PLAYING");
      }

      stateLabel.textContent = machine.phase;

      const reachedPlayingAt = performance.now();
      lastSelectionToPlayingMs = reachedPlayingAt - selectionStartedAt;
      if (contactReachedAt > 0) {
        lastContactToAudioMs = reachedPlayingAt - contactReachedAt;
      }
      stageHost.dataset.selectionToPlayingMs = lastSelectionToPlayingMs.toFixed(1);
      stageHost.dataset.contactToAudioMs =
        lastContactToAudioMs === null ? "n/a" : lastContactToAudioMs.toFixed(1);

      stage?.setPlaying(true);
      setMediaPlaybackState("playing");
      atmosphereShouldPlay = true;
      atmosphere?.setPlaying(true);
      toggle.disabled = false;
      toggle.textContent = "PAUSE";
    } catch (error) {
      machine.fail();
      stateLabel.textContent = "ERROR";
      runtimeLabel.textContent = error instanceof Error ? error.message : "UNKNOWN_ERROR";
    } finally {
      selectionInFlight = false;

      const queued = queuedTrackId;
      queuedTrackId = null;
      delete stageHost.dataset.queuedTrackId;

      if (queued && queued !== machine.activeTrackId) {
        queueMicrotask(() => void selectTrack(queued));
      }
    }
  };

  const syncWheelVolume = () => {
    if (!wheelControl || !wheelVolume) return;
    const percent = Math.round(audio.volume * 100);
    if (wheelMode === "volume") wheelVolume.textContent = String(percent);
    wheelControl.setAttribute("aria-valuenow", String(percent));
    wheelControl.setAttribute("aria-valuetext", `Volume ${percent}%`);
  };

  const setWheelVolume = (value: number) => {
    audio.setVolume(value);
    syncWheelVolume();
  };

  const selectRelative = (direction: -1 | 1) => {
    const activeId = machine.activeTrackId;

    if (!activeId) {
      const first = tracks[0]?.id;
      if (first) void selectTrack(first);
      return;
    }

    const activeTrack = getTrack(activeId);
    const artist = getArtist(activeTrack.artistId);
    const activeIndex = artist.tracks.findIndex((track) => track.id === activeId);
    const base = activeIndex < 0 ? 0 : activeIndex;
    const nextIndex =
      (base + direction + artist.tracks.length) % artist.tracks.length;
    const next = artist.tracks[nextIndex]?.id;
    if (next) void selectTrack(next);
  };

  syncWheelVolume();
  setWheelMode("volume");

  if (wheel && wheelControl) {
    let pointerId: number | null = null;
    let lastAngle = 0;
    let trackRotationAccumulator = 0;

    const angleForPointer = (event: PointerEvent) => {
      const rect = wheel.getBoundingClientRect();
      const x = event.clientX - (rect.left + rect.width / 2);
      const y = event.clientY - (rect.top + rect.height / 2);
      return Math.atan2(y, x);
    };

    wheel.addEventListener("pointerdown", (event) => {
      if ((event.target as Element | null)?.closest("button")) return;
      pointerId = event.pointerId;
      lastAngle = angleForPointer(event);
      wheel.setPointerCapture(event.pointerId);
      event.preventDefault();
    });

    wheel.addEventListener("pointermove", (event) => {
      if (pointerId !== event.pointerId) return;
      const angle = angleForPointer(event);
      let delta = angle - lastAngle;
      if (delta > Math.PI) delta -= Math.PI * 2;
      if (delta < -Math.PI) delta += Math.PI * 2;
      lastAngle = angle;

      if (wheelMode === "tracks") {
        trackRotationAccumulator += delta;
        const threshold = 0.34;
        while (Math.abs(trackRotationAccumulator) >= threshold) {
          const direction: -1 | 1 = trackRotationAccumulator > 0 ? 1 : -1;
          selectRelative(direction);
          trackRotationAccumulator -= threshold * direction;
        }
      } else {
        setWheelVolume(audio.volume + delta / (Math.PI * 2) * 0.72);
      }
    });

    const releaseWheel = (event: PointerEvent) => {
      if (pointerId !== event.pointerId) return;
      pointerId = null;
      try { wheel.releasePointerCapture(event.pointerId); } catch {}
    };
    wheel.addEventListener("pointerup", releaseWheel);
    wheel.addEventListener("pointercancel", releaseWheel);

    wheelControl.addEventListener("keydown", (event) => {
      if (wheelMode === "tracks") {
        if (event.key === "ArrowUp" || event.key === "ArrowRight") {
          event.preventDefault();
          selectRelative(1);
        } else if (event.key === "ArrowDown" || event.key === "ArrowLeft") {
          event.preventDefault();
          selectRelative(-1);
        }
        return;
      }

      if (event.key === "ArrowUp" || event.key === "ArrowRight") {
        event.preventDefault();
        setWheelVolume(audio.volume + 0.05);
      } else if (event.key === "ArrowDown" || event.key === "ArrowLeft") {
        event.preventDefault();
        setWheelVolume(audio.volume - 0.05);
      } else if (event.key === "Home") {
        event.preventDefault();
        setWheelVolume(0);
      } else if (event.key === "End") {
        event.preventDefault();
        setWheelVolume(1);
      }
    });
  }

  wheelActions.forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.wheelAction;
      if (action === "archive") setWheelMode(wheelMode === "tracks" ? "volume" : "tracks");
      if (action === "previous") selectRelative(-1);
      if (action === "next") selectRelative(1);
      if (action === "toggle") {
        if (!machine.activeTrackId) {
          const first = tracks[0]?.id;
          if (first) void selectTrack(first);
        } else {
          toggle.click();
        }
      }
    });
  });

  buttons.forEach((button, index) => {
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => {
      const trackId = button.dataset.trackId;
      if (trackId) void selectTrack(trackId);
    });

    button.addEventListener("keydown", (event) => {
      const horizontal =
        event.key === "ArrowRight" || event.key === "ArrowLeft";
      const boundary = event.key === "Home" || event.key === "End";
      if (!horizontal && !boundary) return;

      event.preventDefault();
      let nextIndex = index;
      if (event.key === "ArrowRight") nextIndex = (index + 1) % buttons.length;
      if (event.key === "ArrowLeft") nextIndex = (index - 1 + buttons.length) % buttons.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = buttons.length - 1;

      buttons[nextIndex]?.focus({ preventScroll: false });
    });
  });

  archiveButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const trackId = button.dataset.archiveTrackId;
      if (!trackId) return;

      // Artist chapters play in place. Scroll is the narrative authority, so
      // selecting music must not teleport the visitor away from the chapter.
      void selectTrack(trackId);
    });
  });

  seek.addEventListener("input", () => {
    timeCurrent.textContent = formatTime(Number(seek.value));
  });

  seek.addEventListener("change", () => {
    void audio.seek(Number(seek.value));
  });

  toggle.addEventListener("click", () => {
    if (audio.state === "PLAYING") {
      audio.pause();
      if (machine.phase === "PLAYING") machine.transition("PAUSED");
      stateLabel.textContent = machine.phase;
      toggle.textContent = "PLAY";
      setMediaPlaybackState("paused");
      experience?.setPlaying(false);
      atmosphereShouldPlay = false;
      atmosphere?.setPlaying(false);
    } else if (audio.state === "PAUSED") {
      void audio.resume().then(() => {
        if (machine.phase === "PAUSED") machine.transition("PLAYING");
        stateLabel.textContent = machine.phase;
        toggle.textContent = "PAUSE";
        setMediaPlaybackState("playing");
        experience?.setPlaying(true);
        atmosphereShouldPlay = true;
        atmosphere?.setPlaying(true);
      });
    } else if (audio.state === "ENDED" && audio.track) {
      void audio.play(audio.track, 0).then(() => {
        if (machine.phase === "ENDED") machine.transition("PLAYING");
        stateLabel.textContent = machine.phase;
        toggle.textContent = "PAUSE";
        setMediaPlaybackState("playing");
        experience?.setPlaying(true);
        atmosphereShouldPlay = true;
        atmosphere?.setPlaying(true);
      });
    }
  });

  if (mediaSession) {
    const bindMediaAction = (
      action: MediaSessionAction,
      handler: MediaSessionActionHandler | null
    ) => {
      try {
        mediaSession.setActionHandler(action, handler);
      } catch {
        // Individual actions have different browser/platform support.
      }
    };

    bindMediaAction("play", () => {
      if (audio.state === "PAUSED" || audio.state === "ENDED") toggle.click();
    });
    bindMediaAction("pause", () => {
      if (audio.state === "PLAYING") toggle.click();
    });
    bindMediaAction("seekto", (details) => {
      if (typeof details.seekTime !== "number") return;
      void audio.seek(details.seekTime);
      seek.value = String(details.seekTime);
      timeCurrent.textContent = formatTime(details.seekTime);
    });
    bindMediaAction("nexttrack", () => selectRelative(1));
    bindMediaAction("previoustrack", () => selectRelative(-1));
  }

  let lastSemanticSection: "intro" | "verse" | "break" | "chorus" | "outro" | null = null;
  let spectrumFrame = 0;
  let mediaPositionFrame = 0;

  const signalLoop = () => {
    const energy = audio.energy();
    experience?.setSignalEnergy(energy);
    atmosphere?.setEnergy(energy);
    livingWorld?.setAudioEnergy(energy);
    if ((spectrumFrame++ & 1) === 0) {
      const spectrum = audio.spectrumBands(8);
      experience?.setSpectrum(spectrum);
      livingWorld?.setSpectrum(spectrum);
    }

    const activeTrack = audio.track;
    if (activeTrack) {
      const position = audio.positionSeconds();
      const trackProgress = Math.max(
        0,
        Math.min(1, position / Math.max(activeTrack.durationSeconds, 0.001))
      );
      experience?.setTrackProgress(trackProgress);
      pendingAtmosphereProgress = trackProgress;
      atmosphere?.setProgress(trackProgress);
      if (document.activeElement !== seek) seek.value = String(Math.min(position, activeTrack.durationSeconds));
      timeCurrent.textContent = formatTime(position);

      if (
        mediaSession &&
        (mediaPositionFrame++ % 30 === 0) &&
        "setPositionState" in mediaSession
      ) {
        try {
          mediaSession.setPositionState({
            duration: Math.max(activeTrack.durationSeconds, 0.001),
            playbackRate: 1,
            position: Math.min(position, activeTrack.durationSeconds)
          });
        } catch {
          // Position state is optional and rejects invalid/transient values.
        }
      }

      if (audio.state !== "PLAYING") {
        requestAnimationFrame(signalLoop);
        return;
      }

      if (position >= activeTrack.durationSeconds) {
        audio.finish();
        if (machine.phase === "PLAYING") machine.transition("ENDED");
        stateLabel.textContent = machine.phase;
        toggle.textContent = "REPLAY";
        setMediaPlaybackState("paused");
        experience?.setPlaying(false);
        atmosphereShouldPlay = false;
        atmosphere?.setPlaying(false);
        seek.value = String(activeTrack.durationSeconds);
        timeCurrent.textContent = formatTime(activeTrack.durationSeconds);
        if (deckBeaconSection) deckBeaconSection.textContent = "ENDED";
        requestAnimationFrame(signalLoop);
        return;
      }

      const secondsPerBeat = 60 / Math.max(activeTrack.visual.bpm, 1);
      const beatPhase = (position % secondsPerBeat) / secondsPerBeat;
      const beatPulse = Math.max(0, 1 - beatPhase / 0.24);
      experience?.setBeatPulse(beatPulse);

      const semanticSection =
        [...activeTrack.visual.sections].reverse().find((section) => position >= section.at) ??
        activeTrack.visual.sections[0];

      if (semanticSection && semanticSection.kind !== lastSemanticSection) {
        lastSemanticSection = semanticSection.kind;
        experience?.setSection(semanticSection.kind);
        sectionLabel.textContent = semanticSection.kind.toUpperCase();
        if (deckBeaconSection) deckBeaconSection.textContent = semanticSection.kind.toUpperCase();
        sectionMap.querySelectorAll<HTMLElement>(".player-section-marker").forEach((marker) => {
          marker.dataset.active = String(marker.dataset.sectionKind === semanticSection.kind);
        });
      }
    }

    requestAnimationFrame(signalLoop);
  };
  requestAnimationFrame(signalLoop);

  const diagnosticsEnabled =
    new URLSearchParams(window.location.search).get("diagnostics") === "1";

  let diagnosticsTimer: number | null = null;

  if (diagnosticsEnabled) {
    const panel = document.createElement("pre");
    panel.id = "hazewave-diagnostics";
    panel.setAttribute("aria-label", "Hazewave runtime diagnostics");
    document.body.append(panel);

    const deviceMemory =
      (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? null;

    const renderDiagnostics = () => {
      const snapshot = {
        project: "HAZEWAVE_WAVE_SITE_V1",
        quality: quality.tier,
        reducedMotion: quality.reducedMotion,
        renderer: runtimeLabel.textContent,
        viewport: `${window.innerWidth}x${window.innerHeight}`,
        deviceDpr: window.devicePixelRatio,
        renderPixelRatio: quality.pixelRatio,
        fps: stageHost.dataset.fps ?? "warming",
        frameP95Ms: stageHost.dataset.frameP95Ms ?? "warming",
        performanceMode: stageHost.dataset.performance ?? "standard",
        gpuAtmosphere: stageHost.dataset.gpuAtmosphere ?? "off",
        worldRuntime: backdropHost?.dataset.worldRuntime ?? "unavailable",
        worldActivity: backdropHost?.dataset.worldActivity ?? "fallback",
        worldPerformance: backdropHost?.dataset.worldPerformance ?? "fallback",
        worldFps: backdropHost?.dataset.worldFps ?? "warming",
        worldFrameP95Ms: backdropHost?.dataset.worldFrameP95Ms ?? "warming",
        storyProgress: pendingStoryState
          ? Number(pendingStoryState.globalProgress.toFixed(4))
          : 0,
        storyBeat: pendingStoryState?.narrativeBeat ?? "WORLD_SLEEP",
        artistPhase: document.documentElement.dataset.artistPhase ?? "EMERGE",
        worldDepthModel: backdropHost?.dataset.worldDepthModel ?? "css-fallback",
        selectionToContactMs:
          lastSelectionToContactMs === null ? null : Number(lastSelectionToContactMs.toFixed(1)),
        contactToAudioMs:
          lastContactToAudioMs === null ? null : Number(lastContactToAudioMs.toFixed(1)),
        selectionToPlayingMs:
          lastSelectionToPlayingMs === null ? null : Number(lastSelectionToPlayingMs.toFixed(1)),
        audioState: audio.state,
        appState: machine.phase,
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemoryGiB: deviceMemory,
        userAgent: navigator.userAgent
      };

      panel.textContent = JSON.stringify(snapshot, null, 2);
      document.documentElement.dataset.runtimeProof = JSON.stringify(snapshot);
    };

    renderDiagnostics();
    diagnosticsTimer = window.setInterval(renderDiagnostics, 1000);
  }

  const syncVisibility = () => {
    stageHost.dataset.visibility = document.visibilityState;
  };
  syncVisibility();
  document.addEventListener("visibilitychange", syncVisibility);

  window.addEventListener(
    "pagehide",
    () => {
      if (diagnosticsTimer !== null) window.clearInterval(diagnosticsTimer);
      document.removeEventListener("visibilitychange", syncVisibility);
      worldFocusControls.forEach((button) =>
        button.removeEventListener("click", onWorldFocusControlClick)
      );
      artistJourneyRoot?.removeEventListener("click", onArtistJourneyClick);
      document.removeEventListener("keydown", onArtistJourneyKeydown);
      document.querySelectorAll<HTMLVideoElement>("[data-video-mount] video").forEach((video) => {
        video.pause();
        video.removeAttribute("src");
        video.load();
      });
      document.querySelectorAll<HTMLIFrameElement>("[data-video-mount] iframe").forEach((iframe) => {
        iframe.src = "about:blank";
      });
      experience?.dispose();
      atmosphere?.dispose();
      livingWorld?.dispose();
      archivePlayerObserver?.disconnect();
      artistJourney.dispose();
      conductor.dispose();
    },
    { once: true }
  );
}
