import type { Track, VisualMusicManifest } from "../../data/catalog";

export interface WaveVisualState {
  trackId: string;
  bpm: number;
  energy: number;
  onsetDensity: number;
  sectionCount: number;
  motifs: readonly string[];
}

export function bridgeFixtureManifest(track: Track): WaveVisualState {
  const manifest: VisualMusicManifest = track.visual;
  return {
    trackId: track.id,
    bpm: manifest.bpm,
    energy: manifest.energy,
    onsetDensity: manifest.onsetDensity,
    sectionCount: manifest.sections.length,
    motifs: manifest.motifs
  };
}
