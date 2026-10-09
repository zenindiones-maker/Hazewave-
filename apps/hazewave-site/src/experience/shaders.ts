export const VERT = `#version 300 es
void main() {
  vec2 verts[3] = vec2[3](vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
  gl_Position = vec4(verts[gl_VertexID], 0.0, 1.0);
}
`;

export const SCENE = `#version 300 es
precision highp float;

uniform vec2 uResolution;
uniform float uTime;
uniform float uProgress;
uniform float uReduced;
uniform vec2 uPointer;

out vec4 fragColor;

float hash(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 3; i++) {
    v += a * noise(p);
    p = p * 2.03 + vec2(17.1, 9.2);
    a *= 0.5;
  }
  return v;
}

float galaxy(vec2 uv, float tightness, float arms) {
  float r = length(uv);
  float ang = atan(uv.y, uv.x);
  float spiral = ang * arms + log(r + 0.02) * tightness;
  float arm = pow(clamp(0.5 + 0.5 * sin(spiral), 0.0, 1.0), 7.0);
  float disk = exp(-r * 3.1);
  float core = exp(-r * r * 46.0);
  return core * 1.7 + disk * arm + exp(-r * 1.5) * 0.12;
}

void main() {
  vec2 frag = gl_FragCoord.xy;
  vec2 uv = frag / uResolution;
  float aspect = uResolution.x / max(uResolution.y, 1.0);
  float reduced = step(0.5, uReduced);
  float t = uTime * (1.0 - reduced);
  float p = clamp(uProgress, 0.0, 1.0);
  vec2 st = (uv - 0.5) * vec2(aspect, 1.0);
  st += uPointer * 0.04 * (1.0 - reduced);

  float cam = p * 0.88;
  float front = min(0.985, 0.05 + p * 0.95);
  vec3 color = vec3(0.012, 0.014, 0.012);
  color += vec3(0.03, 0.02, 0.045) * (1.0 - uv.y) * 0.6;

  float voidNeb = fbm(st * 1.25 + vec2(t * 0.015, 0.2));
  color += vec3(0.05, 0.015, 0.07) * voidNeb * (1.0 - smoothstep(0.18, 0.55, p));

  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float planeZ = 0.12 + fi * 0.16;
    float rel = planeZ - cam;
    float presence = smoothstep(-0.1, 0.02, rel) * exp(-max(rel, 0.0) * 0.48);
    float zoom = 0.38 + max(rel, 0.0) * 1.85;
    vec2 offset = vec2(sin(fi * 2.35) * 0.46, cos(fi * 1.55) * 0.2);
    vec2 puv = (st + offset + uPointer * rel * 0.06 * (1.0 - reduced)) / max(zoom, 0.18);
    puv += vec2(t * 0.006 * (0.35 + fi * 0.12), sin(t * 0.05 + fi) * 0.012);

    float delta = planeZ - front;
    float pass = (1.0 - smoothstep(-0.035, 0.055, delta));
    float crest = exp(-delta * delta * 70.0);

    vec2 turb = vec2(fbm(puv * 1.55 + fi * 2.0), fbm(puv * 1.55 + vec2(8.0, fi)));
    vec2 ordered = vec2(sin(puv.y * 11.0 + fi * 1.7) * 0.22, sin(puv.x * 6.0) * 0.04);
    vec2 warped = puv + mix(turb, ordered, pass) * (0.2 + crest * 0.55);
    warped.x += crest * 0.32 * sin(puv.y * 20.0 + t);

    float fogN = fbm(warped * 1.3 + vec2(t * 0.02, fi));
    float filaments = pow(clamp(smoothstep(0.42, 0.86, fogN), 0.0, 1.0), 1.35);
    float strand = pow(clamp(0.5 + 0.5 * sin(warped.x * 16.0 + warped.y * 1.4), 0.0, 1.0), 5.0);
    float fog = mix(filaments * 0.65, strand * max(filaments, 0.35) * 1.25, pass);
    fog *= presence;

    vec3 beforeCol = vec3(0.09, 0.045, 0.14);
    vec3 afterCol = mix(vec3(0.55, 1.0, 0.22), vec3(0.62, 0.08, 0.86), 0.42);
    color += mix(beforeCol, afterCol, pass) * fog * (0.7 + crest * 1.6) * (0.55 + presence);

    vec2 suv = warped * (70.0 + fi * 24.0);
    vec2 cell = floor(suv);
    vec2 f = fract(suv) - 0.5;
    float h = hash(cell + fi * 19.0);
    float star = (1.0 - smoothstep(0.0, 0.05, length(f))) * step(0.986, h);
    float streak = (1.0 - smoothstep(0.0, 0.018, abs(f.y))) * step(0.993, h) * crest;
    vec3 starCol = mix(vec3(0.78, 0.84, 1.0), vec3(0.85, 1.0, 0.62), pass);
    color += starCol * (star + streak) * presence * (0.55 + pass * 0.7 + crest);

    if (i == 1 || i == 3 || i == 4) {
      float spin = t * 0.04 * (0.25 + pass);
      float cs = cos(spin);
      float sn = sin(spin);
      vec2 g = mat2(cs, -sn, sn, cs) * (warped - vec2(0.0, 0.04));
      float tight = mix(6.5, 17.0, pass);
      float arms = i == 4 ? 2.0 : 3.0;
      float scale = i == 3 ? 0.72 : 1.05;
      float body = galaxy(g * scale, tight, arms);
      vec3 gCol = mix(vec3(0.45, 0.55, 0.95), vec3(0.7, 1.0, 0.35), pass);
      color += gCol * body * presence * (0.85 + crest);
      float core = exp(-dot(g, g) * 30.0);
      color += vec3(1.0, 0.97, 0.9) * core * presence * (0.9 + crest * 2.0);
      vec2 ghost = g + vec2(crest * 0.22, crest * 0.04);
      color += vec3(0.65, 0.15, 1.0) * galaxy(ghost * scale, tight, arms) * crest * presence * 0.45;
    }
  }

  vec2 starSt = st * 150.0 + vec2(t * 0.4, 0.0);
  vec2 scell = floor(starSt);
  vec2 sf = fract(starSt) - 0.5;
  float sh = hash(scell);
  float field = (1.0 - smoothstep(0.0, 0.045, length(sf))) * step(0.972, sh);
  color += vec3(0.82, 0.88, 1.0) * field * 0.55;

  float birthAmp = 1.0 - smoothstep(0.14, 0.42, p);
  float radius = smoothstep(0.0, 0.36, p) * 1.22;
  float rd = length(st);
  float ring = exp(-pow(rd - radius, 2.0) * 160.0);
  float fringe = exp(-pow(rd - radius - 0.028, 2.0) * 90.0);
  float seed = exp(-rd * rd * 26.0) * (0.4 + 0.6 * (0.5 + 0.5 * sin(t * 1.7))) * (1.0 - smoothstep(0.0, 0.14, p));
  color += vec3(0.78, 1.0, 0.35) * ring * birthAmp * 1.6;
  color += vec3(0.58, 0.08, 0.9) * fringe * birthAmp * 1.15;
  color += vec3(0.96, 1.0, 0.92) * seed * 1.4;
  float pushed = exp(-pow(rd - radius, 2.0) * 28.0) * birthAmp;
  float dust = noise(st * 26.0 + vec2(radius * 3.0, t * 0.2));
  color += vec3(0.9, 0.95, 0.8) * smoothstep(0.68, 0.96, dust) * pushed;

  float traverse = smoothstep(0.2, 0.34, p) * (1.0 - smoothstep(0.74, 0.9, p));
  float waveY = 0.03 * sin(st.x * 2.4 + t * 0.65) + 0.05 * sin(st.x * 7.5 - t * 1.15);
  float band = st.y - waveY;
  float shock = exp(-band * band * 110.0);
  float side = exp(-pow(band - 0.04, 2.0) * 55.0);
  float partial = exp(-pow(band - 0.12, 2.0) * 140.0);
  color += vec3(0.8, 1.0, 0.38) * shock * traverse * 1.45;
  color += vec3(0.55, 0.06, 0.9) * side * traverse;
  color += vec3(0.75, 0.9, 1.0) * partial * traverse * 0.4;
  float wake = (1.0 - smoothstep(-0.55, 0.02, band)) * traverse;
  color += vec3(0.16, 0.28, 0.08) * wake * 0.22;

  float reveal = smoothstep(0.68, 0.94, p);
  float plate = (1.0 - smoothstep(0.15, 1.05, length(st * vec2(0.72, 1.05))));
  color *= mix(1.0, 0.28, reveal * plate);
  color += vec3(0.45, 0.9, 0.25) * exp(-dot(st, st) * (2.0 + reveal * 6.0)) * reveal * 0.28;

  float vignette = (1.0 - smoothstep(0.25, 1.25, length(st)));
  color *= mix(0.45, 1.0, vignette);
  color = color / (1.0 + color * 0.72);
  color += (hash(frag + fract(t * 3.0)) - 0.5) * 0.004;
  fragColor = vec4(color, 1.0);
}
`;

export const COMPOSITE = `#version 300 es
precision highp float;

uniform vec2 uResolution;
uniform float uTime;
uniform float uProgress;
uniform float uReduced;
uniform sampler2D uScene;
uniform sampler2D uLogo;
uniform float uLogoAspect;
uniform float uLogoReady;
uniform vec2 uFrameOrigin;
uniform vec2 uFrameSpan;

out vec4 fragColor;

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution;
  vec3 scene = texture(uScene, uv).rgb;
  vec2 frameUv = (uv - uFrameOrigin) / uFrameSpan;
  float frameAspect = (uResolution.x * uFrameSpan.x) / max(uResolution.y * uFrameSpan.y, 1.0);
  vec2 scale = frameAspect > uLogoAspect
    ? vec2(uLogoAspect / frameAspect, 1.0)
    : vec2(1.0, frameAspect / uLogoAspect);
  vec2 logoUv = (frameUv - 0.5) / scale + 0.5;
  float inside = step(0.0, logoUv.x) * step(logoUv.x, 1.0) * step(0.0, logoUv.y) * step(logoUv.y, 1.0);

  float open = smoothstep(0.66, 0.985, clamp(uProgress, 0.0, 1.0));
  float t = uTime * (1.0 - step(0.5, uReduced));
  vec2 q = (logoUv - vec2(0.5, 0.57)) * vec2(0.8, 1.0);
  float rad = length(q);
  float ripple = sin(logoUv.y * 48.0 - t * 2.0 + rad * 9.0) * (1.0 - open) * 0.035;
  float reached = rad - mix(0.0, 1.5, open) + ripple;
  // The untouched source must be fully occluded until the interference actually arrives.
  float mask = (1.0 - smoothstep(-0.008, 0.03, reached)) * smoothstep(0.015, 0.14, open) * inside * step(0.5, uLogoReady);

  vec3 logo = texture(uLogo, clamp(logoUv, 0.0, 1.0)).rgb;
  float core = smoothstep(0.4, 0.56, mask);
  vec3 color = mix(scene, logo, core);
  float rim = smoothstep(0.0, 0.48, mask) * (1.0 - core);
  color += rim * vec3(0.75, 1.0, 0.32) * 0.7;
  color += rim * vec3(0.52, 0.08, 0.9) * 0.4;
  fragColor = vec4(color, 1.0);
}
`;
