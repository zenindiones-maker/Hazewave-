import * as THREE from "three";
import type { QualityProfile } from "../quality/quality";

export interface RendererAdapter {
  readonly backend: "WEBGL2";
  readonly renderer: THREE.WebGLRenderer;
  resize(width: number, height: number): void;
  render(scene: THREE.Scene, camera: THREE.Camera): void;
  dispose(): void;
}

export function createRenderer(canvas: HTMLCanvasElement, quality: QualityProfile): RendererAdapter {
  const context = canvas.getContext("webgl2", {
    antialias: quality.tier !== "LOW",
    alpha: false,
    powerPreference: "high-performance"
  });
  if (!context) throw new Error("WEBGL2_UNAVAILABLE");

  const renderer = new THREE.WebGLRenderer({ canvas, context, antialias: quality.tier !== "LOW" });
  renderer.setPixelRatio(quality.pixelRatio);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = quality.shadows;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  return {
    backend: "WEBGL2",
    renderer,
    resize(width, height) {
      renderer.setSize(width, height, false);
    },
    render(scene, camera) {
      renderer.render(scene, camera);
    },
    dispose() {
      renderer.dispose();
    }
  };
}
