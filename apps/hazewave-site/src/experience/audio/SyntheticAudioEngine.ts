import type { Track } from "../../data/catalog";

export type AudioStatus = "IDLE" | "PLAYING" | "PAUSED" | "ERROR";

export class HazewaveAudioEngine {
  private context: AudioContext | null = null;
  private master: GainNode | null = null;
  private analyser: AnalyserNode | null = null;
  private uiMaster: GainNode | null = null;
  private uiCompressor: DynamicsCompressorNode | null = null;
  private nodes: AudioScheduledSourceNode[] = [];
  private synthAuxNodes: AudioNode[] = [];
  private synthBuffers = new Map<string, AudioBuffer>();
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
      // Keep the product bus near unity so final owner-authorized media is not
      // accidentally attenuated. Synthetic fixtures are gain-staged locally.
      this.master.gain.value = 0.82;
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.minDecibels = -92;
      this.analyser.maxDecibels = -12;
      this.analyser.smoothingTimeConstant = 0.86;
      this.energyBuffer = new Uint8Array(this.analyser.frequencyBinCount);
      this.uiMaster = this.context.createGain();
      this.uiMaster.gain.value = 0.16;
      this.uiCompressor = this.context.createDynamicsCompressor();
      this.uiCompressor.threshold.value = -18;
      this.uiCompressor.knee.value = 14;
      this.uiCompressor.ratio.value = 5;
      this.uiCompressor.attack.value = 0.004;
      this.uiCompressor.release.value = 0.12;
      this.master.connect(this.analyser);
      this.analyser.connect(this.context.destination);
      this.uiMaster.connect(this.uiCompressor);
      this.uiCompressor.connect(this.context.destination);
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

  cue(kind: "SELECTED" | "CONTACT" | "EJECT", pan = 0): void {
    if (!this.context || !this.uiMaster) return;

    const ctx = this.context;
    const now = ctx.currentTime;

    const tone = ctx.createOscillator();
    const toneGain = ctx.createGain();
    const click = ctx.createBufferSource();
    const clickGain = ctx.createGain();
    const filter = ctx.createBiquadFilter();
    const cueBus = ctx.createGain();
    const panner = ctx.createStereoPanner();

    cueBus.gain.value = 1;
    panner.pan.value = Math.max(-0.72, Math.min(0.72, pan));

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

    tone.connect(toneGain).connect(cueBus);
    click.connect(filter).connect(clickGain).connect(cueBus);
    cueBus.connect(panner).connect(this.uiMaster);

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

  spectrumBands(count = 8): number[] {
    const safeCount = Math.max(1, Math.min(32, Math.floor(count)));
    if (!this.energyBuffer || this.status !== "PLAYING") {
      return Array.from({ length: safeCount }, () => 0);
    }

    const values = new Array<number>(safeCount).fill(0);
    const span = Math.max(1, Math.floor(this.energyBuffer.length / safeCount));

    for (let band = 0; band < safeCount; band += 1) {
      const start = band * span;
      const end = band === safeCount - 1
        ? this.energyBuffer.length
        : Math.min(this.energyBuffer.length, start + span);

      let total = 0;
      let samples = 0;
      for (let index = start; index < end; index += 1) {
        total += this.energyBuffer[index] ?? 0;
        samples += 1;
      }

      values[band] = samples > 0 ? total / samples / 255 : 0;
    }

    return values;
  }

  private startSynthetic(track: Track, offsetSeconds: number): void {
    const ctx = this.context!;
    const source = ctx.createBufferSource();
    const filter = ctx.createBiquadFilter();
    const dryGain = ctx.createGain();
    const wetGain = ctx.createGain();
    const delay = ctx.createDelay(0.8);
    const feedback = ctx.createGain();

    source.buffer = this.syntheticBuffer(track);
    source.loop = true;

    const profile =
      track.artistId === "aether"
        ? { cutoff: 3400, q: 0.72, dry: 0.115, wet: 0.042, delay: 0.23, feedback: 0.24 }
        : track.artistId === "monolith"
          ? { cutoff: 1850, q: 0.9, dry: 0.13, wet: 0.022, delay: 0.16, feedback: 0.16 }
          : { cutoff: 2950, q: 0.78, dry: 0.12, wet: 0.034, delay: 0.19, feedback: 0.2 };

    filter.type = "lowpass";
    filter.frequency.value = profile.cutoff;
    filter.Q.value = profile.q;

    const now = ctx.currentTime;
    dryGain.gain.setValueAtTime(0.0001, now);
    dryGain.gain.setTargetAtTime(profile.dry, now, 0.018);
    wetGain.gain.value = profile.wet;
    delay.delayTime.value = profile.delay;
    feedback.gain.value = profile.feedback;

    source.connect(filter);
    filter.connect(dryGain).connect(this.master!);
    filter.connect(delay);
    delay.connect(wetGain).connect(this.master!);
    delay.connect(feedback).connect(delay);

    const loopDuration = source.buffer?.duration ?? 1;
    const loopOffset = loopDuration > 0 ? offsetSeconds % loopDuration : 0;
    source.start(now, loopOffset);

    this.nodes = [source];
    this.synthAuxNodes = [filter, dryGain, wetGain, delay, feedback];
    this.startedAt = now - offsetSeconds;
    this.status = "PLAYING";
  }

  private syntheticBuffer(track: Track): AudioBuffer {
    const ctx = this.context!;
    const key = `${track.id}@${ctx.sampleRate}`;
    const cached = this.synthBuffers.get(key);
    if (cached) return cached;

    const sampleRate = ctx.sampleRate;
    const secondsPerBeat = 60 / Math.max(1, track.visual.bpm);
    const beats = 8;
    const duration = secondsPerBeat * beats;
    const frameCount = Math.max(1, Math.floor(duration * sampleRate));
    const buffer = ctx.createBuffer(2, frameCount, sampleRate);
    const left = buffer.getChannelData(0);
    const right = buffer.getChannelData(1);
    const base = track.audio.synthHz ?? 110;

    let seed = 2166136261;
    for (const char of track.id) {
      seed ^= char.charCodeAt(0);
      seed = Math.imul(seed, 16777619) >>> 0;
    }
    const noise = () => {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      return (seed / 0xffffffff) * 2 - 1;
    };

    const bassRatios = track.artistId === "monolith"
      ? [1, 1, 0.75, 1, 1.125, 1, 0.75, 1.25]
      : track.artistId === "flora"
        ? [1, 1.25, 1.5, 1.25, 1.125, 1.5, 1.25, 1.75]
        : [1, 1.125, 1.5, 1.25, 1, 1.334, 1.5, 1.125];

    for (let index = 0; index < frameCount; index += 1) {
      const t = index / sampleRate;
      const beatPosition = t / secondsPerBeat;
      const beatIndex = Math.floor(beatPosition) % beats;
      const beatPhase = beatPosition - Math.floor(beatPosition);
      const halfBeatPosition = beatPosition * 2;
      const halfBeatPhase = halfBeatPosition - Math.floor(halfBeatPosition);
      const barPhase = t / duration;

      const bassFrequency = base * 0.5 * (bassRatios[beatIndex] ?? 1);
      const bassEnvelope = Math.exp(-beatPhase * (track.artistId === "monolith" ? 4.6 : 5.8));
      const bass =
        Math.sin(2 * Math.PI * bassFrequency * t) *
        bassEnvelope *
        (track.artistId === "monolith" ? 0.34 : 0.2);

      const kickActive = beatIndex === 0 || beatIndex === 4 || (track.artistId === "flora" && beatIndex === 6);
      const kickEnvelope = kickActive ? Math.exp(-beatPhase * 13) : 0;
      const kickFrequency = 46 + 54 * Math.exp(-beatPhase * 7);
      const kick = Math.sin(2 * Math.PI * kickFrequency * t) * kickEnvelope * 0.31;

      const hatEnvelope = Math.exp(-halfBeatPhase * 24);
      const hatGate =
        track.artistId === "monolith"
          ? (Math.floor(halfBeatPosition) % 2 === 1 ? 1 : 0.25)
          : 0.65 + (Math.floor(halfBeatPosition) % 2) * 0.35;
      const hat = noise() * hatEnvelope * hatGate * (track.artistId === "aether" ? 0.035 : 0.052);

      const padRoot = Math.sin(2 * Math.PI * base * 0.5 * t);
      const padFifth = Math.sin(2 * Math.PI * base * 0.75 * t + 0.42);
      const padOctave = Math.sin(2 * Math.PI * base * t + 1.1);
      const slowBreath = 0.72 + Math.sin(2 * Math.PI * barPhase) * 0.18;
      const pad =
        (padRoot * 0.52 + padFifth * 0.3 + padOctave * 0.18) *
        slowBreath *
        (track.artistId === "aether" ? 0.22 : track.artistId === "flora" ? 0.13 : 0.09);

      const pluckEnvelope = Math.exp(-halfBeatPhase * 8.5);
      const pluckRatio = track.artistId === "flora" ? 2.5 : 2;
      const pluck =
        Math.sin(2 * Math.PI * base * pluckRatio * t + beatIndex * 0.37) *
        pluckEnvelope *
        (track.artistId === "flora" ? 0.11 : track.artistId === "aether" ? 0.055 : 0.025);

      const shimmer =
        Math.sin(2 * Math.PI * base * 4 * t + Math.sin(t * 0.9) * 0.8) *
        (0.5 + 0.5 * Math.sin(t * 0.73)) *
        (track.artistId === "aether" ? 0.045 : 0.012);

      const body = bass + kick + hat + pad + pluck + shimmer;
      const stereoMotion = Math.sin(2 * Math.PI * barPhase + beatIndex * 0.17) * 0.055;
      const leftSample = Math.tanh(body + shimmer * stereoMotion);
      const rightSample = Math.tanh(body - shimmer * stereoMotion + pluck * 0.035);

      left[index] = leftSample;
      right[index] = rightSample;
    }

    this.synthBuffers.set(key, buffer);
    return buffer;
  }

  private stopSynthetic(): void {
    for (const node of this.nodes) {
      try { node.stop(); } catch {}
      try { node.disconnect(); } catch {}
    }
    for (const node of this.synthAuxNodes) {
      try { node.disconnect(); } catch {}
    }
    this.nodes = [];
    this.synthAuxNodes = [];
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
