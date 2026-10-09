import { FRAME_ORIGIN, FRAME_SPAN, LOGO_ASPECT } from "./layout";
import { COMPOSITE, SCENE, VERT } from "./shaders";

export interface CosmosEngine {
  setProgress(progress: number): void;
  setPointer(x: number, y: number): void;
  setReduced(reduced: boolean): void;
  destroy(): void;
}

const LOGO_URL = "/media/hazewave-world.jpg";

function compile(gl: WebGL2RenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("HAZEWAVE_SHADER_ALLOC");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader) || "compile";
    gl.deleteShader(shader);
    throw new Error(log);
  }
  return shader;
}

function link(gl: WebGL2RenderingContext, fragment: string): WebGLProgram {
  const program = gl.createProgram();
  if (!program) throw new Error("HAZEWAVE_PROGRAM_ALLOC");
  const vertex = compile(gl, gl.VERTEX_SHADER, VERT);
  const frag = compile(gl, gl.FRAGMENT_SHADER, fragment);
  gl.attachShader(program, vertex);
  gl.attachShader(program, frag);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(frag);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const log = gl.getProgramInfoLog(program) || "link";
    gl.deleteProgram(program);
    throw new Error(log);
  }
  return program;
}

function texture2d(gl: WebGL2RenderingContext): WebGLTexture {
  const texture = gl.createTexture();
  if (!texture) throw new Error("HAZEWAVE_TEXTURE_ALLOC");
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  return texture;
}

export function mountCosmos(canvas: HTMLCanvasElement, reduced: boolean): CosmosEngine {
  const gl = canvas.getContext("webgl2", {
    alpha: false,
    antialias: false,
    depth: false,
    stencil: false,
    premultipliedAlpha: false,
    preserveDrawingBuffer: true,
    powerPreference: "high-performance",
  });
  if (!gl) throw new Error("HAZEWAVE_WEBGL2_UNAVAILABLE");

  const sceneProgram = link(gl, SCENE);
  const compositeProgram = link(gl, COMPOSITE);
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);

  const sceneTex = texture2d(gl);
  const logoTex = texture2d(gl);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255]));

  const sceneFbo = gl.createFramebuffer();
  if (!sceneFbo) throw new Error("HAZEWAVE_FBO_ALLOC");

  const sceneLoc = {
    resolution: gl.getUniformLocation(sceneProgram, "uResolution"),
    time: gl.getUniformLocation(sceneProgram, "uTime"),
    progress: gl.getUniformLocation(sceneProgram, "uProgress"),
    reduced: gl.getUniformLocation(sceneProgram, "uReduced"),
    pointer: gl.getUniformLocation(sceneProgram, "uPointer"),
  };
  const plateLoc = {
    resolution: gl.getUniformLocation(compositeProgram, "uResolution"),
    time: gl.getUniformLocation(compositeProgram, "uTime"),
    progress: gl.getUniformLocation(compositeProgram, "uProgress"),
    reduced: gl.getUniformLocation(compositeProgram, "uReduced"),
    scene: gl.getUniformLocation(compositeProgram, "uScene"),
    logo: gl.getUniformLocation(compositeProgram, "uLogo"),
    aspect: gl.getUniformLocation(compositeProgram, "uLogoAspect"),
    ready: gl.getUniformLocation(compositeProgram, "uLogoReady"),
    origin: gl.getUniformLocation(compositeProgram, "uFrameOrigin"),
    span: gl.getUniformLocation(compositeProgram, "uFrameSpan"),
  };

  let progress = 0;
  let pointerX = 0;
  let pointerY = 0;
  let reducedFlag = reduced ? 1 : 0;
  let logoReady = 0;
  let time = 0;
  let last = performance.now();
  let sceneScale = 0.5;
  let slowFrames = 0;
  let running = true;
  let animationFrame = 0;
  let width = 1;
  let height = 1;
  let sceneW = 2;
  let sceneH = 2;

  function allocateScene() {
    gl.bindTexture(gl.TEXTURE_2D, sceneTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, sceneW, sceneH, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.bindFramebuffer(gl.FRAMEBUFFER, sceneFbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, sceneTex, 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }

  function resize() {
    const dprCap = window.innerWidth < 800 ? 1.15 : 1.35;
    const dpr = Math.min(window.devicePixelRatio || 1, reducedFlag ? 1 : dprCap);
    width = Math.max(2, Math.floor(canvas.clientWidth * dpr));
    height = Math.max(2, Math.floor(canvas.clientHeight * dpr));
    canvas.width = width;
    canvas.height = height;
    sceneW = Math.max(2, Math.floor(width * sceneScale));
    sceneH = Math.max(2, Math.floor(height * sceneScale));
    allocateScene();
  }

  function render() {
    gl.bindFramebuffer(gl.FRAMEBUFFER, sceneFbo);
    gl.viewport(0, 0, sceneW, sceneH);
    gl.useProgram(sceneProgram);
    gl.uniform2f(sceneLoc.resolution, sceneW, sceneH);
    gl.uniform1f(sceneLoc.time, time);
    gl.uniform1f(sceneLoc.progress, progress);
    gl.uniform1f(sceneLoc.reduced, reducedFlag);
    gl.uniform2f(sceneLoc.pointer, pointerX, pointerY);
    gl.drawArrays(gl.TRIANGLES, 0, 3);

    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, width, height);
    gl.useProgram(compositeProgram);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, sceneTex);
    gl.uniform1i(plateLoc.scene, 0);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, logoTex);
    gl.uniform1i(plateLoc.logo, 1);
    gl.uniform2f(plateLoc.resolution, width, height);
    gl.uniform1f(plateLoc.time, time);
    gl.uniform1f(plateLoc.progress, progress);
    gl.uniform1f(plateLoc.reduced, reducedFlag);
    gl.uniform1f(plateLoc.aspect, LOGO_ASPECT);
    gl.uniform1f(plateLoc.ready, logoReady);
    gl.uniform2f(plateLoc.origin, FRAME_ORIGIN.x, FRAME_ORIGIN.y);
    gl.uniform2f(plateLoc.span, FRAME_SPAN.x, FRAME_SPAN.y);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  const resizeObserver = new ResizeObserver(() => resize());
  resizeObserver.observe(canvas);
  resize();

  const tick = (now: number) => {
    if (!running || gl.isContextLost()) return;
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (dt > 0.028) slowFrames += 1;
    else slowFrames = Math.max(0, slowFrames - 1);
    if (slowFrames > 10 && sceneScale > 0.34) {
      sceneScale = 0.34;
      slowFrames = 0;
      resize();
    }
    time += reducedFlag ? 0 : dt;
    render();
    animationFrame = requestAnimationFrame(tick);
  };
  animationFrame = requestAnimationFrame(tick);

  const loadLogo = async () => {
    const response = await fetch(LOGO_URL);
    if (!response.ok) throw new Error(`HAZEWAVE_LOGO_HTTP_${response.status}`);
    const blob = await response.blob();
    let bitmap: ImageBitmap;
    try {
      bitmap = await createImageBitmap(blob, {
        colorSpaceConversion: "none",
        premultiplyAlpha: "none",
        imageOrientation: "none",
      });
    } catch {
      bitmap = await createImageBitmap(blob);
    }
    if (!running || gl.isContextLost()) {
      bitmap.close?.();
      return;
    }
    gl.bindTexture(gl.TEXTURE_2D, logoTex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, bitmap);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    bitmap.close?.();
    logoReady = 1;
    document.body.dataset.logoReady = "yes";
  };

  void loadLogo().catch((error: unknown) => {
    console.error(error);
    document.body.dataset.logoReady = "no";
    document.body.dataset.gl = "unavailable";
    document.getElementById("logo-plate")?.removeAttribute("hidden");
  });

  return {
    setProgress(value: number) {
      progress = Math.min(1, Math.max(0, value));
    },
    setPointer(x: number, y: number) {
      pointerX = x;
      pointerY = y;
    },
    setReduced(next: boolean) {
      const flag = next ? 1 : 0;
      if (flag !== reducedFlag) {
        reducedFlag = flag;
        resize();
      }
    },
    destroy() {
      running = false;
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      if (!gl.isContextLost()) {
        gl.deleteTexture(sceneTex);
        gl.deleteTexture(logoTex);
        gl.deleteFramebuffer(sceneFbo);
        gl.deleteProgram(sceneProgram);
        gl.deleteProgram(compositeProgram);
        if (vao) gl.deleteVertexArray(vao);
      }
    },
  };
}
