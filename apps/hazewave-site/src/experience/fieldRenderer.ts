/** Original artwork is sampled directly. No generated artwork or particle proxy. */
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
    const fragment = `#version 300 es
    precision highp float;
    in vec2 vUv;
    out vec4 outColor;
    uniform sampler2D uFrom,uTo,uPreview;
    uniform vec2 uFromSize,uToSize,uResolution,uOrigin,uWaveOrigin,uPointer,uPreviewOrigin,uPreviewSize;
    uniform float uTime,uWaveAge,uProgress,uFromType,uToType,uPreviewType,uPreviewAmount,uEntryOpen;
    float hash(vec2 p){ return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
    float noise(vec2 p){ vec2 i=floor(p),f=fract(p); f=f*f*(3.-2.*f); return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y); }
    float mist(vec2 p){return noise(p)*.58+noise(p*2.08+3.)*.28+noise(p*4.1+7.)*.14;}
    vec3 imageAt(sampler2D tex,vec2 uv){ float mask=step(0.,uv.x)*step(uv.x,1.)*step(0.,uv.y)*step(uv.y,1.); return texture(tex,clamp(uv,.001,.999)).rgb*mask; }
    vec3 scene(sampler2D tex,vec2 size,float kind,vec2 uv,float depth){
      float aspect=uResolution.x/uResolution.y, ia=size.x/size.y;
      bool mobile=aspect<.9;
      vec2 center=vec2(.5,.50);
      float scale=1.18;
      if(kind<.5){ia=size.x/(size.y*.70);center=vec2(.52,.49);}
      if(kind>.5){center=vec2(mobile?.5:.61,mobile?.59:.53);scale=mobile?min(.88,aspect/ia*.96):.97;}
      if(kind>4.5){scale*=1.62;center.y=mobile?.62:.56;}
      if(kind>1.5&&kind<2.5){scale=mobile?aspect/ia*.95:.72;center=vec2(.5,mobile?.6:.54);}
      if(kind>.5&&kind<1.5)scale*=1.13;
      if(kind<.5 && mobile){scale=.96;center.y=.48;}
      if(kind>3.5&&kind<4.5){ia=size.x/(size.y*.78);scale=mobile?.96:1.26;center=vec2(mobile?.37:.50,.50);}
      vec2 coords=(uv-center)*vec2(aspect/ia,1.)/(scale+depth*.06)+.5;
      if(kind<.5)coords.y*=.70;
      if(kind>3.5&&kind<4.5)coords.y*=.78;
      vec2 drift=(uPointer-.5)*vec2(.027,.017);
      // Analytic depth regions anchored to the source artwork: sky, tower and surf.
      float foreground=1.-smoothstep(.05,.48,coords.y);
      float tower=(1.-smoothstep(.045,.15,abs(coords.x-.51)))*(1.-smoothstep(.42,.65,coords.y));
      float depthRegion=mix(.23,1.3,foreground)+tower*.45;
      float luma=dot(imageAt(tex,coords),vec3(.2126,.7152,.0722));
      // Luminance-dependent parallax separates the printed light from the black substrate.
      coords+=drift*(depthRegion+luma*.15);
      if(kind<.5){
        float artGate=1.-smoothstep(.70,.86,coords.y);
        vec2 radial=coords-vec2(.51,.53);
        float flow=sin(length(radial)*16.-uTime*.32)*.007*artGate;
        coords+=vec2(-radial.y,radial.x)*flow;
      }
      if(kind>3.5&&kind<4.5){
        float water=1.-smoothstep(.65,.78,coords.y);
        coords.x+=sin(coords.y*40.+uTime*.6)*.0035*water;
        coords.y+=sin(coords.x*19.-uTime*.4)*.0018*water;
      }
      if(kind>4.5){coords.x+=sin(coords.y*90.+uTime*.23)*.0005;}
      vec3 art=imageAt(tex,coords);
      if(kind>3.5&&kind<4.5)art*=1.-smoothstep(.77,.80,coords.y);
      if(kind<.5)art*=smoothstep(0.,.08,coords.x)*smoothstep(0.,.08,1.-coords.x);
      // Peripheral atmosphere is derived from the same source texture, without cloning the logo.
      vec2 backdrop=vec2(.5)+(uv-.5)*vec2(aspect*.26,.34);
      backdrop.y=min(backdrop.y,.69);
      float edge=smoothstep(.14,.52,abs(uv.x-.5));
      float n=mist(uv*vec2(4.,5.)+vec2(uTime*.015,-uTime*.018));
      vec3 ambient=imageAt(tex,backdrop)*(.055+edge*.24)*n;
      if(kind>3.5&&kind<4.5)ambient=vec3(.014,.019,.017)*n;
      if(kind>4.5){
        float pressure=pow(max(0.,1.-abs(uv.y-.52)*2.),3.);
        vec2 cage=(uv-vec2(.40,.51))*vec2(.39*aspect,.43)+vec2(.53,.44);
        cage.y=.14+uv.y*.35;
        cage += (uPointer-.5)*vec2(.055,.025)+vec2(sin(uTime*.17)*.003,0.);
        vec3 bone=imageAt(tex,cage);
        ambient=bone*vec3(.28,.065,.035)*(.4+n*.6)+vec3(.18,.005,.003)*pressure*n;
        // Torn bands read as tension; the original barbed-wire emblem remains intact.
        float scratch=1.-smoothstep(.0003,.0018,abs(uv.y-(.27+uv.x*.23)));
        scratch+=1.-smoothstep(.0003,.0014,abs(uv.y-(.79-uv.x*.13)));
        ambient+=vec3(.27,.25,.19)*scratch*(.2+.5*noise(uv*90.));
      }
      vec3 result=max(art,ambient)+vec3(.009,.014,.009)*n;
      if(kind<.5){
        // Advected density lives in front of the printed sea, cleared by the contact wave.
        vec2 flow=uv*vec2(2.8,5.5)+vec2(uTime*.021,-uTime*.013);
        float vapor=mist(flow+vec2(mist(flow*.7),0.));
        float banks=exp(-pow((uv.y-.22-sin(uv.x*5.+uTime*.07)*.045)*5.5,2.));
        float filament=pow(max(0.,1.-abs(vapor-.5)*3.2),5.);
        float cleared=exp(-pow((length((uv-uWaveOrigin)*vec2(aspect,1.))-uWaveAge*.55)*9.,2.))*exp(-max(0.,uWaveAge)*.32);
        float haze=banks*filament*.32*(1.-cleared*.9);
        vec3 sourceLight=mix(vec3(.12,.15,.12),vec3(.29,.34,.20),vapor);
        result=mix(result,sourceLight,haze);
        // Light is sourced at the original tower lantern, no arbitrary point particles.
        vec2 light=coords-vec2(.51,.49);
        float shaft=exp(-abs(light.y-light.x*.12)*75.)*exp(-abs(light.x)*4.);
        result+=vec3(.18,.23,.09)*shaft*.19;
      }
      if(kind>3.5&&kind<4.5){
        float beam=pow(max(0.,1.-abs(uv.y-(.66+uv.x*.13)))*.65,8.);
        result+=vec3(.17,.12,.06)*beam*n;
      }
      result*=.8+.2*smoothstep(0.,.16,uv.y);
      return result;
    }
    void main(){
      float aspect=uResolution.x/uResolution.y;
      vec2 delta=(vUv-uOrigin)*vec2(aspect,1.);
      vec2 waveDelta=(vUv-uWaveOrigin)*vec2(aspect,1.);
      float distance=length(waveDelta);
      float age=max(0.,uWaveAge);
      float radius=age*.55;
      float envelope=exp(-pow((distance-radius)*14.,2.))*exp(-age*.65)*step(age,3.1);
      float oscillation=sin((distance-radius)*78.);
      vec2 direction=waveDelta/max(.001,distance)/vec2(aspect,1.);
      vec2 displaced=vUv+direction*oscillation*envelope*.033;
      float p=clamp(uProgress,0.,1.);
      float eased=p*p*(3.-2.*p);
      vec3 fromColor=vec3(0.);
      if(p<.999)fromColor=scene(uFrom,uFromSize,uFromType,displaced,eased);
      vec2 windowUv=displaced-uOrigin+.5;
      vec2 traverse=mix(windowUv,displaced,smoothstep(.0,.85,p));
      vec3 toColor=scene(uTo,uToSize,uToType,uFromType<.5?traverse:displaced,0.);

      float reach=length(vec2(aspect,1.))*1.2;
      float frontier=length(delta*vec2(.85,1.15))+mist(delta*13.+vec2(uTime*.025,0.))*.065;
      if(uToType>4.5){frontier=mix(frontier,abs(delta.x)*.75+abs(delta.y)*.9+noise(vUv*vec2(12.,44.))*.17,eased);}
      float boundary=pow(eased,1.7)*reach+.185;
      float blend=smoothstep(frontier-.06,frontier+.06,boundary);
      if(uEntryOpen<.5)blend*=smoothstep(0.,.13,p);
      if(p>=.999)blend=1.;
      vec3 col=mix(fromColor,toColor,blend);
      // A discovered world is a texture opening in the field, never a DOM thumbnail.
      if(uToType<.5 && p>.999 && uPreviewAmount>.001){
        vec2 pd=(displaced-uPreviewOrigin)*vec2(aspect,1.);
        float turbulence=mist(pd*13.+vec2(uTime*.025,0.));
        float aperture=length(pd*vec2(.85,1.15))+turbulence*.065;
        float opening=(1.-smoothstep(.125*uPreviewAmount,.24*uPreviewAmount,aperture))*uPreviewAmount;
        vec2 puv=displaced-uPreviewOrigin+.5;
        vec3 world=scene(uPreview,uPreviewSize,uPreviewType,puv,0.);
        col=mix(col,world,opening);
        float rim=exp(-abs(aperture-.185*uPreviewAmount)*100.)*uPreviewAmount;
        col+=rim*vec3(.10,.15,.055);
      }
      float crest=exp(-abs(frontier-boundary)*55.)*sin(p*3.14159);
      col+=crest*vec3(.22,.25,.12)*(0.25+dot(col,vec3(.3)));
      col+=envelope*.048*vec3(.7,.85,.45);
      float vignette=1.-.18*pow(length((vUv-.5)*vec2(.7,1.)),1.5);
      outColor=vec4(col*vignette,1.);
    }`;
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
    await Promise.all(
      images.map(async (image, index) => {
        await image.decode();
        if (this.disposed) return;
        const texture = gl.createTexture()!;
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
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
          image,
        );
        this.assets.set(index, {
          texture,
          width: image.naturalWidth,
          height: image.naturalHeight,
        });
      }),
    );
    if (this.disposed) return;
    this.host.dataset.fieldRuntime = "webgl2";
    this.resize();
    window.addEventListener("resize", this.resize, { passive: true });
    document.addEventListener("visibilitychange", this.visibility);
    this.canvas.addEventListener("webglcontextlost", this.contextLost);
    this.raf = requestAnimationFrame(this.frame);
  }
  async setReduced(reduced: boolean, images: HTMLImageElement[]) {
    this.reduced = reduced;
    if (reduced) {
      cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.host.dataset.fieldRuntime = "css-fallback";
      this.progress = 1;
      this.completion?.();
      this.completion = null;
      return;
    }
    if (
      this.gl &&
      !this.gl.isContextLost() &&
      this.assets.size === images.length
    ) {
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
    if (!document.hidden && !this.disposed)
      this.raf = requestAnimationFrame(this.frame);
  };
  private resize = () => {
    if (!this.gl) return;
    const dpr = Math.min(devicePixelRatio, innerWidth < 700 ? 1.25 : 1.5);
    const box = this.canvas.getBoundingClientRect();
    this.canvas.width = Math.round(box.width * dpr);
    this.canvas.height = Math.round(box.height * dpr);
    this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    this.host.dataset.fieldPixelCount = String(
      this.canvas.width * this.canvas.height,
    );
  };
  scrub(index: number, x: number, y: number, progress: number) {
    this.manualProgress = true;
    this.entryOpen = true;
    this.completion = null;
    this.from = 0;
    this.to = index;
    this.origin = [x, 1 - y];
    this.progress = Math.max(0, Math.min(1, progress));
    this.host.dataset.traversalProgress = this.progress.toFixed(3);
  }
  preview(index: number, x: number, y: number) {
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
    this.completion = null;
    this.manualProgress = false;
    this.entryOpen = this.previewTarget > 0 && this.to === 0;
    this.previewTarget = 0;
    this.from = this.to;
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
      this.gl.deleteSync(this.frameFence);
      this.frameFence = null;
    }
    const active = this.progress < 1 || time - this.waveStart < 3100;
    if (time - this.previousFrame < (active ? 16 : 33)) {
      this.raf = requestAnimationFrame(this.frame);
      return;
    }
    const dt = Math.min(70, time - this.previousFrame);
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
    const from = this.assets.get(this.from),
      to = this.assets.get(this.to);
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
    gl.uniform1f(this.uniform("uPreviewAmount"), this.previewAmount);
    gl.uniform1f(this.uniform("uTime"), time / 1000);
    gl.uniform1f(this.uniform("uWaveAge"), (time - this.waveStart) / 1000);
    gl.uniform1f(this.uniform("uProgress"), this.progress);
    gl.uniform1f(this.uniform("uFromType"), this.from);
    gl.uniform1f(this.uniform("uToType"), this.to);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
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
    if (this.vao) this.gl?.deleteVertexArray(this.vao);
    if (this.program) this.gl?.deleteProgram(this.program);
    this.completion = null;
  }
}
