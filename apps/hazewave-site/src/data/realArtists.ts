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
  color: string;
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
    signal: { desktop: [0.22, 0.42], mobile: [0.24, 0.34] },
    worldSystem: "pressure-type",
    color: "#deded1",
    artwork: "/media/artists/barak-ozama-beats.png",
    artworkAlt: "Arte original fornecida pelo artista",
    provenance: "Owner source 1000788665.png; original bytes preserved.",
    materializedWorld: true,
  },
  {
    id: "indionesbala",
    name: "Indionesbala",
    signal: { desktop: [0.75, 0.27], mobile: [0.72, 0.25] },
    worldSystem: "heat-type",
    color: "#ffa22c",
    artwork: "/media/artists/indionesbala.webp",
    artworkAlt: "Arte original fornecida pelo artista",
    provenance: "Owner source 1001044236(1).webp; original bytes preserved.",
    materializedWorld: true,
  },
  {
    id: "baazu",
    name: "Baazü",
    signal: { desktop: [0.29, 0.68], mobile: [0.24, 0.6] },
    worldSystem: "blue-illustration",
    color: "#a4d5e9",
    artwork: "/media/artists/baazu.png",
    artworkAlt: "Arte original fornecida pelo artista",
    provenance: "Owner source 1000788325(2).png; original bytes preserved.",
    materializedWorld: true,
  },
  {
    id: "aquaverno",
    name: "Aquaverno",
    signal: { desktop: [0.8, 0.51], mobile: [0.7, 0.46] },
    worldSystem: "tidal-depth",
    color: "#efcfa2",
    artwork: "/media/artists/aquaverno.jpg",
    artworkAlt: "Arte oficial fornecida pelo owner para Aquaverno",
    provenance: "Owner source 1001084342.jpg ; original bytes preserved.",
    materializedWorld: true,
  },
  {
    id: "hemorragia-cosmica",
    name: "Hemorragia Cósmica",
    signal: { desktop: [0.74, 0.75], mobile: [0.7, 0.66] },
    worldSystem: "pressure-wire",
    color: "#efcb32",
    artwork: "/media/artists/hemorragia-cosmica.jpg",
    artworkAlt: "Arte oficial fornecida pelo owner para Hemorragia Cósmica",
    provenance:
      "Owner clean source 1001084321.jpg ; original bytes preserved. Phone screenshot excluded.",
    materializedWorld: true,
  },
] as const;

export const materializedWorldArtists = realArtists.filter(
  (artist) => artist.materializedWorld,
);

export function getRealArtist(
  id: string | null,
): RealArtistVisualAuthority | null {
  if (!id) return null;
  return realArtists.find((artist) => artist.id === id) ?? null;
}
