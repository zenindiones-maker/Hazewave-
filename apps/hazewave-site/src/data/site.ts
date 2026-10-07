export interface SocialLink {
  handle: string;
  href: string;
  label: string;
}

export interface MerchItem {
  id: string;
  name: string;
  category: "CAP" | "TEE" | "VINYL";
  status: "CONCEPT" | "AVAILABLE";
  message: string;
  accent: string;
}

export const siteIdentity = {
  name: "HAZEWAVE",
  tagline: "Núcleo Sonoro Independente | Santos 2021—",
  archiveCta: "ENTRAR NO ARQUIVO",
  backgroundAsset: "/media/hazewave-world.jpg",
  merchContactHref: "https://www.instagram.com/direct/inbox/",
  merchContactMode: "COPY_MESSAGE_AND_OPEN_DM" as const
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

export const merchItems: MerchItem[] = [
  {
    id: "collective-cap",
    name: "Boné Collective",
    category: "CAP",
    status: "CONCEPT",
    message: "Fala Hazewave, quero o boné Collective",
    accent: "#d8ff7a"
  },
  {
    id: "archive-tee",
    name: "Camiseta Archive",
    category: "TEE",
    status: "CONCEPT",
    message: "Fala Hazewave, quero a camiseta Archive",
    accent: "#8f2cff"
  },
  {
    id: "signal-vinyl",
    name: "Vinil Signal",
    category: "VINYL",
    status: "CONCEPT",
    message: "Fala Hazewave, quero o vinil Signal",
    accent: "#f5f2e9"
  }
];
