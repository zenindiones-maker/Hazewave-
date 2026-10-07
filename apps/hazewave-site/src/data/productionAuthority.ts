export type AuthorityState =
  | "OWNER_CONFIRMED"
  | "DEMO_ONLY"
  | "UNSET";

export interface AuthorityValue<T> {
  state: AuthorityState;
  value: T | null;
  provenance: string;
}

export interface ProductionArtistRecord {
  id: string;
  canonicalName: AuthorityValue<string>;
  instagramHandle: AuthorityValue<string>;
  portraitAsset: AuthorityValue<string>;
  biography: AuthorityValue<string>;
  releases: AuthorityValue<string[]>;
  trackIds: AuthorityValue<string[]>;
  videoUrls: AuthorityValue<string[]>;
  merchIds: AuthorityValue<string[]>;
}

/**
 * Production-content authority manifest.
 *
 * This file intentionally separates facts the owner has explicitly supplied
 * from demo data used to exercise the interaction system. WAVE must never
 * promote DEMO_ONLY or UNSET values into public factual claims.
 */
export const productionIdentity = {
  projectName: {
    state: "OWNER_CONFIRMED",
    value: "HAZEWAVE",
    provenance: "Owner-supplied site direction."
  },
  locationLine: {
    state: "OWNER_CONFIRMED",
    value: "Núcleo Sonoro Independente | Santos 2021—",
    provenance: "Owner-supplied hero direction."
  },
  worldArtwork: {
    state: "OWNER_CONFIRMED",
    value: "/media/hazewave-world.jpg.webp",
    provenance: "Owner-supplied Hazewave lighthouse artwork; exact visual is the persistent world substrate."
  },
  finalArtistRoster: {
    state: "UNSET",
    value: null,
    provenance: "Owner has not yet supplied the authoritative final roster/data pack."
  },
  finalAudioCatalog: {
    state: "UNSET",
    value: null,
    provenance: "Owner-authorized final audio has not yet been supplied to this site mission."
  },
  finalVideoCatalog: {
    state: "UNSET",
    value: null,
    provenance: "No owner-authorized final clip/video IDs have been supplied."
  },
  finalMerchPricing: {
    state: "UNSET",
    value: null,
    provenance: "Concept products exist, but final prices/availability are not authoritative."
  },
  whatsappDestination: {
    state: "UNSET",
    value: null,
    provenance: "No owner-confirmed WhatsApp number has been supplied; do not fabricate one."
  }
} as const satisfies Record<string, AuthorityValue<unknown>>;

export const ownerConfirmedSocialHandles = [
  {
    handle: "@virundun",
    state: "OWNER_CONFIRMED",
    provenance: "Owner supplied for the Hazewave network footer."
  },
  {
    handle: "@barakozamabeats",
    state: "OWNER_CONFIRMED",
    provenance: "Owner supplied for the Hazewave network footer."
  },
  {
    handle: "@indionesbala",
    state: "OWNER_CONFIRMED",
    provenance: "Owner supplied for the Hazewave network footer."
  }
] as const;

/**
 * No relationship mapping is inferred from a social handle alone.
 * The owner can later promote records into the final artist roster explicitly.
 */
export const productionArtists: ProductionArtistRecord[] = [];

export function assertProductionAuthority(): void {
  const forbidden = productionArtists.filter((artist) =>
    [
      artist.canonicalName,
      artist.instagramHandle,
      artist.portraitAsset,
      artist.biography,
      artist.releases,
      artist.trackIds,
      artist.videoUrls,
      artist.merchIds
    ].some((field) => field.state !== "OWNER_CONFIRMED")
  );

  if (forbidden.length > 0) {
    throw new Error(
      `PRODUCTION_CONTENT_AUTHORITY_VIOLATION:${forbidden
        .map((artist) => artist.id)
        .join(",")}`
    );
  }
}
