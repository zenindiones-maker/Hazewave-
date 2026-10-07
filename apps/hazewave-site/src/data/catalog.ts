export type ArtistId = "aether" | "monolith" | "flora";

export interface VisualIdentity {
  background: string;
  accent: string;
  secondary: string;
  metalness: number;
  roughness: number;
}

export interface AudioSource {
  kind: "synthetic-fixture" | "media";
  src?: string;
  mime?: string;
  synthHz?: number;
}

export interface VisualMusicManifest {
  bpm: number;
  energy: number;
  onsetDensity: number;
  sections: Array<{ at: number; kind: "intro" | "verse" | "break" | "chorus" | "outro" }>;
  motifs: string[];
}

export interface Track {
  id: string;
  artistId: ArtistId;
  releaseId: string;
  title: string;
  durationSeconds: number;
  audio: AudioSource;
  visual: VisualMusicManifest;
  rights: {
    class: "SYNTHETIC_DEMO" | "OWNER_AUTHORIZED";
    provenance: string;
  };
}

export interface Artist {
  id: ArtistId;
  name: string;
  releaseTitle: string;
  identity: VisualIdentity;
  tracks: Track[];
}

export const artists: Artist[] = [
  {
    id: "aether",
    name: "AETHER / DEMO",
    releaseTitle: "Glass Signal",
    identity: { background: "#071111", accent: "#a7ffe0", secondary: "#47786f", metalness: 0.72, roughness: 0.2 },
    tracks: [
      {
        id: "aether-01", artistId: "aether", releaseId: "glass-signal", title: "Pale Current", durationSeconds: 24,
        audio: { kind: "synthetic-fixture", synthHz: 110 },
        visual: { bpm: 92, energy: 0.58, onsetDensity: 0.42, sections: [{ at: 0, kind: "intro" }, { at: 8, kind: "chorus" }, { at: 18, kind: "outro" }], motifs: ["glass", "current"] },
        rights: { class: "SYNTHETIC_DEMO", provenance: "Generated in-browser from Web Audio oscillators; no external recording." }
      },
      {
        id: "aether-02", artistId: "aether", releaseId: "glass-signal", title: "Soft Voltage", durationSeconds: 24,
        audio: { kind: "synthetic-fixture", synthHz: 146.83 },
        visual: { bpm: 108, energy: 0.66, onsetDensity: 0.5, sections: [{ at: 0, kind: "intro" }, { at: 7, kind: "verse" }, { at: 15, kind: "chorus" }], motifs: ["voltage", "mist"] },
        rights: { class: "SYNTHETIC_DEMO", provenance: "Generated in-browser from Web Audio oscillators; no external recording." }
      }
    ]
  },
  {
    id: "monolith",
    name: "MONOLITH / DEMO",
    releaseTitle: "Pressure Memory",
    identity: { background: "#0b0b0e", accent: "#e8d9c5", secondary: "#655a54", metalness: 0.9, roughness: 0.34 },
    tracks: [
      {
        id: "monolith-01", artistId: "monolith", releaseId: "pressure-memory", title: "Weightless Iron", durationSeconds: 24,
        audio: { kind: "synthetic-fixture", synthHz: 82.41 },
        visual: { bpm: 76, energy: 0.78, onsetDensity: 0.31, sections: [{ at: 0, kind: "intro" }, { at: 9, kind: "break" }, { at: 14, kind: "chorus" }], motifs: ["iron", "pressure"] },
        rights: { class: "SYNTHETIC_DEMO", provenance: "Generated in-browser from Web Audio oscillators; no external recording." }
      },
      {
        id: "monolith-02", artistId: "monolith", releaseId: "pressure-memory", title: "Fault Line", durationSeconds: 24,
        audio: { kind: "synthetic-fixture", synthHz: 98 },
        visual: { bpm: 84, energy: 0.86, onsetDensity: 0.55, sections: [{ at: 0, kind: "intro" }, { at: 6, kind: "verse" }, { at: 16, kind: "break" }], motifs: ["fault", "mass"] },
        rights: { class: "SYNTHETIC_DEMO", provenance: "Generated in-browser from Web Audio oscillators; no external recording." }
      }
    ]
  },
  {
    id: "flora",
    name: "FLORA / DEMO",
    releaseTitle: "Living Static",
    identity: { background: "#101209", accent: "#d8ff7a", secondary: "#728849", metalness: 0.38, roughness: 0.48 },
    tracks: [
      {
        id: "flora-01", artistId: "flora", releaseId: "living-static", title: "Moss Circuit", durationSeconds: 24,
        audio: { kind: "synthetic-fixture", synthHz: 130.81 },
        visual: { bpm: 118, energy: 0.72, onsetDensity: 0.65, sections: [{ at: 0, kind: "intro" }, { at: 8, kind: "chorus" }, { at: 17, kind: "outro" }], motifs: ["moss", "circuit"] },
        rights: { class: "SYNTHETIC_DEMO", provenance: "Generated in-browser from Web Audio oscillators; no external recording." }
      },
      {
        id: "flora-02", artistId: "flora", releaseId: "living-static", title: "Root Signal", durationSeconds: 24,
        audio: { kind: "synthetic-fixture", synthHz: 164.81 },
        visual: { bpm: 124, energy: 0.81, onsetDensity: 0.7, sections: [{ at: 0, kind: "intro" }, { at: 5, kind: "verse" }, { at: 13, kind: "chorus" }], motifs: ["root", "signal"] },
        rights: { class: "SYNTHETIC_DEMO", provenance: "Generated in-browser from Web Audio oscillators; no external recording." }
      }
    ]
  }
];

export const tracks = artists.flatMap((artist) => artist.tracks);

export function getTrack(trackId: string): Track {
  const track = tracks.find((candidate) => candidate.id === trackId);
  if (!track) throw new Error(`UNKNOWN_TRACK:${trackId}`);
  return track;
}

export function getArtist(artistId: ArtistId): Artist {
  const artist = artists.find((candidate) => candidate.id === artistId);
  if (!artist) throw new Error(`UNKNOWN_ARTIST:${artistId}`);
  return artist;
}
