export interface WorldFrame {
  scale: number;
  translateX: number;
  translateY: number;
  rotate: number;
  brightness: number;
  saturation: number;
  contrast: number;
  vignette: number;
}

export interface StoryChapter {
  id: "threshold" | "archive" | "artists" | "dossiers" | "merch" | "network";
  selector: string;
  label: string;
  world: WorldFrame;
}

export const sceneLedger: StoryChapter[] = [
  {
    id: "threshold",
    selector: ".archive-hero",
    label: "THRESHOLD",
    world: {
      scale: 1,
      translateX: 0,
      translateY: 0,
      rotate: 0,
      brightness: 1,
      saturation: 1,
      contrast: 1,
      vignette: 0.18
    }
  },
  {
    id: "archive",
    selector: "#archive",
    label: "ARCHIVE",
    world: {
      scale: 1.065,
      translateX: -0.8,
      translateY: -2.8,
      rotate: -0.18,
      brightness: 0.92,
      saturation: 1.08,
      contrast: 1.05,
      vignette: 0.28
    }
  },
  {
    id: "artists",
    selector: ".artist-index",
    label: "ARTIST WORLDS",
    world: {
      scale: 1.105,
      translateX: 1.4,
      translateY: -5.2,
      rotate: 0.24,
      brightness: 0.88,
      saturation: 1.12,
      contrast: 1.08,
      vignette: 0.34
    }
  },
  {
    id: "dossiers",
    selector: ".dossier-zone",
    label: "DOSSIERS",
    world: {
      scale: 1.145,
      translateX: -1.2,
      translateY: -7.2,
      rotate: -0.16,
      brightness: 0.82,
      saturation: 1.04,
      contrast: 1.12,
      vignette: 0.42
    }
  },
  {
    id: "merch",
    selector: ".merch-zone",
    label: "OBJECTS",
    world: {
      scale: 1.19,
      translateX: 1.7,
      translateY: -9.8,
      rotate: 0.12,
      brightness: 0.78,
      saturation: 1.16,
      contrast: 1.12,
      vignette: 0.48
    }
  },
  {
    id: "network",
    selector: ".social-footer",
    label: "NETWORK",
    world: {
      scale: 1.23,
      translateX: 0,
      translateY: -12.5,
      rotate: 0,
      brightness: 0.72,
      saturation: 0.96,
      contrast: 1.16,
      vignette: 0.56
    }
  }
];
