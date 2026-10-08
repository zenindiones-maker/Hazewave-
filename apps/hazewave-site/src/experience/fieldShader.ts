export const FIELD_WAVE_SPEED = 0.55;

export const fieldFragment = `#version 300 es
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
      if(kind>4.5){scale*=mobile?1.44:1.62;center=vec2(mobile?.52:.64,mobile?.56:.53);}
      if(kind>1.5&&kind<2.5){scale=mobile?aspect/ia*.95:.72;center=vec2(.5,mobile?.6:.54);}
      if(kind>.5&&kind<1.5)scale*=1.13;
      if(kind<.5 && mobile){scale=.96;center.y=.48;}
      if(kind>3.5&&kind<4.5){ia=size.x/(size.y*.78);scale=mobile?.96:1.26;center=vec2(mobile?.37:.50,.50);}
      vec2 coords=(uv-center)*vec2(aspect/ia,1.)/(scale+depth*.06)+.5;
      if(kind<.5)coords.y*=.70;
      if(kind>3.5&&kind<4.5)coords.y*=.78;
      vec2 camera=(uPointer-.5);
      vec2 original=coords;
      if(kind<-.5){
        float vig=1.-.18*pow(length((uv-.5)*vec2(.7,1.)),1.5);
        return texture(tex,uv).rgb/vig;
      }
      // Three independently projected source planes; hard architecture is never wave-warped.
      if(kind<.5){
        vec2 sky=original-camera*vec2(.016,.009);
        vec2 town=original-camera*vec2(.032,.016);
        vec2 sea=original-camera*vec2(.062,.029);
        vec2 wd=(uv-uWaveOrigin)*vec2(aspect,1.);
        float distance=length(wd),age=max(0.,uWaveAge);
        float ring=exp(-pow((distance-age*${FIELD_WAVE_SPEED.toFixed(2)})*14.,2.))*exp(-age*.65)*step(age,3.1);
        vec2 warp=wd/max(.001,distance)/vec2(aspect,1.)*sin((distance-age*${FIELD_WAVE_SPEED.toFixed(2)})*78.)*ring*.023;
        sea+=warp*vec2(aspect/ia,.7);
        sky+=warp*.22;
        float towerSky=(1.-smoothstep(.054,.063,abs(sky.x-.52)))*smoothstep(.19,.25,sky.y)*(1.-smoothstep(.53,.55,sky.y));
        float tower=(1.-smoothstep(.054,.063,abs(town.x-.52)))*smoothstep(.19,.25,town.y)*(1.-smoothstep(.53,.55,town.y));
        float city=smoothstep(.15,.24,town.y)*(1.-smoothstep(.27,.34,town.y));
        float surf=1.-smoothstep(.15,.24,sea.y);
        vec3 background=imageAt(tex,sky)*(1.-towerSky);
        vec3 architecture=imageAt(tex,town);
        vec3 water=imageAt(tex,sea);
        float rigid=max(tower,city);
        vec3 planes=mix(background,architecture,rigid);
        planes=mix(planes,water,surf);
        float bank=exp(-pow((uv.y-.17-sin(uv.x*4.-uTime*.04)*.035)*7.,2.));
        float density=mist(uv*vec2(3.,5.)+vec2(uTime*.012,-uTime*.01));
        planes=mix(planes,vec3(.13,.17,.10),bank*density*.22*(1.-ring));
        float lantern=exp(-length((town-vec2(.52,.49))*vec2(1.,1.4))*24.);
        planes+=vec3(.12,.16,.04)*lantern*.22;
        float edgeFade=smoothstep(0.,.09,sky.x)*smoothstep(0.,.09,1.-sky.x);
        vec2 periphery=vec2(uv.x<.5?.10:.90,.31+uv.y*.30+sin(uTime*.035+uv.x*3.)*.012);
        vec3 pigment=(imageAt(tex,periphery+vec2(-.05,.06))+imageAt(tex,periphery+vec2(.035,-.05))+imageAt(tex,periphery+vec2(-.025,-.02))+imageAt(tex,periphery+vec2(.05,.04)))*.25;
        vec3 sourcedHaze=pigment*(.055+.08*mist(uv*vec2(2.,4.)+uTime*.009));
        return mix(sourcedHaze,planes,edgeFade);
      }
      if(kind>.5&&kind<1.5){coords-=camera*vec2(.014,.006);}
      if(kind>1.5&&kind<2.5){coords.x-=camera.x*.035;}
      if(kind>2.5&&kind<3.5){coords-=camera*vec2(.028,.014);}
      if(kind>3.5&&kind<4.5){
        float rock=smoothstep(.66,.74,original.x)*(1.-smoothstep(.39,.52,original.y));
        float water=(1.-smoothstep(.56,.71,original.y))*(1.-rock);
        coords-=camera*mix(vec2(.012,.006),vec2(.048,.019),rock);
        coords.x+=sin(coords.y*35.+uTime*.6)*.004*water;
        coords.y+=sin(coords.x*19.-uTime*.4)*.002*water;
        vec2 wd=(uv-uWaveOrigin)*vec2(aspect,1.);
        float dist=length(wd),age=max(0.,uWaveAge);
        float ring=exp(-pow((dist-age*${FIELD_WAVE_SPEED.toFixed(2)})*14.,2.))*exp(-age*.65)*step(age,3.1);
        coords+=wd/max(.001,dist)*sin((dist-age*${FIELD_WAVE_SPEED.toFixed(2)})*78.)*ring*.016*water;
      }
      if(kind>4.5){coords-=camera*vec2(.007,.003);}
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
      if(kind>.5&&kind<1.5){
        vec2 typePlane=(uv-vec2(.28,.52))*vec2(aspect*.42,.46)+vec2(.5,.48)-camera*.035;
        vec3 glyph=imageAt(tex,typePlane);
        float slabs=(1.-smoothstep(.18,.28,uv.x))+smoothstep(.80,.9,uv.x);
        ambient=glyph*.3*slabs;
      }
      if(kind>1.5&&kind<2.5){
        vec2 hot=vec2(.5)+(uv-vec2(.5,.5))*vec2(aspect*.2,.16);
        float bands=exp(-abs(uv.y-.35)*20.)+exp(-abs(uv.y-.66)*25.);
        ambient=imageAt(tex,hot+vec2(camera.x*.035,0.))*vec3(.33,.17,.06)*bands;
      }
      if(kind>2.5&&kind<3.5){
        vec2 foreground=(uv-vec2(.29,.13))*vec2(aspect*.31,.22)+vec2(.55,.21)-camera*.055;
        float near=1.-smoothstep(.06,.28,uv.y);
        ambient=max(ambient,imageAt(tex,foreground)*near*.52);
      }
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
        float cleared=exp(-pow((length((uv-uWaveOrigin)*vec2(aspect,1.))-uWaveAge*${FIELD_WAVE_SPEED.toFixed(2)})*9.,2.))*exp(-max(0.,uWaveAge)*.32);
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
      float radius=age*${FIELD_WAVE_SPEED.toFixed(2)};
      float envelope=exp(-pow((distance-radius)*14.,2.))*exp(-age*.65)*step(age,3.1);
      float oscillation=sin((distance-radius)*78.);
      vec2 direction=waveDelta/max(.001,distance)/vec2(aspect,1.);
      vec2 displaced=vUv+direction*oscillation*envelope*.033;
      float p=clamp(uProgress,0.,1.);
      float eased=p*p*(3.-2.*p);
      vec3 fromColor=vec3(0.);
      if(p<.999)fromColor=scene(uFrom,uFromSize,uFromType,vUv,eased);
      vec2 windowUv=vUv-uOrigin+.5;
      vec2 traverse=mix(windowUv+vec2(-.07,.33)*(1.-smoothstep(.12,.75,p)),vUv,smoothstep(.15,.88,p));
      vec3 toColor=scene(uTo,uToSize,uToType,uFromType<.5&&uFromType>-.5?traverse:vUv,(1.-smoothstep(.5,1.,p))*.9);

      float reach=length(vec2(aspect,1.))*1.2;
      float frontier=length(delta*vec2(.56,1.8))+mist(delta*13.+vec2(uTime*.025,0.))*.065;
      if(uToType>4.5){frontier=mix(frontier,abs(delta.x)*.75+abs(delta.y)*.9+noise(vUv*vec2(12.,44.))*.17,eased);}
      float boundary=pow(eased,1.7)*reach+.225;
      float blend=smoothstep(frontier-.06,frontier+.06,boundary);
      if(uEntryOpen<.5)blend*=smoothstep(0.,.13,p);
      if(p>=.999)blend=1.;
      vec3 col=mix(fromColor,toColor,blend);
      // A discovered world is a texture opening in the field, never a DOM thumbnail.
      if(uToType<.5 && p>.999 && uPreviewAmount>.001){
        vec2 pd=(vUv-uPreviewOrigin)*vec2(aspect,1.);
        float turbulence=mist(pd*13.+vec2(uTime*.025,0.));
        float aperture=length(pd*vec2(.56,1.8))+turbulence*.065;
        float opening=(1.-smoothstep(.15*uPreviewAmount,.30*uPreviewAmount,aperture))*uPreviewAmount;
        vec2 puv=vUv-uPreviewOrigin+.5+vec2(-.07,.33);
        vec3 world=scene(uPreview,uPreviewSize,uPreviewType,puv,0.);
        if(uPreviewType>3.5&&uPreviewType<4.5){
          vec2 detail=vec2(.40,.65)+(vUv-uPreviewOrigin)*vec2(aspect,1.)*.65;
          world=imageAt(uPreview,detail);
        }
        col=mix(col,world,opening);
        float rim=exp(-abs(aperture-.225*uPreviewAmount)*100.)*uPreviewAmount;
        col+=rim*vec3(.10,.15,.055);
      }
      float crest=exp(-abs(frontier-boundary)*55.)*sin(p*3.14159);
      col+=crest*vec3(.22,.25,.12)*(0.25+dot(col,vec3(.3)));
      col+=envelope*.048*vec3(.7,.85,.45);
      float vignette=1.-.18*pow(length((vUv-.5)*vec2(.7,1.)),1.5);
      outColor=vec4(col*vignette,1.);
    }`;
