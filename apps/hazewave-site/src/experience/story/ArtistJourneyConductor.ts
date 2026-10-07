import type { ArtistId } from "../../data/catalog";

export type ArtistJourneyPhase = "EMERGE" | "MUSIC" | "VISUAL" | "TRANSITION";

interface ArtistAnchor {
  id: ArtistId;
  top: number;
  height: number;
}

export interface ArtistJourneyState {
  artistId: ArtistId;
  progress: number;
  phase: ArtistJourneyPhase;
}

type JourneySink = (state: ArtistJourneyState) => void;

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

function phaseForProgress(progress: number): ArtistJourneyPhase {
  if (progress < 0.24) return "EMERGE";
  if (progress < 0.52) return "MUSIC";
  if (progress < 0.78) return "VISUAL";
  return "TRANSITION";
}

/**
 * Exact semantic artist state derived from native scroll position.
 *
 * This intentionally does not smooth the authoritative state. Visual layers
 * may damp/interpolate independently, but the same scroll position must always
 * resolve to the same artist and progress.
 */
export class ArtistJourneyConductor {
  private readonly root = document.documentElement;
  private readonly onChange?: JourneySink;
  private anchors: ArtistAnchor[] = [];
  private raf = 0;
  private resizeTimer = 0;
  private activeId: ArtistId | null = null;
  private activeProgress = -1;
  private activePhase: ArtistJourneyPhase | null = null;

  constructor(onChange?: JourneySink) {
    this.onChange = onChange;
    this.refresh();

    window.addEventListener("scroll", this.scheduleUpdate, { passive: true });
    window.addEventListener("resize", this.onResize, { passive: true });
    window.addEventListener("orientationchange", this.refresh, { passive: true });

    this.update();
  }

  dispose(): void {
    cancelAnimationFrame(this.raf);
    window.clearTimeout(this.resizeTimer);
    window.removeEventListener("scroll", this.scheduleUpdate);
    window.removeEventListener("resize", this.onResize);
    window.removeEventListener("orientationchange", this.refresh);
  }

  private refresh = (): void => {
    const scrollY = window.scrollY;
    this.anchors = Array.from(
      document.querySelectorAll<HTMLElement>("[data-artist-chapter]")
    )
      .map((element) => {
        const id = element.dataset.artistChapter as ArtistId | undefined;
        if (!id) return null;
        const rect = element.getBoundingClientRect();
        return {
          id,
          top: scrollY + rect.top,
          height: Math.max(1, rect.height)
        };
      })
      .filter((value): value is ArtistAnchor => value !== null)
      .sort((a, b) => a.top - b.top);

    this.update();
  };

  private onResize = (): void => {
    window.clearTimeout(this.resizeTimer);
    this.resizeTimer = window.setTimeout(this.refresh, 120);
  };

  private scheduleUpdate = (): void => {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      this.update();
    });
  };

  private update(): void {
    if (this.anchors.length === 0) return;

    const position = window.scrollY + window.innerHeight * 0.5;
    let active = this.anchors[0]!;

    for (const anchor of this.anchors) {
      if (position >= anchor.top) active = anchor;
      else break;
    }

    const progress = clamp01((position - active.top) / active.height);
    const phase = phaseForProgress(progress);

    if (
      active.id === this.activeId &&
      phase === this.activePhase &&
      Math.abs(progress - this.activeProgress) < 0.002
    ) {
      return;
    }

    this.activeId = active.id;
    this.activeProgress = progress;
    this.activePhase = phase;
    this.root.dataset.scrollArtist = active.id;
    this.root.dataset.artistPhase = phase;
    this.root.style.setProperty("--artist-chapter-progress", progress.toFixed(4));

    this.onChange?.({
      artistId: active.id,
      progress,
      phase
    });
  }
}
