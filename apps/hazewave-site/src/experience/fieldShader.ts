export const FIELD_WAVE_SPEED = 0.55;

/** V6 cinematic environment compositor. Source typography is kept in the semantic DOM. */
export const fieldFragment = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 outColor;
uniform sampler2D uFrom,uTo,uPreview,uCanonical;
uniform vec2 uFromSize,uToSize,uPreviewSize,uCanonicalSize,uResolution,uOrigin,uWaveOrigin,uPointer,uPreviewOrigin;
uniform float uTime,uWaveAge,uProgress,uFromType,uToType,uPreviewType,uPreviewAmount,uEntryOpen;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+1.),f.x),f.y);}
float haze(vec2 p){return noise(p)*.67+noise(p*2.03+3.1)*.33;}
vec3 sampleWorld(sampler2D tex,vec2 uv){return texture(tex,clamp(uv,.001,.999)).rgb;}
vec2 projection(vec2 uv,vec2 size,float kind,float travel){
  float aspect=uResolution.x/uResolution.y,ia=size.x/size.y;
  vec2 ratio=aspect<ia?vec2(aspect/ia,1.):vec2(1.,ia/aspect);
  vec2 focus=vec2(.5);
  bool mobile=aspect<.9;
  if(mobile){
    if(kind<.5)focus=vec2(.69,.5);
    else if(kind>3.5&&kind<4.5)focus=vec2(.74,.50);
    else if(kind>4.5)focus=vec2(.64,.51);
    else if(kind>2.5&&kind<3.5)focus=vec2(.52,.50);
    else focus=vec2(.56,.50);
  }
  float zoom=1.035;
  if(kind<.5){
    float approach=smoothstep(0.,.7,travel);
    vec2 destination=vec2(mobile?.71:.69,.57);
    focus=mix(focus,destination,approach*.45);
    zoom+=approach*.42;
  }else zoom+=travel*.24;
  return focus+(uv-.5)*ratio/zoom;
}
vec3 scene(sampler2D tex,vec2 size,float kind,vec2 uv,float travel){
  if(kind<-.5)return sampleWorld(tex,uv)/(1.-.18*pow(length((uv-.5)*vec2(.8,1.)),1.5));
  float aspect=uResolution.x/uResolution.y;
  vec2 coords=projection(uv,size,kind,travel);
  vec2 camera=(uPointer-.5)*vec2(aspect>.9?1.:.35,1.);
  vec2 wd=(uv-uWaveOrigin)*vec2(aspect,1.);
  float distance=length(wd),age=max(0.,uWaveAge);
  float ring=exp(-pow((distance-age*${FIELD_WAVE_SPEED.toFixed(2)})*15.,2.))*exp(-age*.58)*step(age,3.1);
  vec2 refraction=wd/max(distance,.001)/vec2(aspect,1.)*sin((distance-age*${FIELD_WAVE_SPEED.toFixed(2)})*66.)*ring*.018;
  vec2 sky=coords-camera*vec2(.008,.005);
  vec2 middle=coords-camera*vec2(.014,.009);
  vec2 foreground=coords-camera*vec2(.033,.022);
  float near=1.-smoothstep(.08,.43,coords.y);
  if(kind>4.5){near=max(near,(1.-smoothstep(.1,.4,coords.x))*(1.-smoothstep(.7,.96,coords.y)));}
  if(kind>.5&&kind<1.5){near=max(near,(1.-smoothstep(.08,.42,coords.x))*.75);}
  if(kind>2.5&&kind<3.5){near=max(near,(1.-smoothstep(.12,.46,coords.x))*.75);}
  float skyMask=smoothstep(.55,.82,coords.y);
  // Water responds, while beacon, rocks, gear and skeletal architecture remain rigid.
  if(kind<.5){
    float water=1.-smoothstep(.37,.46,coords.y);
    foreground+=refraction*water;
    middle+=refraction*water*.3;
    foreground.x+=sin(coords.y*37.+uTime*.5)*.0016*water;
  }
  if(kind>3.5&&kind<4.5){
    float water=1.-smoothstep(.32,.46,coords.y);
    float curl=(1.-smoothstep(.36,.51,coords.x))*smoothstep(.2,.36,coords.y)*(1.-smoothstep(.84,.95,coords.y));
    middle+=refraction*max(water,curl)*.75;
    middle.x+=sin(coords.y*28.-uTime*.48)*.002*max(water,curl);
    foreground+=refraction*water;
  }
  if(kind>1.5&&kind<2.5){
    float heat=smoothstep(.2,.4,coords.x)*(1.-smoothstep(.66,.82,coords.x))*(1.-near);
    middle.x+=sin(coords.y*30.+uTime*.9)*.0018*heat;
  }
  if(kind>2.5&&kind<3.5){
    // Clockwork plane drifts independently from the distant city, with no water deformation.
    foreground+=vec2(sin(uTime*.16),cos(uTime*.13))*.0012*near;
  }
  if(kind>4.5){
    // Pressure and heat disturb only the deep crimson channel, never bone/wire.
    float molten=(1.-smoothstep(.13,.30,coords.y))*(1.-near*.65);
    middle.x+=sin(coords.y*42.+uTime*.65)*.0021*molten;
  }
  vec3 distant=sampleWorld(tex,sky);
  vec3 mid=sampleWorld(tex,middle);
  vec3 close=sampleWorld(tex,foreground);
  vec3 color=mix(mid,distant,skyMask);
  color=mix(color,close,near);
  if(kind<.5){
    // The canonical etched vortex is woven into the expanded environment.
    // Contact displaces these actual source pixels, then clears their haze.
    vec2 anchor=vec2(aspect<.9?.68:.77,.67);
    vec2 echo=(uv-anchor)*vec2(aspect,1.);
    float imprint=1.-smoothstep(.13,.32,length(echo));
    vec2 engraved=vec2(.50,.47)+echo*vec2(1.25,.90)+refraction*.65;
    engraved=clamp(engraved,vec2(.015),vec2(.985,.69));
    vec3 canon=sampleWorld(uCanonical,engraved);
    float chroma=max(canon.r,max(canon.g,canon.b))-min(canon.r,min(canon.g,canon.b));
    float pigment=smoothstep(.09,.22,chroma);
    imprint*=smoothstep(.56,.66,uv.y);
    color=mix(color,canon,imprint*pigment*(.30+ring*.50));
  }
  float mist=haze(uv*vec2(3.,4.)+vec2(uTime*.015,-uTime*.009));
  float fogBand=exp(-pow((uv.y-.30+sin(uv.x*4.)*.035)*8.,2.));
  vec3 fog=vec3(.10,.11,.12);
  if(kind<.5)fog=vec3(.12,.085,.18);
  if(kind>3.5&&kind<4.5)fog=vec3(.11,.15,.18);
  if(kind>4.5)fog=vec3(.17,.035,.025);
  if(kind>1.5&&kind<2.5)fog=vec3(.18,.085,.025);
  color=mix(color,fog,fogBand*mist*.16*(1.-ring*.8));
  // Contact clears the atmospheric material along the propagating wavefront.
  color+=vec3(.025,.034,.021)*ring*fogBand;
  return color;
}
float frontierFor(vec2 delta,float kind){
  float f=length(delta*vec2(.55,1.6));
  if(kind>4.5)f=abs(delta.x+delta.y*.32)*.60+abs(delta.y)*1.10;
  if(kind>.5&&kind<1.5)f=max(abs(delta.x)*.65,abs(delta.y)*1.15);
  if(kind>1.5&&kind<2.5)f=abs(delta.x-delta.y*.18)*.8+abs(delta.y)*.7;
  return f+haze(delta*11.)*.045;
}
void main(){
  float aspect=uResolution.x/uResolution.y;
  float p=clamp(uProgress,0.,1.),eased=p*p*(3.-2.*p);
  vec2 delta=(vUv-uOrigin)*vec2(aspect,1.);
  vec3 from=vec3(0.);
  if(p<.999)from=scene(uFrom,uFromSize,uFromType,vUv,eased);
  vec2 openingUv=vUv-uOrigin+.5;
  vec2 destinationUv=mix(openingUv,vUv,smoothstep(.05,.78,p));
  if(uFromType<-.5||uFromType>.5)destinationUv=vUv;
  vec3 to=scene(uTo,uToSize,uToType,destinationUv,(1.-smoothstep(.25,.90,p))*.8);
  float frontier=frontierFor(delta,uToType);
  float reach=length(vec2(aspect,1.))*1.25;
  float boundary=pow(eased,1.45)*reach+.16;
  float blend=smoothstep(frontier-.07,frontier+.07,boundary);
  if(uEntryOpen<.5)blend*=smoothstep(0.,.10,p);
  if(p>=.999)blend=1.;
  vec3 color=mix(from,to,blend);
  if(uToType<.5&&p>.999&&uPreviewAmount>.001){
    vec2 pd=(vUv-uPreviewOrigin)*vec2(aspect,1.);
    float aperture=frontierFor(pd,uPreviewType);
    float opened=(1.-smoothstep(.13*uPreviewAmount,.29*uPreviewAmount,aperture))*uPreviewAmount;
    vec2 worldUv=vUv-uPreviewOrigin+.5;
    vec3 world=scene(uPreview,uPreviewSize,uPreviewType,worldUv,.25);
    color=mix(color,world,opened);
    float rim=exp(-abs(aperture-.21*uPreviewAmount)*80.)*uPreviewAmount;
    vec3 tint=uPreviewType>4.5?vec3(.28,.025,.015):vec3(.13,.18,.15);
    color+=tint*rim*.3;
  }
  float vignette=1.-.18*pow(length((vUv-.5)*vec2(.8,1.)),1.5);
  color*=vignette;
  outColor=vec4(color,1.);
}`;
