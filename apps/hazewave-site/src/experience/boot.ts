import { getArtist, getTrack } from "../data/catalog";
import { HazewaveAudioEngine } from "./audio/SyntheticAudioEngine";
import { bridgeFixtureManifest } from "./bridge/visualManifest";
import { detectQuality } from "./quality/quality";
import { PlayerMachine, type PlayerPhase } from "./state/playerMachine";

interface StageController {
  select(trackId: string): Promise<void>;
  setPlaying(playing: boolean): void;
  setSignalEnergy(value: number): void;
  dispose(): void;
}

export function bootHazewaveSite(): void {
  const stageHost = document.querySelector<HTMLElement>("#premium-stage");
  const runtimeLabel = document.querySelector<HTMLElement>("#runtime-label");
  const stateLabel = document.querySelector<HTMLElement>("#state-label");
  const title = document.querySelector<HTMLElement>("#player-title");
  const artistLabel = document.querySelector<HTMLElement>("#player-artist");
  const toggle = document.querySelector<HTMLButtonElement>("#toggle-play");
  const worldRelease = document.querySelector<HTMLElement>("#world-release");
  const worldTrack = document.querySelector<HTMLElement>("#world-track");
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-track-id]"));

  if (!stageHost || !runtimeLabel || !stateLabel || !title || !artistLabel || !toggle) return;

  const quality = detectQuality();
  document.documentElement.dataset.qualityTier = quality.tier;
  document.documentElement.dataset.reducedMotion = String(quality.reducedMotion);

  const machine = new PlayerMachine();
  const audio = new HazewaveAudioEngine();
  let experience: StageController | null = null;
  let selectionToken = 0;

  const commitUiState = (update: () => void) => {
    const transitionDocument = document as Document & {
      startViewTransition?: (callback: () => void) => { finished: Promise<void> };
    };
    if (!quality.reducedMotion && transitionDocument.startViewTransition) {
      transitionDocument.startViewTransition(update);
    } else {
      update();
    }
  };

  const showPhase = (phase: PlayerPhase) => {
    try {
      if (machine.phase !== phase) machine.transition(phase);
    } catch {
      return;
    }
    stateLabel.textContent = phase;

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

        title.textContent = track.title;
        artistLabel.textContent = `${artist.name.replace(" / DEMO", "")} · ${artist.releaseTitle} · ${manifest.bpm} BPM`;
        if (worldRelease) worldRelease.textContent = artist.releaseTitle.toUpperCase();
        if (worldTrack) worldTrack.textContent = track.title.toUpperCase();
      });

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

  toggle.addEventListener("click", () => {
    if (audio.state === "PLAYING") {
      audio.pause();
      if (machine.phase === "PLAYING") machine.transition("PAUSED");
      stateLabel.textContent = machine.phase;
      toggle.textContent = "PLAY";
      experience?.setPlaying(false);
    } else if (audio.state === "PAUSED") {
      void audio.resume().then(() => {
        if (machine.phase === "PAUSED") machine.transition("PLAYING");
        stateLabel.textContent = machine.phase;
        toggle.textContent = "PAUSE";
        experience?.setPlaying(true);
      });
    }
  });

  const signalLoop = () => {
    experience?.setSignalEnergy(audio.energy());
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
    },
    { once: true }
  );
}
