/** Single artist authorized for the public site. Preserve other owner art in source history only. */
export const PUBLIC_ARTISTS = [
  { slug: "indionesbala", name: "Indionesbala", image: "/media/artists/indionesbala.webp" },
] as const;
export type PublicArtist = (typeof PUBLIC_ARTISTS)[number];
