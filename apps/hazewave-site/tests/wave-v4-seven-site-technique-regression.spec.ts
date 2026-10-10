import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

// This CI fixture is deliberately SYNTHETIC: it tests the ORIGINAL runtime
// and interaction logic, NOT the authenticity of owner-private painted media.
const ROOT=resolve(fileURLToPath(new URL("../experiments/travessia-v4/", import.meta.url)));
const DOC=readFileSync(resolve(ROOT,"index.html"),"utf8");
const CSS=readFileSync(resolve(ROOT,"travessia.css"),"utf8");
const RUNTIME=readFileSync(resolve(ROOT,"travessia.js"),"utf8");
const PIXEL="data:image/svg+xml,"+encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"><rect width="4" height="4" fill="#7b3aae"/></svg>'
);
const piece=(type:"pad"|"knob"|"speaker",number:number) => ({
  id:type+"_"+String(number).padStart(2,"0"),type,
  file:type+"_"+String(number).padStart(2,"0")+".webp",
  energizedFile:type+"_"+String(number).padStart(2,"0")+"_on.webp",
  x:200+number*(type==='pad'?95:40),y:150+number*45,width:40,height:40,
  activation:0.2+number*0.035
});
const PIECES=[
  ...Array.from({length:12},(_,i)=>piece("pad",i)),
  ...Array.from({length:8},(_,i)=>piece("knob",i)),
  ...Array.from({length:4},(_,i)=>piece("speaker",i))
];
const manifest={
  schema:"HazewaveTraversalV4ArtSource/v1",
  ownerOriginalsInGithub:false,
  productionApproved:false,
  v3aSourceActionsSha:"SYNTHETIC_CI_MOCK_NOT_AN_OWNER_SOURCE",
  v3aPieces:PIECES,
  // Test-only fake hash structure; these are NEVER owner media.
  assetSha256:Object.fromEntries(["station.webp","controller.webp","city.webp","hub.webp","fog.webp"].map((name,i)=>[name,String(i+1).repeat(64)]))
};
type Pose={phase:number;progress:number;activePads:number;activeKnobs:number;
  activeSpeakers:number;portalRadiusPct:number;hubOpacity:number;
  secondIllustratedRegionVisible:boolean;visualQualityTier:string};
const pose=async (page:Page) => page.evaluate(()=>(
  (window as unknown as {__HAZEWAVE_TRAVERSAL_V4:Pose}).__HAZEWAVE_TRAVERSAL_V4
));
async function fixture(page:Page, syntheticFx=false) {
  const html=DOC.replace('<link rel="stylesheet" href="travessia.css">',
    "<style>"+CSS+"</style>")
    .replace(/src="assets\/[^"]+"/g, 'src="'+PIXEL+'"')
    .replace('<script src="travessia.js" defer></script>',"");
  await page.route("**/*",route=>route.abort("blockedbyclient"));
  await page.setContent(html,{waitUntil:"load"});
  const urls:Record<string,string>={};
  for(const part of PIECES) {
    urls[part.file]=PIXEL;
    if(part.type==="pad")urls[part.energizedFile]=PIXEL;
  }
  await page.evaluate((values)=>{
    Object.assign(window,{__assetManifest:values.manifest,__assetUrls:values.urls});
    if(values.syntheticFx){
      // TEST DOUBLE ONLY: never represent this generated raster as EffectCraft output.
      const c=document.createElement("canvas");c.width=420;c.height=820;
      const ctx=c.getContext("2d");if(!ctx)throw Error("CANVAS_UNAVAILABLE");
      const frames=[];
      for(let i=0;i<8;i++){
        ctx.clearRect(0,0,420,820);
        ctx.strokeStyle="rgba(240,120,255,.85)";ctx.lineWidth=8;
        ctx.beginPath();ctx.ellipse(210,410,35+i*16,55+i*22,0,0,Math.PI*2);ctx.stroke();
        frames.push({url:c.toDataURL("image/png")});
      }
      Object.assign(window,{__hazewaveEffectArt:{
        schema:"HazewaveRealArtcraftPortalOverlay/v1",
        real_effectcraft_render:true,filmcraft_probe_executed:true,
        production_approved:false,frames
      }});
    }
  },{manifest,urls,syntheticFx});
  await page.addScriptTag({content:RUNTIME});
  await expect.poll(async()=>page.evaluate(()=>Boolean(
    (window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{ready:boolean}}).__HAZEWAVE_TRAVERSAL_V4?.ready
  )),{timeout:25000}).toBe(true);
}

async function ensureLiteMode(page:Page,desired:boolean){
  const actual=(await page.locator("#stage").getAttribute("data-quality"))==="lite";
  if(actual!==desired)await page.locator("#lightweight-mode").click();
  await expect(page.locator("#stage")).toHaveAttribute("data-quality",desired?"lite":"full");
}
async function scrollToExactProgress(page:Page,p:number){
  await page.evaluate((position)=>{
    const journey=document.getElementById("journey")!;
    const available=Math.max(1,journey.offsetHeight-innerHeight);
    window.scrollTo({top:available*position,behavior:"instant"});
  },p);
  await expect.poll(async()=>(await pose(page)).progress,{timeout:12000}).toBeGreaterThanOrEqual(p-.004);
  await expect.poll(async()=>(await pose(page)).progress,{timeout:12000}).toBeLessThanOrEqual(p+.004);
}

test("NASA-derived navigation reverses all five acts in ACTUAL WAVE source, synthetic images only",async ({page},info)=>{
  const errors:string[]=[];
  page.on("pageerror",err=>errors.push(err.message));
  await fixture(page);
  const sequence=[0,1,2,3,4,2,0];
  for(const index of sequence){
    await page.locator('[data-world-stop="'+index+'"]').click();
    await expect.poll(async()=>(await pose(page)).phase,{timeout:10000}).toBe(index);
    await expect(page.locator('[data-world-stop="'+index+'"]')).toHaveAttribute("aria-current","step");
    expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
  }
  const reset=await pose(page);
  expect(reset.progress).toBeLessThan(.006);
  expect(reset.portalRadiusPct).toBe(0);
  expect(reset.activePads).toBe(0);
  expect(errors).toEqual([]);
  expect(await page.locator("img[data-part-id]").count()).toBe(24);
  expect(await page.locator("img[data-pad-id]").count()).toBe(12);
  await page.screenshot({path:info.outputPath("v5-synthetic-chapter-controls-"+info.project.name+".png"),animations:"disabled"});
});

test("V4 mechanical camera and portal remain independent of optional effects budget",async ({page})=>{
  await fixture(page);
  await page.locator('[data-world-stop="4"]').click();
  await expect.poll(async()=>(await pose(page)).phase).toBe(4);
  const full=await pose(page);
  expect(full.activePads).toBe(12);
  expect(full.activeKnobs).toBe(8);
  expect(full.activeSpeakers).toBe(4);
  expect(full.portalRadiusPct).toBeGreaterThan(68);
  expect(full.secondIllustratedRegionVisible).toBe(true);
  await ensureLiteMode(page,true);
  await expect(page.locator("#lightweight-mode")).toHaveAttribute("aria-pressed","true");
  const lite=await pose(page);
  expect(lite.portalRadiusPct).toBe(full.portalRadiusPct);
  expect(lite.activePads).toBe(full.activePads);
  expect(lite.hubOpacity).toBe(full.hubOpacity);
  await page.locator('[data-world-stop="0"]').click();
  await expect.poll(async()=>(await pose(page)).phase).toBe(0);
  expect((await pose(page)).portalRadiusPct).toBe(0);
});

test("original V4 reference extension honors reduced motion and keyboard access",async ({page})=>{
  await page.emulateMedia({reducedMotion:"reduce"});
  await fixture(page);
  await page.locator('[data-world-stop="3"]').focus();
  await page.keyboard.press("Enter");
  await expect.poll(async()=>(await pose(page)).phase).toBe(3);
  expect((await pose(page)).portalRadiusPct).toBeGreaterThan(40);
  await page.locator('[data-world-stop="0"]').focus();
  await page.keyboard.press("Space");
  await expect.poll(async()=>(await pose(page)).phase).toBe(0);
  expect((await pose(page)).progress).toBeLessThan(.006);
});

test("V7 optional EFFECT LAYER scrubs forward and backward without replacing owner scene — TEST-DOUBLE RASTERS",async ({page})=>{
  await fixture(page,true);
  await expect.poll(async()=>page.evaluate(()=>
    (window as unknown as {__HAZEWAVE_ARTCRAFT_V7:{getReadiness:()=>string}}).__HAZEWAVE_ARTCRAFT_V7.getReadiness()
  )).toBe("READY");
  await page.locator('[data-world-stop="3"]').click();
  await expect.poll(async()=>(await pose(page)).phase).toBe(3);
  await ensureLiteMode(page,false);
  await expect.poll(async()=>page.evaluate(()=>
    (window as unknown as {__HAZEWAVE_ARTCRAFT_V7:{getFrame:()=>number}}).__HAZEWAVE_ARTCRAFT_V7.getFrame()
  )).toBeGreaterThan(0);
  const opacity=Number(await page.locator("#effectcraft-aperture").evaluate((x)=>(x as HTMLElement).style.opacity));
  expect(opacity).toBeGreaterThan(0);
  const portal=await pose(page);
  expect(portal.portalRadiusPct).toBeGreaterThan(0);
  await ensureLiteMode(page,true);
  await expect.poll(async()=>page.evaluate(()=>
    (window as unknown as {__HAZEWAVE_ARTCRAFT_V7:{getFrame:()=>number}}).__HAZEWAVE_ARTCRAFT_V7.getFrame()
  )).toBe(-1);
  expect((await pose(page)).portalRadiusPct).toBe(portal.portalRadiusPct);
  await ensureLiteMode(page,false);
  await page.locator('[data-world-stop="0"]').click();
  await expect.poll(async()=>(await pose(page)).phase).toBe(0);
  expect((await pose(page)).portalRadiusPct).toBe(0);
  expect(Number(await page.locator("#effectcraft-aperture").evaluate((x)=>(x as HTMLElement).style.opacity))).toBe(0);
});

test("V7 missing optional FX never breaks the original 24-piece interactive site",async ({page})=>{
  await fixture(page);
  await expect.poll(async()=>page.evaluate(()=>
    (window as unknown as {__HAZEWAVE_ARTCRAFT_V7:{getReadiness:()=>string}}).__HAZEWAVE_ARTCRAFT_V7.getReadiness()
  )).toBe("NOT_ATTACHED");
  await page.locator('[data-world-stop="4"]').click();
  await expect.poll(async()=>(await pose(page)).phase).toBe(4);
  expect((await pose(page)).activePads).toBe(12);
  expect((await pose(page)).portalRadiusPct).toBeGreaterThan(68);
});

test("V7 real portal engine interpolates two frames INSIDE same pair — SYNTHETIC test-only PNGs",async ({page})=>{
  const errors:string[]=[];
  page.on("pageerror",err=>errors.push(err.message));
  await fixture(page,true);
  await expect.poll(async()=>page.evaluate(()=>
    (window as unknown as {__HAZEWAVE_ARTCRAFT_V7:{getReadiness:()=>string}}).__HAZEWAVE_ARTCRAFT_V7.getReadiness()
  )).toBe("READY");
  const samples:{frame:number;blend:number;image:string}[]=[];
  for(const position of [0.64,0.65,0.66]){
    await scrollToExactProgress(page,position);
    await ensureLiteMode(page,false);
    samples.push(await page.evaluate(()=>({
      frame:(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{effectcraftFrame:number}}).__HAZEWAVE_TRAVERSAL_V4.effectcraftFrame,
      blend:(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{effectcraftBlend:number}}).__HAZEWAVE_TRAVERSAL_V4.effectcraftBlend,
      image:(document.getElementById("effectcraft-aperture") as HTMLCanvasElement).toDataURL("image/png")
    })));
  }
  expect(samples.map(x=>x.frame)).toEqual([4,4,4]);
  expect(samples[0].blend).toBeLessThan(samples[1].blend);
  expect(samples[1].blend).toBeLessThan(samples[2].blend);
  expect(new Set(samples.map(x=>x.image)).size).toBe(3);
  expect(errors).toEqual([]);
  // In auto-lite mode the owner still regains FULL graphics on request.
  await ensureLiteMode(page,true);
  await expect.poll(async()=>page.evaluate(()=>(
    (window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{effectcraftFrame:number}}).__HAZEWAVE_TRAVERSAL_V4.effectcraftFrame
  ))).toBe(-1);
  await ensureLiteMode(page,false);
  expect(await page.evaluate(()=>(
    (window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{qualityUserOverride:string}}).__HAZEWAVE_TRAVERSAL_V4.qualityUserOverride
  ))).toBe("FULL");
});

test("V7 focal portal composition stays inside phone viewport and releases idle GPU layer — SYNTHETIC ONLY",async ({page})=>{
  await fixture(page,true);
  await expect.poll(async()=>page.evaluate(()=>
    (window as unknown as {__HAZEWAVE_ARTCRAFT_V7:{getReadiness:()=>string}}).__HAZEWAVE_ARTCRAFT_V7.getReadiness()
  )).toBe("READY");
  await scrollToExactProgress(page,.70);
  await ensureLiteMode(page,false);
  const sample=await page.evaluate(()=>{
    const stage=document.getElementById("stage") as HTMLElement;
    const fx=document.getElementById("effectcraft-aperture") as HTMLElement;
    const r=fx.getBoundingClientRect();
    return {stageActive:stage.dataset.fxActive,width:r.width,viewport:innerWidth,
      opacity:Number(fx.style.opacity),quality:stage.dataset.quality};
  });
  expect(sample.stageActive).toBe("true");
  expect(sample.width).toBeLessThan(sample.viewport*.70);
  expect(sample.opacity).toBeGreaterThan(0);
  expect(sample.opacity).toBeLessThanOrEqual(.61);
  await ensureLiteMode(page,true);
  await expect(page.locator("#stage")).toHaveAttribute("data-fx-active","false");
  await page.locator('[data-world-stop="0"]').click();
  await expect.poll(async()=>(await pose(page)).phase).toBe(0);
  await expect(page.locator("#stage")).toHaveAttribute("data-fx-active","false");
});

test("V9 optical portal hands off early to hub without double signage — synthetic media",async ({page},info)=>{
  await fixture(page,true);
  const portal=page.locator("#portal-window");
  await scrollToExactProgress(page,.82);
  const reveal=Number(await portal.evaluate((node)=>(node as HTMLElement).style.opacity));
  expect(reveal).toBeGreaterThan(.5);
  expect(reveal).toBeLessThan(.85);
  await scrollToExactProgress(page,.92);
  const destination=Number(await portal.evaluate((node)=>(node as HTMLElement).style.opacity));
  const hub=Number(await page.locator("#hub-scene").evaluate((node)=>(node as HTMLElement).style.opacity));
  expect(destination).toBeLessThan(.025);
  expect(hub).toBeGreaterThan(.95);
  expect((await pose(page)).secondIllustratedRegionVisible).toBe(true);
  await page.screenshot({path:info.outputPath("v7-hub-handoff-"+info.project.name+".png"),animations:"disabled"});
  await scrollToExactProgress(page,.82);
  const restore=Number(await portal.evaluate((node)=>(node as HTMLElement).style.opacity));
  expect(restore).toBeCloseTo(reveal,3);
  await scrollToExactProgress(page,0);
  expect((await pose(page)).portalRadiusPct).toBe(0);
});


test("V7 cinematic mobile framing prevents pad-only overzoom and ghost-logo handoff — SYNTHETIC MEDIA",async ({page})=>{
  const errors:string[]=[];
  page.on("pageerror",error=>errors.push(error.message));
  await fixture(page,true);
  await scrollToExactProgress(page,.40);
  await ensureLiteMode(page,false);
  const midpoint=await page.evaluate(()=>{
    const state=(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{machineScale:number}}).__HAZEWAVE_TRAVERSAL_V4;
    return state.machineScale*1448/innerWidth;
  });
  expect(midpoint).toBeLessThan(2);
  await scrollToExactProgress(page,.69);
  const opening=await page.evaluate(()=>({
    deviceOpacity:Number((document.getElementById("machine") as HTMLElement).style.opacity),
    fxOpacity:(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{effectcraftOpacity:number}}).__HAZEWAVE_TRAVERSAL_V4.effectcraftOpacity,
  }));
  expect(opening.deviceOpacity).toBeLessThan(.45);
  expect(opening.fxOpacity).toBeGreaterThan(.4);
  await scrollToExactProgress(page,.86);
  const ghostOpacity=Number(await page.locator("#portal-inner-hub").evaluate(el=>(el as HTMLElement).style.opacity));
  expect(ghostOpacity).toBeLessThan(.35);
  await scrollToExactProgress(page,.92);
  expect((await pose(page)).hubOpacity).toBeGreaterThan(.95);
  await scrollToExactProgress(page,.40);
  const reverse=await page.evaluate(()=>
    (window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{machineScale:number}}).__HAZEWAVE_TRAVERSAL_V4.machineScale*1448/innerWidth);
  expect(reverse).toBeCloseTo(midpoint,3);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});


test("V9 rig halves remain aligned while rift softens to optical alpha mask — SYNTHETIC IMAGES",async ({page})=>{
 const errors:string[]=[];
 page.on("pageerror",e=>errors.push(e.message));
 await fixture(page,true);
 const x=(value:string)=>{
   const m=value.match(/translate3d\((-?[0-9.]+)px/);
   if(!m)throw Error("MISSING_TRANSLATION:"+value);
   return Number(m[1]);
 };
 await scrollToExactProgress(page,.68);
 await ensureLiteMode(page,false);
 const opened=await page.evaluate(()=>{
   const style=(selector:string)=>(document.querySelector(selector) as HTMLElement).style;
   return {
     chassisLeft:style("#chassis-left").transform,chassisRight:style("#chassis-right").transform,
     padLeft:style('img[data-part-id="pad_00"]').transform,
     padRight:style('img[data-part-id="pad_11"]').transform,
     mask:style("#portal-window").maskImage,clip:style("#portal-window").clipPath,
     wallLeft:style("#portal-wall-left").transform,wallRight:style("#portal-wall-right").transform,
     opacity:Number(style("#portal-wall-left").opacity)
   };
 });
 expect(Math.abs(x(opened.padLeft)-x(opened.chassisLeft))).toBeLessThan(12);
 expect(Math.abs(x(opened.padRight)-x(opened.chassisRight))).toBeLessThan(12);
 expect(opened.mask).toMatch(/^radial-gradient\(/);
 expect(opened.clip).toBe("none");
 expect(opened.wallLeft).toContain("rotateY(");
 expect(opened.wallRight).toContain("rotateY(");
 expect(opened.opacity).toBeGreaterThan(.08);
 expect(opened.opacity).toBeLessThan(.25);
 await scrollToExactProgress(page,0);
 const reset=await page.evaluate(()=>({
   left:(document.getElementById("portal-wall-left") as HTMLElement).style.opacity,
   part:(document.querySelector('img[data-part-id="pad_00"]') as HTMLElement).style.transform,
   mask:(document.getElementById("portal-window") as HTMLElement).style.maskImage
 }));
 expect(Number(reset.left)).toBe(0);
 expect(x(reset.part)).toBeCloseTo(0,0);
 expect(reset.mask).toMatch(/^radial-gradient\(/);
 expect(errors).toEqual([]);
});

test("V8 perspective corridor moves the camera THROUGH true Z geometry with reversible LOD — SYNTHETIC artwork",async ({page})=>{
 const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
 await fixture(page,true);
 const state=()=>page.evaluate(()=>(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:unknown}).__HAZEWAVE_TRAVERSAL_V4 as {
  depthScene:string;depthGateCount:number;depthWallCount:number;
  depthCameraZ:number;depthOpacity:number;mountedPieces:number
 });
 const initial=await state();
 const phone=page.viewportSize()!.width<700;
 expect(initial.depthScene).toBe("CSS_3D_PERSPECTIVE_GEOMETRY");
 expect(initial.depthGateCount).toBe(phone?30:56);
 expect(initial.depthWallCount).toBe(phone?24:48);
 expect(await page.locator("#depth-world .depth-wall").count()).toBe(phone?24:48);
 await scrollToExactProgress(page,.52);
 const approach=await state();
 await scrollToExactProgress(page,.73);
 const crossing=await state();
 expect(crossing.depthCameraZ).toBeGreaterThan(approach.depthCameraZ+600);
 expect(crossing.depthOpacity).toBeGreaterThan(0);
 const form=await page.locator("#depth-world").evaluate(el=>(el as HTMLElement).style.transform);
 expect(form).toContain("translate3d(");
 expect(form).toContain("rotateY(");
 await scrollToExactProgress(page,.52);
 const rewind=await state();
 expect(rewind.depthCameraZ).toBeCloseTo(approach.depthCameraZ,3);
 await scrollToExactProgress(page,0);
 const reset=await state();
 expect(reset.depthCameraZ).toBe(0);
 expect(reset.mountedPieces).toBe(24);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
 expect(errors).toEqual([]);
});

test("V9 feathered portal avoids a hard bright core, double-exposed worlds, and caption collision — SYNTHETIC IMAGE QA",async ({page})=>{
 const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
 await fixture(page,true);
 await ensureLiteMode(page,false);
 const sample=async(p:number)=>{
  await scrollToExactProgress(page,p);
  return page.evaluate(()=>{
   const sty=(s:string)=>(document.querySelector(s) as HTMLElement).style;
   const state=(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{portalSoftMask:string;portalFeatherPercent:string}}).__HAZEWAVE_TRAVERSAL_V4;
   return {mask:sty("#portal-window").maskImage,clip:sty("#portal-window").clipPath,
    ring:Number(sty("#portal-ring").opacity),city:Number(sty("#city-scene").opacity),
    hub:Number(sty("#hub-scene").opacity),caption:Number(sty("#narrative").opacity),
    mode:state.portalSoftMask,feather:Number(state.portalFeatherPercent)};
  });
 };
 const early=await sample(.46);
 const mid=await sample(.64);
 const cross=await sample(.86);
 expect(mid.mode).toBe("RADIAL_ALPHA_FEATHER");
 expect(mid.mask).toMatch(/^radial-gradient\(/);
 expect(mid.mask).toContain("transparent 100%");
 expect(mid.clip).toBe("none");
 expect(mid.feather).toBeGreaterThan(early.feather);
 expect(mid.ring).toBeLessThan(.10);
 expect(mid.caption).toBeLessThan(.05);
 await sample(.64); // Read FX optics at peak portal, not after hub arrival at .86.
 const optic=await page.evaluate(()=>({
   machine:Number((document.getElementById("machine") as HTMLElement).style.opacity),
   fx:Number((document.getElementById("effectcraft-aperture") as HTMLElement).style.opacity),
   fxFilter:getComputedStyle(document.getElementById("effectcraft-aperture")!).filter
 }));
 expect(optic.machine).toBeLessThan(.5);
 expect(optic.fx).toBeGreaterThan(.4);
 expect(optic.fx).toBeLessThan(.46);
 expect(optic.fxFilter).toContain("blur(6px)");
 expect(cross.city+cross.hub).toBeGreaterThan(.65);
 expect(cross.city).toBeLessThan(.05);
 expect(cross.hub).toBeGreaterThan(.98);
 expect(cross.city+cross.hub).toBeLessThan(1.01);
 expect(cross.ring).toBeLessThan(.10);
 await sample(.64);
 const restored=await sample(.86);
 expect(restored.city).toBeCloseTo(cross.city,3);
 expect(restored.hub).toBeCloseTo(cross.hub,3);
 expect(restored.mask).toBe(cross.mask);
 expect(errors).toEqual([]);
});

test("V11 paints five owner-derived scenes with a reversible revealing ink front — SYNTHETIC pixels",async({page})=>{
 for(const basename of ["station","controller","city","hub","fog"])
  expect(DOC).toContain('src="assets/'+basename+'.webp"');
 await fixture(page);
 expect(await page.locator("#station-left,#station-right").count()).toBe(2);
 expect(await page.locator("#controller-left,#controller-right").count()).toBe(2);
 await scrollToExactProgress(page,.12);
 const start=await page.evaluate(()=>{const s=(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{ownerArtRevealPct:number}}).__HAZEWAVE_TRAVERSAL_V4;return {ink:s.ownerArtRevealPct,mask:(document.getElementById("controller-left") as HTMLElement).style.maskImage}});
 expect(start.ink).toBe(0);
 await scrollToExactProgress(page,.44);
 const mid=await page.evaluate(()=>{const ink=document.getElementById("controller-left") as HTMLElement;const fog=document.getElementById("fog-left") as HTMLElement;const s=(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{ownerArtRevealPct:number}}).__HAZEWAVE_TRAVERSAL_V4;return {ink:s.ownerArtRevealPct,mask:ink.style.maskImage,opacity:ink.style.opacity,contour:fog.style.clipPath}});
 expect(mid.ink).toBeGreaterThan(30);expect(mid.mask).not.toBe(start.mask);expect(mid.opacity).toBe("1");
 await scrollToExactProgress(page,.92);
 const end=await page.evaluate(()=>{const s=(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{arrivalInk:number;hubOpacity:number}}).__HAZEWAVE_TRAVERSAL_V4;return {arrival:s.arrivalInk,hub:s.hubOpacity}});
 expect(end.arrival).toBeGreaterThan(.6);expect(end.hub).toBeGreaterThan(.95);
 const headerOpacity=Number(await page.locator("header.brand").evaluate(x=>(x as HTMLElement).style.opacity));
 expect(headerOpacity).toBeLessThan(.2);
 const finalFraming=await page.evaluate(()=>({
  hubWidth:(document.getElementById("hub-scene") as HTMLElement).getBoundingClientRect().width,
  viewport:innerWidth,narrative:Number((document.getElementById("narrative") as HTMLElement).style.opacity)
 }));
 expect(finalFraming.hubWidth).toBeLessThan(finalFraming.viewport*.8);
 expect(finalFraming.narrative).toBeLessThan(.28);
 await scrollToExactProgress(page,.12);
 const reset=await page.evaluate(()=>{const s=(window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{ownerArtRevealPct:number;arrivalInk:number}}).__HAZEWAVE_TRAVERSAL_V4;return {ink:s.ownerArtRevealPct,arrival:s.arrivalInk}});
 expect(reset.ink).toBe(0);expect(reset.arrival).toBe(0);
 await expect(page.locator("header.brand")).toHaveCSS("opacity","1");
});
