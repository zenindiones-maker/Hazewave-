import { getArtist, getTrack, type ArtistId } from "../data/catalog";
import { HazewaveAudioEngine } from "./audio/SyntheticAudioEngine";
import { bridgeFixtureManifest } from "./bridge/visualManifest";
import { detectQuality } from "./quality/quality";
import { PlayerMachine, type PlayerPhase } from "./state/playerMachine";

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

  if (!stageHost || !player || !runtimeLabel || !stateLabel || !title || !artistLabel || !toggle || !seek || !sectionMap || !sectionLabel || !timeCurrent || !timeTotal) return;

  const quality = detectQuality();
  document.documentElement.dataset.qualityTier = quality.tier;
  document.documentElement.dataset.reducedMotion = String(quality.reducedMotion);

  const machine = new PlayerMachine();
  const audio = new HazewaveAudioEngine();

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
  let experience: StageController | null = null;
  let atmosphere: AtmosphereController | null = null;
  let atmosphereLoad: Promise<AtmosphereController | null> | null = null;
  let pendingAtmosphereArtist: ArtistId = "aether";
  let pendingAtmosphereProgress = 0;
  let atmosphereShouldPlay = false;
  let selectionToken = 0;

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

    const source = buttons.find((button) => button.dataset.trackId === trackId);
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

    if (phase === "SELECTED" || phase === "CONTACT" || phase === "EJECT") {
      const cuePan = phase === "SELECTED" ? cuePanForActiveObject() : 0;
      audio.cue(phase, cuePan);
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
    const token = ++selectionToken;

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
          button.setAttribute("aria-pressed", String(button.dataset.trackId === trackId))
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
      }, `artist-${artist.id}`);

      pendingAtmosphereArtist = artist.id;
      atmosphere?.setArtist(artist.id);
      await audio.prepare(track);

      const stage = await stageReady;
      if (stage) {
        await stage.select(trackId);
      } else {
        await new Promise((resolve) =>
          window.setTimeout(resolve, quality.reducedMotion ? 10 : 120)
        );
      }

      if (token !== selectionToken) return;

      if (machine.phase === "CONTACT") machine.transition("ACTIVATING");
      if (machine.phase === "ACTIVATING" || machine.phase === "SELECTED") {
        await audio.play(track);
        machine.transition("PLAYING");
      }

      stateLabel.textContent = machine.phase;
      stage?.setPlaying(true);
      atmosphereShouldPlay = true;
      atmosphere?.setPlaying(true);
      toggle.disabled = false;
      toggle.textContent = "PAUSE";
    } catch (error) {
      machine.fail();
      stateLabel.textContent = "ERROR";
      runtimeLabel.textContent = error instanceof Error ? error.message : "UNKNOWN_ERROR";
    }
  };

  buttons.forEach((button) => {
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => {
      const trackId = button.dataset.trackId;
      if (trackId) void selectTrack(trackId);
    });
  });

  archiveButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const trackId = button.dataset.archiveTrackId;
      if (!trackId) return;

      stageHost.scrollIntoView({
        behavior: quality.reducedMotion ? "auto" : "smooth",
        block: "start"
      });

      window.setTimeout(
        () => void selectTrack(trackId),
        quality.reducedMotion ? 0 : 260
      );
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
      experience?.setPlaying(false);
      atmosphereShouldPlay = false;
      atmosphere?.setPlaying(false);
    } else if (audio.state === "PAUSED") {
      void audio.resume().then(() => {
        if (machine.phase === "PAUSED") machine.transition("PLAYING");
        stateLabel.textContent = machine.phase;
        toggle.textContent = "PAUSE";
        experience?.setPlaying(true);
        atmosphereShouldPlay = true;
        atmosphere?.setPlaying(true);
      });
    }
  });

  let lastSemanticSection: "intro" | "verse" | "break" | "chorus" | "outro" | null = null;
  let spectrumFrame = 0;

  const signalLoop = () => {
    const energy = audio.energy();
    experience?.setSignalEnergy(energy);
    atmosphere?.setEnergy(energy);
    if ((spectrumFrame++ & 1) === 0) {
      experience?.setSpectrum(audio.spectrumBands(8));
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

      if (audio.state !== "PLAYING") {
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

  window.addEventListener(
    "pagehide",
    () => {
      if (diagnosticsTimer !== null) window.clearInterval(diagnosticsTimer);
      experience?.dispose();
      atmosphere?.dispose();
    },
    { once: true }
  );
}
