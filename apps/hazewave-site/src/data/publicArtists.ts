/**
 * Owner-supplied artist visual registry.
 * Names and asset paths only. No fabricated releases, biography, audio, or dates.
 */
export const PUBLIC_ARTISTS = [
  { slug: "indionesbala", name: "Indionesbala", image: "/media/artists/indionesbala.webp" },
  { slug: "barak-ozama-beats", name: "Barak Ozama Beats", image: "/media/artists/barak-ozama-beats.png" },
  { slug: "baazu", name: "Baazü", image: "/media/artists/baazu.png" },
  { slug: "aquaverno", name: "Aquaverno", image: "/media/artists/aquaverno.jpg" },
  { slug: "hemorragia-cosmica", name: "Hemorragia Cósmica", image: "/media/artists/hemorragia-cosmica.jpg" },
] as const;

export type PublicArtist = (typeof PUBLIC_ARTISTS)[number];
