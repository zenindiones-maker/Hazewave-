import type { ArtistId } from "../../data/catalog";
import type { QualityProfile } from "../quality/quality";

type WebGpuHandle = {
  requestAdapter(options?: { powerPreference?: "low-power" | "high-performance" }): Promise<any>;
  getPreferredCanvasFormat(): string;
};

const ARTIST_INDEX: Record<ArtistId, number> = {
  aether: 0,
  monolith: 1,
  flora: 2
};

const ARTIST_RGB: Record<ArtistId, [number, number, number]> = {
  aether: [0.6549, 1, 0.8784],
  monolith: [0.9098, 0.851, 0.7725],
  flora: [0.8471, 1, 0.4784]
};

const SHADER = `
struct Uniforms {
  time: f32,
  energy: f32,
  artist: f32,
  aspect: f32,
  color: vec4f,
}

@group(0) @binding(0) var<uniform> u: Uniforms;

struct VertexOut {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
  @location(1) intensity: f32,
}

fn hash(value: f32) -> f32 {
  return fract(sin(value * 91.3458) * 47453.5453);
}

@vertex
fn vertex_main(
  @builtin(vertex_index) vertex_index: u32,
  @builtin(instance_index) instance_index: u32
) -> VertexOut {
  let corners = array<vec2f, 6>(
    vec2f(-1.0, -1.0),
    vec2f( 1.0, -1.0),
    vec2f(-1.0,  1.0),
    vec2f(-1.0,  1.0),
    vec2f( 1.0, -1.0),
    vec2f( 1.0,  1.0)
  );

  let id = f32(instance_index);
  let seed = hash(id + 1.0);
  let phase = id * 2.399963 + seed * 0.9;
  let speed = 0.055 + hash(id * 1.71 + 3.0) * 0.085;
  let radius = 0.22 + hash(id * 2.37 + 7.0) * 0.64;
  let lift = 0.22 + hash(id * 3.11 + 13.0) * 0.31;
  let orbit = phase + u.time * speed;

  var center = vec2f(
    cos(orbit) * radius,
    sin(orbit * 1.31) * lift
  );

  if (u.artist > 0.5 && u.artist < 1.5) {
    center.x = floor(center.x * 10.0) / 10.0;
    center.y = floor(center.y * 9.0) / 9.0;
  }

  if (u.artist > 1.5) {
    center.y += sin(phase * 1.7 + u.time * 0.17) * 0.12;
    center.x *= 0.9 + hash(id * 4.27) * 0.18;
  }

  let breathe = 0.82 + (sin(u.time * (0.33 + speed) + phase) + 1.0) * 0.08;
  let base_size = 0.006 + hash(id * 5.19 + 17.0) * 0.009;
  let reactive_size = base_size * breathe * (1.0 + u.energy * (1.2 + seed));
  let corner = corners[vertex_index] * reactive_size;

  var out: VertexOut;
  out.position = vec4f(
    center.x + corner.x / max(u.aspect, 0.5),
    center.y + corner.y,
    0.0,
    1.0
  );
  out.uv = corners[vertex_index];
  out.intensity = 0.62 + seed * 0.38;
  return out;
}

@fragment
fn fragment_main(input: VertexOut) -> @location(0) vec4f {
  let distance = length(input.uv);
  let soft = 1.0 - smoothstep(0.12, 1.0, distance);
  let alpha = soft * input.intensity * (0.20 + u.energy * 0.34);
  let bloom = u.color.rgb * (0.84 + u.energy * 0.72);
  return vec4f(bloom, alpha);
}
`;

export class HighTierAtmosphere {
  private readonly host: HTMLElement;
  private readonly canvas: HTMLCanvasElement;
  private readonly gpu: WebGpuHandle;
  private readonly adapter: any;
  private readonly device: any;
  private readonly context: any;
  private readonly pipeline: any;
  private readonly uniformBuffer: any;
  private readonly bindGroup: any;
  private readonly uniformData = new Float32Array(8);
  private readonly observer: ResizeObserver;
  private readonly particleCount: number;
  private artist: ArtistId = "aether";
  private energy = 0;
  private playing = false;
  private disposed = false;
  private raf = 0;
  private startedAt = performance.now();

  static async create(
    host: HTMLElement,
    quality: QualityProfile
  ): Promise<HighTierAtmosphere> {
    const gpu = (navigator as Navigator & { gpu?: WebGpuHandle }).gpu;
    if (!gpu) throw new Error("WEBGPU_UNAVAILABLE");

    const adapter = await gpu.requestAdapter({ powerPreference: "high-performance" });
    if (!adapter) throw new Error("WEBGPU_ADAPTER_UNAVAILABLE");

    const device = await adapter.requestDevice();
    const canvas = document.createElement("canvas");
    canvas.className = "gpu-atmosphere";
    canvas.setAttribute("aria-hidden", "true");

    const context = canvas.getContext("webgpu") as any;
    if (!context) throw new Error("WEBGPU_CANVAS_CONTEXT_UNAVAILABLE");

    return new HighTierAtmosphere(
      host,
      canvas,
      gpu,
      adapter,
      device,
      context,
      quality
    );
  }

  private constructor(
    host: HTMLElement,
    canvas: HTMLCanvasElement,
    gpu: WebGpuHandle,
    adapter: any,
    device: any,
    context: any,
    quality: QualityProfile
  ) {
    this.host = host;
    this.canvas = canvas;
    this.gpu = gpu;
    this.adapter = adapter;
    this.device = device;
    this.context = context;
    this.particleCount = quality.tier === "ULTRA" ? 112 : 72;

    const format = this.gpu.getPreferredCanvasFormat();
    this.context.configure({
      device: this.device,
      format,
      alphaMode: "premultiplied"
    });

    const module = this.device.createShaderModule({
      label: "hazewave-atmosphere-wgsl",
      code: SHADER
    });

    this.pipeline = this.device.createRenderPipeline({
      label: "hazewave-atmosphere-pipeline",
      layout: "auto",
      vertex: {
        module,
        entryPoint: "vertex_main"
      },
      fragment: {
        module,
        entryPoint: "fragment_main",
        targets: [
          {
            format,
            blend: {
              color: {
                srcFactor: "src-alpha",
                dstFactor: "one",
                operation: "add"
              },
              alpha: {
                srcFactor: "one",
                dstFactor: "one-minus-src-alpha",
                operation: "add"
              }
            }
          }
        ]
      },
      primitive: {
        topology: "triangle-list"
      }
    });

    this.uniformBuffer = this.device.createBuffer({
      label: "hazewave-atmosphere-uniforms",
      size: this.uniformData.byteLength,
      usage: 64 | 8
    });

    this.bindGroup = this.device.createBindGroup({
      label: "hazewave-atmosphere-bind-group",
      layout: this.pipeline.getBindGroupLayout(0),
      entries: [
        {
          binding: 0,
          resource: { buffer: this.uniformBuffer }
        }
      ]
    });

    this.host.prepend(this.canvas);
    this.observer = new ResizeObserver(() => this.resize(quality.pixelRatio));
    this.observer.observe(this.host);
    this.resize(quality.pixelRatio);
    this.host.dataset.gpuAtmosphere = "webgpu-native";

    if (this.device.lost?.then) {
      void this.device.lost.then(() => this.dispose());
    }

    this.raf = requestAnimationFrame(this.frame);
  }

  setArtist(artist: ArtistId): void {
    this.artist = artist;
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
    cancelAnimationFrame(this.raf);
    this.observer.disconnect();

    try {
      this.context.unconfigure?.();
    } catch {
      // Context may already be lost or unconfigured.
    }

    try {
      this.uniformBuffer.destroy?.();
    } catch {
      // Device loss makes destruction unnecessary.
    }

    this.canvas.remove();
  }

  private resize(pixelRatio: number): void {
    const ratio = Math.min(Math.max(pixelRatio, 1), 1.35);
    const width = Math.max(1, Math.round(this.host.clientWidth * ratio));
    const height = Math.max(1, Math.round(this.host.clientHeight * ratio));

    if (this.canvas.width !== width) this.canvas.width = width;
    if (this.canvas.height !== height) this.canvas.height = height;
  }

  private frame = (now: number): void => {
    if (this.disposed) return;

    const elapsed = (now - this.startedAt) * 0.001;
    const [r, g, b] = ARTIST_RGB[this.artist];
    this.uniformData[0] = elapsed;
    this.uniformData[1] = this.playing ? this.energy : 0;
    this.uniformData[2] = ARTIST_INDEX[this.artist];
    this.uniformData[3] = this.canvas.width / Math.max(this.canvas.height, 1);
    this.uniformData[4] = r;
    this.uniformData[5] = g;
    this.uniformData[6] = b;
    this.uniformData[7] = 1;

    this.device.queue.writeBuffer(
      this.uniformBuffer,
      0,
      this.uniformData.buffer,
      this.uniformData.byteOffset,
      this.uniformData.byteLength
    );

    const encoder = this.device.createCommandEncoder({
      label: "hazewave-atmosphere-frame"
    });
    const view = this.context.getCurrentTexture().createView();
    const pass = encoder.beginRenderPass({
      label: "hazewave-atmosphere-pass",
      colorAttachments: [
        {
          view,
          clearValue: { r: 0, g: 0, b: 0, a: 0 },
          loadOp: "clear",
          storeOp: "store"
        }
      ]
    });

    pass.setPipeline(this.pipeline);
    pass.setBindGroup(0, this.bindGroup);
    pass.draw(6, this.particleCount);
    pass.end();

    this.device.queue.submit([encoder.finish()]);
    this.raf = requestAnimationFrame(this.frame);
  };
}
