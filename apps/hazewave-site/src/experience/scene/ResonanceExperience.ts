import * as THREE from "three";
import { getArtist, tracks } from "../../data/catalog";
import type { Track } from "../../data/catalog";
import type { PlayerPhase } from "../state/playerMachine";
import type { QualityProfile } from "../quality/quality";
import { createRenderer, type RendererAdapter } from "../renderer/createRenderer";
import { CinematicMotionDriver } from "../animation/CinematicMotionDriver";

type PhaseSink = (phase: PlayerPhase) => void;
type TrackSink = (trackId: string) => void;

interface ModuleRecord {
  group: THREE.Group;
  homePosition: THREE.Vector3;
  homeQuaternion: THREE.Quaternion;
  track: Track;
  accent: THREE.Color;
  focusScale: number;
}

interface DeckParts {
  root: THREE.Group;
  light: THREE.PointLight;
  gateLeft: THREE.Mesh;
  gateRight: THREE.Mesh;
  ring: THREE.Mesh;
  ringMaterial: THREE.MeshStandardMaterial;
  haloMaterial: THREE.MeshBasicMaterial;
  contactPulse: THREE.Mesh;
  contactPulseMaterial: THREE.MeshBasicMaterial;
  screenTexture: THREE.CanvasTexture;
  screenContext: CanvasRenderingContext2D;
}

const easeOutQuint = (t: number) => 1 - Math.pow(1 - t, 5);
const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const easeOutBack = (t: number) => {
  const c1 = 1.18;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};

function roundedRectShape(width: number, height: number, radius: number): THREE.Shape {
  const x = -width / 2;
  const y = -height / 2;
  const r = Math.min(radius, width / 2, height / 2);
  const shape = new THREE.Shape();
  shape.moveTo(x + r, y);
  shape.lineTo(x + width - r, y);
  shape.quadraticCurveTo(x + width, y, x + width, y + r);
  shape.lineTo(x + width, y + height - r);
  shape.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  shape.lineTo(x + r, y + height);
  shape.quadraticCurveTo(x, y + height, x, y + height - r);
  shape.lineTo(x, y + r);
  shape.quadraticCurveTo(x, y, x + r, y);
  return shape;
}

function extrudedPanel(width: number, height: number, depth: number, radius: number): THREE.ExtrudeGeometry {
  const geometry = new THREE.ExtrudeGeometry(roundedRectShape(width, height, radius), {
    depth,
    steps: 1,
    curveSegments: 12,
    bevelEnabled: true,
    bevelSegments: 3,
    bevelSize: Math.min(0.055, depth * 0.16),
    bevelThickness: Math.min(0.055, depth * 0.16)
  });
  geometry.translate(0, 0, -depth / 2);
  geometry.computeVertexNormals();
  return geometry;
}

function makeLabelTexture(track: Track, accent: string): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 768;
  canvas.height = 384;
  const ctx = canvas.getContext("2d")!;
  const artist = getArtist(track.artistId);

  ctx.fillStyle = "#0a0d0c";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  gradient.addColorStop(0, accent);
  gradient.addColorStop(0.58, accent);
  gradient.addColorStop(1, "#ffffff");
  ctx.globalAlpha = 0.12;
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.globalAlpha = 1;

  ctx.fillStyle = accent;
  ctx.fillRect(54, 48, 92, 8);

  ctx.font = "700 26px Arial, sans-serif";
  ctx.fillStyle = "rgba(255,255,255,.58)";
  ctx.letterSpacing = "3px";
  ctx.fillText(artist.name.replace(" / DEMO", ""), 54, 108);

  ctx.font = "700 56px Arial, sans-serif";
  ctx.fillStyle = "#f8f6ef";
  ctx.fillText(track.title.toUpperCase(), 54, 190, 630);

  ctx.font = "600 20px ui-monospace, monospace";
  ctx.fillStyle = "rgba(255,255,255,.46)";
  ctx.fillText(`HZV // ${track.visual.bpm} BPM // ${track.id.toUpperCase()}`, 54, 250);

  ctx.strokeStyle = "rgba(255,255,255,.18)";
  ctx.lineWidth = 2;
  for (let i = 0; i < 18; i += 1) {
    const x = 54 + i * 28;
    const height = 22 + ((i * 17) % 34);
    ctx.beginPath();
    ctx.moveTo(x, 320 - height / 2);
    ctx.lineTo(x, 320 + height / 2);
    ctx.stroke();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;
  return texture;
}

export class ResonanceExperience {
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
  private renderer: RendererAdapter;
  private motion = new CinematicMotionDriver();
  private quality: QualityProfile;
  private world = new THREE.Group();
  private modules = new Map<string, ModuleRecord>();
  private pickables: THREE.Object3D[] = [];
  private raycaster = new THREE.Raycaster();
  private pointer = new THREE.Vector2();
  private activeTrackId: string | null = null;
  private deck: DeckParts;
  private running = true;
  private playing = false;
  private signalEnergy = 0;
  private targetBackground = new THREE.Color("#06100f");
  private currentBackground = new THREE.Color("#06100f");
  private targetAccent = new THREE.Color("#a7ffe0");
  private currentAccent = new THREE.Color("#a7ffe0");
  private onPhase: PhaseSink;
  private onRequestSelect: TrackSink;
  private resizeObserver: ResizeObserver;
  private canvas: HTMLCanvasElement;
  private pointerDownLocked = false;
  private hoveredTrackId: string | null = null;
  private idleClock = new THREE.Clock();
  private lastFrameAt = performance.now();
  private frameSamples: number[] = [];
  private frameMetricCounter = 0;

  constructor(
    canvas: HTMLCanvasElement,
    quality: QualityProfile,
    onPhase: PhaseSink,
    onRequestSelect: TrackSink
  ) {
    this.canvas = canvas;
    this.quality = quality;
    this.onPhase = onPhase;
    this.onRequestSelect = onRequestSelect;
    this.renderer = createRenderer(canvas, quality);

    this.scene.background = this.currentBackground;
    this.scene.fog = new THREE.FogExp2(this.currentBackground.clone(), 0.035);
    this.scene.add(this.world);

    this.camera.position.set(0, 1.15, 11.6);
    this.camera.lookAt(0, -0.15, 0);

    const hemi = new THREE.HemisphereLight(0xd9f6ef, 0x050505, 1.5);
    this.scene.add(hemi);

    const key = new THREE.DirectionalLight(0xf8fff9, 4.8);
    key.position.set(-4.5, 7, 5.5);
    key.castShadow = quality.shadows;
    if (quality.shadows) {
      key.shadow.mapSize.set(1024, 1024);
      key.shadow.camera.near = 0.5;
      key.shadow.camera.far = 22;
    }
    this.scene.add(key);

    const rim = new THREE.DirectionalLight(0x77e8d0, 2.2);
    rim.position.set(5, 2.5, -3);
    this.scene.add(rim);

    this.deck = this.buildDeck();
    this.world.add(this.deck.root);
    this.buildModules();
    this.buildEnvironment();

    canvas.addEventListener("pointerdown", this.handlePointerDown);
    canvas.addEventListener("pointermove", this.handlePointerMove);
    canvas.addEventListener("pointerleave", this.handlePointerLeave);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas);
    this.resize();
    this.drawDeckScreen(null, "STANDBY");
    this.frame();
  }

  async select(trackId: string): Promise<void> {
    if (this.pointerDownLocked) return;
    const next = this.modules.get(trackId);
    if (!next) throw new Error(`MODULE_NOT_FOUND:${trackId}`);
    if (this.activeTrackId === trackId) return;

    this.pointerDownLocked = true;
    try {
      if (this.activeTrackId) {
        const previous = this.modules.get(this.activeTrackId);
        if (previous) await this.eject(previous);
      }

      this.activeTrackId = trackId;
      const artist = getArtist(next.track.artistId);
      this.targetBackground.set(artist.identity.background);
      this.targetAccent.set(artist.identity.accent);
      this.drawDeckScreen(next.track, "SELECTED");

      if (this.quality.reducedMotion) {
        this.onPhase("SELECTED");
        next.group.position.set(0, -0.22, 1.02);
        next.group.rotation.set(-0.04, 0, 0);
        next.group.scale.setScalar(1);
        this.setOtherModuleFocus(trackId, 0.84);
        this.openGate(1);
        this.onPhase("CONTACT");
        this.drawDeckScreen(next.track, "READY");
        return;
      }

      await this.insert(next);
    } finally {
      this.pointerDownLocked = false;
    }
  }

  setSignalEnergy(value: number): void {
    this.signalEnergy = THREE.MathUtils.clamp(value, 0, 1);
  }

  setPlaying(isPlaying: boolean): void {
    this.playing = isPlaying;
    const track = this.activeTrackId ? this.modules.get(this.activeTrackId)?.track ?? null : null;
    this.drawDeckScreen(track, isPlaying ? "PLAYING" : "PAUSED");
  }

  dispose(): void {
    this.running = false;
    this.motion.killAll();
    this.resizeObserver.disconnect();
    this.canvas.removeEventListener("pointerdown", this.handlePointerDown);
    this.canvas.removeEventListener("pointermove", this.handlePointerMove);
    this.canvas.removeEventListener("pointerleave", this.handlePointerLeave);
    for (const record of this.modules.values()) {
      record.group.traverse((node) => {
        const mesh = node as THREE.Mesh;
        if (!mesh.isMesh) return;
        mesh.geometry?.dispose();
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const material of materials) material?.dispose();
      });
    }
    this.deck.screenTexture.dispose();
    this.renderer.dispose();
  }

  private buildDeck(): DeckParts {
    const root = new THREE.Group();
    root.position.set(0, -1.0, -0.15);

    const housing = new THREE.Mesh(
      extrudedPanel(5.35, 2.14, 0.7, 0.28),
      new THREE.MeshPhysicalMaterial({
        color: 0x101413,
        metalness: 0.72,
        roughness: 0.27,
        clearcoat: 0.58,
        clearcoatRoughness: 0.2
      })
    );
    housing.castShadow = this.quality.shadows;
    housing.receiveShadow = this.quality.shadows;
    root.add(housing);

    const crown = new THREE.Mesh(
      extrudedPanel(5.0, 0.22, 0.1, 0.08),
      new THREE.MeshStandardMaterial({
        color: 0x272e2c,
        metalness: 0.9,
        roughness: 0.2
      })
    );
    crown.position.set(0, 0.84, 0.43);
    root.add(crown);

    const bay = new THREE.Mesh(
      extrudedPanel(1.72, 1.62, 0.12, 0.24),
      new THREE.MeshStandardMaterial({
        color: 0x030504,
        metalness: 0.24,
        roughness: 0.34
      })
    );
    bay.position.set(-0.84, 0.02, 0.47);
    root.add(bay);

    const bayBack = new THREE.Mesh(
      new THREE.PlaneGeometry(1.42, 1.32),
      new THREE.MeshBasicMaterial({ color: 0x060a09, toneMapped: false })
    );
    bayBack.position.set(-0.84, 0.02, 0.545);
    root.add(bayBack);

    const ringMaterial = new THREE.MeshStandardMaterial({
      color: 0xa7ffe0,
      emissive: 0x3ecfaf,
      emissiveIntensity: 1.8,
      metalness: 0.55,
      roughness: 0.18
    });
    const ring = new THREE.Mesh(
      new THREE.BoxGeometry(1.42, 0.055, 0.045),
      ringMaterial
    );
    ring.position.set(-0.84, -0.73, 0.59);
    root.add(ring);

    const gateMaterial = new THREE.MeshPhysicalMaterial({
      color: 0xcbd3d0,
      metalness: 0.92,
      roughness: 0.2,
      clearcoat: 0.38
    });
    const gateLeft = new THREE.Mesh(
      extrudedPanel(0.12, 1.18, 0.12, 0.045),
      gateMaterial
    );
    const gateRight = gateLeft.clone();
    gateLeft.position.set(-1.62, 0.02, 0.62);
    gateRight.position.set(-0.06, 0.02, 0.62);
    root.add(gateLeft, gateRight);

    const screenCanvas = document.createElement("canvas");
    screenCanvas.width = 1024;
    screenCanvas.height = 512;
    const screenContext = screenCanvas.getContext("2d")!;
    const screenTexture = new THREE.CanvasTexture(screenCanvas);
    screenTexture.colorSpace = THREE.SRGBColorSpace;

    const screenFrame = new THREE.Mesh(
      extrudedPanel(2.35, 1.18, 0.1, 0.18),
      new THREE.MeshStandardMaterial({
        color: 0x1a1f1e,
        metalness: 0.88,
        roughness: 0.19
      })
    );
    screenFrame.position.set(1.25, 0.13, 0.48);
    root.add(screenFrame);

    const screen = new THREE.Mesh(
      new THREE.PlaneGeometry(2.15, 0.98),
      new THREE.MeshBasicMaterial({ map: screenTexture, toneMapped: false })
    );
    screen.position.set(1.25, 0.13, 0.545);
    root.add(screen);

    const statusBar = new THREE.Mesh(
      new THREE.BoxGeometry(1.72, 0.045, 0.035),
      new THREE.MeshBasicMaterial({ color: 0xa7ffe0 })
    );
    statusBar.position.set(1.08, -0.65, 0.56);
    root.add(statusBar);

    const knob = new THREE.Mesh(
      new THREE.CylinderGeometry(0.18, 0.18, 0.1, this.quality.tier === "LOW" ? 20 : 40),
      new THREE.MeshStandardMaterial({
        color: 0xd2d7d4,
        metalness: 0.95,
        roughness: 0.22
      })
    );
    knob.rotation.x = Math.PI / 2;
    knob.position.set(2.22, -0.58, 0.51);
    root.add(knob);

    const seamMaterial = new THREE.MeshBasicMaterial({
      color: 0xa7ffe0,
      transparent: true,
      opacity: 0.26
    });
    for (const x of [-2.42, 2.42]) {
      const seam = new THREE.Mesh(new THREE.BoxGeometry(0.025, 1.48, 0.025), seamMaterial);
      seam.position.set(x, 0, 0.43);
      root.add(seam);
    }

    const light = new THREE.PointLight(0xa7ffe0, 4.4, 6.5, 1.8);
    light.position.set(-0.84, -0.02, 1.45);
    root.add(light);

    const contactPulseMaterial = new THREE.MeshBasicMaterial({
      color: 0xa7ffe0,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const contactPulse = new THREE.Mesh(
      new THREE.ShapeGeometry(roundedRectShape(1.52, 1.42, 0.22)),
      contactPulseMaterial
    );
    contactPulse.position.set(-0.84, 0.02, 0.655);
    root.add(contactPulse);

    const haloMaterial = new THREE.MeshBasicMaterial({
      color: 0xa7ffe0,
      transparent: true,
      opacity: 0.1,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const halo = new THREE.Mesh(
      new THREE.RingGeometry(2.85, 2.88, this.quality.tier === "LOW" ? 64 : 128),
      haloMaterial
    );
    halo.rotation.x = -Math.PI / 2;
    halo.position.set(0, -1.18, 0);
    root.add(halo);

    return {
      root,
      light,
      gateLeft,
      gateRight,
      ring,
      ringMaterial,
      haloMaterial,
      contactPulse,
      contactPulseMaterial,
      screenTexture,
      screenContext
    };
  }

  private buildModules(): void {
    const homes = [
      new THREE.Vector3(-3.1, 1.55, -0.05),
      new THREE.Vector3(-1.05, 2.05, -0.18),
      new THREE.Vector3(1.05, 2.05, -0.18),
      new THREE.Vector3(3.1, 1.55, -0.05),
      new THREE.Vector3(-2.55, 0.28, -0.32),
      new THREE.Vector3(2.55, 0.28, -0.32)
    ];

    tracks.forEach((track, index) => {
      const artist = getArtist(track.artistId);
      const accent = new THREE.Color(artist.identity.accent);
      const group = new THREE.Group();
      group.position.copy(homes[index] ?? new THREE.Vector3());
      group.rotation.set(
        -0.045,
        group.position.x < 0 ? 0.11 : -0.11,
        group.position.x < 0 ? -0.028 : 0.028
      );

      const shellMaterial = new THREE.MeshPhysicalMaterial({
        color: artist.identity.secondary,
        metalness: artist.identity.metalness,
        roughness: artist.identity.roughness,
        clearcoat: track.artistId === "aether" ? 0.88 : 0.48,
        clearcoatRoughness: 0.18,
        transmission:
          track.artistId === "aether" && (this.quality.tier === "HIGH" || this.quality.tier === "ULTRA")
            ? 0.1
            : 0,
        thickness: 0.22,
        transparent: false
      });

      const shell = new THREE.Mesh(
        extrudedPanel(1.34, 1.34, 0.19, 0.18),
        shellMaterial
      );
      shell.castShadow = this.quality.shadows;
      shell.receiveShadow = this.quality.shadows;
      shell.userData.trackId = track.id;
      group.add(shell);

      const inset = new THREE.Mesh(
        extrudedPanel(1.08, 1.08, 0.055, 0.14),
        new THREE.MeshStandardMaterial({
          color: 0x080b0a,
          metalness: 0.28,
          roughness: 0.38
        })
      );
      inset.position.z = 0.115;
      inset.userData.trackId = track.id;
      group.add(inset);

      const labelTexture = makeLabelTexture(track, artist.identity.accent);
      const label = new THREE.Mesh(
        new THREE.PlaneGeometry(0.98, 0.98),
        new THREE.MeshBasicMaterial({
          map: labelTexture,
          transparent: true,
          toneMapped: false
        })
      );
      label.position.z = 0.148;
      label.userData.trackId = track.id;
      group.add(label);

      const edge = new THREE.LineSegments(
        new THREE.EdgesGeometry(shell.geometry, 24),
        new THREE.LineBasicMaterial({
          color: accent,
          transparent: true,
          opacity: track.artistId === "aether" ? 0.46 : 0.24
        })
      );
      edge.userData.trackId = track.id;
      group.add(edge);

      if (track.artistId === "monolith") {
        const barMaterial = new THREE.MeshStandardMaterial({
          color: 0xd1c2ad,
          metalness: 0.94,
          roughness: 0.22
        });
        for (const y of [-0.48, 0.48]) {
          const rail = new THREE.Mesh(new THREE.BoxGeometry(0.86, 0.055, 0.25), barMaterial);
          rail.position.set(0, y, 0.02);
          rail.userData.trackId = track.id;
          group.add(rail);
        }
      } else if (track.artistId === "flora") {
        const spine = new THREE.Mesh(
          new THREE.BoxGeometry(0.085, 0.86, 0.26),
          new THREE.MeshStandardMaterial({
            color: accent,
            emissive: accent,
            emissiveIntensity: 0.42,
            metalness: 0.12,
            roughness: 0.45
          })
        );
        spine.position.set(-0.55, 0, 0.01);
        spine.userData.trackId = track.id;
        group.add(spine);
      } else {
        const lens = new THREE.Mesh(
          new THREE.CircleGeometry(0.085, this.quality.tier === "LOW" ? 20 : 32),
          new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.82 })
        );
        lens.position.set(0.5, -0.49, 0.155);
        lens.userData.trackId = track.id;
        group.add(lens);
      }

      const indexPlate = new THREE.Mesh(
        new THREE.BoxGeometry(0.36, 0.045, 0.035),
        new THREE.MeshBasicMaterial({ color: accent })
      );
      indexPlate.position.set(-0.37, -0.55, 0.155);
      indexPlate.userData.trackId = track.id;
      group.add(indexPlate);

      this.world.add(group);
      group.traverse((node) => {
        if ((node as THREE.Mesh).isMesh) {
          node.userData.trackId = track.id;
          this.pickables.push(node);
        }
      });

      this.modules.set(track.id, {
        group,
        homePosition: group.position.clone(),
        homeQuaternion: group.quaternion.clone(),
        track,
        accent,
        focusScale: 1
      });
    });
  }

  private buildEnvironment(): void {
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(28, 22),
      new THREE.MeshStandardMaterial({
        color: 0x030504,
        metalness: 0.12,
        roughness: 0.8
      })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -2.18;
    floor.receiveShadow = this.quality.shadows;
    this.world.add(floor);

    const platform = new THREE.Mesh(
      new THREE.CylinderGeometry(3.65, 4.0, 0.32, 96),
      new THREE.MeshPhysicalMaterial({
        color: 0x080b0a,
        metalness: 0.48,
        roughness: 0.34,
        clearcoat: 0.35
      })
    );
    platform.position.y = -2.0;
    platform.receiveShadow = this.quality.shadows;
    this.world.add(platform);

    const horizon = new THREE.Mesh(
      new THREE.TorusGeometry(5.8, 0.012, 8, 160),
      new THREE.MeshBasicMaterial({
        color: 0x5a8f84,
        transparent: true,
        opacity: 0.18,
        depthWrite: false
      })
    );
    horizon.rotation.x = Math.PI / 2;
    horizon.position.y = -1.75;
    this.world.add(horizon);

    const points = new THREE.BufferGeometry();
    const count = this.quality.tier === "LOW" ? 48 : 110;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const angle = i * 2.399963;
      const radius = 6 + ((i * 37) % 100) / 15;
      positions[i * 3] = Math.cos(angle) * radius;
      positions[i * 3 + 1] = -0.5 + ((i * 23) % 100) / 18;
      positions[i * 3 + 2] = -3 - ((i * 13) % 100) / 14;
    }
    points.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const particles = new THREE.Points(
      points,
      new THREE.PointsMaterial({
        color: 0xcaf7eb,
        size: this.quality.tier === "LOW" ? 0.025 : 0.035,
        transparent: true,
        opacity: 0.22,
        depthWrite: false
      })
    );
    this.world.add(particles);
  }

  private async insert(record: ModuleRecord): Promise<void> {
    const start = record.group.position.clone();
    const startQuaternion = record.group.quaternion.clone();
    const alignQuaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.04, 0, 0));
    const target = new THREE.Vector3(-0.84, -0.98, 0.66);
    const path = new THREE.CatmullRomCurve3([
      start,
      start.clone().add(new THREE.Vector3(start.x < 0 ? 0.45 : -0.45, 0.55, 0.95)),
      new THREE.Vector3(start.x * 0.34, 0.9, 2.85),
      new THREE.Vector3(-0.25, -0.15, 2.25),
      new THREE.Vector3(-0.84, -0.64, 1.5),
      target
    ]);

    this.setOtherModuleFocus(record.track.id, 0.88);

    this.onPhase("SELECTED");
    await this.animate(125, (t) => {
      const s = THREE.MathUtils.lerp(1, 1.075, easeOutBack(t));
      record.group.scale.setScalar(s);
      record.group.position.z = THREE.MathUtils.lerp(start.z, start.z + 0.18, easeOutQuint(t));
    });

    this.onPhase("ANTICIPATION");
    this.drawDeckScreen(record.track, "LINKING");
    await this.animate(190, (t) => {
      this.openGate(t);
      this.deck.light.intensity = THREE.MathUtils.lerp(5.2, 10.5, t);
      this.deck.ringMaterial.emissiveIntensity = THREE.MathUtils.lerp(2.4, 5.6, t);
      this.camera.position.z = THREE.MathUtils.lerp(this.camera.position.z, 10.9, 0.08);
    });

    this.onPhase("TRAVEL");
    await this.animate(760, (t) => {
      const u = easeInOutCubic(t);
      record.group.position.copy(path.getPoint(u));
      record.group.quaternion.copy(startQuaternion).slerp(alignQuaternion, u);
      record.group.scale.setScalar(THREE.MathUtils.lerp(1.075, 1.02, u));
      this.camera.position.x = THREE.MathUtils.lerp(0, start.x * -0.055, Math.sin(t * Math.PI));
      this.camera.position.y = THREE.MathUtils.lerp(1.15, 0.95, Math.sin(t * Math.PI));
    });

    this.onPhase("ALIGN");
    const alignFrom = record.group.position.clone();
    await this.animate(185, (t) => {
      const u = easeOutQuint(t);
      record.group.position.lerpVectors(alignFrom, new THREE.Vector3(-0.84, -0.78, 1.18), u);
      record.group.quaternion.copy(record.group.quaternion).slerp(alignQuaternion, u);
    });

    this.onPhase("INSERT");
    const insertFrom = record.group.position.clone();
    await this.animate(250, (t) => {
      const u = easeInOutCubic(t);
      record.group.position.lerpVectors(insertFrom, target, u);
      record.group.scale.setScalar(THREE.MathUtils.lerp(1.02, 0.8, u));
      this.closeGate(u);
    });

    this.onPhase("CONTACT");
    this.deck.light.intensity = 14;
    this.deck.ringMaterial.emissiveIntensity = 7.5;
    this.deck.contactPulseMaterial.color.copy(record.accent);
    this.deck.contactPulseMaterial.opacity = 0.82;
    this.deck.contactPulse.scale.setScalar(0.72);
    this.drawDeckScreen(record.track, "LOCKED");
    await this.animate(128, (t) => {
      const kick = Math.sin(t * Math.PI);
      record.group.position.z = target.z - kick * 0.035;
      this.deck.root.position.z = -0.15 - kick * 0.018;
      this.deck.contactPulse.scale.setScalar(THREE.MathUtils.lerp(0.72, 1.65, easeOutQuint(t)));
      this.deck.contactPulseMaterial.opacity = THREE.MathUtils.lerp(0.82, 0, easeOutQuint(t));
    });
    this.deck.root.position.z = -0.15;

    this.onPhase("ACTIVATING");
    await this.animate(190, (t) => {
      this.deck.light.intensity = THREE.MathUtils.lerp(14, 8.5, t);
      this.deck.ringMaterial.emissiveIntensity = THREE.MathUtils.lerp(7.5, 3.7, t);
      this.camera.position.x = THREE.MathUtils.lerp(this.camera.position.x, 0, t);
      this.camera.position.y = THREE.MathUtils.lerp(this.camera.position.y, 1.05, t);
    });
  }

  private async eject(record: ModuleRecord): Promise<void> {
    this.playing = false;
    this.onPhase("EJECT");
    this.drawDeckScreen(record.track, "EJECTING");
    const start = record.group.position.clone();
    const retreat = new THREE.Vector3(-0.2, -0.05, 2.55);

    await this.animate(this.quality.reducedMotion ? 45 : 310, (t) => {
      const u = easeOutQuint(t);
      record.group.position.lerpVectors(start, retreat, u);
      record.group.scale.setScalar(THREE.MathUtils.lerp(0.8, 1.02, u));
      this.openGate(u);
      this.deck.ringMaterial.emissiveIntensity = THREE.MathUtils.lerp(3.7, 1.8, u);
    });

    this.onPhase("RETURN");
    const qStart = record.group.quaternion.clone();
    await this.animate(this.quality.reducedMotion ? 45 : 510, (t) => {
      const u = easeInOutCubic(t);
      record.group.position.lerpVectors(retreat, record.homePosition, u);
      record.group.quaternion.copy(qStart).slerp(record.homeQuaternion, u);
      record.group.scale.setScalar(THREE.MathUtils.lerp(1.02, 1, u));
    });

    this.setAllModuleFocus();
    this.closeGate(1);
    this.drawDeckScreen(null, "STANDBY");
  }

  private setOtherModuleFocus(trackId: string, scale: number): void {
    for (const [id, record] of this.modules) {
      record.focusScale = id === trackId ? 1 : scale;
    }
  }

  private setAllModuleFocus(): void {
    for (const record of this.modules.values()) record.focusScale = 1;
  }

  private openGate(t: number): void {
    const u = easeOutQuint(THREE.MathUtils.clamp(t, 0, 1));
    this.deck.gateLeft.position.x = THREE.MathUtils.lerp(-1.14, -1.42, u);
    this.deck.gateRight.position.x = THREE.MathUtils.lerp(-0.54, -0.26, u);
    this.deck.gateLeft.rotation.z = THREE.MathUtils.lerp(0, -0.18, u);
    this.deck.gateRight.rotation.z = THREE.MathUtils.lerp(0, 0.18, u);
  }

  private closeGate(t: number): void {
    const u = easeInOutCubic(THREE.MathUtils.clamp(t, 0, 1));
    this.deck.gateLeft.position.x = THREE.MathUtils.lerp(-1.42, -1.14, u);
    this.deck.gateRight.position.x = THREE.MathUtils.lerp(-0.26, -0.54, u);
    this.deck.gateLeft.rotation.z = THREE.MathUtils.lerp(-0.18, 0, u);
    this.deck.gateRight.rotation.z = THREE.MathUtils.lerp(0.18, 0, u);
  }

  private drawDeckScreen(track: Track | null, status: string): void {
    const ctx = this.deck?.screenContext;
    const texture = this.deck?.screenTexture;
    if (!ctx || !texture) return;
    const w = ctx.canvas.width;
    const h = ctx.canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#050807";
    ctx.fillRect(0, 0, w, h);

    const accent = track ? getArtist(track.artistId).identity.accent : "#a7ffe0";
    const gradient = ctx.createLinearGradient(0, 0, w, h);
    gradient.addColorStop(0, accent);
    gradient.addColorStop(1, "#0b1110");
    ctx.globalAlpha = 0.12;
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);
    ctx.globalAlpha = 1;

    ctx.fillStyle = accent;
    ctx.fillRect(54, 52, 120, 9);
    ctx.font = "700 23px ui-monospace, monospace";
    ctx.fillText(`HAZEWAVE // ${status}`, 54, 110);

    ctx.fillStyle = "#f7f4ec";
    ctx.font = "700 54px Arial, sans-serif";
    ctx.fillText(track ? track.title.toUpperCase() : "AWAITING SIGNAL", 54, 210, 860);

    ctx.font = "600 22px ui-monospace, monospace";
    ctx.fillStyle = "rgba(255,255,255,.55)";
    if (track) {
      const artist = getArtist(track.artistId);
      ctx.fillText(`${artist.name.replace(" / DEMO", "")}  //  ${track.visual.bpm} BPM`, 54, 270);
    } else {
      ctx.fillText("SELECT A RESONANCE MODULE", 54, 270);
    }

    ctx.strokeStyle = "rgba(255,255,255,.12)";
    ctx.lineWidth = 2;
    for (let i = 0; i < 34; i += 1) {
      const x = 54 + i * 26;
      const amp = 18 + ((i * 29) % 76);
      ctx.beginPath();
      ctx.moveTo(x, 390 - amp / 2);
      ctx.lineTo(x, 390 + amp / 2);
      ctx.stroke();
    }
    texture.needsUpdate = true;
  }

  private animate(durationMs: number, update: (t: number) => void): Promise<void> {
    return this.motion.progress(durationMs, update);
  }

  private frame = (): void => {
    if (!this.running) return;
    requestAnimationFrame(this.frame);

    const elapsed = this.idleClock.getElapsedTime();
    const now = performance.now();
    const delta = now - this.lastFrameAt;
    this.lastFrameAt = now;
    if (delta > 0 && delta < 500) {
      this.frameSamples.push(delta);
      if (this.frameSamples.length > 180) this.frameSamples.shift();
      this.frameMetricCounter += 1;
      if (this.frameMetricCounter % 30 === 0 && this.frameSamples.length >= 30) {
        const sorted = [...this.frameSamples].sort((a, b) => a - b);
        const p95 = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))] ?? 0;
        const average = this.frameSamples.reduce((sum, value) => sum + value, 0) / this.frameSamples.length;
        this.canvas.dataset.fps = (1000 / average).toFixed(1);
        this.canvas.dataset.frameP95Ms = p95.toFixed(1);
      }
    }

    this.currentBackground.lerp(this.targetBackground, 0.028);
    this.currentAccent.lerp(this.targetAccent, 0.04);
    this.scene.background = this.currentBackground;
    if (this.scene.fog instanceof THREE.FogExp2) {
      this.scene.fog.color.lerp(this.currentBackground, 0.05);
    }

    this.deck.ringMaterial.color.lerp(this.currentAccent, 0.06);
    this.deck.ringMaterial.emissive.lerp(this.currentAccent, 0.06);
    this.deck.haloMaterial.color.lerp(this.currentAccent, 0.06);

    const baseLight = this.playing ? 7.8 : 4.8;
    const audioLift = this.playing ? this.signalEnergy * 8 : Math.sin(elapsed * 1.8) * 0.45;
    this.deck.light.color.lerp(this.currentAccent, 0.08);
    this.deck.light.intensity += (baseLight + audioLift - this.deck.light.intensity) * 0.1;

    const ringTarget = this.playing ? 3.8 + this.signalEnergy * 4.2 : 2.2;
    this.deck.ringMaterial.emissiveIntensity +=
      (ringTarget - this.deck.ringMaterial.emissiveIntensity) * 0.08;

    for (const [trackId, record] of this.modules) {
      if (trackId !== this.activeTrackId && !this.pointerDownLocked) {
        const phase = Number.parseInt(trackId.replace(/\D/g, "").slice(-2) || "1", 10);
        const hovered = trackId === this.hoveredTrackId;
        const targetScale = record.focusScale * (hovered ? 1.045 : 1);
        const nextScale = THREE.MathUtils.lerp(record.group.scale.x, targetScale, hovered ? 0.16 : 0.1);
        record.group.scale.setScalar(nextScale);
        record.group.rotation.z =
          (record.homePosition.x < 0 ? -0.035 : 0.035) +
          Math.sin(elapsed * 0.38 + phase) * 0.012 +
          (hovered ? (record.homePosition.x < 0 ? -0.018 : 0.018) : 0);
        record.group.position.y =
          record.homePosition.y +
          Math.sin(elapsed * 0.52 + phase * 0.9) * 0.025 +
          (hovered ? 0.055 : 0);
        record.group.position.z = THREE.MathUtils.lerp(
          record.group.position.z,
          record.homePosition.z + (hovered ? 0.18 : 0),
          0.12
        );
      }
    }

    this.deck.root.rotation.y = Math.sin(elapsed * 0.22) * 0.012;
    this.camera.lookAt(0, -0.18, 0);
    this.renderer.render(this.scene, this.camera);
  };

  private resize(): void {
    const rect = this.canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    const aspect = width / height;

    this.renderer.resize(width, height);
    this.camera.aspect = aspect;

    if (aspect < 0.82) {
      this.camera.fov = 43;
      this.camera.position.z = 12.9;
      this.world.scale.setScalar(0.82);
      this.world.position.set(0, -0.15, 0);
    } else if (aspect < 1.2) {
      this.camera.fov = 38;
      this.camera.position.z = 12.1;
      this.world.scale.setScalar(0.9);
      this.world.position.set(0, -0.1, 0);
    } else {
      this.camera.fov = 32;
      this.camera.position.z = 11.6;
      this.world.scale.setScalar(1);
      this.world.position.set(0.45, -0.05, 0);
    }
    this.camera.updateProjectionMatrix();
  }

  private getTrackAtPointer(event: PointerEvent): string | null {
    const rect = this.canvas.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hit = this.raycaster.intersectObjects(this.pickables, false)[0];
    const trackId = hit?.object.userData.trackId;
    return typeof trackId === "string" ? trackId : null;
  }

  private handlePointerDown = (event: PointerEvent): void => {
    if (this.pointerDownLocked) return;
    const trackId = this.getTrackAtPointer(event);
    if (trackId) this.onRequestSelect(trackId);
  };

  private handlePointerMove = (event: PointerEvent): void => {
    if (this.pointerDownLocked) {
      this.hoveredTrackId = null;
      this.canvas.style.cursor = "progress";
      return;
    }
    this.hoveredTrackId = this.getTrackAtPointer(event);
    this.canvas.style.cursor = this.hoveredTrackId ? "pointer" : "default";
  };

  private handlePointerLeave = (): void => {
    this.hoveredTrackId = null;
    this.canvas.style.cursor = "default";
  };
}
