import type { QualityProfile } from "../quality/quality";
import type { StoryRuntimeState } from "../story/ScrollConductor";

type GL = WebGL2RenderingContext;

const VERTEX_SHADER = `#version 300 es
precision highp float;
out vec2 vUv;

void main() {
  vec2 position;
  if (gl_VertexID == 0) position = vec2(-1.0, -1.0);
  else if (gl_VertexID == 1) position = vec2(3.0, -1.0);
  else position = vec2(-1.0, 3.0);

  vUv = position * 0.5 + 0.5;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 outColor;

uniform sampler2D uWorld;
uniform float uTime;
uniform float uProgress;
uniform float uChapterProgress;
uniform float uVelocity;
uniform float uWater;
uniform float uFog;
uniform float uLighthouse;
uniform float uDepth;
uniform float uAudio;
uniform float uViewportAspect;
uniform float uImageAspect;
uniform float uContain;
uniform vec2 uPointer;

float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 345.45));
  p += dot(p, p + 34.345);
  return fract(p.x * p.y);
}

float noise21(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);

  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));

  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec3 fitWorld(vec2 uv, out float inside) {
  vec2 source = uv;
  inside = 1.0;

  if (uContain > 0.5) {
    if (uViewportAspect > uImageAspect) {
      float visibleWidth = uImageAspect / uViewportAspect;
      float left = (1.0 - visibleWidth) * 0.5;
      if (source.x < left || source.x > 1.0 - left) inside = 0.0;
      source.x = (source.x - left) / max(visibleWidth, 0.0001);
    } else {
      float visibleHeight = uViewportAspect / uImageAspect;
      float bottom = (1.0 - visibleHeight) * 0.5;
      if (source.y < bottom || source.y > 1.0 - bottom) inside = 0.0;
      source.y = (source.y - bottom) / max(visibleHeight, 0.0001);
    }
  } else {
    if (uViewportAspect > uImageAspect) {
      source.y = 0.5 + (source.y - 0.5) * (uImageAspect / uViewportAspect);
    } else {
      source.x = 0.5 + (source.x - 0.5) * (uViewportAspect / uImageAspect);
    }
  }

  source.y = 1.0 - source.y;
  return texture(uWorld, clamp(source, 0.001, 0.999)).rgb;
}

void main() {
  vec2 screenUv = vUv;
  float screenTop = 1.0 - screenUv.y;

  float zoom = 1.0 + uDepth * 0.052 + uProgress * 0.012;
  vec2 cameraUv = (screenUv - 0.5) / zoom + 0.5;

  float depthWeight = mix(
    0.22,
    1.0,
    smoothstep(0.10, 0.96, screenTop)
  );

  vec2 pointerOffset =
    (uPointer - 0.5) *
    (0.0045 + uDepth * 0.0055) *
    depthWeight;

  cameraUv += pointerOffset;
  cameraUv.x += uVelocity * 0.0018 * depthWeight;
  cameraUv.y -= uVelocity * 0.0011 * depthWeight;

  float waterMask =
    smoothstep(0.70, 0.84, screenTop) *
    (1.0 - smoothstep(0.99, 1.0, screenTop));

  float nearWater = smoothstep(0.79, 0.98, screenTop);
  float waterDrive = uWater * (0.72 + uAudio * 0.42);

  float longWave =
    sin(cameraUv.x * 26.0 + uTime * 0.58 + uProgress * 5.2) * 0.5 +
    sin(cameraUv.x * 49.0 - uTime * 0.34 + uChapterProgress * 3.1) * 0.22;

  float crossWave =
    sin(cameraUv.y * 44.0 + cameraUv.x * 12.0 - uTime * 0.42) * 0.5 +
    sin(cameraUv.y * 79.0 - cameraUv.x * 7.0 + uTime * 0.24) * 0.18;

  cameraUv.x +=
    longWave *
    waterMask *
    waterDrive *
    (0.0018 + nearWater * 0.0026);

  cameraUv.y +=
    crossWave *
    waterMask *
    waterDrive *
    (0.0011 + nearWater * 0.0018);

  float inside = 1.0;
  vec3 world = fitWorld(cameraUv, inside);

  if (inside < 0.5) {
    outColor = vec4(0.0, 0.0, 0.0, 1.0);
    return;
  }

  float foam =
    smoothstep(0.60, 0.94, abs(longWave + crossWave * 0.45)) *
    nearWater *
    uWater *
    (0.025 + uAudio * 0.035);

  world += vec3(0.74, 0.92, 0.36) * foam;

  vec2 fogUv = vec2(
    screenUv.x * 2.4 + uTime * 0.012,
    screenTop * 2.1 - uTime * 0.008
  );
  float fogNoise =
    noise21(fogUv * 2.0) * 0.65 +
    noise21(fogUv * 4.1 + 17.0) * 0.35;
  float fogRegion =
    smoothstep(0.13, 0.34, screenTop) *
    (1.0 - smoothstep(0.68, 0.84, screenTop));
  float fogAmount = fogRegion * fogNoise * uFog * 0.11;
  world = mix(world, vec3(0.18, 0.13, 0.22), fogAmount);

  vec2 lightCenter = vec2(0.505, 0.455);
  vec2 aspectDelta = screenUv - lightCenter;
  aspectDelta.x *= uViewportAspect;
  float lightDistance = length(aspectDelta);
  float lighthouseGlow =
    exp(-lightDistance * 20.0) *
    uLighthouse *
    (0.12 + uAudio * 0.05);

  float sweepAngle = uTime * 0.14 + uProgress * 1.9;
  vec2 sweepDirection = vec2(cos(sweepAngle), sin(sweepAngle) * 0.42);
  vec2 lightVector = normalize(aspectDelta + vec2(0.00001));
  float beam =
    pow(max(dot(lightVector, sweepDirection), 0.0), 34.0) *
    smoothstep(0.025, 0.34, lightDistance) *
    (1.0 - smoothstep(0.34, 0.92, lightDistance)) *
    uLighthouse *
    0.06;

  world += vec3(0.78, 1.0, 0.34) * (lighthouseGlow + beam);

  float vignette = smoothstep(0.42, 0.78, distance(screenUv, vec2(0.5)));
  world *= 1.0 - vignette * 0.08;

  float film =
    (hash21(gl_FragCoord.xy + floor(uTime * 12.0)) - 0.5) *
    0.008;
  world += film;

  outColor = vec4(max(world, vec3(0.0)), 1.0);
}
`;

function compileShader(
  gl: GL,
  type: number,
  source: string
): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("WORLD_SHADER_ALLOCATION_FAILED");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(shader) ?? "unknown shader error";
    gl.deleteShader(shader);
    throw new Error(`WORLD_SHADER_COMPILE_FAILED:${info}`);
  }

  return shader;
}

function createProgram(gl: GL): WebGLProgram {
  const vertex = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragment = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  const program = gl.createProgram();
  if (!program) throw new Error("WORLD_PROGRAM_ALLOCATION_FAILED");

  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(program) ?? "unknown link error";
    gl.deleteProgram(program);
    throw new Error(`WORLD_PROGRAM_LINK_FAILED:${info}`);
  }

  return program;
}

export class LivingWorldStage {
  private readonly host: HTMLElement;
  private readonly fallbackImage: HTMLImageElement;
  private readonly quality: QualityProfile;
  private readonly canvas = document.createElement("canvas");
  private gl: GL | null = null;
  private program: WebGLProgram | null = null;
  private texture: WebGLTexture | null = null;
  private vao: WebGLVertexArrayObject | null = null;
  private raf = 0;
  private startedAt = performance.now();
  private disposed = false;
  private contextLost = false;
  private story: StoryRuntimeState | null = null;
  private audioEnergy = 0;
  private pointerX = 0.5;
  private pointerY = 0.42;
  private imageAspect = 2 / 3;
  private resizeObserver: ResizeObserver | null = null;

  private readonly onPointerMove = (event: PointerEvent) => {
    if (this.quality.reducedMotion) return;
    this.pointerX = Math.max(0, Math.min(1, event.clientX / Math.max(innerWidth, 1)));
    this.pointerY = Math.max(0, Math.min(1, event.clientY / Math.max(innerHeight, 1)));
  };

  private readonly onContextLost = (event: Event) => {
    event.preventDefault();
    this.contextLost = true;
    cancelAnimationFrame(this.raf);
    this.host.dataset.worldRuntime = "fallback-context-lost";
  };

  private readonly onContextRestored = () => {
    if (this.disposed) return;
    try {
      this.contextLost = false;
      this.buildResources();
      this.host.dataset.worldRuntime = "webgl2";
      this.startedAt = performance.now();
      this.raf = requestAnimationFrame(this.frame);
    } catch {
      this.host.dataset.worldRuntime = "fallback-restore-failed";
    }
  };

  static async create(
    host: HTMLElement,
    fallbackImage: HTMLImageElement,
    quality: QualityProfile
  ): Promise<LivingWorldStage> {
    const stage = new LivingWorldStage(host, fallbackImage, quality);
    await stage.initialize();
    return stage;
  }

  private constructor(
    host: HTMLElement,
    fallbackImage: HTMLImageElement,
    quality: QualityProfile
  ) {
    this.host = host;
    this.fallbackImage = fallbackImage;
    this.quality = quality;
    this.canvas.className = "living-world-canvas";
    this.canvas.setAttribute("aria-hidden", "true");
  }

  setStoryState(state: StoryRuntimeState): void {
    this.story = state;
  }

  setAudioEnergy(value: number): void {
    this.audioEnergy = Math.max(0, Math.min(1, value));
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.resizeObserver?.disconnect();
    window.removeEventListener("pointermove", this.onPointerMove);
    this.canvas.removeEventListener("webglcontextlost", this.onContextLost);
    this.canvas.removeEventListener("webglcontextrestored", this.onContextRestored);

    const gl = this.gl;
    if (gl) {
      if (this.texture) gl.deleteTexture(this.texture);
      if (this.vao) gl.deleteVertexArray(this.vao);
      if (this.program) gl.deleteProgram(this.program);
    }

    this.canvas.remove();
    this.host.dataset.worldRuntime = "fallback";
  }

  private async initialize(): Promise<void> {
    if (!this.fallbackImage.complete || this.fallbackImage.naturalWidth === 0) {
      await new Promise<void>((resolve, reject) => {
        this.fallbackImage.addEventListener("load", () => resolve(), { once: true });
        this.fallbackImage.addEventListener(
          "error",
          () => reject(new Error("OWNER_WORLD_IMAGE_LOAD_FAILED")),
          { once: true }
        );
      });
    }

    this.imageAspect =
      this.fallbackImage.naturalWidth /
      Math.max(this.fallbackImage.naturalHeight, 1);

    const gl = this.canvas.getContext("webgl2", {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      premultipliedAlpha: false,
      preserveDrawingBuffer: false,
      powerPreference: "default",
      failIfMajorPerformanceCaveat: true
    });

    if (!gl) throw new Error("WEBGL2_UNAVAILABLE");

    this.gl = gl;
    this.host.prepend(this.canvas);
    this.canvas.addEventListener("webglcontextlost", this.onContextLost, false);
    this.canvas.addEventListener("webglcontextrestored", this.onContextRestored, false);
    window.addEventListener("pointermove", this.onPointerMove, { passive: true });

    this.buildResources();

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.host);
    this.resize();

    this.host.dataset.worldRuntime = "webgl2";
    this.raf = requestAnimationFrame(this.frame);
  }

  private buildResources(): void {
    const gl = this.gl;
    if (!gl) throw new Error("WEBGL2_CONTEXT_MISSING");

    if (this.texture) gl.deleteTexture(this.texture);
    if (this.vao) gl.deleteVertexArray(this.vao);
    if (this.program) gl.deleteProgram(this.program);

    this.program = createProgram(gl);
    this.vao = gl.createVertexArray();
    this.texture = gl.createTexture();

    if (!this.vao || !this.texture) {
      throw new Error("WORLD_GPU_RESOURCE_ALLOCATION_FAILED");
    }

    gl.bindVertexArray(this.vao);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, 0);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      this.fallbackImage
    );

    gl.useProgram(this.program);
    const sampler = gl.getUniformLocation(this.program, "uWorld");
    if (sampler) gl.uniform1i(sampler, 0);
  }

  private resize(): void {
    const gl = this.gl;
    if (!gl) return;

    const dpr = Math.min(
      this.quality.tier === "MEDIUM" ? 1.15 : 1.35,
      Math.max(1, this.quality.pixelRatio)
    );
    const width = Math.max(1, Math.round(innerWidth * dpr));
    const height = Math.max(1, Math.round(innerHeight * dpr));

    if (this.canvas.width !== width) this.canvas.width = width;
    if (this.canvas.height !== height) this.canvas.height = height;

    gl.viewport(0, 0, width, height);
  }

  private uniform1(name: string, value: number): void {
    const gl = this.gl;
    const program = this.program;
    if (!gl || !program) return;
    const location = gl.getUniformLocation(program, name);
    if (location) gl.uniform1f(location, value);
  }

  private frame = (now: number): void => {
    if (this.disposed || this.contextLost) return;

    const gl = this.gl;
    const program = this.program;
    const vao = this.vao;
    if (!gl || !program || !vao) {
      this.host.dataset.worldRuntime = "fallback";
      return;
    }

    const story = this.story;
    const world = story?.world;

    gl.useProgram(program);
    gl.bindVertexArray(vao);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);

    this.uniform1("uTime", (now - this.startedAt) * 0.001);
    this.uniform1("uProgress", story?.globalProgress ?? 0);
    this.uniform1("uChapterProgress", story?.chapterProgress ?? 0);
    this.uniform1("uVelocity", story?.velocity ?? 0);
    this.uniform1("uWater", world?.water ?? 0);
    this.uniform1("uFog", world?.fog ?? 0);
    this.uniform1("uLighthouse", world?.lighthouse ?? 0);
    this.uniform1("uDepth", world?.depth ?? 0);
    this.uniform1("uAudio", this.audioEnergy);
    this.uniform1(
      "uViewportAspect",
      this.canvas.width / Math.max(this.canvas.height, 1)
    );
    this.uniform1("uImageAspect", this.imageAspect);
    this.uniform1("uContain", innerWidth >= 1200 ? 1 : 0);

    const pointerLocation = gl.getUniformLocation(program, "uPointer");
    if (pointerLocation) {
      gl.uniform2f(pointerLocation, this.pointerX, this.pointerY);
    }

    gl.drawArrays(gl.TRIANGLES, 0, 3);
    this.raf = requestAnimationFrame(this.frame);
  };
}
