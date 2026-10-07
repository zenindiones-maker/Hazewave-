import { gsap } from "gsap";

export class CinematicMotionDriver {
  private active = new Set<gsap.core.Tween>();

  progress(durationMs: number, update: (progress: number) => void): Promise<void> {
    if (durationMs <= 0) {
      update(1);
      return Promise.resolve();
    }

    return new Promise((resolve) => {
      const state = { progress: 0 };
      let tween: gsap.core.Tween;

      tween = gsap.to(state, {
        progress: 1,
        duration: durationMs / 1000,
        ease: "none",
        overwrite: false,
        onUpdate: () => update(state.progress),
        onComplete: () => {
          this.active.delete(tween);
          resolve();
        },
        onInterrupt: () => {
          this.active.delete(tween);
          resolve();
        }
      });

      this.active.add(tween);
    });
  }

  killAll(): void {
    for (const tween of this.active) tween.kill();
    this.active.clear();
  }
}
