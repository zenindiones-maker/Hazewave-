export type QualityTier = "LOW" | "MEDIUM" | "HIGH" | "ULTRA";

export interface QualityProfile {
  tier: QualityTier;
  pixelRatio: number;
  shadows: boolean;
  reducedMotion: boolean;
}

export function detectQuality(): QualityProfile {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const dpr = window.devicePixelRatio || 1;
  const shortSide = Math.min(window.innerWidth, window.innerHeight);

  if (reducedMotion || shortSide < 430) {
    return { tier: "LOW", pixelRatio: Math.min(dpr, 1.0), shadows: false, reducedMotion };
  }
  if (shortSide < 768) {
    return { tier: "MEDIUM", pixelRatio: Math.min(dpr, 1.35), shadows: false, reducedMotion };
  }
  if (dpr > 1.75) {
    return { tier: "HIGH", pixelRatio: Math.min(dpr, 1.75), shadows: true, reducedMotion };
  }
  return { tier: "ULTRA", pixelRatio: Math.min(dpr, 2), shadows: true, reducedMotion };
}
