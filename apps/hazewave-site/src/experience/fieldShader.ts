export const FIELD_WAVE_SPEED = 0.55;

/** V7: one persistent illustrated environment, never a pair of panoramic worlds.
 * Scroll changes the projection, fluid material and haze, with the same landmarks.
 * This is an analytic 2.5D surface, not a claim of geometric 3D reconstruction.
 */
export const fieldFragment = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 outColor;
uniform sampler2D uWorld;
uniform vec2 uWorldSize,uResolution,uWaveOrigin,uPointer;
uniform float uTime,uWaveAge,uClimate,uTravel,uPreviewAmount;
float hash(vec2 p){vec2 q=fract(p*vec2(.1031,.11369));q+=dot(q,q.yx+19.19);return fract(q.x*q.y*(q.x+q.y));}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+1.),f.x),f.y);}
float haze(vec2 p){return noise(p)*.64+noise(p*2.03+3.1)*.36;}
mat2 rotation(float a){float c=cos(a),s=sin(a);return mat2(c,-s,s,c);}
vec3 sampleWorld(vec2 uv){return texture(uWorld,clamp(uv,.001,.999)).rgb;}
void main(){
  float aspect=uResolution.x/uResolution.y,ia=uWorldSize.x/uWorldSize.y;
  float depth=clamp(uTravel,0.,1.),climate=clamp(uClimate,0.,1.);
  vec2 ratio=aspect<ia?vec2(aspect/ia,1.):vec2(1.,ia/aspect);
  // The anchor remains the same physical image coordinate throughout the journey.
  vec2 anchor=vec2(.62,.54);
  vec2 focus=mix(vec2(aspect<.9?.61:.5,.5),anchor,depth*.55);
  vec2 uv=focus+rotation(-.065*depth)*(vUv-.5)*ratio/(1.025+depth*.88);
  vec2 relative=(uv-anchor)*vec2(ia,1.);
  float radius=length(relative),angle=atan(relative.y,relative.x);
  // Protect the distant beacon; refraction belongs to the fluid around it.
  float fluid=smoothstep(.055,.135,radius);
  float foreground=1.-smoothstep(.14,.55,uv.y);
  vec2 parallax=(uPointer-.5)*vec2(.014,.01)*(0.3+foreground*1.4);
  uv-=parallax*fluid;
  // A front really moves across the image with scroll, rather than just fading it.
  float scrollFront=exp(-pow((radius-(.08+.66*depth))*9.,2.));
  vec2 pd=(vUv-uWaveOrigin)*vec2(aspect,1.);
  float distance=length(pd),age=max(0.,uWaveAge);
  float contact=exp(-pow((distance-age*${FIELD_WAVE_SPEED.toFixed(2)})*14.,2.))*exp(-age*.55)*step(age,3.1);
  vec2 normal=pd/max(distance,.001)/vec2(aspect,1.);
  vec2 tidal=vec2(sin(angle*3.-uTime*.58+radius*28.),cos(angle*2.+uTime*.36-radius*19.));
  float pulse=sin(radius*51.-depth*19.+angle*2.);
  vec2 displacement=tidal*.0035*(.5+foreground)*fluid;
  displacement+=normalize(relative+vec2(.0001))/vec2(ia,1.)*pulse*scrollFront*.018*fluid;
  displacement+=normal*sin((distance-age*${FIELD_WAVE_SPEED.toFixed(2)})*59.)*contact*.022*fluid;
  uv+=displacement;
  vec3 base=sampleWorld(uv);
  float light=dot(base,vec3(.2126,.7152,.0722));
  // Indionesbala's supplied copper/orange lettering determines material temperature.
  // No invented city, biography, recording or fictional release is introduced.
  vec3 copper=vec3(light*1.25,light*.61,light*.29);
  // The artist's angular lettering informs a change in mark-making as well as heat.
  // Resolve the same landscape into a limited amber/ink print, retaining landmarks.
  float printLight=.5*smoothstep(.06,.5,light)+.5*smoothstep(.48,.96,light);
  vec3 printColor=mix(vec3(.045,.016,.025),vec3(1.,.59,.22),printLight);
  float contour=smoothstep(.035,.12,length(vec2(dFdx(light),dFdy(light))));
  printColor=mix(printColor,vec3(.025,.01,.02),contour*.4);
  float hatch=1.-smoothstep(.07,.22,abs(sin((uv.x*1.7+uv.y)*210.)));
  printColor*=1.-hatch*.19*(1.-smoothstep(.18,.6,light))*fluid;
  vec3 color=mix(base,mix(copper,printColor,.4),climate*.88);
  float separation=(scrollFront*.0018+contact*.0035)*fluid;
  if(separation>.0001){color.r=mix(color.r,sampleWorld(uv+normal*separation).r,.35);color.b=mix(color.b,sampleWorld(uv-normal*separation).b,.35);}
  // Two depth layers of drifting painted haze. The propagating front clears it.
  float farMist=haze(uv*vec2(4.,5.)+vec2(uTime*.024,-uTime*.016));
  float nearMist=haze(vUv*vec2(3.,4.)+vec2(-uTime*.031,uTime*.014)+depth*1.8);
  float fogBand=exp(-pow((vUv.y-.42+sin(vUv.x*4.+depth)*.10)*3.1,2.));
  float fogDensity=(farMist*.13+nearMist*.16)*fogBand*(1.-min(.85,scrollFront*.72+contact*.88));
  vec3 fog=mix(vec3(.10,.075,.16),vec3(.23,.085,.026),climate);
  color=mix(color,fog,fogDensity);
  vec3 waveLight=mix(vec3(.10,.12,.08),vec3(.19,.07,.018),climate);
  color+=waveLight*(scrollFront*.25+contact*.52)*light;
  color*=1.-.14*pow(length((vUv-.5)*vec2(.8,1.)),1.5);
  outColor=vec4(color,1.);
}`;
