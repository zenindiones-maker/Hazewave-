import { fieldFragment, FIELD_WAVE_SPEED } from "./fieldShader";
export { FIELD_WAVE_SPEED };

/** Scene textures and the canonical owner artwork remain separately sampled materials. */
export class FieldRenderer {
  private gl: WebGL2RenderingContext | null = null;
  private program: WebGLProgram | null = null;
  private vao: WebGLVertexArrayObject | null = null;
  private uniforms = new Map<string, WebGLUniformLocation | null>();
  private assets = new Map<
    number,
    { texture: WebGLTexture; width: number; height: number }
  >();
  private raf = 0;
  private frameFence: WebGLSync | null = null;
  private from = 0;
  private to = 0;
  private progress = 1;
  private transitionStart = 0;
  private transitionDuration = 2400;
  private manualProgress = false;
  private previewIndex = 4;
  private previewOrigin = [0.5, 0.5];
  private previewAmount = 0;
  private previewTarget = 0;
  private smoothPointer = [0.5, 0.5];
  private origin = [0.5, 0.5];
  private waveOrigin = [0.5, 0.5];
  private entryOpen = false;
  private pointer = [0.5, 0.5];
  private waveStart = -10000;
  private previousFrame = 0;
  private disposed = false;
  private completion: (() => void) | null = null;
  private initialization: Promise<void> | null = null;
  private images: HTMLImageElement[] = [];
  private loading = new Map<number, Promise<boolean>>();
  private request = 0;
  private targetBuffer: WebGLFramebuffer | null = null;
  private targetTexture: WebGLTexture | null = null;
  private snapshot: WebGLTexture | null = null;
  private hasFrame = false;
  private qualityScale = 1;
  private slowFrames = 0;
  private severeFrames = 0;
  private fenceStarted = 0;
  private fencePressureValid = false;
  private lastFrameProbe = 0;
  private previousDraw = 0;
  constructor(
    private host: HTMLElement,
    private canvas: HTMLCanvasElement,
    private reduced: boolean,
  ) {}

  async initialize(images: HTMLImageElement[]): Promise<void> {
    if (this.reduced) {
      this.host.dataset.fieldRuntime = "css-fallback";
      return;
    }
    if (this.initialization) return this.initialization;
    this.initialization = this.initializeResources(images).finally(() => {
      this.initialization = null;
    });
    return this.initialization;
  }

  private async initializeResources(images: HTMLImageElement[]): Promise<void> {
    const gl = this.canvas.getContext("webgl2", {
      alpha: false,
      antialias: false,
      depth: false,
      powerPreference: "low-power",
    });
    if (!gl) {
      this.host.dataset.fieldRuntime = "css-fallback";
      return;
    }
    this.gl = gl;
    const vertex = `#version 300 es
    precision highp float;
    out vec2 vUv;
    void main(){ vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2)); vUv=p; gl_Position=vec4(p*2.-1.,0.,1.); }`;
    const fragment = fieldFragment;
    const compile = (type: number, source: string) => {
      const shader = gl.createShader(type)!;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        const error = gl.getShaderInfoLog(shader);
        gl.deleteShader(shader);
        throw new Error(error ?? "Shader compilation failed");
      }
      return shader;
    };
    const vs = compile(gl.VERTEX_SHADER, vertex),
      fs = compile(gl.FRAGMENT_SHADER, fragment);
    this.program = gl.createProgram()!;
    gl.attachShader(this.program, vs);
    gl.attachShader(this.program, fs);
    gl.linkProgram(this.program);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    if (!gl.getProgramParameter(this.program, gl.LINK_STATUS))
      throw new Error(gl.getProgramInfoLog(this.program) ?? "Link failed");
    this.vao = gl.createVertexArray();
    this.images = images.slice();
    // The original is a required material in the field, independent of its expanded environment.
    const canonical = this.canvas.ownerDocument.createElement("img");
    canonical.src = this.canvas.ownerDocument.querySelector(".hazewave-lettering image")?.getAttribute("href") ?? "/media/hazewave-world.jpg";
    canonical.loading = "eager";
    this.images[6] = canonical;
    if (!(await this.ensureAsset(0)))
      throw new Error("Origin artwork unavailable");
    this.host.dataset.canonicalAssetUnavailable = String(!(await this.ensureAsset(6)));
    if (this.from > 0) await this.ensureAsset(this.from);
    if (this.to)
      this.host.dataset.assetUnavailable = String(
        !(await this.ensureAsset(this.to)),
      );
    if (this.disposed) return;
    window.addEventListener("resize", this.resize, { passive: true });
    document.addEventListener("visibilitychange", this.visibility);
    this.canvas.addEventListener("webglcontextlost", this.contextLost);
    // Image decode may finish after the user has changed their motion preference.
    // Keep the allocated resources ready for a later opt-in, without restarting motion.
    if (this.reduced) {
      this.host.dataset.fieldRuntime = "css-fallback";
      return;
    }
    this.host.dataset.fieldRuntime = "webgl2";
    this.resize();
    this.raf = requestAnimationFrame(this.frame);
  }
  async setReduced(
    reduced: boolean,
    images: HTMLImageElement[],
  ): Promise<void> {
    this.reduced = reduced;
    if (reduced) {
      cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.fencePressureValid = false;
      this.slowFrames = this.severeFrames = 0;
      this.host.dataset.fieldRuntime = "css-fallback";
      this.progress = 1;
      this.completion?.();
      this.completion = null;
      return;
    }
    if (this.initialization) await this.initialization;
    if (this.reduced || this.disposed) return;
    if (this.gl && !this.gl.isContextLost() && this.assets.has(0)) {
      cancelAnimationFrame(this.raf);
      const selected = this.to;
      const ready = await this.ensureAsset(selected);
      if (this.reduced || this.disposed || this.gl.isContextLost()) return;
      if (selected !== this.to) return this.setReduced(false, images);
      this.host.dataset.assetUnavailable = String(!ready);
      cancelAnimationFrame(this.raf);
      this.host.dataset.fieldRuntime = "webgl2";
      this.resize();
      this.raf = requestAnimationFrame(this.frame);
    } else await this.initialize(images);
  }
  private contextLost = (event: Event) => {
    event.preventDefault();
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    this.host.dataset.fieldRuntime = "css-fallback";
    this.host.dispatchEvent(new Event("fieldfallback"));
    this.completion?.();
    this.completion = null;
  };
  private visibility = () => {
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    // A pending fence may complete while the page is suspended. Its wall time
    // cannot establish rendering pressure after resuming.
    this.fencePressureValid = false;
    this.lastFrameProbe = 0;
    this.previousDraw = 0;
    this.slowFrames = this.severeFrames = 0;
    if (!document.hidden && !this.disposed)
      this.raf = requestAnimationFrame(this.frame);
  };
  private async ensureAsset(index: number): Promise<boolean> {
    if (this.assets.has(index)) return true;
    if (this.loading.has(index)) return this.loading.get(index)!;
    // A scrub can precede initialization; a transient lack of resources must not
    // permanently cache a failed warm and prevent the eventual texture upload.
    if (!this.images[index] || !this.gl || this.disposed) return false;
    const pending = (async () => {
      const image = this.images[index];
      if (!image || !this.gl || this.disposed) return false;
      try {
        image.loading = "eager";
        await image.decode();
        if (this.disposed || this.gl.isContextLost()) return false;
        const gl = this.gl;
        const ratio = Math.min(
          1,
          1024 / Math.max(image.naturalWidth, image.naturalHeight),
        );
        const bitmap = await createImageBitmap(image, {
          imageOrientation: "flipY",
          resizeWidth: Math.round(image.naturalWidth * ratio),
          resizeHeight: Math.round(image.naturalHeight * ratio),
          resizeQuality: "high",
        });
        if (this.disposed || gl.isContextLost()) {
          bitmap.close();
          return false;
        }
        const texture = gl.createTexture()!;
        gl.bindTexture(gl.TEXTURE_2D, texture);
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
          bitmap,
        );
        this.assets.set(index, {
          texture,
          width: bitmap.width,
          height: bitmap.height,
        });
        bitmap.close();
        this.host.dataset.fieldTextureBytes = String(
          [...this.assets.values()].reduce(
            (sum, a) => sum + a.width * a.height * 4,
            0,
          ),
        );
        return true;
      } catch {
        return false;
      }
    })();
    this.loading.set(index, pending);
    try {
      return await pending;
    } finally {
      if (this.loading.get(index) === pending) this.loading.delete(index);
    }
  }
  private resize = () => {
    if (!this.gl) return;
    const gl = this.gl;
    const dpr = Math.min(devicePixelRatio, innerWidth < 700 ? 1.25 : 1.5);
    const box = this.canvas.getBoundingClientRect();
    const budget = (innerWidth < 700 ? 700000 : 1400000) * this.qualityScale;
    const ratio = Math.min(
      dpr,
      Math.sqrt(budget / Math.max(1, box.width * box.height)),
    );
    this.canvas.width = Math.max(1, Math.round(box.width * ratio));
    this.canvas.height = Math.max(1, Math.round(box.height * ratio));
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    if (this.targetBuffer) gl.deleteFramebuffer(this.targetBuffer);
    if (this.targetTexture) gl.deleteTexture(this.targetTexture);
    this.targetBuffer = gl.createFramebuffer();
    this.targetTexture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.targetTexture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      this.canvas.width,
      this.canvas.height,
      0,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      null,
    );
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.targetBuffer);
    gl.framebufferTexture2D(
      gl.FRAMEBUFFER,
      gl.COLOR_ATTACHMENT0,
      gl.TEXTURE_2D,
      this.targetTexture,
      0,
    );
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE)
      throw new Error("Field framebuffer unavailable");
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    this.hasFrame = false;
    this.host.dataset.fieldPixelCount = String(
      this.canvas.width * this.canvas.height,
    );
    this.host.dataset.fieldQuality =
      this.qualityScale < 1 ? "economy" : "balanced";
    this.host.dataset.fieldQualityScale = this.qualityScale.toFixed(3);
  };
  private retainComposition() {
    if (!this.gl || !this.targetBuffer || !this.hasFrame) return false;
    const gl = this.gl;
    this.snapshot ??= gl.createTexture();
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.targetBuffer);
    gl.bindTexture(gl.TEXTURE_2D, this.snapshot);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.copyTexImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      0,
      0,
      this.canvas.width,
      this.canvas.height,
      0,
    );
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    this.assets.set(-1, {
      texture: this.snapshot!,
      width: this.canvas.width,
      height: this.canvas.height,
    });
    return true;
  }
  scrub(index: number, x: number, y: number, progress: number) {
    this.scrubBetween(0, index, x, y, progress);
  }
  /** Native scroll owns a deterministic pair; asset decode never writes a late scene. */
  scrubBetween(fromIndex: number, toIndex: number, x: number, y: number, progress: number) {
    if (this.disposed) return;
    const from = Number.isInteger(fromIndex) && fromIndex >= 0 && fromIndex <= 5 ? fromIndex : 0;
    const to = Number.isInteger(toIndex) && toIndex >= 0 && toIndex <= 5 ? toIndex : 0;
    const changed = !this.manualProgress || this.from !== from || this.to !== to;
    if (changed) this.request++;
    this.manualProgress = true;
    this.entryOpen = from === 0;
    this.completion = null;
    this.previewTarget = 0;
    this.from = from;
    this.to = to;
    this.origin = [Number.isFinite(x) ? Math.max(0, Math.min(1, x)) : 0.5,
      Number.isFinite(y) ? 1 - Math.max(0, Math.min(1, y)) : 0.5];
    this.progress = Number.isFinite(progress) ? Math.max(0, Math.min(1, progress)) : 0;
    this.host.dataset.traversalProgress = this.progress.toFixed(3);
    if (changed) {
      const request = this.request;
      this.host.dataset.assetLoading = String(!this.assets.has(from) || !this.assets.has(to));
      void Promise.all([this.ensureAsset(from), this.ensureAsset(to)]).then(([fromReady, toReady]) => {
        if (this.disposed || request !== this.request || !this.manualProgress) return;
        this.host.dataset.assetLoading = "false";
        this.host.dataset.assetUnavailable = String(!fromReady || !toReady);
      });
    }
  }
  prepare(index: number) {
    void this.ensureAsset(index);
  }
  preview(index: number, x: number, y: number) {
    void this.ensureAsset(index);
    this.previewIndex = index;
    this.previewOrigin = [x, 1 - y];
    this.previewTarget = 1;
  }
  clearPreview() {
    this.previewTarget = 0;
  }
  point(x: number, y: number) {
    this.pointer = [x, 1 - y];
  }
  wave(x: number, y: number) {
    this.waveOrigin = [x, 1 - y];
    this.waveStart = performance.now();
  }
  transition(
    index: number,
    x: number,
    y: number,
    complete: () => void,
    instant = false,
  ) {
    const request = ++this.request;
    if (this.gl && !this.assets.has(index) && !instant && !this.reduced) {
      void this.ensureAsset(index).then((ready) => {
        if (request !== this.request || this.disposed) return;
        this.host.dataset.assetUnavailable = String(!ready);
        if (!ready) {
          complete();
          return;
        }
        this.transition(index, x, y, complete, instant);
      });
      return;
    }
    this.host.dataset.assetUnavailable = String(
      index > 0 && this.gl !== null && !this.assets.has(index),
    );
    this.completion = null;
    this.manualProgress = false;
    this.entryOpen = this.previewTarget > 0 && this.to === 0;
    this.previewTarget = 0;
    const interrupted = this.progress < 1 && this.retainComposition();
    this.from = interrupted ? -1 : this.to;
    this.to = index;
    this.origin = [x, 1 - y];
    this.progress = instant ? 1 : 0;
    this.transitionStart = performance.now();
    if (
      this.reduced ||
      !this.gl ||
      this.host.dataset.fieldRuntime !== "webgl2" ||
      instant
    ) {
      this.progress = 1;
      complete();
      return;
    }
    this.completion = complete;
  }
  private uniform(name: string) {
    if (!this.uniforms.has(name))
      this.uniforms.set(name, this.gl!.getUniformLocation(this.program!, name));
    return this.uniforms.get(name)!;
  }
  private frame = (time: number) => {
    this.raf = 0;
    // Ignore resumed/frozen or long-blocked main-thread intervals when adapting.
    // Fence latency is a conservative completion probe, not a hardware GPU timer.
    if (this.lastFrameProbe && time - this.lastFrameProbe > 250) {
      this.fencePressureValid = false;
      this.slowFrames = this.severeFrames = 0;
    }
    this.lastFrameProbe = time;
    if (
      !this.gl ||
      !this.program ||
      this.disposed ||
      document.hidden ||
      this.host.dataset.fieldRuntime !== "webgl2"
    )
      return;
    // Never enqueue a second full-screen draw while the previous GPU job is pending.
    // Polling with zero timeout keeps pointer, scroll and keyboard work on the main thread free.
    if (this.frameFence) {
      const fenceState = this.gl.clientWaitSync(this.frameFence, 0, 0);
      if (fenceState === this.gl.TIMEOUT_EXPIRED) {
        this.raf = requestAnimationFrame(this.frame);
        return;
      }
      const latency = time - this.fenceStarted;
      this.host.dataset.fieldFenceLatencyMs = latency.toFixed(1);
      if (this.fencePressureValid && fenceState !== this.gl.WAIT_FAILED) {
        this.slowFrames = latency > 65 ? this.slowFrames + 1 : 0;
        this.severeFrames = latency > 120 ? this.severeFrames + 1 : 0;
      }
      this.gl.deleteSync(this.frameFence);
      this.frameFence = null;
    }
    if ((this.slowFrames >= 3 || this.severeFrames >= 2) && this.qualityScale > 0.25) {
      this.qualityScale = Math.max(0.25, this.qualityScale * (this.severeFrames >= 2 ? 0.65 : 0.75));
      this.slowFrames = this.severeFrames = 0;
      this.resize();
    }
    const active = this.progress < 1 || time - this.waveStart < 3100;
    if (time - this.previousFrame < (active ? 16 : 33)) {
      this.raf = requestAnimationFrame(this.frame);
      return;
    }
    const dt = Math.min(500, time - this.previousFrame);
    this.previousFrame = time;
    this.previewAmount +=
      (this.previewTarget - this.previewAmount) * (1 - Math.exp(-dt / 240));
    this.smoothPointer = this.smoothPointer.map(
      (v, i) => v + (this.pointer[i] - v) * (1 - Math.exp(-dt / 180)),
    );
    if (this.progress < 1 && !this.manualProgress) {
      this.progress = Math.min(
        1,
        (time - this.transitionStart) / this.transitionDuration,
      );
      if (this.progress === 1) {
        const done = this.completion;
        this.completion = null;
        done?.();
      }
    }
    const gl = this.gl;
    const from = this.assets.get(this.from) ?? this.assets.get(0),
      to = this.assets.get(this.to) ?? this.assets.get(0);
    if (!from || !to) return;
    gl.useProgram(this.program);
    gl.bindVertexArray(this.vao);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, from.texture);
    gl.uniform1i(this.uniform("uFrom"), 0);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, to.texture);
    gl.uniform1i(this.uniform("uTo"), 1);
    gl.uniform2f(this.uniform("uFromSize"), from.width, from.height);
    gl.uniform2f(this.uniform("uToSize"), to.width, to.height);
    const canonical = this.assets.get(6) ?? this.assets.get(0)!;
    gl.activeTexture(gl.TEXTURE3);
    gl.bindTexture(gl.TEXTURE_2D, canonical.texture);
    gl.uniform1i(this.uniform("uCanonical"), 3);
    gl.uniform2f(this.uniform("uCanonicalSize"), canonical.width, canonical.height);
    gl.uniform2f(
      this.uniform("uResolution"),
      this.canvas.width,
      this.canvas.height,
    );
    gl.uniform2f(this.uniform("uOrigin"), this.origin[0], this.origin[1]);
    gl.uniform2f(
      this.uniform("uWaveOrigin"),
      this.waveOrigin[0],
      this.waveOrigin[1],
    );
    gl.uniform1f(this.uniform("uEntryOpen"), this.entryOpen ? 1 : 0);
    gl.uniform2f(
      this.uniform("uPointer"),
      this.smoothPointer[0],
      this.smoothPointer[1],
    );
    const preview = this.assets.get(this.previewIndex) ?? to;
    gl.activeTexture(gl.TEXTURE2);
    gl.bindTexture(gl.TEXTURE_2D, preview.texture);
    gl.uniform1i(this.uniform("uPreview"), 2);
    gl.uniform2f(this.uniform("uPreviewSize"), preview.width, preview.height);
    gl.uniform2f(
      this.uniform("uPreviewOrigin"),
      ...(this.previewOrigin as [number, number]),
    );
    gl.uniform1f(this.uniform("uPreviewType"), this.previewIndex);
    gl.uniform1f(
      this.uniform("uPreviewAmount"),
      this.assets.has(this.previewIndex) ? this.previewAmount : 0,
    );
    gl.uniform1f(this.uniform("uTime"), time / 1000);
    gl.uniform1f(this.uniform("uWaveAge"), (time - this.waveStart) / 1000);
    gl.uniform1f(this.uniform("uProgress"), this.progress);
    gl.uniform1f(
      this.uniform("uFromType"),
      this.assets.has(this.from) ? this.from : 0,
    );
    gl.uniform1f(
      this.uniform("uToType"),
      this.assets.has(this.to) ? this.to : 0,
    );
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.targetBuffer);
    const drawTime = performance.now();
    if (this.previousDraw) {
      this.host.dataset.fieldDrawIntervalMs = (drawTime - this.previousDraw).toFixed(1);
    }
    this.previousDraw = drawTime;
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.bindFramebuffer(gl.READ_FRAMEBUFFER, this.targetBuffer);
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER, null);
    gl.blitFramebuffer(
      0,
      0,
      this.canvas.width,
      this.canvas.height,
      0,
      0,
      this.canvas.width,
      this.canvas.height,
      gl.COLOR_BUFFER_BIT,
      gl.NEAREST,
    );
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    this.hasFrame = true;
    this.fenceStarted = time;
    this.fencePressureValid = true;
    this.frameFence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
    this.raf = requestAnimationFrame(this.frame);
  };
  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    window.removeEventListener("resize", this.resize);
    document.removeEventListener("visibilitychange", this.visibility);
    this.canvas.removeEventListener("webglcontextlost", this.contextLost);
    if (this.frameFence) this.gl?.deleteSync(this.frameFence);
    this.assets.forEach((a) => this.gl?.deleteTexture(a.texture));
    if (this.targetBuffer) this.gl?.deleteFramebuffer(this.targetBuffer);
    if (this.targetTexture) this.gl?.deleteTexture(this.targetTexture);
    if (this.vao) this.gl?.deleteVertexArray(this.vao);
    if (this.program) this.gl?.deleteProgram(this.program);
    this.completion = null;
  }
}
