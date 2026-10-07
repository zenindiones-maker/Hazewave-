import * as THREE from "three/webgpu";
import type { ArtistId } from "../../data/catalog";
import type { QualityProfile } from "../quality/quality";

interface ParticleSeed {
  phase: number;
  radius: number;
  speed: number;
  lift: number;
  depth: number;
  size: number;
}

const ARTIST_COLORS: Record<ArtistId, string> = {
  aether: "#a7ffe0",
  monolith: "#e8d9c5",
  flora: "#d8ff7a"
};

export class HighTierAtmosphere {
  private readonly host: HTMLElement;
  private readonly renderer: THREE.WebGPURenderer;
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.PerspectiveCamera(42, 1, 0.1, 40);
  private readonly material = new THREE.MeshBasicMaterial({
    color: ARTIST_COLORS.aether,
    transparent: true,
    opacity: 0.16,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });
  private readonly geometry = new THREE.IcosahedronGeometry(0.075, 0);
  private readonly mesh: THREE.InstancedMesh;
  private readonly dummy = new THREE.Object3D();
  private readonly seeds: ParticleSeed[];
  private readonly observer: ResizeObserver;
  private artist: ArtistId = "aether";
  private energy = 0;
  private playing = false;
  private disposed = false;

  constructor(host: HTMLElement, quality: QualityProfile) {
    this.host = host;
    this.renderer = new THREE.WebGPURenderer({
      alpha: true,
      antialias: false,
      depth: true,
      outputBufferType: THREE.UnsignedByteType
    });
    this.renderer.setPixelRatio(Math.min(quality.pixelRatio, 1.35));
    this.renderer.setClearColor(0x000000, 0);

    const count = quality.tier === "ULTRA" ? 56 : 40;
    this.mesh = new THREE.InstancedMesh(this.geometry, this.material, count);
    this.mesh.frustumCulled = false;
    this.scene.add(this.mesh);

    this.seeds = Array.from({ length: count }, (_, index) => {
      const golden = index * 2.399963229728653;
      return {
        phase: golden,
        radius: 0.9 + (index % 9) * 0.23,
        speed: 0.08 + (index % 7) * 0.012,
        lift: 0.48 + (index % 5) * 0.17,
        depth: -0.6 - (index % 11) * 0.22,
        size: 0.56 + (index % 6) * 0.11
      };
    });

    this.camera.position.set(0, 0, 5.4);

    const canvas = this.renderer.domElement;
    canvas.className = "gpu-atmosphere";
    canvas.setAttribute("aria-hidden", "true");
    this.host.prepend(canvas);

    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(this.host);
    this.resize();

    void this.renderer.setAnimationLoop((time) => this.render(time));
    this.host.dataset.gpuAtmosphere = "webgpu";
  }

  setArtist(artist: ArtistId): void {
    this.artist = artist;
    this.material.color.set(ARTIST_COLORS[artist]);
    this.host.dataset.gpuArtist = artist;
  }

  setEnergy(value: number): void {
    this.energy = Math.max(0, Math.min(1, value));
  }

  setPlaying(playing: boolean): void {
    this.playing = playing;
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.observer.disconnect();
    void this.renderer.setAnimationLoop(null);
    this.mesh.removeFromParent();
    this.geometry.dispose();
    this.material.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  private resize(): void {
    const width = Math.max(1, this.host.clientWidth);
    const height = Math.max(1, this.host.clientHeight);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  private render(timeMs: number): void {
    if (this.disposed) return;

    const t = timeMs * 0.001;
    const active = this.playing ? 1 : 0;
    const energy = this.energy * active;
    const signature =
      this.artist === "aether" ? 0.82 :
      this.artist === "monolith" ? 0.38 :
      0.62;

    for (let index = 0; index < this.seeds.length; index += 1) {
      const seed = this.seeds[index]!;
      const orbit = seed.phase + t * seed.speed * (0.72 + signature);
      const breathe = Math.sin(t * (0.42 + seed.speed) + seed.phase * 0.8);

      let x = Math.cos(orbit) * seed.radius;
      let y = Math.sin(orbit * 1.31) * seed.lift;
      let z = seed.depth + Math.sin(orbit * 0.74) * 0.54;

      if (this.artist === "monolith") {
        x = Math.round(x * 3.2) / 3.2;
        y *= 0.62;
      } else if (this.artist === "flora") {
        y += Math.sin(seed.phase * 1.7 + t * 0.16) * 0.44;
        x *= 0.9 + (index % 3) * 0.08;
      }

      const scale =
        seed.size *
        (0.72 + (breathe + 1) * 0.12) *
        (1 + energy * (1.2 + (index % 4) * 0.13));

      this.dummy.position.set(x, y, z);
      this.dummy.rotation.set(
        orbit * 0.42,
        orbit * (0.58 + signature * 0.2),
        seed.phase * 0.22 + t * seed.speed
      );
      this.dummy.scale.setScalar(scale);
      this.dummy.updateMatrix();
      this.mesh.setMatrixAt(index, this.dummy.matrix);
    }

    this.mesh.instanceMatrix.needsUpdate = true;
    this.material.opacity = 0.085 + signature * 0.055 + energy * 0.13;
    this.scene.rotation.z = Math.sin(t * 0.09) * 0.035;
    this.scene.rotation.y = Math.sin(t * 0.07) * 0.06;
    this.renderer.render(this.scene, this.camera);
  }
}
