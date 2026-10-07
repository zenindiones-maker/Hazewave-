export interface SocialLink {
  handle: string;
  href: string;
  label: string;
}

export interface MerchItem {
  id: string;
  name: string;
  category: "CAP" | "TEE";
  status: "CONCEPT";
  accent: string;
}

export const siteIdentity = {
  name: "HAZEWAVE",
  tagline: "Núcleo Sonoro Independente | Santos 2021—",
  archiveCta: "ENTRAR NO ARQUIVO",
  backgroundAsset: "/media/hazewave-world.jpg.webp",
  merchContactHref: null,
  merchContactMode: "UNSET" as const
};

export const socials: SocialLink[] = [
  {
    handle: "@virundun",
    href: "https://www.instagram.com/virundun/",
    label: "Instagram Virundun"
  },
  {
    handle: "@barakozamabeats",
    href: "https://www.instagram.com/barakozamabeats/",
    label: "Instagram Barakoza Beats"
  },
  {
    handle: "@indionesbala",
    href: "https://www.instagram.com/indionesbala/",
    label: "Instagram Indiones Bala"
  }
];

/**
 * Merch remains concept-only until the owner supplies final product assets,
 * availability/pricing and an authorized contact destination.
 */
export const merchItems: MerchItem[] = [
  {
    id: "hazewave-cap",
    name: "Boné",
    category: "CAP",
    status: "CONCEPT",
    accent: "#d8ff7a"
  },
  {
    id: "hazewave-tee",
    name: "Camiseta",
    category: "TEE",
    status: "CONCEPT",
    accent: "#8f2cff"
  }
];
