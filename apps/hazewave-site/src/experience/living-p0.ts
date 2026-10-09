/**
 * WAVE-only P0: a genuinely interactive, multi-plane 2D cartoon animation.
 * Temporal ambient motion and deterministic scroll pose are intentionally distinct.
 * This is an isolated exploratory proof, not the approved production asset pack.
 */
import { Application, Container, Graphics } from "pixi.js";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const W=1100, H=1680;
const clamp=(n:number)=>Math.min(1,Math.max(0,n));
const mix=(a:number,b:number,t:number)=>a+(b-a)*clamp(t);
const smooth=(a:number,b:number,v:number)=>{const t=clamp((v-a)/(b-a));return t*t*(3-2*t);};
type WorldController={stop:()=>void};

function createRng(seed:number){
  return ()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
}
function blob(color:number,alpha:number,x:number,y:number,rx:number,ry:number):Graphics{
  return new Graphics()
    .ellipse(0,0,rx,ry).fill({color,alpha})
    .ellipse(-rx*.11,-ry*.2,rx*.68,ry*.54).stroke({color:0x9f85ed,alpha:alpha*.32,width:3});
}
function createMpc(container:Container,x:number,y:number,scale:number,rotation:number,variant:number) {
  const group=new Container();
  group.position.set(x,y);
  group.scale.set(scale);
  group.rotation=rotation;
  container.addChild(group);
  // A sampler-shaped floating musical machine, with real independently animated pads.
  const chassis=new Graphics();
  chassis.poly([-204,-90,150,-104,246,84,-151,117])
    .fill({color:0x070b18})
    .stroke({color:0x91a2e8,alpha:.85,width:5})
    .poly([-151,117,246,84,228,138,-161,161])
    .fill({color:0x050716}).stroke({color:0x283954,width:4})
    .poly([-183,-78,138,-88,212,77,-144,99])
    .fill({color:0x172033}).stroke({color:0x354766,width:4})
    .poly([-183,-78,138,-88,133,-65,-173,-54])
    .fill({color:0x40506c,alpha:.7})
    .roundRect(-117,-62,142,52,7)
    .fill({color:0x070e1e}).stroke({color:0x56799a,width:3})
    .rect(-99,-48,104,23).fill({color:0x2a678b,alpha:.75});
  for(let i=0;i<5;i++){
    chassis.moveTo(-97,-43+i*4).lineTo(-2,-43+i*4).stroke({color:0xaad8ff,alpha:.12,width:1});
  }
  // Mix panel, encoders, fader travel and decorated volume bars.
  for(let i=0;i<4;i++){
    const cy=-32+i*24;
    chassis.roundRect(103,cy,61,7,2).fill({color:0x080b17})
      .roundRect(104+i*4,cy-1,12,9,2).fill({color:0xe78d42});
  }
  for(let i=0;i<5;i++){
    const xx=21+i*30;
    chassis.circle(xx,-69,9).fill({color:0x050713})
      .circle(xx,-69,5).fill({color:0x344d6f})
      .circle(xx-2,-72,2).fill({color:0xe89b49,alpha:.9});
  }
  group.addChild(chassis);
  const pads:Graphics[]=[];
  for(let row=0;row<4;row++)for(let col=0;col<4;col++){
    const px=-111+col*48+row*11, py=6+row*24;
    const pad=new Graphics().roundRect(0,0,39,20,3)
      .fill({color:0x9c4527}).stroke({color:0xefa461,width:2});
    pad.position.set(px,py);
    group.addChild(pad);pads.push(pad);
  }
  const leds=new Graphics();
  for(let i=0;i<8;i++){
    leds.rect(-168+i*19,80,11,4).fill({color:i%2?0x6151cf:0xea8248,alpha:.9});
  }
  group.addChild(leds);
  const cables=new Graphics();
  cables.moveTo(-145,130).bezierCurveTo(-180,230,-55,196,20,246)
    .stroke({color:0x1c2748,width:13})
    .moveTo(-145,130).bezierCurveTo(-180,230,-55,196,20,246)
    .stroke({color:0x6866b6,width:2,alpha:.75})
    .moveTo(150,123).bezierCurveTo(270,161,190,225,272,300)
    .stroke({color:0x1b2139,width:12});
  group.addChild(cables);
  return { group,pads,variant,baseY:y };
}
function makeStarfield(parent:Container,seed:number,count:number,minY:number,maxY:number,alpha:number){
  const rng=createRng(seed);
  const field=new Container();
  const g=new Graphics();
  for(let i=0;i<count;i++){
    const x=rng()*W, y=minY+rng()*(maxY-minY), radius=rng()>.94?2.1:.5+rng();
    g.circle(x,y,radius).fill({color:rng()>.75?0xa2aafa:0xe6e5ff,alpha:(.18+rng()*.72)*alpha});
  }
  field.addChild(g); parent.addChild(field);return field;
}
function createNebula(container:Container,x:number,y:number,color:number,seed:number,scale=1){
  const g=new Container(),rng=createRng(seed);
  g.position.set(x,y);g.scale.set(scale);
  const clouds=new Graphics();
  for(let i=0;i<18;i++){
    const ang=(i/18)*Math.PI*2;
    const radius=100+rng()*185;
    const cx=Math.cos(ang)*radius,cy=Math.sin(ang)*radius*.75;
    clouds.ellipse(cx,cy,95+rng()*90,45+rng()*95).fill({color,alpha:.045+rng()*.045});
  }
  clouds.ellipse(0,0,120,80).stroke({color:0x908aff,alpha:.19,width:18});
  g.addChild(clouds);container.addChild(g);return g;
}

export async function mountLivingP0():Promise<WorldController|undefined>{
  const host=document.getElementById("living-p0-canvas"),section=document.getElementById("living-p0-scroll");
  const stage=document.getElementById("living-p0-stage");
  const artistLogo=document.getElementById("living-p0-artist-logo") as HTMLElement|null;
  if(!host||!section||!stage||!artistLogo)return;
  const reduced=matchMedia("(prefers-reduced-motion: reduce)");
  const app=new Application();
  const global=window as Window & {__hazewaveLivingP0?:WorldController;__hazewaveP0State?:{progress:number;phase:string;activePads:number;ambientSeconds:number;ready:boolean}};
  global.__hazewaveLivingP0?.stop();

  try {
    await app.init({resizeTo:host,backgroundAlpha:0,antialias:true,
      autoDensity:true, resolution:Math.min(devicePixelRatio||1,1.5),preference:"webgl"});
  }catch(e){
    host.dataset.state="fallback";
    document.body.dataset.p0Status="fallback";
    console.error("P0 renderer fallback",e);
    return;
  }
  host.appendChild(app.canvas);
  host.dataset.state="running";
  document.body.dataset.p0Status="running";
  const far=new Container(),middle=new Container(),foreground=new Container(),fx=new Container(),world=new Container();
  world.addChild(far,middle,foreground,fx);
  app.stage.addChild(world);
  const stars=makeStarfield(far,3211,165,-200,H+400,.96);
  const deepStars=makeStarfield(middle,995,55,-200,H+400,.48);
  const nebulaA=createNebula(far,550,240,0x603e9b,19,1.3);
  const nebulaB=createNebula(middle,330,820,0x413d93,43,1.5);
  const nebulaC=createNebula(foreground,720,1220,0x433785,72,1.2);
  const vortex=new Container();
  vortex.position.set(550,280);
  const coil=new Graphics();
  for(let i=0;i<9;i++){
    coil.ellipse(0,0,90+i*20,27+i*9)
      .stroke({color:i%3===0?0xd6bdff:0x755cd6,width:i%3===0?3:5,alpha:.9-i*.07});
  }
  vortex.addChild(coil);
  far.addChild(vortex);
  const mpcA=createMpc(middle,330,610,.62,-.12,0);
  const mpcB=createMpc(middle,880,840,.83,.17,1);
  const mpcC=createMpc(foreground,210,1250,1.25,-.17,2);
  const hub=createMpc(middle,550,1550,1.4,0,3);
  const energy=new Graphics();
  energy.moveTo(550,285).bezierCurveTo(870,460,230,620,560,820)
    .bezierCurveTo(1020,1090,110,1250,540,1540)
    .stroke({color:0x5544dd,alpha:.29,width:40})
    .moveTo(550,285).bezierCurveTo(870,460,230,620,560,820)
    .bezierCurveTo(1020,1090,110,1250,540,1540)
    .stroke({color:0xcbb2ff,width:8,alpha:1});
  const energyMask=new Graphics().rect(0,0,W,1).fill(0xffffff);
  fx.addChild(energy,energyMask);
  energy.mask=energyMask;
  const pulses=Array.from({length:15},(_,i)=>{
    const g=new Graphics().circle(0,0,4+i%3).fill({color:0xd7c2ff,alpha:.8});
    fx.addChild(g);return g;
  });
  const objects=[mpcA,mpcB,mpcC,hub];
  gsap.registerPlugin(ScrollTrigger);
  const state={progress:0};
  let ambientSeconds=0,destroyed=false,lastProgress=-1;
  const live:typeof global.__hazewaveP0State={progress:0,phase:"sleep",activePads:0,ambientSeconds:0,ready:true};
  global.__hazewaveP0State=live;

  const adjustFrame=()=>{
    if(destroyed)return;
    const p=clamp(state.progress);
    const ambient=reduced.matches?0:ambientSeconds;
    const zoom=mix(.9,1.38,smooth(0,1,p));
    const centerY=mix(530,1460,smooth(0,1,p));
    const baseline=Math.max(app.screen.width/W,app.screen.height/1050);
    const ss=baseline*zoom;
    world.scale.set(ss);
    world.position.set(app.screen.width*.5-(550+Math.sin(p*Math.PI)*90)*ss,
      app.screen.height*.47-centerY*ss);
    const activation=(threshold:number)=>smooth(threshold-.045,threshold+.08,p);
    stars.alpha=.73+Math.sin(ambient*.45)*.08;
    deepStars.position.y=reduced.matches?0:Math.sin(ambient*.14)*7;
    vortex.rotation=(reduced.matches?0:ambient*.016)+p*.8;
    vortex.scale.set(1+(reduced.matches?0:Math.sin(ambient*.6)*.035)+p*.2);
    nebulaA.position.x=550+p*80+(reduced.matches?0:Math.sin(ambient*.16)*10);
    nebulaB.position.x=330-p*110+(reduced.matches?0:Math.sin(ambient*.22)*16);
    nebulaC.position.x=720+p*220+(reduced.matches?0:Math.cos(ambient*.13)*22);
    nebulaC.alpha=1-smooth(.32,.54,p)*.8;
    objects.forEach((o,i)=>{
      o.group.position.y=o.baseY+(reduced.matches?0:Math.sin(ambient*(.29+i*.08)+i)*5);
      o.group.alpha=(i===3?activation(.55):.5+activation(.13+i*.13)*.5);
      o.pads.forEach((pad,j)=>{
        const on=activation((i===3?.6:.17+i*.11)+j*.007);
        pad.tint=on>.5?0xffc36a:0x7c486e;
        pad.alpha=.47+on*.53+(reduced.matches?0:Math.sin(ambient*2+j)*.035);
      });
    });
    if(Math.abs(p-lastProgress)>.0001){
      const reached=300+smooth(.1,.92,p)*1390;
      energyMask.clear().rect(0,0,W,reached).fill(0xffffff);
      lastProgress=p;
    }
    energy.alpha=.24+smooth(.08,.4,p)*.7+(reduced.matches?0:Math.sin(ambient*2)*.045);
    pulses.forEach((g,i)=>{
      const s=((ambient*.045+i/pulses.length)%1);
      g.position.set(550+Math.sin(s*8*Math.PI)*Math.sin(s*Math.PI)*180,
        320+s*1220);
      g.alpha=(s<p*.91?1:0)*(reduced.matches?.45:.4+Math.sin(ambient*3+i)*.25);
    });
    const show=smooth(.68,.91,p);
    artistLogo.style.opacity=show.toFixed(3);
    artistLogo.style.transform="translate(-50%,-50%) scale("+(1.5-show*.5).toFixed(3)+")";
    artistLogo.setAttribute("aria-hidden",String(show<.2));
    document.body.dataset.p0Phase=p<.17?"sleep":p<.35?"signal":p<.62?"traverse":p<.85?"hub":"awake";
    live.progress=p;
    live.phase=document.body.dataset.p0Phase;
    live.ambientSeconds=ambient;
    live.activePads=objects.flatMap(o=>o.pads).filter(pad=>pad.tint===0xffc36a).length;
    const progress=document.getElementById("living-p0-progress");
    if(progress)progress.style.width=(p*100).toFixed(2)+"%";
  };
  app.ticker.maxFPS=matchMedia("(max-width: 700px)").matches?30:60;
  app.ticker.add((ticker)=>{
    if(document.hidden||destroyed)return;
    ambientSeconds+=Math.min(.05,ticker.deltaMS/1000);
    adjustFrame();
  });
  const timeline=gsap.timeline({paused:true});
  timeline.to(state,{progress:1,duration:1,ease:"none",onUpdate:adjustFrame});
  const trigger=ScrollTrigger.create({
    trigger:section,start:"top top",end:"bottom bottom",
    pin:stage,pinSpacing:false,scrub:true,animation:timeline,
    invalidateOnRefresh:true,
  });
  const observer=new ResizeObserver(()=>{adjustFrame();ScrollTrigger.refresh();});
  observer.observe(host);
  const stop=()=>{
    if(destroyed)return;
    destroyed=true;observer.disconnect();trigger.kill();timeline.kill();app.destroy(true,{children:true});
    global.__hazewaveP0State=undefined;
  };
  global.__hazewaveLivingP0={stop};
  window.addEventListener("pagehide",stop,{once:true});
  adjustFrame();
  return {stop};
}
