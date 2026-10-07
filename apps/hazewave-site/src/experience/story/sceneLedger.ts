export interface WorldFrame {
  scale: number;
  translateX: number;
  translateY: number;
  rotate: number;
  brightness: number;
  saturation: number;
  contrast: number;
  vignette: number;
  water: number;
  fog: number;
  lighthouse: number;
  depth: number;
  particles: number;
}

export interface StoryChapter {
  id: "threshold" | "archive" | "artists" | "dossiers" | "merch" | "network";
  selector: string;
  label: string;
  narrativeBeat:
    | "WORLD_SLEEP"
    | "WORLD_AWAKENING"
    | "ARTIST_DISCOVERY"
    | "ARTIST_FOCUS"
    | "MERCH_APPROACH"
    | "FINAL_DESCENT";
  world: WorldFrame;
}

/**
 * Persistent-world scene ledger.
 *
 * These are art-direction states, not independent scenes. ScrollConductor
 * interpolates between adjacent entries so the owner-supplied artwork remains
 * one continuous universe from threshold to final descent.
 */
export const sceneLedger: StoryChapter[] = [
  {
    id: "threshold",
    selector: ".archive-hero",
    label: "THRESHOLD",
    narrativeBeat: "WORLD_SLEEP",
    world: {
      scale: 1,
      translateX: 0,
      translateY: 0,
      rotate: 0,
      brightness: 0.9,
      saturation: 0.9,
      contrast: 1.02,
      vignette: 0.2,
      water: 0.12,
      fog: 0.08,
      lighthouse: 0.08,
      depth: 0.06,
      particles: 0
    }
  },
  {
    id: "archive",
    selector: "#archive",
    label: "ARCHIVE",
    narrativeBeat: "WORLD_AWAKENING",
    world: {
      scale: 1.045,
      translateX: -0.45,
      translateY: -1.7,
      rotate: -0.09,
      brightness: 0.96,
      saturation: 1.02,
      contrast: 1.04,
      vignette: 0.25,
      water: 0.48,
      fog: 0.18,
      lighthouse: 0.42,
      depth: 0.32,
      particles: 0.08
    }
  },
  {
    id: "artists",
    selector: "#artist-worlds",
    label: "ARTIST WORLDS",
    narrativeBeat: "ARTIST_DISCOVERY",
    world: {
      scale: 1.075,
      translateX: 0.7,
      translateY: -3.4,
      rotate: 0.12,
      brightness: 0.94,
      saturation: 1.08,
      contrast: 1.06,
      vignette: 0.3,
      water: 0.62,
      fog: 0.28,
      lighthouse: 0.58,
      depth: 0.46,
      particles: 0.2
    }
  },
  {
    id: "dossiers",
    selector: "#dossiers",
    label: "DOSSIERS",
    narrativeBeat: "ARTIST_FOCUS",
    world: {
      scale: 1.105,
      translateX: -0.62,
      translateY: -5.2,
      rotate: -0.08,
      brightness: 0.89,
      saturation: 1.03,
      contrast: 1.09,
      vignette: 0.36,
      water: 0.7,
      fog: 0.34,
      lighthouse: 0.66,
      depth: 0.56,
      particles: 0.26
    }
  },
  {
    id: "merch",
    selector: "#objects",
    label: "OBJECTS",
    narrativeBeat: "MERCH_APPROACH",
    world: {
      scale: 1.135,
      translateX: 0.85,
      translateY: -7.5,
      rotate: 0.06,
      brightness: 0.84,
      saturation: 1.07,
      contrast: 1.1,
      vignette: 0.43,
      water: 0.54,
      fog: 0.28,
      lighthouse: 0.78,
      depth: 0.48,
      particles: 0.16
    }
  },
  {
    id: "network",
    selector: "#network",
    label: "NETWORK",
    narrativeBeat: "FINAL_DESCENT",
    world: {
      scale: 1.16,
      translateX: 0,
      translateY: -9.4,
      rotate: 0,
      brightness: 0.77,
      saturation: 0.94,
      contrast: 1.12,
      vignette: 0.52,
      water: 0.24,
      fog: 0.16,
      lighthouse: 0.88,
      depth: 0.34,
      particles: 0.05
    }
  }
];
