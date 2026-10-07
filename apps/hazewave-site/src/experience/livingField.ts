import { getRealArtist, type RealArtistId } from "../data/realArtists";

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

interface WaveState {
  origin: [number, number];
  startedAt: number;
  active: boolean;
}

class LivingFieldRenderer {
  private gl: WebGL2RenderingContext | null = null;
  private program: WebGLProgram | null = null;
  private texture: WebGLTexture | null = null;
  private vao: WebGLVertexArrayObject | null = null;
  private raf = 0;
  private wave: WaveState = { origin: [0.5, 0.5], startedAt: -10, active: false };
  private pointer: [number, number] = [0.5, 0.48];
  private lastFrame = 0;
  private visible = true;

  constructor(
    private readonly host: HTMLElement,
    private readonly canvas: HTMLCanvasElement,
    private readonly source: HTMLImageElement,
    private readonly reducedMotion: boolean
  ) {}

  async initialize(): Promise<void> {
    if (this.reducedMotion) {
      this.host.dataset.fieldRuntime = "css-fallback";
      return;
    }

    if (!this.source.complete || this.source.naturalWidth === 0) {
      await new Promise<void>((resolve, reject) => {
        this.source.addEventListener("load", () => resolve(), { once: true });
        this.source.addEventListener(
          "error",
          () => reject(new Error("OWNER_WORLD_IMAGE_LOAD_FAILED")),
          { once: true }
        );
      });
    }

    const gl = this.canvas.getContext("webgl2", {
      alpha: true,
      antialias: false,
      depth: false,
      stencil: false,
      premultipliedAlpha: false,
      powerPreference: "default",
      failIfMajorPerformanceCaveat: true
    });
    if (!gl) {
      this.host.dataset.fieldRuntime = "css-fallback";
      return;
    }

    this.gl = gl;
    this.program = this.createProgram(gl);
    this.vao = gl.createVertexArray();
    this.texture = gl.createTexture();
    if (!this.vao || !this.texture) {
      throw new Error("FIELD_GPU_RESOURCE_CREATION_FAILED");
    }

    gl.bindVertexArray(this.vao);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, this.source);

    this.resize();
    this.host.dataset.fieldRuntime = "webgl2";
    this.canvas.dataset.ready = "true";
    window.addEventListener("resize", this.resize, { passive: true });
    document.addEventListener("visibilitychange", this.onVisibility);
    this.raf = requestAnimationFrame(this.frame);
  }

  setPointer(x: number, y: number): void {
    this.pointer = [clamp01(x), clamp01(y)];
  }

  triggerWave(x: number, y: number): void {
    this.wave = {
      origin: [clamp01(x), clamp01(y)],
      startedAt: performance.now() / 1000,
      active: true
    };
    this.host.dataset.waveActive = "true";
    if (!this.raf) this.raf = requestAnimationFrame(this.frame);
  }

  dispose(): void {
    cancelAnimationFrame(this.raf);
    window.removeEventListener("resize", this.resize);
    document.removeEventListener("visibilitychange", this.onVisibility);
    const gl = this.gl;
    if (!gl) return;
    if (this.texture) gl.deleteTexture(this.texture);
    if (this.vao) gl.deleteVertexArray(this.vao);
    if (this.program) gl.deleteProgram(this.program);
  }

  private readonly onVisibility = () => {
    this.visible = !document.hidden;
    if (!this.visible) cancelAnimationFrame(this.raf);
    else this.raf = requestAnimationFrame(this.frame);
  };

  private readonly resize = () => {
    const gl = this.gl;
    if (!gl) return;
    const rect = this.canvas.getBoundingClientRect();
    const dpr = Math.min(devicePixelRatio || 1, innerWidth <= 700 ? 1.15 : 1.35);
    const width = Math.max(1, Math.round(rect.width * dpr));
    const height = Math.max(1, Math.round(rect.height * dpr));
    if (this.canvas.width !== width) this.canvas.width = width;
    if (this.canvas.height !== height) this.canvas.height = height;
    gl.viewport(0, 0, width, height);
    this.host.dataset.fieldPixelCount = String(width * height);
  };

  private createProgram(gl: WebGL2RenderingContext): WebGLProgram {
    const vertex = `#version 300 es
      precision highp float;
      const vec2 POSITIONS[3] = vec2[3](vec2(-1.0,-1.0), vec2(3.0,-1.0), vec2(-1.0,3.0));
      out vec2 vUv;
      void main(){
        vec2 p = POSITIONS[gl_VertexID];
        vUv = p * 0.5 + 0.5;
        gl_Position = vec4(p,0.0,1.0);
      }
    `;
    const fragment = `#version 300 es
      precision highp float;
      in vec2 vUv;
      out vec4 outColor;
      uniform sampler2D uTexture;
      uniform vec2 uResolution;
      uniform vec2 uImageSize;
      uniform vec2 uWaveOrigin;
      uniform vec2 uPointer;
      uniform float uWaveStart;
      uniform float uTime;

      vec2 coverUv(vec2 uv){
        float screenAspect = uResolution.x / max(uResolution.y, 1.0);
        float imageAspect = uImageSize.x / max(uImageSize.y, 1.0);
        vec2 scale = screenAspect > imageAspect
          ? vec2(1.0, imageAspect / screenAspect)
          : vec2(screenAspect / imageAspect, 1.0);
        return (uv - 0.5) * scale + 0.5;
      }

      void main(){
        float age = max(0.0, uTime - uWaveStart);
        vec2 aspect = vec2(uResolution.x / max(uResolution.y,1.0), 1.0);
        vec2 fromWave = (vUv - uWaveOrigin) * aspect;
        float dist = length(fromWave);
        float radius = age * 0.34;
        float envelope = exp(-abs(dist - radius) * 24.0) * exp(-age * 1.05);
        float oscillation = sin((dist - radius) * 72.0 - age * 3.0);
        float wave = age < 2.35 ? envelope * oscillation : 0.0;
        vec2 direction = normalize(fromWave + vec2(0.0001));
        direction.x /= max(aspect.x, 0.0001);
        vec2 pointerDrift = (uPointer - 0.5) * 0.0026;
        float haze = sin(vUv.y * 10.0 + uTime * 0.24) * 0.00075;
        vec2 displaced = vUv + direction * wave * 0.014 + pointerDrift + vec2(haze, 0.0);
        vec4 color = texture(uTexture, coverUv(displaced));
        vec4 original = texture(uTexture, coverUv(vUv));
        float contactGlow = exp(-dist * 8.5) * exp(-age * 1.9) * step(age, 1.5);
        color.rgb += vec3(0.055, 0.035, 0.075) * contactGlow;
        color.rgb = mix(original.rgb, color.rgb, 0.9);
        outColor = color;
      }
    `;

    const compile = (type: number, source: string) => {
      const shader = gl.createShader(type);
      if (!shader) throw new Error("FIELD_SHADER_CREATE_FAILED");
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        const info = gl.getShaderInfoLog(shader) ?? "UNKNOWN_SHADER_ERROR";
        gl.deleteShader(shader);
        throw new Error(info);
      }
      return shader;
    };

    const vs = compile(gl.VERTEX_SHADER, vertex);
    const fs = compile(gl.FRAGMENT_SHADER, fragment);
    const program = gl.createProgram();
    if (!program) throw new Error("FIELD_PROGRAM_CREATE_FAILED");
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      const info = gl.getProgramInfoLog(program) ?? "UNKNOWN_LINK_ERROR";
      gl.deleteProgram(program);
      throw new Error(info);
    }
    return program;
  }

  private uniform(name: string): WebGLUniformLocation | null {
    if (!this.gl || !this.program) return null;
    return this.gl.getUniformLocation(this.program, name);
  }

  private frame = (ms: number) => {
    this.raf = 0;
    if (!this.visible || !this.gl || !this.program || !this.vao) return;
    if (ms - this.lastFrame < (this.wave.active ? 16 : 42)) {
      this.raf = requestAnimationFrame(this.frame);
      return;
    }
    this.lastFrame = ms;

    const gl = this.gl;
    const now = ms / 1000;
    if (this.wave.active && now - this.wave.startedAt > 2.35) {
      this.wave.active = false;
      this.host.dataset.waveActive = "false";
    }

    gl.useProgram(this.program);
    gl.bindVertexArray(this.vao);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    const texture = this.uniform("uTexture");
    const resolution = this.uniform("uResolution");
    const imageSize = this.uniform("uImageSize");
    const waveOrigin = this.uniform("uWaveOrigin");
    const pointer = this.uniform("uPointer");
    const waveStart = this.uniform("uWaveStart");
    const time = this.uniform("uTime");
    if (texture) gl.uniform1i(texture, 0);
    if (resolution) gl.uniform2f(resolution, this.canvas.width, this.canvas.height);
    if (imageSize) gl.uniform2f(imageSize, this.source.naturalWidth, this.source.naturalHeight);
    if (waveOrigin) gl.uniform2f(waveOrigin, this.wave.origin[0], 1 - this.wave.origin[1]);
    if (pointer) gl.uniform2f(pointer, this.pointer[0], 1 - this.pointer[1]);
    if (waveStart) gl.uniform1f(waveStart, this.wave.startedAt);
    if (time) gl.uniform1f(time, now);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    this.raf = requestAnimationFrame(this.frame);
  };
}

export function bootLivingField(): void {
  const root = document.documentElement;
  const field = document.querySelector<HTMLElement>("#living-field");
  const canvas = document.querySelector<HTMLCanvasElement>("#living-field-canvas");
  const source = document.querySelector<HTMLImageElement>("#hazewave-world-source");
  const status = document.querySelector<HTMLElement>("#field-status");
  const search = document.querySelector<HTMLDialogElement>("#artist-search");
  const transport = document.querySelector<HTMLElement>("#persistent-transport");
  const transportArtist = document.querySelector<HTMLElement>("#transport-artist");
  const back = document.querySelector<HTMLButtonElement>("#world-back");
  if (!field || !canvas || !source || !status || !search || !transport || !transportArtist || !back) return;

  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  field.dataset.motion = reducedMotion ? "reduced" : "full";
  field.dataset.waveActive = "false";
  const renderer = new LivingFieldRenderer(field, canvas, source, reducedMotion);
  void renderer.initialize().catch((error) => {
    field.dataset.fieldRuntime = "css-fallback";
    console.warn("Hazewave Living Field fallback:", error);
  });

  const signals = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-artist-signal]"));
  const worlds = Array.from(document.querySelectorAll<HTMLElement>("[data-artist-world]"));
  let currentArtist: RealArtistId | null = null;
  let revealTimer = 0;
  let worldReadyTimer = 0;

  const setSignalPositions = () => {
    const mobile = innerWidth <= 700;
    signals.forEach((button) => {
      const artist = getRealArtist(button.dataset.artistSignal ?? null);
      if (!artist) return;
      const [x, y] = mobile ? artist.signal.mobile : artist.signal.desktop;
      button.style.setProperty("--signal-x", `${x * 100}%`);
      button.style.setProperty("--signal-y", `${y * 100}%`);
    });
  };

  const nearestSignal = (x: number, y: number): HTMLButtonElement | null => {
    const rect = field.getBoundingClientRect();
    let nearest: { button: HTMLButtonElement; distance: number } | null = null;
    for (const button of signals) {
      const box = button.getBoundingClientRect();
      const bx = (box.left + box.width / 2 - rect.left) / Math.max(rect.width, 1);
      const by = (box.top + box.height / 2 - rect.top) / Math.max(rect.height, 1);
      const distance = Math.hypot(bx - x, by - y);
      if (!nearest || distance < nearest.distance) nearest = { button, distance };
    }
    return nearest?.button ?? null;
  };

  const revealSignal = (button: HTMLButtonElement) => {
    signals.forEach((candidate) => {
      if (candidate !== button) candidate.dataset.revealed = "false";
    });
    button.dataset.revealed = "true";
    clearTimeout(revealTimer);
    revealTimer = window.setTimeout(() => {
      if (currentArtist === null) button.dataset.revealed = "false";
    }, 4_200);
  };

  const triggerWave = (clientX: number, clientY: number) => {
    const rect = field.getBoundingClientRect();
    const x = clamp01((clientX - rect.left) / Math.max(rect.width, 1));
    const y = clamp01((clientY - rect.top) / Math.max(rect.height, 1));
    renderer.setPointer(x, y);
    renderer.triggerWave(x, y);
    field.style.setProperty("--wave-x", `${x * 100}%`);
    field.style.setProperty("--wave-y", `${y * 100}%`);
    field.dataset.waveActive = "true";
    const nearest = nearestSignal(x, y);
    if (nearest) {
      revealSignal(nearest);
      status.textContent = `${nearest.dataset.artistName ?? "Sinal"} encontrado.`;
    }
  };

  const writeArtistUrl = (artistId: RealArtistId | null, mode: "push" | "replace") => {
    const url = new URL(location.href);
    if (artistId) url.searchParams.set("artist", artistId);
    else url.searchParams.delete("artist");
    const state = { ...(history.state ?? {}), hazewaveArtist: artistId };
    if (mode === "push") history.pushState(state, "", url);
    else history.replaceState(state, "", url);
  };

  const applyArtist = (
    artistId: RealArtistId | null,
    historyMode: "push" | "replace" | "none" = "none"
  ) => {
    const artist = getRealArtist(artistId);
    const materialized = artist?.materializedWorld ? artist : null;
    currentArtist = materialized?.id ?? null;
    worlds.forEach((world) => {
      world.dataset.active = String(world.dataset.artistWorld === currentArtist);
    });

    clearTimeout(worldReadyTimer);
    field.dataset.worldReady = "false";

    if (currentArtist && materialized) {
      root.dataset.activeArtist = currentArtist;
      field.dataset.worldActive = "true";
      transport.dataset.active = "true";
      transportArtist.textContent = materialized.name;
      status.textContent = `${materialized.name}. Mundo visual ativo.`;
      back.hidden = false;
      worldReadyTimer = window.setTimeout(() => {
        field.dataset.worldReady = "true";
      }, reducedMotion ? 0 : 980);
    } else {
      delete root.dataset.activeArtist;
      field.dataset.worldActive = "false";
      transport.dataset.active = "false";
      transportArtist.textContent = "HAZEWAVE";
      back.hidden = true;
      field.dataset.worldReady = "true";
    }
    if (historyMode !== "none") writeArtistUrl(currentArtist, historyMode);
  };

  const openSignal = (button: HTMLButtonElement) => {
    const artist = getRealArtist(button.dataset.artistSignal ?? null);
    if (!artist) return;
    revealSignal(button);
    if (!artist.materializedWorld) {
      status.textContent = `${artist.name}. Sinal real confirmado; mundo ainda não materializado neste slice.`;
      return;
    }
    const box = button.getBoundingClientRect();
    triggerWave(box.left + box.width / 2, box.top + box.height / 2);
    field.dataset.transitioning = "true";
    setTimeout(() => {
      applyArtist(artist.id, "push");
      worldReadyTimer = window.setTimeout(() => {
        field.dataset.transitioning = "false";
      }, reducedMotion ? 0 : 980);
    }, reducedMotion ? 0 : 220);
  };

  signals.forEach((button) => {
    button.dataset.revealed = "false";
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openSignal(button);
    });
  });

  field.addEventListener("pointermove", (event) => {
    const target = event.target;
    if (target instanceof Element && target.closest("button,dialog,input,a")) return;
    const rect = field.getBoundingClientRect();
    renderer.setPointer(
      clamp01((event.clientX - rect.left) / Math.max(rect.width, 1)),
      clamp01((event.clientY - rect.top) / Math.max(rect.height, 1))
    );
  }, { passive: true });

  field.addEventListener("pointerdown", (event) => {
    const target = event.target;
    if (target instanceof Element && target.closest("button,dialog,input,a")) return;
    triggerWave(event.clientX, event.clientY);
  });

  document.querySelector<HTMLButtonElement>("[data-primary-action='explore']")?.addEventListener("click", () => {
    const rect = field.getBoundingClientRect();
    triggerWave(rect.left + rect.width * 0.72, rect.top + rect.height * 0.5);
  });

  document.querySelector<HTMLButtonElement>("[data-primary-action='listen']")?.addEventListener("click", () => {
    transport.focus({ preventScroll: true });
    status.textContent = "Player persistente pronto. Áudio real ainda não materializado neste slice.";
  });

  document.querySelector<HTMLButtonElement>("[data-primary-action='search']")?.addEventListener("click", () => search.showModal());
  document.querySelector<HTMLButtonElement>("[data-search-close]")?.addEventListener("click", () => search.close());

  search.querySelectorAll<HTMLButtonElement>("[data-search-artist]").forEach((button) => {
    button.addEventListener("click", () => {
      const artist = getRealArtist(button.dataset.searchArtist ?? null);
      search.close();
      if (!artist) return;
      const signal = signals.find((candidate) => candidate.dataset.artistSignal === artist.id);
      if (signal) openSignal(signal);
    });
  });

  back.addEventListener("click", () => {
    if (new URL(location.href).searchParams.has("artist")) history.back();
    else applyArtist(null, "replace");
  });

  addEventListener("popstate", () => {
    const artist = getRealArtist(new URL(location.href).searchParams.get("artist"));
    applyArtist(artist?.materializedWorld ? artist.id : null, "none");
  });
  addEventListener("resize", setSignalPositions, { passive: true });
  setSignalPositions();

  const initial = getRealArtist(new URL(location.href).searchParams.get("artist"));
  applyArtist(initial?.materializedWorld ? initial.id : null, "none");
  if (!new URL(location.href).searchParams.has("artist")) writeArtistUrl(null, "replace");

  addEventListener("pagehide", () => renderer.dispose(), { once: true });
}
