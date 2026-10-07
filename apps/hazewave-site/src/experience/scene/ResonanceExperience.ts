import * as THREE from "three";
import { getArtist, tracks } from "../../data/catalog";
import type { Track } from "../../data/catalog";
import type { PlayerPhase } from "../state/playerMachine";
import type { QualityProfile } from "../quality/quality";
import { createRenderer, type RendererAdapter } from "../renderer/createRenderer";
import { CinematicMotionDriver } from "../animation/CinematicMotionDriver";
import { createArtifactLabelTexture } from "./ArtifactLabelTexture";

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
  private worldLight: THREE.HemisphereLight;
  private targetFogDensity = 0.035;
  private targetAmbientIntensity = 1.5;
  private targetDeckGlow = 1;
  private targetCameraDrift = 0.5;
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

    this.worldLight = new THREE.HemisphereLight(0xd9f6ef, 0x050505, 1.5);
    this.scene.add(this.worldLight);

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
      this.targetFogDensity = artist.identity.world.fogDensity;
      this.targetAmbientIntensity = artist.identity.world.ambientIntensity;
      this.targetDeckGlow = artist.identity.world.deckGlow;
      this.targetCameraDrift = artist.identity.world.cameraDrift;
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
    root.position.set(0, -0.08, -0.55);

    const bodyMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x0c1110,
      metalness: 0.76,
      roughness: 0.23,
      clearcoat: 0.52,
      clearcoatRoughness: 0.18
    });

    const spine = new THREE.Mesh(
      extrudedPanel(2.7, 3.55, 0.62, 0.34),
      bodyMaterial
    );
    spine.castShadow = this.quality.shadows;
    spine.receiveShadow = this.quality.shadows;
    root.add(spine);

    const shoulder = new THREE.Mesh(
      extrudedPanel(3.65, 0.52, 0.48, 0.2),
      new THREE.MeshStandardMaterial({
        color: 0x151b19,
        metalness: 0.82,
        roughness: 0.2
      })
    );
    shoulder.position.set(0, -1.35, -0.02);
    root.add(shoulder);

    const crown = new THREE.Mesh(
      new THREE.TorusGeometry(
        1.17,
        0.08,
        this.quality.tier === "LOW" ? 10 : 18,
        this.quality.tier === "LOW" ? 48 : 96,
        Math.PI
      ),
      new THREE.MeshStandardMaterial({
        color: 0x29312f,
        metalness: 0.9,
        roughness: 0.18
      })
    );
    crown.position.set(0, 1.55, 0.28);
    crown.rotation.z = Math.PI;
    root.add(crown);

    const coreBack = new THREE.Mesh(
      new THREE.CircleGeometry(0.84, this.quality.tier === "LOW" ? 40 : 72),
      new THREE.MeshBasicMaterial({ color: 0x020504, toneMapped: false })
    );
    coreBack.position.set(0, 0.56, 0.42);
    root.add(coreBack);

    const ringMaterial = new THREE.MeshStandardMaterial({
      color: 0xa7ffe0,
      emissive: 0x4fd9bd,
      emissiveIntensity: 2.1,
      metalness: 0.58,
      roughness: 0.14
    });
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(
        0.9,
        0.075,
        this.quality.tier === "LOW" ? 12 : 22,
        this.quality.tier === "LOW" ? 48 : 96
      ),
      ringMaterial
    );
    ring.position.set(0, 0.56, 0.5);
    root.add(ring);

    const irisMaterial = new THREE.MeshPhysicalMaterial({
      color: 0xd8dfdc,
      metalness: 0.93,
      roughness: 0.16,
      clearcoat: 0.32
    });
    const gateLeft = new THREE.Mesh(extrudedPanel(0.38, 1.18, 0.13, 0.18), irisMaterial);
    const gateRight = gateLeft.clone();
    gateLeft.position.set(-0.46, 0.56, 0.58);
    gateRight.position.set(0.46, 0.56, 0.58);
    gateLeft.rotation.z = -0.12;
    gateRight.rotation.z = 0.12;
    root.add(gateLeft, gateRight);

    const coreLens = new THREE.Mesh(
      new THREE.CircleGeometry(0.58, this.quality.tier === "LOW" ? 32 : 64),
      new THREE.MeshBasicMaterial({
        color: 0x0a1714,
        transparent: true,
        opacity: 0.92,
        toneMapped: false
      })
    );
    coreLens.position.set(0, 0.56, 0.62);
    root.add(coreLens);

    const screenCanvas = document.createElement("canvas");
    screenCanvas.width = 1024;
    screenCanvas.height = 512;
    const screenContext = screenCanvas.getContext("2d")!;
    const screenTexture = new THREE.CanvasTexture(screenCanvas);
    screenTexture.colorSpace = THREE.SRGBColorSpace;

    const screenFrame = new THREE.Mesh(
      extrudedPanel(1.95, 0.88, 0.1, 0.18),
      new THREE.MeshStandardMaterial({
        color: 0x171d1b,
        metalness: 0.88,
        roughness: 0.19
      })
    );
    screenFrame.position.set(0, -0.67, 0.34);
    root.add(screenFrame);

    const screen = new THREE.Mesh(
      new THREE.PlaneGeometry(1.76, 0.69),
      new THREE.MeshBasicMaterial({ map: screenTexture, toneMapped: false })
    );
    screen.position.set(0, -0.67, 0.43);
    root.add(screen);

    const statusBar = new THREE.Mesh(
      new THREE.BoxGeometry(1.34, 0.045, 0.035),
      new THREE.MeshBasicMaterial({ color: 0xa7ffe0 })
    );
    statusBar.position.set(0, -1.16, 0.42);
    root.add(statusBar);

    const footMaterial = new THREE.MeshStandardMaterial({
      color: 0x202725,
      metalness: 0.9,
      roughness: 0.2
    });
    for (const x of [-1.28, 1.28]) {
      const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.23, 0.2, 20), footMaterial);
      foot.position.set(x, -1.66, -0.05);
      root.add(foot);
    }

    const light = new THREE.PointLight(0xa7ffe0, 5.0, 7.5, 1.7);
    light.position.set(0, 0.56, 1.6);
    root.add(light);

    const contactPulseMaterial = new THREE.MeshBasicMaterial({
      color: 0xa7ffe0,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const contactPulse = new THREE.Mesh(
      new THREE.RingGeometry(
        0.94,
        0.99,
        this.quality.tier === "LOW" ? 48 : 96
      ),
      contactPulseMaterial
    );
    contactPulse.position.set(0, 0.56, 0.69);
    root.add(contactPulse);

    const haloMaterial = new THREE.MeshBasicMaterial({
      color: 0xa7ffe0,
      transparent: true,
      opacity: 0.09,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const halo = new THREE.Mesh(
      new THREE.RingGeometry(
        2.15,
        2.2,
        this.quality.tier === "LOW" ? 48 : 96
      ),
      haloMaterial
    );
    halo.rotation.x = -Math.PI / 2;
    halo.position.set(0, -1.72, 0);
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
      new THREE.Vector3(-3.05, -1.12, 0.46),
      new THREE.Vector3(-1.92, -1.7, 1.02),
      new THREE.Vector3(-0.66, -1.92, 1.42),
      new THREE.Vector3(0.66, -1.92, 1.42),
      new THREE.Vector3(1.92, -1.7, 1.02),
      new THREE.Vector3(3.05, -1.12, 0.46)
    ];

    tracks.forEach((track, index) => {
      const artist = getArtist(track.artistId);
      const accent = new THREE.Color(artist.identity.accent);
      const group = new THREE.Group();
      group.position.copy(homes[index] ?? new THREE.Vector3());
      group.rotation.set(
        -0.02,
        group.position.x < 0 ? 0.12 : -0.12,
        group.position.x * -0.025
      );

      const bodyMaterial = new THREE.MeshPhysicalMaterial({
        color: artist.identity.secondary,
        metalness: artist.identity.metalness,
        roughness: artist.identity.roughness,
        clearcoat: track.artistId === "aether" ? 0.82 : 0.5,
        clearcoatRoughness: 0.18
      });

      const body = new THREE.Mesh(
        new THREE.CylinderGeometry(
          0.71,
          0.71,
          0.19,
          6,
          1,
          false
        ),
        bodyMaterial
      );
      body.rotation.x = Math.PI / 2;
      body.castShadow = this.quality.shadows;
      body.receiveShadow = this.quality.shadows;
      body.userData.trackId = track.id;
      group.add(body);

      const bevel = new THREE.Mesh(
        new THREE.TorusGeometry(
          0.59,
          0.035,
          8,
          6
        ),
        new THREE.MeshStandardMaterial({
          color: accent,
          metalness: 0.76,
          roughness: 0.22,
          emissive: accent,
          emissiveIntensity: 0.16
        })
      );
      bevel.position.z = 0.115;
      bevel.rotation.z = Math.PI / 6;
      bevel.userData.trackId = track.id;
      group.add(bevel);

      const labelTexture = createArtifactLabelTexture(track, artist.identity.accent);
      const label = new THREE.Mesh(
        new THREE.CircleGeometry(0.56, 6),
        new THREE.MeshBasicMaterial({
          map: labelTexture,
          toneMapped: false
        })
      );
      label.position.z = 0.145;
      label.rotation.z = Math.PI / 6;
      label.userData.trackId = track.id;
      group.add(label);

      const latchMaterial = new THREE.MeshStandardMaterial({
        color: track.artistId === "monolith" ? 0xe0d3c2 : accent,
        metalness: 0.9,
        roughness: 0.18
      });
      const latch = new THREE.Mesh(
        new THREE.BoxGeometry(0.42, 0.075, 0.08),
        latchMaterial
      );
      latch.position.set(0, -0.59, 0.15);
      latch.userData.trackId = track.id;
      group.add(latch);

      if (track.artistId === "flora") {
        for (const x of [-0.3, 0.3]) {
          const vein = new THREE.Mesh(
            new THREE.BoxGeometry(0.045, 0.65, 0.035),
            new THREE.MeshBasicMaterial({ color: accent })
          );
          vein.position.set(x, 0, 0.16);
          vein.rotation.z = x < 0 ? 0.25 : -0.25;
          vein.userData.trackId = track.id;
          group.add(vein);
        }
      } else if (track.artistId === "monolith") {
        for (const y of [-0.34, 0.34]) {
          const rib = new THREE.Mesh(
            new THREE.BoxGeometry(0.9, 0.045, 0.05),
            new THREE.MeshStandardMaterial({
              color: 0xcabda9,
              metalness: 0.95,
              roughness: 0.2
            })
          );
          rib.position.set(0, y, 0.16);
          rib.userData.trackId = track.id;
          group.add(rib);
        }
      }

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
      new THREE.CylinderGeometry(3.65, 4.0, 0.32, this.quality.tier === "LOW" ? 40 : 96),
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
      new THREE.TorusGeometry(5.8, 0.012, 6, this.quality.tier === "LOW" ? 72 : 160),
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
    const count = this.quality.tier === "LOW" ? 0 : this.quality.tier === "MEDIUM" ? 64 : 110;
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
    const alignQuaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, 0));
    const target = new THREE.Vector3(0, 0.48, 0.7);
    const path = new THREE.CatmullRomCurve3([
      start,
      start.clone().add(new THREE.Vector3(start.x < 0 ? 0.45 : -0.45, 0.55, 0.95)),
      new THREE.Vector3(start.x * 0.34, 0.9, 2.85),
      new THREE.Vector3(-0.25, -0.15, 2.25),
      new THREE.Vector3(0, 0.58, 1.58),
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
      record.group.position.lerpVectors(alignFrom, new THREE.Vector3(0, 0.58, 1.24), u);
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
    const retreat = new THREE.Vector3(0, 0.82, 2.75);

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
    this.deck.gateLeft.position.x = THREE.MathUtils.lerp(-0.46, -0.88, u);
    this.deck.gateRight.position.x = THREE.MathUtils.lerp(0.46, 0.88, u);
    this.deck.gateLeft.rotation.z = THREE.MathUtils.lerp(-0.12, -0.34, u);
    this.deck.gateRight.rotation.z = THREE.MathUtils.lerp(0.12, 0.34, u);
  }

  private closeGate(t: number): void {
    const u = easeInOutCubic(THREE.MathUtils.clamp(t, 0, 1));
    this.deck.gateLeft.position.x = THREE.MathUtils.lerp(-0.88, -0.46, u);
    this.deck.gateRight.position.x = THREE.MathUtils.lerp(0.88, 0.46, u);
    this.deck.gateLeft.rotation.z = THREE.MathUtils.lerp(-0.34, -0.12, u);
    this.deck.gateRight.rotation.z = THREE.MathUtils.lerp(0.34, 0.12, u);
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
      this.scene.fog.density = THREE.MathUtils.lerp(this.scene.fog.density, this.targetFogDensity, 0.035);
    }

    this.worldLight.intensity = THREE.MathUtils.lerp(
      this.worldLight.intensity,
      this.targetAmbientIntensity,
      0.04
    );

    this.deck.ringMaterial.color.lerp(this.currentAccent, 0.06);
    this.deck.ringMaterial.emissive.lerp(this.currentAccent, 0.06);
    this.deck.haloMaterial.color.lerp(this.currentAccent, 0.06);

    const baseLight = this.playing ? 7.8 : 4.8;
    const audioLift = this.playing ? this.signalEnergy * 8 : Math.sin(elapsed * 1.8) * 0.45;
    this.deck.light.color.lerp(this.currentAccent, 0.08);
    this.deck.light.intensity += (baseLight + audioLift - this.deck.light.intensity) * 0.1;

    const ringTarget = this.playing
      ? (3.2 + this.signalEnergy * 3.6) * this.targetDeckGlow
      : 1.7 * this.targetDeckGlow;
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

    this.deck.root.rotation.y = Math.sin(elapsed * 0.22) * 0.012 * this.targetCameraDrift;
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
