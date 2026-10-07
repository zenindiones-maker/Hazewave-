export type RealArtistId =
  | "barak-ozama-beats"
  | "indionesbala"
  | "baazu"
  | "aquaverno"
  | "hemorragia-cosmica";

export type WorldSystem =
  | "pressure-type"
  | "heat-type"
  | "blue-illustration"
  | "tidal-depth"
  | "pressure-wire";

export interface RealArtistVisualAuthority {
  id: RealArtistId;
  name: string;
  signal: {
    desktop: readonly [number, number];
    mobile: readonly [number, number];
  };
  worldSystem: WorldSystem;
  artwork: string | null;
  artworkAlt: string;
  provenance: string;
  materializedWorld: boolean;
}

/**
 * Owner-authority manifest for the Living Resonance Field.
 *
 * This contains visual identity only. It deliberately contains no invented
 * biography, release, track, event, collaboration, merch or social mapping.
 * Missing factual surfaces remain absent until owner-authorized.
 */
export const realArtists: readonly RealArtistVisualAuthority[] = [
  {
    id: "barak-ozama-beats",
    name: "Barak Ozama Beats",
    signal: { desktop: [0.18, 0.58], mobile: [0.24, 0.63] },
    worldSystem: "pressure-type",
    artwork: null,
    artworkAlt: "",
    provenance: "Owner-supplied visual asset confirmed; production derivative not yet materialized in this bounded slice.",
    materializedWorld: false
  },
  {
    id: "indionesbala",
    name: "Indionesbala",
    signal: { desktop: [0.36, 0.34], mobile: [0.7, 0.32] },
    worldSystem: "heat-type",
    artwork: null,
    artworkAlt: "",
    provenance: "Owner-supplied visual asset confirmed; production derivative not yet materialized in this bounded slice.",
    materializedWorld: false
  },
  {
    id: "baazu",
    name: "Baazü",
    signal: { desktop: [0.52, 0.7], mobile: [0.38, 0.78] },
    worldSystem: "blue-illustration",
    artwork: null,
    artworkAlt: "",
    provenance: "Owner-supplied visual assets confirmed; production derivatives not yet materialized in this bounded slice.",
    materializedWorld: false
  },
  {
    id: "aquaverno",
    name: "Aquaverno",
    signal: { desktop: [0.72, 0.5], mobile: [0.54, 0.46] },
    worldSystem: "tidal-depth",
    artwork: "/media/artists/aquaverno.webp",
    artworkAlt: "Arte oficial fornecida pelo owner para Aquaverno",
    provenance: "Owner source 1001084342.jpg → bounded WebP derivative; source composition preserved.",
    materializedWorld: true
  },
  {
    id: "hemorragia-cosmica",
    name: "Hemorragia Cósmica",
    signal: { desktop: [0.84, 0.72], mobile: [0.76, 0.7] },
    worldSystem: "pressure-wire",
    artwork: "/media/artists/hemorragia-cosmica.webp",
    artworkAlt: "Arte oficial fornecida pelo owner para Hemorragia Cósmica",
    provenance: "Owner clean source 1001084321.jpg → bounded WebP derivative; phone screenshot explicitly excluded.",
    materializedWorld: true
  }
] as const;

export const materializedWorldArtists = realArtists.filter(
  (artist) => artist.materializedWorld
);

export function getRealArtist(id: string | null): RealArtistVisualAuthority | null {
  if (!id) return null;
  return realArtists.find((artist) => artist.id === id) ?? null;
}
