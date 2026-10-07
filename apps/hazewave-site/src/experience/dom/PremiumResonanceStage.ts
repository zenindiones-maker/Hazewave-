import { gsap } from "gsap";
import type { QualityProfile } from "../quality/quality";
import type { PlayerPhase } from "../state/playerMachine";
import { getArtist, getTrack } from "../../data/catalog";

type PhaseSink = (phase: PlayerPhase) => void;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function center(rect: DOMRect) {
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
}

export class PremiumResonanceStage {
  private host: HTMLElement;
  private deck: HTMLElement;
  private slot: HTMLElement;
  private screenTitle: HTMLElement;
  private screenArtist: HTMLElement;
  private artifacts: HTMLButtonElement[];
  private onPhase: PhaseSink;
  private quality: QualityProfile;
  private activeTrackId: string | null = null;
  private loadedArtifact: HTMLElement | null = null;
  private busy = false;
  private playing = false;
  private energy = 0;
  private raf = 0;
  private frameSamples: number[] = [];
  private lastFrame = performance.now();
  private metricCounter = 0;

  constructor(host: HTMLElement, quality: QualityProfile, onPhase: PhaseSink) {
    this.host = host;
    this.quality = quality;
    this.onPhase = onPhase;
    this.deck = this.requireElement<HTMLElement>("#resonance-deck");
    this.slot = this.requireElement<HTMLElement>("#deck-slot");
    this.screenTitle = this.requireElement<HTMLElement>("#deck-screen-title");
    this.screenArtist = this.requireElement<HTMLElement>("#deck-screen-artist");
    this.artifacts = Array.from(
      host.querySelectorAll<HTMLButtonElement>(".resonance-artifact[data-track-id]")
    );

    this.host.dataset.runtime = "DOM_CINEMATIC";
    this.host.dataset.quality = quality.tier;
    this.frame();
  }

  async select(trackId: string): Promise<void> {
    if (this.busy || this.activeTrackId === trackId) return;
    const source = this.artifacts.find((artifact) => artifact.dataset.trackId === trackId);
    if (!source) throw new Error(`ARTIFACT_NOT_FOUND:${trackId}`);

    this.busy = true;
    try {
      if (this.activeTrackId) await this.eject(this.activeTrackId);

      this.activeTrackId = trackId;
      const track = getTrack(trackId);
      const artist = getArtist(track.artistId);

      this.host.style.setProperty("--world-accent", artist.identity.accent);
      this.host.style.setProperty("--world-secondary", artist.identity.secondary);
      this.host.style.setProperty("--world-bg", artist.identity.background);
      this.host.dataset.artist = artist.id;

      this.artifacts.forEach((artifact) => {
        const selected = artifact === source;
        artifact.dataset.focus = selected ? "selected" : "receded";
      });

      this.onPhase("SELECTED");
      this.deck.dataset.state = "selected";

      if (this.quality.reducedMotion) {
        source.dataset.loaded = "true";
        this.screenTitle.textContent = track.title;
        this.screenArtist.textContent = artist.name.replace(" / DEMO", "");
        this.onPhase("CONTACT");
        this.deck.dataset.state = "contact";
        await sleep(24);
        return;
      }

      await this.animateSelection(source, track.title, artist.name.replace(" / DEMO", ""));
    } finally {
      this.busy = false;
    }
  }

  setPlaying(playing: boolean): void {
    this.playing = playing;
    this.deck.dataset.state = playing ? "playing" : "paused";
    this.host.dataset.playing = String(playing);
  }

  setSignalEnergy(value: number): void {
    this.energy = Math.max(0, Math.min(1, value));
    this.host.style.setProperty("--audio-energy", this.energy.toFixed(3));
    this.host.style.setProperty("--audio-glow", (0.68 + this.energy * 0.24).toFixed(3));
    this.host.style.setProperty("--audio-scale", (1 + this.energy * 0.018).toFixed(4));
    this.host.style.setProperty("--audio-lift", `${(this.energy * 5).toFixed(2)}px`);
  }

  dispose(): void {
    cancelAnimationFrame(this.raf);
    gsap.killTweensOf(".cinematic-artifact-clone");
  }

  private async animateSelection(source: HTMLButtonElement, title: string, artist: string): Promise<void> {
    const sourceRect = source.getBoundingClientRect();
    const slotRect = this.slot.getBoundingClientRect();
    const sourceCenter = center(sourceRect);
    const slotCenter = center(slotRect);

    const clone = source.cloneNode(true) as HTMLElement;
    clone.classList.add("cinematic-artifact-clone");
    clone.removeAttribute("id");
    clone.setAttribute("aria-hidden", "true");
    Object.assign(clone.style, {
      position: "fixed",
      left: `${sourceRect.left}px`,
      top: `${sourceRect.top}px`,
      width: `${sourceRect.width}px`,
      height: `${sourceRect.height}px`,
      margin: "0",
      zIndex: "9998",
      pointerEvents: "none"
    });
    document.body.append(clone);

    source.dataset.loaded = "pending";

    const dx = slotCenter.x - sourceCenter.x;
    const dy = slotCenter.y - sourceCenter.y;
    const direction = sourceCenter.x < slotCenter.x ? -1 : 1;

    this.onPhase("ANTICIPATION");
    this.deck.dataset.state = "anticipation";

    await this.timeline((tl) => {
      tl.to(source, {
        scale: 0.94,
        opacity: 0.42,
        duration: 0.12,
        ease: "power2.out"
      }, 0);
      tl.to(this.deck, {
        scale: 1.018,
        duration: 0.22,
        ease: "power2.out"
      }, 0);
      tl.to(".deck-gate-left", {
        xPercent: -58,
        rotate: -12,
        duration: 0.28,
        ease: "power3.out"
      }, 0.04);
      tl.to(".deck-gate-right", {
        xPercent: 58,
        rotate: 12,
        duration: 0.28,
        ease: "power3.out"
      }, 0.04);
    });

    this.onPhase("TRAVEL");
    this.deck.dataset.state = "travel";

    await this.timeline((tl) => {
      tl.to(clone, {
        x: dx * 0.56,
        y: dy * 0.42 - Math.min(120, window.innerHeight * 0.12),
        scale: 1.12,
        rotateZ: direction * -8,
        rotateY: direction * 14,
        duration: 0.46,
        ease: "power3.inOut"
      });
      tl.to(clone, {
        x: dx * 0.88,
        y: dy * 0.82 - 18,
        scale: 0.86,
        rotateZ: direction * 2,
        rotateY: direction * 5,
        duration: 0.34,
        ease: "power2.inOut"
      });
    });

    this.onPhase("ALIGN");
    this.deck.dataset.state = "align";

    await this.tween(clone, {
      x: dx,
      y: dy,
      width: Math.max(56, slotRect.width * 0.72),
      height: Math.max(72, slotRect.height * 0.72),
      rotateZ: 0,
      rotateY: 0,
      borderRadius: 18,
      duration: 0.22,
      ease: "power4.out"
    });

    this.onPhase("INSERT");
    this.deck.dataset.state = "insert";

    await this.timeline((tl) => {
      tl.to(clone, {
        scale: 0.72,
        filter: "brightness(1.16) saturate(1.08)",
        duration: 0.18,
        ease: "power2.in"
      });
      tl.to(clone, {
        scale: 0.56,
        opacity: 0,
        duration: 0.13,
        ease: "power2.in"
      });
      tl.to(".deck-gate-left", {
        xPercent: 0,
        rotate: 0,
        duration: 0.2,
        ease: "power3.out"
      }, "-=0.05");
      tl.to(".deck-gate-right", {
        xPercent: 0,
        rotate: 0,
        duration: 0.2,
        ease: "power3.out"
      }, "<");
    });

    this.onPhase("CONTACT");
    this.deck.dataset.state = "contact";
    this.screenTitle.textContent = title;
    this.screenArtist.textContent = artist;
    source.dataset.loaded = "true";

    this.loadedArtifact?.remove();
    const loadedSource = source.querySelector<HTMLElement>(".artifact-shell");
    if (loadedSource) {
      const loaded = loadedSource.cloneNode(true) as HTMLElement;
      loaded.classList.add("deck-loaded-artifact");
      loaded.setAttribute("aria-hidden", "true");
      this.slot.append(loaded);
      this.loadedArtifact = loaded;
    }

    await this.timeline((tl) => {
      tl.fromTo(".deck-contact-flash", {
        opacity: 0,
        scale: 0.65
      }, {
        opacity: 0.82,
        scale: 1.16,
        duration: 0.08,
        ease: "power1.out"
      });
      tl.to(".deck-contact-flash", {
        opacity: 0,
        scale: 1.48,
        duration: 0.24,
        ease: "power3.out"
      });
      tl.to(this.deck, {
        scale: 1,
        duration: 0.2,
        ease: "power2.out"
      }, 0);
    });

    clone.remove();
    gsap.set(source, { clearProps: "scale,opacity" });

    this.onPhase("ACTIVATING");
    this.deck.dataset.state = "activating";
    await sleep(110);
  }

  private async eject(trackId: string): Promise<void> {
    const source = this.artifacts.find((artifact) => artifact.dataset.trackId === trackId);
    if (!source) return;

    this.playing = false;
    this.onPhase("EJECT");
    this.deck.dataset.state = "eject";

    const sourceRect = source.getBoundingClientRect();
    const slotRect = this.slot.getBoundingClientRect();
    const sourceCenter = center(sourceRect);
    const slotCenter = center(slotRect);

    const clone = source.cloneNode(true) as HTMLElement;
    clone.classList.add("cinematic-artifact-clone");
    clone.dataset.loaded = "false";
    clone.setAttribute("aria-hidden", "true");
    Object.assign(clone.style, {
      position: "fixed",
      left: `${slotRect.left + slotRect.width * 0.14}px`,
      top: `${slotRect.top + slotRect.height * 0.14}px`,
      width: `${Math.max(56, slotRect.width * 0.72)}px`,
      height: `${Math.max(72, slotRect.height * 0.72)}px`,
      margin: "0",
      zIndex: "9998",
      pointerEvents: "none"
    });
    document.body.append(clone);

    const dx = sourceCenter.x - slotCenter.x;
    const dy = sourceCenter.y - slotCenter.y;

    await this.timeline((tl) => {
      tl.to(".deck-gate-left", { xPercent: -58, duration: 0.18, ease: "power2.out" });
      tl.to(".deck-gate-right", { xPercent: 58, duration: 0.18, ease: "power2.out" }, "<");
      tl.fromTo(clone, { opacity: 0, scale: 0.56 }, {
        opacity: 1,
        scale: 0.78,
        duration: 0.16,
        ease: "power2.out"
      }, 0.04);
    });

    this.onPhase("RETURN");
    await this.timeline((tl) => {
      tl.to(clone, {
        x: dx * 0.62,
        y: dy * 0.58 - 26,
        scale: 0.92,
        rotateZ: dx < 0 ? -5 : 5,
        duration: 0.3,
        ease: "power2.inOut"
      });
      tl.to(clone, {
        x: dx,
        y: dy,
        width: sourceRect.width,
        height: sourceRect.height,
        scale: 1,
        rotateZ: 0,
        opacity: 0,
        duration: 0.28,
        ease: "power3.out"
      });
    });

    clone.remove();
    this.loadedArtifact?.remove();
    this.loadedArtifact = null;
    source.dataset.loaded = "false";
    this.artifacts.forEach((artifact) => (artifact.dataset.focus = "idle"));
    this.screenTitle.textContent = "Awaiting signal";
    this.screenArtist.textContent = "Select a resonance object";
    this.deck.dataset.state = "idle";

    gsap.set(".deck-gate-left", { clearProps: "transform" });
    gsap.set(".deck-gate-right", { clearProps: "transform" });
  }

  private frame = (): void => {
    const now = performance.now();
    const delta = now - this.lastFrame;
    this.lastFrame = now;

    if (delta > 0 && delta < 500) {
      this.frameSamples.push(delta);
      if (this.frameSamples.length > 180) this.frameSamples.shift();
      this.metricCounter += 1;
      if (this.metricCounter % 30 === 0 && this.frameSamples.length >= 30) {
        const sorted = [...this.frameSamples].sort((a, b) => a - b);
        const p95 = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))] ?? 0;
        const average = this.frameSamples.reduce((sum, value) => sum + value, 0) / this.frameSamples.length;
        this.host.dataset.fps = (1000 / average).toFixed(1);
        this.host.dataset.frameP95Ms = p95.toFixed(1);
      }
    }

    this.host.style.setProperty("--audio-energy", this.playing ? this.energy.toFixed(3) : "0");
    this.raf = requestAnimationFrame(this.frame);
  };

  private tween(target: gsap.TweenTarget, vars: gsap.TweenVars): Promise<void> {
    return new Promise((resolve) => {
      gsap.to(target, {
        ...vars,
        onComplete: resolve,
        onInterrupt: resolve
      });
    });
  }

  private timeline(build: (timeline: gsap.core.Timeline) => void): Promise<void> {
    return new Promise((resolve) => {
      const timeline = gsap.timeline({
        onComplete: resolve,
        onInterrupt: resolve
      });
      build(timeline);
    });
  }

  private requireElement<T extends Element>(selector: string): T {
    const element = this.host.querySelector<T>(selector);
    if (!element) throw new Error(`PREMIUM_STAGE_ELEMENT_MISSING:${selector}`);
    return element;
  }
}
