import { artists, type ArtistId, type Track } from "./catalog";

export type ArtistChapterAuthority = "DEMO_ONLY" | "OWNER_CONFIRMED";

export interface ArtistChapterWorld {
  accent: string;
  secondary: string;
  background: string;
  fogDensity: number;
  waterResponse: number;
  particleResponse: number;
  lightResponse: number;
  cameraDrift: number;
  transitionSignature: "REFRACT" | "WEIGHT" | "GROW";
}

export interface ArtistChapter {
  id: ArtistId;
  authority: ArtistChapterAuthority;
  displayName: string;
  releaseLabel: string;
  logoAsset: string | null;
  portraitAsset: string | null;
  biography: string | null;
  videoSource: string | null;
  links: readonly string[];
  merchRelation: readonly string[];
  tracks: readonly Track[];
  world: ArtistChapterWorld;
}

const behaviorByArtist: Record<
  ArtistId,
  Pick<
    ArtistChapterWorld,
    "waterResponse" | "particleResponse" | "lightResponse" | "transitionSignature"
  >
> = {
  aether: {
    waterResponse: 0.72,
    particleResponse: 0.5,
    lightResponse: 0.68,
    transitionSignature: "REFRACT"
  },
  monolith: {
    waterResponse: 0.34,
    particleResponse: 0.2,
    lightResponse: 0.42,
    transitionSignature: "WEIGHT"
  },
  flora: {
    waterResponse: 0.58,
    particleResponse: 0.74,
    lightResponse: 0.56,
    transitionSignature: "GROW"
  }
};

/**
 * Demo artist chapters exist only to exercise the experience architecture.
 *
 * The owner-authorized production roster remains UNSET in productionAuthority.ts.
 * No logo, portrait, biography, clip, social mapping or merch relation is inferred.
 */
export const artistChapters: readonly ArtistChapter[] = artists.map((artist) => {
  const behavior = behaviorByArtist[artist.id];

  return {
    id: artist.id,
    authority: "DEMO_ONLY",
    displayName: artist.name.replace(" / DEMO", ""),
    releaseLabel: artist.releaseTitle,
    logoAsset: null,
    portraitAsset: null,
    biography: null,
    videoSource: null,
    links: [],
    merchRelation: [],
    tracks: artist.tracks,
    world: {
      accent: artist.identity.accent,
      secondary: artist.identity.secondary,
      background: artist.identity.background,
      fogDensity: artist.identity.world.fogDensity,
      waterResponse: behavior.waterResponse,
      particleResponse: behavior.particleResponse,
      lightResponse: behavior.lightResponse,
      cameraDrift: artist.identity.world.cameraDrift,
      transitionSignature: behavior.transitionSignature
    }
  };
});
