import type { ArtistChapterWorld } from "../../data/artistChapters";
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
uniform float uParticles;
uniform float uBrightness;
uniform float uSaturation;
uniform float uContrast;
uniform float uVignette;
uniform float uAudio;
uniform float uViewportAspect;
uniform float uImageAspect;
uniform float uContain;
uniform vec2 uPointer;

uniform vec3 uArtistAccent;
uniform float uArtistInfluence;
uniform float uArtistWater;
uniform float uArtistFog;
uniform float uArtistLight;
uniform float uArtistParticles;
uniform float uArtistSignature;

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

float fbm(vec2 p) {
  float value = 0.0;
  float amplitude = 0.52;
  mat2 rotation = mat2(0.80, -0.60, 0.60, 0.80);

  for (int octave = 0; octave < 4; octave++) {
    value += noise21(p) * amplitude;
    p = rotation * p * 2.03 + vec2(13.7, 9.2);
    amplitude *= 0.48;
  }

  return value;
}

vec3 gradeWorld(vec3 color) {
  float luminance = dot(color, vec3(0.2126, 0.7152, 0.0722));
  color = mix(vec3(luminance), color, max(0.0, uSaturation));
  color = (color - 0.5) * uContrast + 0.5;
  color *= uBrightness;
  return color;
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

  float artistDepth = uArtistInfluence * (0.018 + uArtistSignature * 0.006);
  float zoom = 1.0 + uDepth * 0.052 + uProgress * 0.012 + artistDepth;
  vec2 cameraUv = (screenUv - 0.5) / zoom + 0.5;

  float depthWeight = mix(
    0.20,
    1.0,
    smoothstep(0.10, 0.96, screenTop)
  );

  vec2 pointerOffset =
    (uPointer - 0.5) *
    (0.0038 + uDepth * 0.0052) *
    depthWeight;

  cameraUv += pointerOffset;
  cameraUv.x += uVelocity * (0.0015 + uDepth * 0.0007) * depthWeight;
  cameraUv.y -= uVelocity * 0.0009 * depthWeight;

  float waterMask =
    smoothstep(0.69, 0.80, screenTop) *
    (1.0 - smoothstep(0.995, 1.0, screenTop));
  float nearWater = smoothstep(0.79, 0.985, screenTop);

  float waterDrive =
    uWater *
    mix(1.0, 0.72 + uArtistWater * 0.68, uArtistInfluence) *
    (0.76 + uAudio * 0.36);

  vec2 waterCoord = vec2(
    cameraUv.x * 7.4,
    screenTop * 18.0
  );

  float warp =
    fbm(
      waterCoord * 0.72 +
      vec2(uTime * 0.075 + uProgress * 1.8, -uTime * 0.028)
    );

  float flow =
    fbm(
      waterCoord * 1.34 +
      vec2(
        warp * (1.35 + uArtistSignature * 0.28),
        -uTime * 0.052 + warp * 0.72 + uChapterProgress * 1.4
      )
    );

  float fineFlow =
    noise21(
      waterCoord * 3.6 +
      vec2(uTime * 0.11, -uTime * 0.07)
    );

  float waveField =
    (flow - 0.49) * 1.46 +
    (fineFlow - 0.5) * 0.23 +
    sin(cameraUv.x * 19.0 + uTime * 0.22 + warp * 2.4) * 0.09;

  float crossField =
    (fbm(waterCoord.yx * 0.92 + vec2(-uTime * 0.035, uTime * 0.025)) - 0.5) *
    0.72;

  cameraUv.x +=
    waveField *
    waterMask *
    waterDrive *
    (0.00155 + nearWater * 0.00235);

  cameraUv.y +=
    crossField *
    waterMask *
    waterDrive *
    (0.00085 + nearWater * 0.00165);

  float inside = 1.0;
  vec3 world = fitWorld(cameraUv, inside);

  if (inside < 0.5) {
    outColor = vec4(0.0, 0.0, 0.0, 1.0);
    return;
  }

  world = gradeWorld(world);

  float foamRidge =
    smoothstep(0.44, 0.82, abs(waveField * 0.84 + crossField * 0.46));
  float foam =
    foamRidge *
    nearWater *
    waterDrive *
    (0.020 + uAudio * 0.028);

  vec3 foamColor = mix(
    vec3(0.74, 0.92, 0.36),
    max(uArtistAccent, vec3(0.18)),
    uArtistInfluence * 0.34
  );
  world += foamColor * foam;

  vec2 fogUv = vec2(
    screenUv.x * 2.15 + uTime * 0.010,
    screenTop * 1.92 - uTime * 0.006
  );
  float fogNoise = fbm(fogUv * 2.05 + vec2(uProgress * 0.6, 0.0));
  float fogRegion =
    smoothstep(0.12, 0.31, screenTop) *
    (1.0 - smoothstep(0.70, 0.86, screenTop));

  float fogDrive =
    uFog *
    mix(1.0, 0.78 + uArtistFog * 8.0, uArtistInfluence);
  float fogAmount = fogRegion * fogNoise * fogDrive * 0.105;

  vec3 fogColor = mix(
    vec3(0.18, 0.13, 0.22),
    uArtistAccent * 0.42 + vec3(0.055),
    uArtistInfluence * 0.24
  );
  world = mix(world, fogColor, clamp(fogAmount, 0.0, 0.18));

  vec2 lightCenter = vec2(0.505, 0.455);
  vec2 aspectDelta = screenUv - lightCenter;
  aspectDelta.x *= uViewportAspect;
  float lightDistance = length(aspectDelta);

  float lightDrive =
    uLighthouse *
    mix(1.0, 0.80 + uArtistLight * 0.62, uArtistInfluence);

  float lighthouseGlow =
    exp(-lightDistance * 20.0) *
    lightDrive *
    (0.105 + uAudio * 0.048);

  float sweepAngle =
    uTime * (0.105 + uArtistSignature * 0.02) +
    uProgress * 1.9 +
    uArtistInfluence * uArtistSignature * 0.26;
  vec2 sweepDirection = vec2(cos(sweepAngle), sin(sweepAngle) * 0.42);
  vec2 lightVector = normalize(aspectDelta + vec2(0.00001));

  float beam =
    pow(max(dot(lightVector, sweepDirection), 0.0), 38.0) *
    smoothstep(0.028, 0.34, lightDistance) *
    (1.0 - smoothstep(0.34, 0.92, lightDistance)) *
    lightDrive *
    0.055;

  vec3 lighthouseColor = mix(
    vec3(0.78, 1.0, 0.34),
    uArtistAccent,
    uArtistInfluence * 0.27
  );
  world += lighthouseColor * (lighthouseGlow + beam);

  float particleDrive =
    uParticles *
    mix(1.0, 0.52 + uArtistParticles * 0.96, uArtistInfluence);

  vec2 particleFlow = vec2(
    screenUv.x * 17.0 + uTime * 0.008,
    screenTop * 12.0 - uTime * (0.018 + uArtistSignature * 0.004)
  );
  vec2 particleCell = floor(particleFlow);
  vec2 particleLocal = fract(particleFlow) - 0.5;
  float particleSeed = hash21(particleCell + 31.7);
  vec2 particleOffset = vec2(
    hash21(particleCell + 4.7) - 0.5,
    hash21(particleCell + 19.2) - 0.5
  ) * 0.52;
  float mote =
    smoothstep(0.075, 0.008, length(particleLocal - particleOffset)) *
    smoothstep(0.64, 0.96, particleSeed) *
    particleDrive *
    (1.0 - waterMask * 0.76);

  world += mix(vec3(0.68, 0.72, 0.76), uArtistAccent, uArtistInfluence * 0.4) * mote * 0.22;

  float artistGrade = uArtistInfluence * 0.075;
  float artistLuma = dot(uArtistAccent, vec3(0.2126, 0.7152, 0.0722));
  vec3 safeAccent = uArtistAccent / max(artistLuma, 0.24);
  world = mix(world, world * mix(vec3(1.0), safeAccent, 0.10), artistGrade);

  float vignette =
    smoothstep(0.40, 0.80, distance(screenUv, vec2(0.5)));
  world *= 1.0 - vignette * (0.035 + uVignette * 0.18);

  float film =
    (hash21(gl_FragCoord.xy + floor(uTime * 10.0)) - 0.5) *
    0.0055;
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

function hexToRgb(hex: string): [number, number, number] {
  const normalized = hex.trim().replace(/^#/, "");
  const value = Number.parseInt(
    normalized.length === 3
      ? normalized.split("").map((digit) => digit + digit).join("")
      : normalized,
    16
  );

  if (!Number.isFinite(value)) return [0.72, 1.0, 0.42];

  return [
    ((value >> 16) & 255) / 255,
    ((value >> 8) & 255) / 255,
    (value & 255) / 255
  ];
}

function signatureValue(
  signature: ArtistChapterWorld["transitionSignature"]
): number {
  if (signature === "WEIGHT") return 0.28;
  if (signature === "GROW") return 0.72;
  return 0.5;
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
  private artistWorld: ArtistChapterWorld | null = null;
  private artistProgress = 0;
  private artistAccent: [number, number, number] = [0.72, 1.0, 0.42];

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

  setArtistWorld(world: ArtistChapterWorld, progress: number): void {
    this.artistWorld = world;
    this.artistProgress = Math.max(0, Math.min(1, progress));
    this.artistAccent = hexToRgb(world.accent);
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

    this.texture = null;
    this.vao = null;
    this.program = null;
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
    if (sampler !== null) gl.uniform1i(sampler, 0);
  }

  private resize(): void {
    const gl = this.gl;
    if (!gl) return;

    const dpr = Math.min(
      this.quality.tier === "MEDIUM" ? 1.12 : 1.32,
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
    if (location !== null) gl.uniform1f(location, value);
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
    const artistWorld = this.artistWorld;

    const artistChapterActive =
      story?.chapterId === "artists" || story?.chapterId === "dossiers";
    const artistInfluence =
      artistWorld && artistChapterActive
        ? Math.min(1, 0.34 + this.artistProgress * 0.66)
        : 0;

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
    this.uniform1("uParticles", world?.particles ?? 0);
    this.uniform1("uBrightness", world?.brightness ?? 1);
    this.uniform1("uSaturation", world?.saturation ?? 1);
    this.uniform1("uContrast", world?.contrast ?? 1);
    this.uniform1("uVignette", world?.vignette ?? 0.18);
    this.uniform1("uAudio", this.audioEnergy);
    this.uniform1("uArtistInfluence", artistInfluence);
    this.uniform1("uArtistWater", artistWorld?.waterResponse ?? 0.5);
    this.uniform1("uArtistFog", artistWorld?.fogDensity ?? 0.025);
    this.uniform1("uArtistLight", artistWorld?.lightResponse ?? 0.5);
    this.uniform1("uArtistParticles", artistWorld?.particleResponse ?? 0.4);
    this.uniform1(
      "uArtistSignature",
      artistWorld ? signatureValue(artistWorld.transitionSignature) : 0.5
    );
    this.uniform1(
      "uViewportAspect",
      this.canvas.width / Math.max(this.canvas.height, 1)
    );
    this.uniform1("uImageAspect", this.imageAspect);
    this.uniform1("uContain", innerWidth >= 1200 ? 1 : 0);

    const pointerLocation = gl.getUniformLocation(program, "uPointer");
    if (pointerLocation !== null) {
      gl.uniform2f(pointerLocation, this.pointerX, this.pointerY);
    }

    const accentLocation = gl.getUniformLocation(program, "uArtistAccent");
    if (accentLocation !== null) {
      gl.uniform3f(
        accentLocation,
        this.artistAccent[0],
        this.artistAccent[1],
        this.artistAccent[2]
      );
    }

    gl.drawArrays(gl.TRIANGLES, 0, 3);
    this.raf = requestAnimationFrame(this.frame);
  };
}
