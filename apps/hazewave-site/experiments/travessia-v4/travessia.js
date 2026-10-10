/* HAZEWAVE TRAVESSIA V4 — physical scroll scene, not a sequence of posters.
 * Reconstructed first-party V3A 12-pad/8-knob/4-speaker pixel textures.
 * Camera, occlusion, portal radius, machine halves and strokes derive from ONE scroll value.
 * NO agent authority, network-side effects, autoplay, third-party scripts or production approval.
 */
(()=>{'use strict';
const doc=document, el=id=>doc.getElementById(id), clamp=v=>Math.max(0,Math.min(1,v));
const smooth=(a,b,p)=>{const t=clamp((p-a)/(b-a));return t*t*(3-2*t)};
const ramp=(a,b,p)=>smooth(a,b,p);
const band=(a,b,c,d,p)=>smooth(a,b,p)*(1-smooth(c,d,p));
const lerp=(a,b,t)=>a+(b-a)*t;
const chapters=[
 ['01 / 05','O silêncio tem profundidade.','No coração da névoa, a primeira frequência aguarda.'],
 ['02 / 05','O traço nasce.','A onda se desenha no espaço e desperta a estação.'],
 ['03 / 05','Atravesse o mecanismo.','A câmera cruza pads, alto-falantes, circuitos e cabos.'],
 ['04 / 05','A névoa se rompe.','A energia abre o chassi, empurra as camadas e revela o outro lado.'],
 ['05 / 05','Outro mundo.','A interferência alcança o hub Indionesbala. O universo responde.']
];
const vars={section:el('journey'),stage:el('stage'),stars:el('stars'),machine:el('machine'),
left:el('chassis-left'),right:el('chassis-right'),parts:el('parts'),
fogBack:el('fog-back'),fogLeft:el('fog-left'),fogRight:el('fog-right'),
city:el('city-scene'),cityFlight:el('city-flight'),hub:el('hub-scene'),
window:el('portal-window'),portalWorld:el('portal-world'),innerHub:el('portal-inner-hub'),
ring:el('portal-ring'),rim:el('portal-rim'),halo:el('portal-halo'),tear:el('portal-tear'),
trace:el('trace'),shadow:el('trace-shadow'),traceHead:el('trace-head'),
worldSignal:el('world-signal'),worldPath:el('world-signal-path'),worldBlur:el('world-signal-blur'),worldHead:el('world-head'),
planet:el('far-planet'),vortex:el('cosmic-vortex'),debrisA:el('debris-a'),debrisB:el('debris-b'),
title:el('chapter-title'),copy:el('chapter-copy'),num:el('chapter-num'),narrative:el('narrative'),
progress:el('progress-bar'),progressText:el('progress-text')};
let pieces=[],manifest=null,lastPhase=-1,lastSize='',lastProgress=NaN,traceLen=0,worldLen=0,ringLen=0;
const state={schema:'HazewaveV4PhysicalTraversalRuntime/v1',ready:false,progress:0,phase:0,
 activePads:0,activeKnobs:0,activeSpeakers:0,mountedPieces:0,
 traceDrawn:0,worldWaveDrawn:0,portalRadiusPct:0,mechanicalSplitPx:0,
 cameraTravelPx:0,machineScale:0,fogSeparationPx:0,cityOpacity:0,hubOpacity:0,
 changedRegion:false,secondIllustratedRegionVisible:false,sourceV3A:'',
 humanCreativeApproval:false,productionApproved:false};
window.__HAZEWAVE_TRAVERSAL_V4=state;

 // NASA Prospect MIT-inspired principles: chapter-aware navigation, reversed
 // scroll state, and optional low-detail compositor. Original Hazewave code.
 const chapterStops=Object.freeze([0,.25,.47,.70,.92]);
 const chapterLinks=[...doc.querySelectorAll('[data-world-stop]')];
 let userRequestedLite=false,autoLite=false,frameBudgetStreak=0,lastFrameAt=NaN;
 function updateQuality(){
  const lite=userRequestedLite||autoLite;
  vars.stage.dataset.quality=lite?'lite':'full';
  const button=el('lightweight-mode');
  if(button){button.setAttribute('aria-pressed',String(userRequestedLite));button.textContent=userRequestedLite?'EFEITOS':'LEVE';}
  state.visualQualityTier=lite?'lite':'full';
  state.qualityDowngradeAutomatic=autoLite;
  if(Number.isFinite(state.progress))renderArtcraftEffect(state.progress);
  // Geometry, original art, and interaction authority NEVER change with quality.
 }
 function observeFrameBudget(timestamp){
  if(Number.isFinite(lastFrameAt)){
   const delta=timestamp-lastFrameAt;
   if(delta>0&&delta<180){
    frameBudgetStreak=delta>44?frameBudgetStreak+1:Math.max(0,frameBudgetStreak-1);
    if(frameBudgetStreak>=5&&!autoLite){autoLite=true;updateQuality();}
   } else if(delta>=180){frameBudgetStreak=0;}
  }
  lastFrameAt=timestamp;
 }
 function gotoAct(index){
  if(!Number.isInteger(index)||index<0||index>=chapterStops.length)return false;
  const start=vars.section.getBoundingClientRect().top+window.scrollY;
  const travel=Math.max(1,vars.section.offsetHeight-innerHeight);
  window.scrollTo({top:start+travel*chapterStops[index],behavior:'instant'});
  schedule();return true;
 }
 function setupChapterNavigation(){
  for(const button of chapterLinks){
   const index=Number(button.dataset.worldStop);
   if(Number.isInteger(index))button.addEventListener('click',()=>gotoAct(index));
  }
  const light=el('lightweight-mode');
  if(light)light.addEventListener('click',()=>{userRequestedLite=!userRequestedLite;updateQuality();});
  updateQuality();
 }
 state.researchReferenceTechniques=['nasa-prospect-direction-reversible-chapter-nav','ponpon-mania-layered-illustration-camera','whoisguilty-motion-graphic-compositor'];
 state.productionApproved=false;
 window.__HAZEWAVE_RESEARCH_V5={gotoAct,getStops:()=>[...chapterStops],getQuality:()=>state.visualQualityTier};

// Optional first-party portal overlay rendered OFFLINE with real EffectCraft.
 // The FilmCraft validation receipt is checked by the private site composer,
 // NOT by the browser (which never invokes untrusted native applications).
 const fxCanvas=el('effectcraft-aperture');
 const fxCtx=fxCanvas?.getContext('2d',{alpha:true}) || null;
 let fxDecoded=[],fxFrameIndex=-1,fxReadiness='NOT_ATTACHED';
 const fxSpec=window.__hazewaveEffectArt;
 async function prepareArtcraftEffect(){
  if(!fxCtx||!fxSpec){state.effectcraftStatus='NOT_ATTACHED';return}
  const frames=fxSpec.frames;
  if(fxSpec.schema!=='HazewaveRealArtcraftPortalOverlay/v1' ||
     fxSpec.production_approved!==false ||
     fxSpec.real_effectcraft_render!==true ||
     fxSpec.filmcraft_probe_executed!==true ||
     !Array.isArray(frames) || frames.length!==8){
   state.effectcraftStatus='REJECTED_UNTRUSTED_MANIFEST';return;
  }
  const images=[];
  for(let i=0;i<8;i++){
   const frame=frames[i],path=frame?.url;
   const expected='assets/fx/sonic-portal-'+String(i).padStart(2,'0')+'.png';
   if(typeof path!=='string' || !(path===expected ||
      (path.startsWith('data:image/png;base64,') && path.length<3000000))){
    state.effectcraftStatus='REJECTED_ASSET_PATH';return;
   }
   const image=new Image();image.decoding='async';image.src=path;
   images.push(image);
  }
  try{
   await Promise.all(images.map(img=>img.decode()));
   if(images.some(img=>img.naturalWidth!==420||img.naturalHeight!==820))
     throw Error('EFFECT_FRAME_CANVAS_DRIFT');
   fxDecoded=images;fxReadiness='READY';state.effectcraftStatus='READY';
   renderArtcraftEffect(progressFromScroll());
  }catch{
   fxReadiness='UNAVAILABLE';state.effectcraftStatus='ASSET_DECODE_FAILED';
   // The native CSS/SVG physical aperture keeps working without FX.
  }
 }
 function renderArtcraftEffect(p){
  const t=smooth(.45,.79,p);
  const alpha=band(.45,.61,.75,.87,p);
  const idx=Math.min(7,Math.max(0,Math.floor(t*8)));
  const lite=vars.stage.dataset.quality==='lite' ||
     window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(!fxCanvas){state.effectcraftFrame=-1;return}
  fxCanvas.style.opacity=(fxReadiness==='READY'&&!lite?alpha*.58:0).toFixed(4);
  fxCanvas.style.transform='translate(-50%,-50%) scale('+(0.48+0.94*t).toFixed(4)+') rotate('+(26*t).toFixed(2)+'deg)';
  if(fxReadiness==='READY'&&!lite&&idx!==fxFrameIndex){
   fxCtx.clearRect(0,0,420,820);
   fxCtx.drawImage(fxDecoded[idx],0,0,420,820);
   fxFrameIndex=idx;
  }
  state.effectcraftFrame=fxReadiness==='READY'&&!lite?idx:-1;
  state.effectcraftOpacity=parseFloat(fxCanvas.style.opacity);
  state.effectcraftSuppressed=Boolean(lite);
 }
 window.__HAZEWAVE_ARTCRAFT_V7={
  version:'V7',site:'Hazewave',getReadiness:()=>fxReadiness,
  getFrame:()=>state.effectcraftFrame,source:'real-offline-effectcraft-frames'
 };

function mount(spec){
 const piece=doc.createElement('img');piece.src=(window.__assetUrls?.[spec.file] || 'assets/'+spec.file);
 piece.alt='';piece.draggable=false;piece.decoding='async';piece.className='rig-part rig-'+spec.type;
 piece.dataset.partId=spec.id;
 Object.assign(piece.style,{left:spec.x+'px',top:spec.y+'px',width:spec.width+'px',height:spec.height+'px',zIndex:spec.type==='pad'?'10':'8'});
 vars.parts.appendChild(piece);
 let on=null;
 if(spec.type==='pad'){
  on=doc.createElement('img');on.src=(window.__assetUrls?.[spec.energizedFile] || 'assets/'+spec.energizedFile);on.alt='';on.draggable=false;
  on.decoding='async';on.className='rig-part pad-on';on.dataset.padId=spec.id;
  Object.assign(on.style,{left:spec.x+'px',top:spec.y+'px',width:spec.width+'px',height:spec.height+'px',zIndex:'11'});
  vars.parts.appendChild(on);
 }
 return {spec,piece,on};
}
function setStroke(path,length,value){path.style.strokeDasharray=String(length);path.style.strokeDashoffset=String(length*(1-clamp(value)));}
function moveImage(element,x,y,scale,rot=0){element.style.transform=`translate3d(calc(-50% + ${x.toFixed(2)}px),calc(-50% + ${y.toFixed(2)}px),0px) scale(${scale.toFixed(5)}) rotate(${rot.toFixed(3)}deg)`;}
function makeStars(){
 const canvas=vars.stars,ctx=canvas.getContext('2d');if(!ctx)return;
 const dpr=Math.min(1.5,window.devicePixelRatio||1);
 canvas.width=Math.round(window.innerWidth*dpr);canvas.height=Math.round(window.innerHeight*dpr);
 ctx.scale(dpr,dpr);
 let seed=0xfeedbacc;const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};
 const w=innerWidth,h=innerHeight;
 for(let i=0;i<170;i++){
  const x=rand()*w,y=rand()*h,r=.3+rand()*1.3;
  ctx.fillStyle=`rgba(${170+Math.round(rand()*55)},${140+Math.round(rand()*65)},255,${(.16+rand()*.7).toFixed(2)})`;
  ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();
 }
}
function updatePose(p){
 const W=innerWidth,H=innerHeight,phone=W<700;
 // ARC ONE: far approach. ARC TWO: fly THROUGH machine. ARC THREE: break into new world.
 const approach=smooth(.035,.31,p),through=smooth(.30,.625,p),rupture=smooth(.54,.77,p),arrival=smooth(.74,.98,p);
 const rigSize=Math.min((phone?W*1.7:W*.87)/1448,(H*(phone?.87:1.1))/1086);
 const scale=rigSize*lerp(.30,1.22,approach)*lerp(1,3.9,through);
 const camX=lerp(phone?W*.42:W*.23,0,approach) + lerp(0,phone?-W*.96:-W*.55,through);
 const camY=lerp(-H*.28,H*.19,approach)+lerp(0,-H*.52,through);
 const twist=lerp(-6,0,approach)+lerp(0,-18,through);
 moveImage(vars.machine,camX,camY,scale,twist);
 vars.machine.style.opacity=String(clamp((1-smooth(.65,.81,p))*.97));
 const split=85*smooth(.43,.66,p); // true separated source-painted halves
 vars.left.style.transform=`translate3d(${-split.toFixed(2)}px,${-14*through}px,0) rotate(${-3*through}deg)`;
 vars.right.style.transform=`translate3d(${split.toFixed(2)}px,${14*through}px,0) rotate(${3*through}deg)`;
 const pulse=(p>=.185)?smooth(.185,.49,p):0;
 let activePads=0,activeKnobs=0,activeSpeakers=0;
 for(const {spec,piece,on} of pieces){
  // The wave is physically the single causal source for mechanical response.
  const energy=smooth(Math.max(.19,spec.activation*.72)-.035,Math.max(.19,spec.activation*.72)+.105,p);
  if(spec.type==='pad'){
   const push=energy*(2.7+2.0*Math.sin(spec.activation*16));
   const shift=rupture*12;piece.style.transform=`translate3d(${(rupture*(spec.x-724)*.030).toFixed(2)}px,${(-push-shift).toFixed(2)}px,${(22*energy).toFixed(2)}px)`;
   if(on){on.style.transform=piece.style.transform;on.style.opacity=(energy*(.9+.06*Math.sin(spec.activation*30))).toFixed(4)}
   if(energy>.5)activePads++;
  }else if(spec.type==='knob'){
   const spin=(spec.x%2?1:-1)*energy*32;
   piece.style.transform=`rotate(${spin.toFixed(3)}deg) translateZ(${energy*11}px)`;
   if(energy>.5)activeKnobs++;
  }else{
   const cone=1+energy*.075;piece.style.transform=`scale(${cone.toFixed(4)}) translateZ(${energy*13}px)`;
   if(energy>.5)activeSpeakers++;
  }
 }
 const lineValue=smooth(.08,.575,p);
 setStroke(vars.trace,traceLen,lineValue);setStroke(vars.shadow,traceLen,lineValue);
 const pos=vars.trace.getPointAtLength(traceLen*lineValue);
 vars.traceHead.setAttribute('cx',pos.x.toFixed(2));vars.traceHead.setAttribute('cy',pos.y.toFixed(2));
 vars.traceHead.style.opacity=String(lineValue>.03&&lineValue<.996?1:0);
 const signalValue=smooth(.12,.87,p);
 setStroke(vars.worldPath,worldLen,signalValue);setStroke(vars.worldBlur,worldLen,signalValue);
 const worldPosition=vars.worldPath.getPointAtLength(worldLen*signalValue);
 vars.worldHead.setAttribute('cx',worldPosition.x.toFixed(2));vars.worldHead.setAttribute('cy',worldPosition.y.toFixed(2));
 vars.worldHead.style.opacity=String(signalValue>.01&&signalValue<.99?.85:0);
 // Separate fog planes are pushed APART by the causal wave, never merely faded.
 const fogPush=rupture*(phone?W*.95:W*.78);
 vars.fogLeft.style.transform=`translate3d(${-fogPush.toFixed(2)}px,${(-H*.23*rupture).toFixed(2)}px,0) rotate(${-17*rupture}deg)`;
 vars.fogRight.style.transform=`translate3d(${fogPush.toFixed(2)}px,${(H*.22*rupture).toFixed(2)}px,0) rotate(${15*rupture}deg)`;
 vars.fogLeft.style.opacity=String(.65*(1-.63*arrival));
 vars.fogRight.style.opacity=String(.57*(1-.59*arrival));
 vars.fogBack.style.transform=`translate3d(${(-W*.11*approach+W*.38*rupture).toFixed(2)}px,${(H*.2*through).toFixed(2)}px,0) scale(${(1.05+.7*approach+.18*through).toFixed(3)})`;
 vars.fogBack.style.opacity=String(.35*(1-smooth(.60,.84,p)));
 // Substantial actual 3D parallax: SECOND CITY behind the split chassis.
 const cityScale=lerp(.23,1.20,smooth(.38,.71,p))*lerp(1,2.6,smooth(.72,.95,p));
 const cityX=lerp(W*.46,0,smooth(.38,.68,p))+lerp(0,-W*.55,smooth(.78,.98,p));
 const cityY=lerp(-H*.27,H*.10,smooth(.4,.70,p))-H*.2*arrival;
 moveImage(vars.city,cityX,cityY,cityScale,lerp(-15,4,approach));
 vars.city.style.opacity=String(band(.35,.53,.76,.98,p));
 vars.cityFlight.style.transform=`translate3d(${(-W*.16*rupture).toFixed(2)}px,${(H*.22*rupture).toFixed(2)}px,120px) scale(${(1+.6*rupture).toFixed(3)})`;
 // A physical aperture in the fog, fully clipping the new illustrated region.
 const portalRadius=lerp(0,69,smooth(.47,.80,p));
 renderArtcraftEffect(p);
 vars.window.style.clipPath=`circle(${portalRadius.toFixed(3)}% at 50% 50%)`;
 vars.window.style.opacity=String(smooth(.43,.66,p));
 const portalMove=smooth(.69,.95,p);
 moveImage(vars.window,0,H*.07*portalMove,lerp(.72,2.15,portalMove));
 vars.portalWorld.style.opacity=String(1-smooth(.78,.95,p));
 vars.portalWorld.style.transform=`translate3d(${(-W*.25*arrival).toFixed(2)}px,${(-H*.18*arrival).toFixed(2)}px,0) scale(${lerp(.88,1.35,arrival).toFixed(3)})`;
 vars.innerHub.style.opacity=String(band(.74,.86,.89,.98,p));
 vars.innerHub.style.transform=`translate3d(0,${(-H*.11*arrival).toFixed(2)}px,0) scale(${lerp(.6,1.16,arrival).toFixed(3)})`;
 vars.ring.style.opacity=String(band(.42,.60,.78,.96,p));
 vars.ring.style.transform=`translate(-50%,-50%) scale(${lerp(.24,2.75,smooth(.46,.89,p)).toFixed(3)}) rotate(${(rupture*28).toFixed(2)}deg)`;
 for(const node of [vars.rim,vars.halo,vars.tear])setStroke(node,ringLen,smooth(.49,.69,p));
 // After flying through the portal, a new independent hub in depth.
 moveImage(vars.hub,0,H*.04*arrival,lerp(.19,.77,arrival),lerp(8,0,arrival));
 vars.hub.style.opacity=String(smooth(.77,.93,p));
 vars.debrisA.style.opacity=String(band(.43,.63,.84,.95,p)*.9);
 vars.debrisB.style.opacity=String(band(.47,.66,.83,.95,p)*.9);
 vars.debrisA.style.transform=`translate3d(${(-W*.7*rupture).toFixed(2)}px,${(-H*.4*rupture).toFixed(2)}px,${260*rupture}px) rotate(${(-23-60*rupture).toFixed(2)}deg)`;
 vars.debrisB.style.transform=`translate3d(${(W*.75*rupture).toFixed(2)}px,${(H*.32*rupture).toFixed(2)}px,${220*rupture}px) rotate(${(19+85*rupture).toFixed(2)}deg)`;
 vars.vortex.style.opacity=String(band(.20,.41,.6,.8,p));
 vars.vortex.style.transform=`translate(-50%,-50%) scale(${lerp(.3,3.8,smooth(.22,.76,p)).toFixed(3)})`;
 vars.planet.style.transform=`translate3d(${(-W*.18*through).toFixed(2)}px,${(H*.10*through).toFixed(2)}px,0) scale(${(1+through*.35).toFixed(3)})`;
 // One immutable scroll progress determines every visible pose; reverse is exact.
 const phase=p<.16?0:p<.36?1:p<.58?2:p<.80?3:4;
 if(phase!==lastPhase){vars.num.textContent=chapters[phase][0];vars.title.textContent=chapters[phase][1];vars.copy.textContent=chapters[phase][2];lastPhase=phase;}
 vars.narrative.style.opacity=String(clamp(1-(band(.26,.4,.63,.78,p)*.78)));
 vars.progress.style.width=(p*100).toFixed(2)+'%';vars.progressText.textContent=String(Math.round(p*100)).padStart(2,'0')+'%';
 Object.assign(state,{progress:p,phase,activePads,activeKnobs,activeSpeakers,
  traceDrawn:lineValue,worldWaveDrawn:signalValue,portalRadiusPct:portalRadius,
  mechanicalSplitPx:split,cameraTravelPx:Math.hypot(camX,camY),machineScale:scale,
  fogSeparationPx:2*fogPush,cityOpacity:parseFloat(vars.city.style.opacity),hubOpacity:parseFloat(vars.hub.style.opacity),
  changedRegion:rupture>.45,secondIllustratedRegionVisible:arrival>.4});
 for(const [index,button] of chapterLinks.entries()){
  if(index===phase)button.setAttribute('aria-current','step');
  else button.removeAttribute('aria-current');
 }
 vars.stage.dataset.phase=String(phase);vars.stage.dataset.reversed=p<.001?'start':'travel';
}
function progressFromScroll(){
 const rect=vars.section.getBoundingClientRect();const total=Math.max(1,vars.section.offsetHeight-innerHeight);
 return clamp((-rect.top)/total);
}
function tick(){const p=progressFromScroll();if(!Number.isFinite(lastProgress)||Math.abs(p-lastProgress)>.00007){updatePose(p);lastProgress=p;}}
let scheduled=false;
function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame((ts)=>{scheduled=false;observeFrameBudget(ts);tick()})}}
async function start(){
 try{
  if(window.__assetManifest){manifest=window.__assetManifest;} else {
   const response=await fetch('asset-manifest.json',{cache:'no-store'});
   if(!response.ok)throw new Error('ASSET_MANIFEST_NOT_FOUND');
   manifest=await response.json();
  }
  if(manifest.schema!=='HazewaveTraversalV4ArtSource/v1'||manifest.productionApproved!==false||manifest.ownerOriginalsInGithub!==false||manifest.v3aPieces.length!==24)throw Error('SOURCE_OR_AUTHORITY_INVALID');
  const counts={pad:0,knob:0,speaker:0};
  for(const entry of manifest.v3aPieces){if(!(entry.type in counts))throw Error('UNKNOWN_RIG_PART');counts[entry.type]++;pieces.push(mount(entry));}
  if(counts.pad!==12||counts.knob!==8||counts.speaker!==4)throw Error('V3A_COUNTS_MISMATCH');
  traceLen=vars.trace.getTotalLength();worldLen=vars.worldPath.getTotalLength();ringLen=vars.rim.getTotalLength();
  makeStars();state.mountedPieces=pieces.length;state.sourceV3A=manifest.v3aSourceActionsSha;
  // Require every src image to decode, not merely DOM presence.
  const imgs=[...doc.querySelectorAll('img')];
  await Promise.all(imgs.map(img=>img.decode()));
  setupChapterNavigation();
  state.ready=true;updatePose(progressFromScroll());lastProgress=state.progress;
  void prepareArtcraftEffect();
  addEventListener('scroll',schedule,{passive:true});
  addEventListener('resize',()=>{makeStars();schedule()},{passive:true});
 }catch(error){console.error('HAZEWAVE_V4_FAIL_CLOSED',error);state.error=String(error);state.ready=false;}
}
start();
})();
