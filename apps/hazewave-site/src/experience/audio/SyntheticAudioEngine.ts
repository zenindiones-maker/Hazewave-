import type { Track } from "../../data/catalog";

export type AudioStatus = "IDLE" | "PLAYING" | "PAUSED" | "ERROR";

export class HazewaveAudioEngine {
  private context: AudioContext | null = null;
  private master: GainNode | null = null;
  private analyser: AnalyserNode | null = null;
  private uiMaster: GainNode | null = null;
  private nodes: AudioScheduledSourceNode[] = [];
  private mediaElement: HTMLAudioElement | null = null;
  private mediaSource: MediaElementAudioSourceNode | null = null;
  private preparedTrackId: string | null = null;
  private currentTrack: Track | null = null;
  private status: AudioStatus = "IDLE";
  private startedAt = 0;
  private pausedAt = 0;
  private energyBuffer: Uint8Array<ArrayBuffer> | null = null;

  get state(): AudioStatus { return this.status; }
  get track(): Track | null { return this.currentTrack; }

  async unlock(): Promise<void> {
    if (!this.context) {
      this.context = new AudioContext({ latencyHint: "interactive" });
      this.master = this.context.createGain();
      this.master.gain.value = 0.055;
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 256;
      this.energyBuffer = new Uint8Array(this.analyser.frequencyBinCount);
      this.uiMaster = this.context.createGain();
      this.uiMaster.gain.value = 0.16;
      this.master.connect(this.analyser);
      this.analyser.connect(this.context.destination);
      this.uiMaster.connect(this.context.destination);
    }
    if (this.context.state === "suspended") await this.context.resume();
  }

  async prepare(track: Track): Promise<void> {
    await this.unlock();
    if (track.audio.kind !== "media" || !track.audio.src) {
      this.preparedTrackId = track.id;
      return;
    }
    if (this.preparedTrackId === track.id && this.mediaElement) return;

    this.disposeMedia();
    const element = new Audio();
    element.preload = "auto";
    element.src = track.audio.src;
    element.crossOrigin = "anonymous";

    const source = this.context!.createMediaElementSource(element);
    source.connect(this.master!);

    this.mediaElement = element;
    this.mediaSource = source;
    this.preparedTrackId = track.id;
    element.load();
  }

  async play(track: Track, offsetSeconds = 0): Promise<void> {
    await this.prepare(track);
    this.stopSynthetic();
    this.currentTrack = track;
    this.pausedAt = Math.max(0, offsetSeconds);

    if (track.audio.kind === "media" && track.audio.src) {
      const element = this.mediaElement;
      if (!element) throw new Error("MEDIA_NOT_PREPARED");
      if (Number.isFinite(element.duration)) {
        element.currentTime = Math.min(this.pausedAt, Math.max(0, element.duration - 0.05));
      } else if (this.pausedAt > 0) {
        element.addEventListener("loadedmetadata", () => {
          element.currentTime = Math.min(this.pausedAt, Math.max(0, element.duration - 0.05));
        }, { once: true });
      }
      await element.play();
      this.startedAt = this.context!.currentTime - this.pausedAt;
      this.status = "PLAYING";
      return;
    }

    this.startSynthetic(track, this.pausedAt);
  }

  pause(): void {
    if (!this.context || this.status !== "PLAYING") return;
    this.pausedAt = this.positionSeconds();
    if (this.mediaElement && this.currentTrack?.audio.kind === "media") this.mediaElement.pause();
    this.stopSynthetic();
    this.status = "PAUSED";
  }

  async resume(): Promise<void> {
    if (!this.currentTrack || this.status !== "PAUSED") return;
    await this.play(this.currentTrack, this.pausedAt);
  }

  stop(): void {
    this.stopSynthetic();
    if (this.mediaElement) {
      this.mediaElement.pause();
      this.mediaElement.currentTime = 0;
    }
    this.status = "IDLE";
    this.pausedAt = 0;
  }

  positionSeconds(): number {
    if (!this.context) return 0;
    if (this.currentTrack?.audio.kind === "media" && this.mediaElement) return this.mediaElement.currentTime || 0;
    if (this.status === "PAUSED") return this.pausedAt;
    if (this.status === "PLAYING") return Math.max(0, this.context.currentTime - this.startedAt);
    return 0;
  }

  async seek(seconds: number): Promise<void> {
    if (!this.currentTrack) return;
    const clamped = Math.max(0, Math.min(seconds, this.currentTrack.durationSeconds));
    if (this.currentTrack.audio.kind === "media" && this.mediaElement) {
      this.mediaElement.currentTime = clamped;
      this.pausedAt = clamped;
      return;
    }
    await this.play(this.currentTrack, clamped);
  }

  cue(kind: "SELECTED" | "CONTACT" | "EJECT"): void {
    if (!this.context || !this.uiMaster) return;

    const ctx = this.context;
    const now = ctx.currentTime;

    const tone = ctx.createOscillator();
    const toneGain = ctx.createGain();
    const click = ctx.createBufferSource();
    const clickGain = ctx.createGain();
    const filter = ctx.createBiquadFilter();

    const noise = ctx.createBuffer(1, Math.max(1, Math.floor(ctx.sampleRate * 0.045)), ctx.sampleRate);
    const channel = noise.getChannelData(0);
    for (let i = 0; i < channel.length; i += 1) {
      const envelope = Math.pow(1 - i / channel.length, 2.8);
      channel[i] = (Math.random() * 2 - 1) * envelope;
    }

    click.buffer = noise;
    filter.type = "bandpass";

    if (kind === "SELECTED") {
      tone.type = "sine";
      tone.frequency.setValueAtTime(190, now);
      tone.frequency.exponentialRampToValueAtTime(260, now + 0.12);
      toneGain.gain.setValueAtTime(0.0001, now);
      toneGain.gain.exponentialRampToValueAtTime(0.09, now + 0.018);
      toneGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.14);
      filter.frequency.value = 2200;
      clickGain.gain.setValueAtTime(0.035, now);
      clickGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.05);
    } else if (kind === "CONTACT") {
      tone.type = "triangle";
      tone.frequency.setValueAtTime(92, now);
      tone.frequency.exponentialRampToValueAtTime(62, now + 0.12);
      toneGain.gain.setValueAtTime(0.0001, now);
      toneGain.gain.exponentialRampToValueAtTime(0.16, now + 0.008);
      toneGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.18);
      filter.frequency.value = 3800;
      clickGain.gain.setValueAtTime(0.085, now);
      clickGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.045);
    } else {
      tone.type = "sine";
      tone.frequency.setValueAtTime(165, now);
      tone.frequency.exponentialRampToValueAtTime(118, now + 0.09);
      toneGain.gain.setValueAtTime(0.0001, now);
      toneGain.gain.exponentialRampToValueAtTime(0.07, now + 0.01);
      toneGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.11);
      filter.frequency.value = 1600;
      clickGain.gain.setValueAtTime(0.045, now);
      clickGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.04);
    }

    tone.connect(toneGain).connect(this.uiMaster);
    click.connect(filter).connect(clickGain).connect(this.uiMaster);

    tone.start(now);
    tone.stop(now + 0.22);
    click.start(now);
  }

  energy(): number {
    if (!this.analyser || !this.energyBuffer || this.status !== "PLAYING") return 0;
    this.analyser.getByteFrequencyData(this.energyBuffer);
    let total = 0;
    for (let i = 0; i < this.energyBuffer.length; i += 1) total += this.energyBuffer[i] ?? 0;
    return total / this.energyBuffer.length / 255;
  }

  private startSynthetic(track: Track, offsetSeconds: number): void {
    const ctx = this.context!;
    const base = track.audio.synthHz ?? 110;
    const beat = 60 / track.visual.bpm;

    const carrier = ctx.createOscillator();
    carrier.type = "triangle";
    carrier.frequency.value = base;
    const upper = ctx.createOscillator();
    upper.type = "sine";
    upper.frequency.value = base * 1.5;
    const carrierGain = ctx.createGain();
    carrierGain.gain.value = 0.62;
    const upperGain = ctx.createGain();
    upperGain.gain.value = 0.22;
    const pulse = ctx.createOscillator();
    pulse.type = "sine";
    pulse.frequency.value = 1 / beat;
    const pulseGain = ctx.createGain();
    pulseGain.gain.value = 0.12;

    pulse.connect(pulseGain);
    pulseGain.connect(carrierGain.gain);
    carrier.connect(carrierGain).connect(this.master!);
    upper.connect(upperGain).connect(this.master!);

    const now = ctx.currentTime;
    carrier.start(now);
    upper.start(now);
    pulse.start(now);
    this.nodes = [carrier, upper, pulse];
    this.startedAt = now - offsetSeconds;
    this.status = "PLAYING";
  }

  private stopSynthetic(): void {
    for (const node of this.nodes) {
      try { node.stop(); } catch {}
      try { node.disconnect(); } catch {}
    }
    this.nodes = [];
  }

  private disposeMedia(): void {
    if (this.mediaElement) {
      this.mediaElement.pause();
      this.mediaElement.removeAttribute("src");
      this.mediaElement.load();
    }
    try { this.mediaSource?.disconnect(); } catch {}
    this.mediaElement = null;
    this.mediaSource = null;
  }
}
