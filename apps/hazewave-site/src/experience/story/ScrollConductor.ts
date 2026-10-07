import {
  sceneLedger,
  type StoryChapter,
  type WorldFrame
} from "./sceneLedger";

interface ResolvedChapter {
  chapter: StoryChapter;
  top: number;
  bottom: number;
}

export interface StoryRuntimeState {
  chapterId: StoryChapter["id"];
  narrativeBeat: StoryChapter["narrativeBeat"];
  globalProgress: number;
  chapterProgress: number;
  velocity: number;
  world: WorldFrame;
}

type StoryFrameSink = (state: StoryRuntimeState) => void;

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
const clampSigned = (value: number) => Math.max(-1, Math.min(1, value));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

function mixWorld(a: WorldFrame, b: WorldFrame, t: number): WorldFrame {
  return {
    scale: lerp(a.scale, b.scale, t),
    translateX: lerp(a.translateX, b.translateX, t),
    translateY: lerp(a.translateY, b.translateY, t),
    rotate: lerp(a.rotate, b.rotate, t),
    brightness: lerp(a.brightness, b.brightness, t),
    saturation: lerp(a.saturation, b.saturation, t),
    contrast: lerp(a.contrast, b.contrast, t),
    vignette: lerp(a.vignette, b.vignette, t),
    water: lerp(a.water, b.water, t),
    fog: lerp(a.fog, b.fog, t),
    lighthouse: lerp(a.lighthouse, b.lighthouse, t),
    depth: lerp(a.depth, b.depth, t),
    particles: lerp(a.particles, b.particles, t)
  };
}

function damp(current: number, target: number, lambda: number, dt: number): number {
  return lerp(current, target, 1 - Math.exp(-lambda * dt));
}

function dampWorld(
  current: WorldFrame,
  target: WorldFrame,
  lambda: number,
  dt: number
): WorldFrame {
  return {
    scale: damp(current.scale, target.scale, lambda, dt),
    translateX: damp(current.translateX, target.translateX, lambda, dt),
    translateY: damp(current.translateY, target.translateY, lambda, dt),
    rotate: damp(current.rotate, target.rotate, lambda, dt),
    brightness: damp(current.brightness, target.brightness, lambda, dt),
    saturation: damp(current.saturation, target.saturation, lambda, dt),
    contrast: damp(current.contrast, target.contrast, lambda, dt),
    vignette: damp(current.vignette, target.vignette, lambda, dt),
    water: damp(current.water, target.water, lambda, dt),
    fog: damp(current.fog, target.fog, lambda, dt),
    lighthouse: damp(current.lighthouse, target.lighthouse, lambda, dt),
    depth: damp(current.depth, target.depth, lambda, dt),
    particles: damp(current.particles, target.particles, lambda, dt)
  };
}

export class ScrollConductor {
  private readonly root = document.documentElement;
  private readonly reducedMotion: boolean;
  private readonly onFrame?: StoryFrameSink;
  private chapters: ResolvedChapter[] = [];
  private target: WorldFrame = sceneLedger[0]!.world;
  private smooth: WorldFrame = { ...sceneLedger[0]!.world };
  private raf = 0;
  private last = performance.now();
  private activeId = sceneLedger[0]!.id;
  private activeBeat = sceneLedger[0]!.narrativeBeat;
  private chapterProgress = 0;
  private globalProgress = 0;
  private targetVelocity = 0;
  private smoothVelocity = 0;
  private lastScrollY = window.scrollY;
  private lastScrollAt = performance.now();
  private maxScroll = 1;
  private resizeTimer = 0;
  private layoutRefreshRaf = 0;
  private readonly layoutObserver = new ResizeObserver(() => {
    cancelAnimationFrame(this.layoutRefreshRaf);
    this.layoutRefreshRaf = requestAnimationFrame(this.refresh);
  });

  constructor(reducedMotion: boolean, onFrame?: StoryFrameSink) {
    this.reducedMotion = reducedMotion;
    this.onFrame = onFrame;
    this.refresh();

    window.addEventListener("scroll", this.onScroll, { passive: true });
    window.addEventListener("resize", this.onResize, { passive: true });
    window.addEventListener("orientationchange", this.refresh, { passive: true });
    document.addEventListener("visibilitychange", this.onVisibility);
    this.layoutObserver.observe(document.body);

    this.updateTarget();
    this.render(performance.now());
  }

  scrollTo(selector: string): void {
    const target = document.querySelector<HTMLElement>(selector);
    if (!target) return;

    this.refresh();
    const top =
      window.scrollY +
      target.getBoundingClientRect().top -
      Math.min(72, window.innerHeight * 0.08);

    window.scrollTo({
      top: Math.max(0, top),
      behavior: this.reducedMotion ? "auto" : "smooth"
    });
  }

  dispose(): void {
    cancelAnimationFrame(this.raf);
    cancelAnimationFrame(this.layoutRefreshRaf);
    this.layoutObserver.disconnect();
    window.clearTimeout(this.resizeTimer);
    window.removeEventListener("scroll", this.onScroll);
    window.removeEventListener("resize", this.onResize);
    window.removeEventListener("orientationchange", this.refresh);
    document.removeEventListener("visibilitychange", this.onVisibility);
  }

  private refresh = (): void => {
    const scrollY = window.scrollY;
    this.maxScroll = Math.max(
      1,
      document.documentElement.scrollHeight - window.innerHeight
    );

    this.chapters = sceneLedger
      .map((chapter) => {
        const element = document.querySelector<HTMLElement>(chapter.selector);
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        const top = scrollY + rect.top;
        const bottom = top + Math.max(1, rect.height);
        return { chapter, top, bottom };
      })
      .filter((value): value is ResolvedChapter => value !== null)
      .sort((a, b) => a.top - b.top);

    this.updateTarget();
  };

  private onResize = (): void => {
    window.clearTimeout(this.resizeTimer);
    this.resizeTimer = window.setTimeout(this.refresh, 120);
  };

  private onVisibility = (): void => {
    this.last = performance.now();
    this.lastScrollAt = this.last;
    this.lastScrollY = window.scrollY;
    if (document.hidden) cancelAnimationFrame(this.raf);
    else this.raf = requestAnimationFrame(this.render);
  };

  private onScroll = (): void => {
    const now = performance.now();
    const dy = window.scrollY - this.lastScrollY;
    const dt = Math.max(16, now - this.lastScrollAt);
    this.targetVelocity = clampSigned((dy / dt) * 0.72);
    this.lastScrollY = window.scrollY;
    this.lastScrollAt = now;
    this.updateTarget();
  };

  private updateTarget(): void {
    if (this.chapters.length === 0) return;

    this.globalProgress = clamp01(window.scrollY / this.maxScroll);

    const storyPosition = window.scrollY + window.innerHeight * 0.5;

    let activeIndex = 0;
    if (storyPosition <= this.chapters[0]!.top) {
      activeIndex = 0;
    } else {
      for (let index = 0; index < this.chapters.length; index += 1) {
        const current = this.chapters[index]!;
        if (storyPosition >= current.top) activeIndex = index;
        if (storyPosition >= current.top && storyPosition < current.bottom) break;
      }
    }

    const active = this.chapters[activeIndex]!;
    const next = this.chapters[Math.min(activeIndex + 1, this.chapters.length - 1)]!;
    const span = Math.max(1, active.bottom - active.top);
    const local = clamp01((storyPosition - active.top) / span);

    // Keep chapter authority exact and reversible. Visual interpolation begins
    // only near the end of the current chapter, so a scroll position inside a
    // semantic section never gets mislabeled as the following chapter.
    const transition =
      active === next
        ? 0
        : clamp01((local - 0.58) / 0.42);

    this.chapterProgress = local;
    this.target = mixWorld(active.chapter.world, next.chapter.world, transition);

    this.activeId = active.chapter.id;
    this.activeBeat = active.chapter.narrativeBeat;
    this.root.dataset.storyChapter = active.chapter.id;
    this.root.dataset.storyLabel = active.chapter.label;
    this.root.dataset.storyBeat = active.chapter.narrativeBeat;

    this.root.style.setProperty(
      "--story-global-progress",
      this.globalProgress.toFixed(5)
    );
    this.root.style.setProperty(
      "--story-chapter-progress",
      this.chapterProgress.toFixed(5)
    );
  }

  private render = (now: number): void => {
    const dt = Math.min(0.05, Math.max(0.001, (now - this.last) / 1000));
    this.last = now;

    if (this.reducedMotion) {
      this.smooth = {
        ...this.target,
        scale: 1,
        translateX: 0,
        translateY: 0,
        rotate: 0,
        water: 0,
        fog: Math.min(this.target.fog, 0.08),
        depth: 0,
        particles: 0
      };
      this.smoothVelocity = 0;
    } else {
      this.smooth = dampWorld(this.smooth, this.target, 5.2, dt);
      this.smoothVelocity = damp(
        this.smoothVelocity,
        this.targetVelocity,
        8,
        dt
      );
      this.targetVelocity = damp(this.targetVelocity, 0, 4.2, dt);
    }

    this.root.style.setProperty(
      "--story-world-scale",
      this.smooth.scale.toFixed(4)
    );
    this.root.style.setProperty(
      "--story-world-x",
      `${this.smooth.translateX.toFixed(3)}vw`
    );
    this.root.style.setProperty(
      "--story-world-y",
      `${this.smooth.translateY.toFixed(3)}vh`
    );
    this.root.style.setProperty(
      "--story-world-rotate",
      `${this.smooth.rotate.toFixed(3)}deg`
    );
    this.root.style.setProperty(
      "--story-world-brightness",
      this.smooth.brightness.toFixed(3)
    );
    this.root.style.setProperty(
      "--story-world-saturation",
      this.smooth.saturation.toFixed(3)
    );
    this.root.style.setProperty(
      "--story-world-contrast",
      this.smooth.contrast.toFixed(3)
    );
    this.root.style.setProperty(
      "--story-world-vignette",
      this.smooth.vignette.toFixed(3)
    );
    this.root.style.setProperty(
      "--story-world-water",
      this.smooth.water.toFixed(3)
    );
    this.root.style.setProperty(
      "--story-world-fog",
      this.smooth.fog.toFixed(3)
    );
    this.root.style.setProperty(
      "--story-world-lighthouse",
      this.smooth.lighthouse.toFixed(3)
    );
    this.root.style.setProperty(
      "--story-world-depth",
      this.smooth.depth.toFixed(3)
    );
    this.root.style.setProperty(
      "--story-world-particles",
      this.smooth.particles.toFixed(3)
    );
    this.root.style.setProperty(
      "--story-scroll-velocity",
      this.smoothVelocity.toFixed(4)
    );
    this.root.style.setProperty(
      "--story-water-shift-x",
      `${(this.smoothVelocity * 14 + Math.sin(this.globalProgress * 15) * this.smooth.water * 4).toFixed(2)}px`
    );
    this.root.style.setProperty(
      "--story-water-shift-y",
      `${(Math.sin(this.globalProgress * 21) * this.smooth.water * 3.2).toFixed(2)}px`
    );
    this.root.style.setProperty(
      "--story-fog-shift",
      `${(this.smooth.translateX * 2.8 + this.smoothVelocity * 8).toFixed(2)}px`
    );
    this.root.style.setProperty(
      "--story-light-angle",
      `${(this.globalProgress * 210 + this.smooth.lighthouse * 18).toFixed(2)}deg`
    );

    this.onFrame?.({
      chapterId: this.activeId,
      narrativeBeat: this.activeBeat,
      globalProgress: this.globalProgress,
      chapterProgress: this.chapterProgress,
      velocity: this.smoothVelocity,
      world: this.smooth
    });

    this.raf = requestAnimationFrame(this.render);
  };
}
