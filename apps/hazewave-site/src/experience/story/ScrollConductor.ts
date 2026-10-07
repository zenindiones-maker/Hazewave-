import {
  sceneLedger,
  type StoryChapter,
  type WorldFrame
} from "./sceneLedger";

interface ResolvedChapter {
  chapter: StoryChapter;
  anchor: number;
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

  constructor(reducedMotion: boolean, onFrame?: StoryFrameSink) {
    this.reducedMotion = reducedMotion;
    this.onFrame = onFrame;
    this.refresh();

    window.addEventListener("scroll", this.onScroll, { passive: true });
    window.addEventListener("resize", this.onResize, { passive: true });
    window.addEventListener("orientationchange", this.refresh, { passive: true });
    document.addEventListener("visibilitychange", this.onVisibility);

    this.updateTarget();
    this.render(performance.now());
  }

  scrollTo(selector: string): void {
    const target = document.querySelector<HTMLElement>(selector);
    if (!target) return;
    target.scrollIntoView({
      behavior: this.reducedMotion ? "auto" : "smooth",
      block: "start"
    });
  }

  dispose(): void {
    cancelAnimationFrame(this.raf);
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
        const anchor =
          scrollY +
          rect.top +
          Math.min(rect.height * 0.44, window.innerHeight * 0.54);
        return { chapter, anchor };
      })
      .filter((value): value is ResolvedChapter => value !== null)
      .sort((a, b) => a.anchor - b.anchor);

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

    const storyPosition = window.scrollY + window.innerHeight * 0.52;
    let left = this.chapters[0]!;
    let right = this.chapters[this.chapters.length - 1]!;

    for (let index = 0; index < this.chapters.length - 1; index += 1) {
      const current = this.chapters[index]!;
      const next = this.chapters[index + 1]!;
      if (storyPosition >= current.anchor && storyPosition <= next.anchor) {
        left = current;
        right = next;
        break;
      }
      if (storyPosition < this.chapters[0]!.anchor) {
        left = right = this.chapters[0]!;
        break;
      }
      if (storyPosition > this.chapters[this.chapters.length - 1]!.anchor) {
        left = right = this.chapters[this.chapters.length - 1]!;
        break;
      }
    }

    const span = Math.max(1, right.anchor - left.anchor);
    const local =
      left === right
        ? 0
        : clamp01((storyPosition - left.anchor) / span);

    this.chapterProgress = local;
    this.target = mixWorld(left.chapter.world, right.chapter.world, local);

    const nextActive = local < 0.5 ? left.chapter : right.chapter;
    if (nextActive.id !== this.activeId) {
      this.activeId = nextActive.id;
      this.root.dataset.storyChapter = nextActive.id;
      this.root.dataset.storyLabel = nextActive.label;
    }
    if (nextActive.narrativeBeat !== this.activeBeat) {
      this.activeBeat = nextActive.narrativeBeat;
      this.root.dataset.storyBeat = nextActive.narrativeBeat;
    }

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
