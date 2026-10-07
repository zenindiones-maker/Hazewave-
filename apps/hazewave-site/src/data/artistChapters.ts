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
  focusPoint: readonly [number, number];
  focusZoom: number;
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
    | "waterResponse"
    | "particleResponse"
    | "lightResponse"
    | "focusPoint"
    | "focusZoom"
    | "transitionSignature"
  >
> = {
  aether: {
    waterResponse: 0.72,
    particleResponse: 0.5,
    lightResponse: 0.68,
    focusPoint: [0.43, 0.47],
    focusZoom: 0.028,
    transitionSignature: "REFRACT"
  },
  monolith: {
    waterResponse: 0.34,
    particleResponse: 0.2,
    lightResponse: 0.42,
    focusPoint: [0.57, 0.45],
    focusZoom: 0.019,
    transitionSignature: "WEIGHT"
  },
  flora: {
    waterResponse: 0.58,
    particleResponse: 0.74,
    lightResponse: 0.56,
    focusPoint: [0.5, 0.41],
    focusZoom: 0.024,
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
      focusPoint: behavior.focusPoint,
      focusZoom: behavior.focusZoom,
      transitionSignature: behavior.transitionSignature
    }
  };
});
