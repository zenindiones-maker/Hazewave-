import {
  authorizedTracks,
  isAuthorizedTrack,
  type AuthorizedTrack,
} from "../../data/authorizedTracks";
import { getRealArtist, type RealArtistId } from "../../data/realArtists";

export interface AuthorizedTransport {
  selectArtist(id: RealArtistId | null): void;
  open(): void;
  dispose(): void;
}

export function bootAuthorizedTransport(
  root: HTMLElement = document.querySelector<HTMLElement>(
    "#persistent-transport",
  )!,
  catalog: readonly AuthorizedTrack[] = authorizedTracks,
): AuthorizedTransport {
  if (!root) throw new Error("Persistent transport is missing.");
  const previous = root.querySelector<HTMLButtonElement>(
    '[aria-label="Anterior"]',
  )!;
  const play = root.querySelector<HTMLButtonElement>(".play-control")!;
  const next = root.querySelector<HTMLButtonElement>('[aria-label="Próxima"]')!;
  const seek = root.querySelector<HTMLInputElement>(
    '[aria-label="Posição da faixa"]',
  )!;
  const volume = root.querySelector<HTMLInputElement>('[aria-label="Volume"]')!;
  const artistLabel = root.querySelector<HTMLElement>("#transport-artist")!;
  const stateLabel = root.querySelector<HTMLElement>("#transport-state")!;
  const close = root.querySelector<HTMLButtonElement>("#transport-close")!;
  if (
    ![previous, play, next, seek, volume, artistLabel, stateLabel, close].every(
      Boolean,
    )
  ) {
    throw new Error("Persistent transport controls are incomplete.");
  }
  const abort = new AbortController();
  const eventOptions = { signal: abort.signal };
  const audio = root.ownerDocument.createElement("audio");
  audio.preload = "metadata";
  audio.volume = Math.max(0, Math.min(1, Number(volume.value) / 100 || 0));
  const ids = new Set<string>();
  const tracks = catalog.filter((track) => {
    if (
      !isAuthorizedTrack(track, root.ownerDocument.baseURI) ||
      ids.has(track.id)
    )
      return false;
    ids.add(track.id);
    return true;
  });
  let selectedArtist: RealArtistId | null = null;
  let current: AuthorizedTrack | null = null;
  let failure: string | null = null;
  let disposed = false;
  let requestVersion = 0;

  const playlist = () =>
    tracks.filter(
      (track) => track.artistId === (current?.artistId ?? selectedArtist),
    );
  const render = () => {
    if (disposed) return;
    const available = playlist();
    const index = available.findIndex((track) => track.id === current?.id);
    const duration = audio.duration;
    const seekable = Boolean(
      current && Number.isFinite(duration) && duration > 0,
    );
    artistLabel.textContent =
      getRealArtist(current?.artistId ?? selectedArtist)?.name ?? "HAZEWAVE";
    stateLabel.textContent =
      failure ??
      (current ? current.title : "Nenhuma faixa autorizada disponível.");
    play.disabled = !current;
    previous.disabled = index <= 0;
    next.disabled = index < 0 || index >= available.length - 1;
    volume.disabled = !current;
    seek.disabled = !seekable;
    seek.min = "0";
    seek.max = seekable ? String(duration) : "100";
    seek.step = "0.1";
    seek.value = seekable ? String(audio.currentTime) : "0";
    seek.setAttribute(
      "aria-valuetext",
      seekable
        ? `${Math.floor(audio.currentTime)} de ${Math.floor(duration)} segundos`
        : "Indisponível",
    );
    const playing = Boolean(current && !audio.paused && !audio.ended);
    play.setAttribute("aria-label", playing ? "Pausar" : "Tocar");
    play.textContent = playing ? "Ⅱ" : "▷";
    root.dataset.audioState = current
      ? failure
        ? "error"
        : playing
          ? "playing"
          : "paused"
      : "unavailable";
  };
  const load = (track: AuthorizedTrack) => {
    if (disposed || !isAuthorizedTrack(track, root.ownerDocument.baseURI))
      return;
    requestVersion++;
    audio.pause();
    current = track;
    failure = null;
    audio.src = track.sourceUrl;
    audio.load();
    render();
  };
  const resume = async () => {
    if (!current || disposed) return;
    const version = ++requestVersion;
    failure = null;
    try {
      await audio.play();
    } catch {
      if (!disposed && version === requestVersion)
        failure = "Reprodução indisponível. Tente novamente.";
    }
    if (!disposed && version === requestVersion) render();
  };
  const move = (direction: number) => {
    const available = playlist();
    const index = available.findIndex((track) => track.id === current?.id);
    const track = available[index + direction];
    if (!track) return;
    const wasPlaying = !audio.paused;
    load(track);
    if (wasPlaying) void resume();
  };
  previous.addEventListener("click", () => move(-1), eventOptions);
  next.addEventListener("click", () => move(1), eventOptions);
  play.addEventListener(
    "click",
    () => {
      if (!current) return;
      if (audio.paused) void resume();
      else {
        requestVersion++;
        audio.pause();
      }
    },
    eventOptions,
  );
  seek.addEventListener(
    "input",
    () => {
      if (current && Number.isFinite(audio.duration) && audio.duration > 0) {
        audio.currentTime = Math.max(
          0,
          Math.min(audio.duration, Number(seek.value) || 0),
        );
        render();
      }
    },
    eventOptions,
  );
  volume.addEventListener(
    "input",
    () => {
      audio.volume = Math.max(0, Math.min(1, Number(volume.value) / 100 || 0));
    },
    eventOptions,
  );
  close.addEventListener(
    "click",
    () => {
      root.dataset.expanded = "false";
      close.hidden = true;
      document
        .querySelector<HTMLButtonElement>('[data-primary-action="listen"]')
        ?.focus({ preventScroll: true });
    },
    eventOptions,
  );
  for (const event of [
    "play",
    "pause",
    "ended",
    "loadedmetadata",
    "durationchange",
    "timeupdate",
    "emptied",
  ]) {
    audio.addEventListener(event, render, eventOptions);
  }
  audio.addEventListener(
    "error",
    () => {
      if (current) failure = "Esta faixa não pôde ser carregada.";
      render();
    },
    eventOptions,
  );
  render();
  return {
    selectArtist(id) {
      if (disposed) return;
      selectedArtist = id;
      // Browsing another world never replaces or stops a selected music stream.
      if (!current) {
        const first = tracks.find((track) => !id || track.artistId === id);
        if (first) load(first);
      }
      render();
    },
    open() {
      if (disposed) return;
      if (!current) {
        const first = tracks.find(
          (track) => !selectedArtist || track.artistId === selectedArtist,
        );
        if (first) load(first);
      }
      root.dataset.expanded = "true";
      close.hidden = false;
      render();
      root.focus({ preventScroll: true });
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      requestVersion++;
      abort.abort();
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    },
  };
}
