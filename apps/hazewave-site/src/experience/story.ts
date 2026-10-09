export type ActName = "birth" | "traversal" | "revelation";

export interface StoryLine {
  at: number;
  text: string;
}

/** Literary captions. Thresholds are scroll progress, reversible with the page. */
export const STORY_LINES: readonly StoryLine[] = [
  { at: 0, text: "Antes da matéria, havia silêncio." },
  { at: 0.12, text: "Uma interferência nasce no vazio." },
  { at: 0.3, text: "A onda atravessa a névoa." },
  { at: 0.44, text: "Onde ela passa, as galáxias se deslocam." },
  { at: 0.58, text: "A matéria muda de ordem." },
  { at: 0.72, text: "O universo cede ao som." },
  { at: 0.9, text: "A interferência revela a Hazewave. Muitos mundos, uma travessia." },
];

/**
 * Handles already published in the Hazewave site data.
 * They surface only as text at the end of the traversal.
 */
export const PUBLIC_HANDLES = [
  { handle: "@virundun", href: "https://www.instagram.com/virundun/" },
  { handle: "@barakozamabeats", href: "https://www.instagram.com/barakozamabeats/" },
  { handle: "@indionesbala", href: "https://www.instagram.com/indionesbala/" },
] as const;

export function actFor(progress: number): ActName {
  if (progress < 0.3) return "birth";
  if (progress < 0.72) return "traversal";
  return "revelation";
}

export function lineFor(progress: number): string {
  let text = STORY_LINES[0]?.text ?? "";
  for (const line of STORY_LINES) {
    if (progress >= line.at) text = line.text;
  }
  return text;
}

export function scrollProgress(): number {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  if (max <= 0) return 0;
  return Math.min(1, Math.max(0, window.scrollY / max));
}
