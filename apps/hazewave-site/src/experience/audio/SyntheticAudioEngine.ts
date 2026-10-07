import type { Track } from "../../data/catalog";

export type AudioStatus = "IDLE" | "PLAYING" | "PAUSED" | "ERROR";

export class SyntheticAudioEngine {
  private context: AudioContext | null = null;
  private master: GainNode | null = null;
  private analyser: AnalyserNode | null = null;
  private nodes: AudioScheduledSourceNode[] = [];
  private currentTrack: Track | null = null;
  private status: AudioStatus = "IDLE";
  private startedAt = 0;
  private pausedAt = 0;
  private energyBuffer: Uint8Array<ArrayBuffer> | null = null;

  get state(): AudioStatus {
    return this.status;
  }

  get track(): Track | null {
    return this.currentTrack;
  }

  async unlock(): Promise<void> {
    if (!this.context) {
      this.context = new AudioContext({ latencyHint: "interactive" });
      this.master = this.context.createGain();
      this.master.gain.value = 0.055;
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 256;
      this.energyBuffer = new Uint8Array(this.analyser.frequencyBinCount);
      this.master.connect(this.analyser);
      this.analyser.connect(this.context.destination);
    }
    if (this.context.state === "suspended") await this.context.resume();
  }

  async play(track: Track, offsetSeconds = 0): Promise<void> {
    await this.unlock();
    this.stopNodes();
    this.currentTrack = track;
    this.pausedAt = Math.max(0, offsetSeconds);
    const ctx = this.context!;
    const master = this.master!;
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
    carrier.connect(carrierGain).connect(master);
    upper.connect(upperGain).connect(master);

    const now = ctx.currentTime;
    carrier.start(now);
    upper.start(now);
    pulse.start(now);

    this.nodes = [carrier, upper, pulse];
    this.startedAt = now - offsetSeconds;
    this.status = "PLAYING";
  }

  pause(): void {
    if (!this.context || this.status !== "PLAYING") return;
    this.pausedAt = Math.max(0, this.context.currentTime - this.startedAt);
    this.stopNodes();
    this.status = "PAUSED";
  }

  async resume(): Promise<void> {
    if (!this.currentTrack || this.status !== "PAUSED") return;
    await this.play(this.currentTrack, this.pausedAt);
  }

  stop(): void {
    this.stopNodes();
    this.status = "IDLE";
    this.pausedAt = 0;
  }

  positionSeconds(): number {
    if (!this.context) return 0;
    if (this.status === "PAUSED") return this.pausedAt;
    if (this.status === "PLAYING") return Math.max(0, this.context.currentTime - this.startedAt);
    return 0;
  }

  seek(seconds: number): Promise<void> {
    if (!this.currentTrack) return Promise.resolve();
    const clamped = Math.max(0, Math.min(seconds, this.currentTrack.durationSeconds));
    return this.play(this.currentTrack, clamped);
  }

  energy(): number {
    if (!this.analyser || !this.energyBuffer || this.status !== "PLAYING") return 0;
    this.analyser.getByteFrequencyData(this.energyBuffer);
    let total = 0;
    for (let i = 0; i < this.energyBuffer.length; i += 1) total += this.energyBuffer[i] ?? 0;
    return total / this.energyBuffer.length / 255;
  }

  private stopNodes(): void {
    for (const node of this.nodes) {
      try { node.stop(); } catch { /* already stopped */ }
      try { node.disconnect(); } catch { /* already disconnected */ }
    }
    this.nodes = [];
  }
}
