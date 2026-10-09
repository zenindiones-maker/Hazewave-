/**
 * Diegetic interference. Silent until a gesture. Scroll then sweeps the partials.
 * No audio file, no autoplay.
 */
export interface InterferenceVoice {
  toggle(): boolean;
  follow(progress: number): void;
  destroy(): void;
}

export function createInterferenceVoice(): InterferenceVoice {
  let context: AudioContext | null = null;
  let master: GainNode | null = null;
  let filter: BiquadFilterNode | null = null;
  let fundamental: OscillatorNode | null = null;
  let partial: OscillatorNode | null = null;
  let enabled = false;

  function ensure(): AudioContext {
    if (context) return context;
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    context = new Ctx();
    master = context.createGain();
    master.gain.value = 0;
    fundamental = context.createOscillator();
    fundamental.type = "sine";
    fundamental.frequency.value = 55;
    partial = context.createOscillator();
    partial.type = "triangle";
    partial.frequency.value = 82.5;
    filter = context.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = 240;
    filter.Q.value = 5.5;
    const length = Math.floor(context.sampleRate * 2);
    const buffer = context.createBuffer(1, length, context.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
    const noise = context.createBufferSource();
    noise.buffer = buffer;
    noise.loop = true;
    const noiseGain = context.createGain();
    noiseGain.gain.value = 0.22;
    fundamental.connect(master);
    partial.connect(master);
    noise.connect(noiseGain);
    noiseGain.connect(filter);
    filter.connect(master);
    master.connect(context.destination);
    fundamental.start();
    partial.start();
    noise.start();
    return context;
  }

  return {
    toggle() {
      const ctx = ensure();
      if (ctx.state === "suspended") void ctx.resume();
      enabled = !enabled;
      master?.gain.setTargetAtTime(enabled ? 0.06 : 0, ctx.currentTime, 0.06);
      return enabled;
    },
    follow(progress: number) {
      if (!context || !enabled || !filter || !fundamental || !partial) return;
      const now = context.currentTime;
      const sweep = 160 + progress * 2800;
      filter.frequency.setTargetAtTime(sweep, now, 0.08);
      fundamental.frequency.setTargetAtTime(46 + progress * 18, now, 0.12);
      partial.frequency.setTargetAtTime(70 + Math.sin(progress * Math.PI) * 90, now, 0.1);
    },
    destroy() {
      if (!context) return;
      void context.close();
      context = null;
      enabled = false;
    },
  };
}
