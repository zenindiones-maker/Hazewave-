import * as THREE from "three";
import { artists, getArtist, getTrack, tracks } from "../../data/catalog";
import type { Track } from "../../data/catalog";
import type { PlayerPhase } from "../state/playerMachine";
import type { QualityProfile } from "../quality/quality";
import { createRenderer, type RendererAdapter } from "../renderer/createRenderer";

type PhaseSink = (phase: PlayerPhase) => void;
type TrackSink = (trackId: string) => void;

interface ModuleRecord {
  group: THREE.Group;
  homePosition: THREE.Vector3;
  homeQuaternion: THREE.Quaternion;
  track: Track;
}

const easeOutQuint = (t: number) => 1 - Math.pow(1 - t, 5);
const easeInOutCubic = (t: number) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

export class ResonanceExperience {
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
  private renderer: RendererAdapter;
  private quality: QualityProfile;
  private modules = new Map<string, ModuleRecord>();
  private pickables: THREE.Object3D[] = [];
  private raycaster = new THREE.Raycaster();
  private pointer = new THREE.Vector2();
  private activeTrackId: string | null = null;
  private deckLight: THREE.PointLight;
  private slotGate: THREE.Mesh;
  private running = true;
  private signalEnergy = 0;
  private targetBackground = new THREE.Color("#071010");
  private currentBackground = new THREE.Color("#071010");
  private onPhase: PhaseSink;
  private onRequestSelect: TrackSink;
  private resizeObserver: ResizeObserver;

  constructor(canvas: HTMLCanvasElement, quality: QualityProfile, onPhase: PhaseSink, onRequestSelect: TrackSink) {
    this.quality = quality;
    this.onPhase = onPhase;
    this.onRequestSelect = onRequestSelect;
    this.renderer = createRenderer(canvas, quality);
    this.scene.background = this.currentBackground;
    this.camera.position.set(0, 2.2, 10.5);
    this.camera.lookAt(0, 0.35, 0);

    this.scene.add(new THREE.HemisphereLight(0xb9d8d2, 0x181818, 1.35));
    const key = new THREE.DirectionalLight(0xffffff, 4.1);
    key.position.set(-3, 6, 4);
    key.castShadow = quality.shadows;
    this.scene.add(key);

    const deck = this.buildDeck();
    this.deckLight = deck.light;
    this.slotGate = deck.gate;
    this.scene.add(deck.root);
    this.buildModules();

    canvas.addEventListener("pointerdown", this.handlePointer);
    this.resizeObserver = new ResizeObserver(() => this.resize(canvas));
    this.resizeObserver.observe(canvas);
    this.resize(canvas);
    this.frame();
  }

  async select(trackId: string): Promise<void> {
    const next = this.modules.get(trackId);
    if (!next) throw new Error(`MODULE_NOT_FOUND:${trackId}`);
    if (this.activeTrackId === trackId) return;

    if (this.activeTrackId) {
      const previous = this.modules.get(this.activeTrackId);
      if (previous) await this.eject(previous);
    }

    this.activeTrackId = trackId;
    this.targetBackground.set(getArtist(next.track.artistId).identity.background);

    if (this.quality.reducedMotion) {
      this.onPhase("SELECTED");
      next.group.position.copy(new THREE.Vector3(0, -0.58, 0.92));
      next.group.rotation.set(-0.08, 0, 0);
      this.onPhase("CONTACT");
      return;
    }

    await this.insert(next);
  }

  setSignalEnergy(value: number): void {
    this.signalEnergy = THREE.MathUtils.clamp(value, 0, 1);
  }

  setPlaying(isPlaying: boolean): void {
    this.deckLight.intensity = isPlaying ? 10 : 4;
  }

  dispose(): void {
    this.running = false;
    this.resizeObserver.disconnect();
    this.renderer.dispose();
  }

  private buildDeck(): { root: THREE.Group; light: THREE.PointLight; gate: THREE.Mesh } {
    const root = new THREE.Group();
    root.position.set(0, -1.05, -0.25);

    const body = new THREE.Mesh(
      new THREE.BoxGeometry(4.7, 1.55, 1.75, 5, 3, 3),
      new THREE.MeshPhysicalMaterial({ color: 0x151a19, metalness: 0.86, roughness: 0.25, clearcoat: 0.6, clearcoatRoughness: 0.25 })
    );
    body.castShadow = this.quality.shadows;
    body.receiveShadow = this.quality.shadows;
    root.add(body);

    const face = new THREE.Mesh(
      new THREE.BoxGeometry(3.8, 0.72, 0.08),
      new THREE.MeshStandardMaterial({ color: 0x050706, metalness: 0.2, roughness: 0.18 })
    );
    face.position.set(0, 0.04, 0.915);
    root.add(face);

    const gate = new THREE.Mesh(
      new THREE.BoxGeometry(2.2, 0.12, 0.14),
      new THREE.MeshStandardMaterial({ color: 0xa9cfc5, emissive: 0x243d37, emissiveIntensity: 0.8, metalness: 0.72, roughness: 0.18 })
    );
    gate.position.set(0, 0.16, 1.01);
    root.add(gate);

    const light = new THREE.PointLight(0xa7ffe0, 4, 6, 1.7);
    light.position.set(0, 0.45, 2.15);
    root.add(light);

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(22, 18),
      new THREE.MeshStandardMaterial({ color: 0x050606, metalness: 0.05, roughness: 0.82 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.84;
    floor.receiveShadow = this.quality.shadows;
    root.add(floor);

    return { root, light, gate };
  }

  private buildModules(): void {
    tracks.forEach((track, index) => {
      const artist = getArtist(track.artistId);
      const row = Math.floor(index / 3);
      const col = index % 3;
      const x = (col - 1) * 2.2;
      const y = 0.45 + row * 1.3;
      const z = row === 0 ? 0.3 : -0.35;

      const group = new THREE.Group();
      group.position.set(x, y, z);
      group.rotation.set(-0.18, (col - 1) * -0.08, (col - 1) * 0.035);

      const shell = new THREE.Mesh(
        new THREE.BoxGeometry(1.68, 0.95, 0.24, 3, 2, 2),
        new THREE.MeshPhysicalMaterial({
          color: artist.identity.secondary,
          metalness: artist.identity.metalness,
          roughness: artist.identity.roughness,
          clearcoat: 0.58,
          clearcoatRoughness: 0.22
        })
      );
      shell.castShadow = this.quality.shadows;
      shell.userData.trackId = track.id;
      group.add(shell);

      const inset = new THREE.Mesh(
        new THREE.BoxGeometry(1.12, 0.44, 0.04),
        new THREE.MeshStandardMaterial({ color: artist.identity.accent, emissive: artist.identity.accent, emissiveIntensity: 0.18, metalness: 0.1, roughness: 0.5 })
      );
      inset.position.z = 0.141;
      inset.userData.trackId = track.id;
      group.add(inset);

      const notch = new THREE.Mesh(
        new THREE.CylinderGeometry(0.07, 0.07, 0.16, 18),
        new THREE.MeshStandardMaterial({ color: 0x050706, metalness: 0.75, roughness: 0.2 })
      );
      notch.rotation.x = Math.PI / 2;
      notch.position.set(0.58, -0.25, 0.17);
      notch.userData.trackId = track.id;
      group.add(notch);

      this.scene.add(group);
      this.pickables.push(shell, inset, notch);
      this.modules.set(track.id, {
        group,
        homePosition: group.position.clone(),
        homeQuaternion: group.quaternion.clone(),
        track
      });
    });
  }

  private async insert(record: ModuleRecord): Promise<void> {
    const start = record.group.position.clone();
    const startQuaternion = record.group.quaternion.clone();
    const alignQuaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.08, 0, 0));
    const target = new THREE.Vector3(0, -0.57, 0.93);
    const path = new THREE.CatmullRomCurve3([
      start,
      start.clone().add(new THREE.Vector3(0, 0.9, 1.05)),
      new THREE.Vector3(start.x * 0.28, 0.45, 2.6),
      new THREE.Vector3(0, -0.05, 1.85),
      target
    ]);

    this.onPhase("SELECTED");
    await this.animate(150, (t) => {
      const s = 1 + 0.06 * easeOutQuint(t);
      record.group.scale.setScalar(s);
    });

    this.onPhase("ANTICIPATION");
    await this.animate(180, (t) => {
      this.slotGate.position.y = 0.16 + 0.12 * easeOutQuint(t);
      this.deckLight.intensity = 4 + 4 * t;
    });

    this.onPhase("TRAVEL");
    await this.animate(680, (t) => {
      const p = path.getPoint(easeInOutCubic(t));
      record.group.position.copy(p);
      record.group.quaternion.copy(startQuaternion).slerp(alignQuaternion, easeInOutCubic(t));
      record.group.scale.setScalar(1.06 - 0.04 * t);
      this.camera.position.x = THREE.MathUtils.lerp(0, start.x * -0.06, t);
    });

    this.onPhase("ALIGN");
    await this.animate(170, (t) => {
      record.group.position.lerpVectors(path.getPoint(0.92), new THREE.Vector3(0, -0.36, 1.24), easeOutQuint(t));
      record.group.quaternion.slerp(alignQuaternion, easeOutQuint(t));
    });

    this.onPhase("INSERT");
    const insertFrom = record.group.position.clone();
    await this.animate(210, (t) => {
      record.group.position.lerpVectors(insertFrom, target, easeInOutCubic(t));
      this.slotGate.position.y = THREE.MathUtils.lerp(0.28, 0.16, t);
    });

    this.onPhase("CONTACT");
    this.deckLight.intensity = 12;
    record.group.scale.setScalar(1);
    await this.animate(70, (t) => {
      record.group.position.z = target.z - Math.sin(t * Math.PI) * 0.028;
    });

    this.onPhase("ACTIVATING");
    await this.animate(160, (t) => {
      this.deckLight.intensity = THREE.MathUtils.lerp(12, 8, t);
    });
  }

  private async eject(record: ModuleRecord): Promise<void> {
    this.onPhase("EJECT");
    const start = record.group.position.clone();
    const retreat = new THREE.Vector3(0, 0.1, 2.15);
    await this.animate(this.quality.reducedMotion ? 40 : 300, (t) => {
      record.group.position.lerpVectors(start, retreat, easeOutQuint(t));
      this.deckLight.intensity = THREE.MathUtils.lerp(8, 4, t);
    });
    this.onPhase("RETURN");
    const qStart = record.group.quaternion.clone();
    await this.animate(this.quality.reducedMotion ? 40 : 430, (t) => {
      record.group.position.lerpVectors(retreat, record.homePosition, easeInOutCubic(t));
      record.group.quaternion.copy(qStart).slerp(record.homeQuaternion, easeInOutCubic(t));
    });
  }

  private animate(durationMs: number, update: (t: number) => void): Promise<void> {
    return new Promise((resolve) => {
      const start = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / Math.max(1, durationMs));
        update(t);
        if (t < 1) requestAnimationFrame(step);
        else resolve();
      };
      requestAnimationFrame(step);
    });
  }

  private frame = (): void => {
    if (!this.running) return;
    requestAnimationFrame(this.frame);
    this.currentBackground.lerp(this.targetBackground, 0.035);
    this.scene.background = this.currentBackground;

    const pulse = 1 + this.signalEnergy * 0.22;
    this.deckLight.intensity += (4 * pulse - this.deckLight.intensity) * 0.025;

    for (const [trackId, record] of this.modules) {
      if (trackId !== this.activeTrackId) {
        record.group.rotation.y += 0.0007 * (1 + this.signalEnergy);
      }
    }

    this.camera.lookAt(0, 0.1, 0);
    this.renderer.render(this.scene, this.camera);
  };

  private resize(canvas: HTMLCanvasElement): void {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    this.renderer.resize(width, height);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  private handlePointer = (event: PointerEvent): void => {
    const canvas = event.currentTarget as HTMLCanvasElement;
    const rect = canvas.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hit = this.raycaster.intersectObjects(this.pickables, false)[0];
    const trackId = hit?.object.userData.trackId;
    if (typeof trackId === "string") this.onRequestSelect(trackId);
  };
}
