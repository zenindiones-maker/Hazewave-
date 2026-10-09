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
  x:200+number*40,y:150+number*45,width:40,height:40,
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
  v3aPieces:PIECES
};
type Pose={phase:number;progress:number;activePads:number;activeKnobs:number;
  activeSpeakers:number;portalRadiusPct:number;hubOpacity:number;
  secondIllustratedRegionVisible:boolean;visualQualityTier:string};
const pose=async (page:Page) => page.evaluate(()=>(
  (window as unknown as {__HAZEWAVE_TRAVERSAL_V4:Pose}).__HAZEWAVE_TRAVERSAL_V4
));
async function fixture(page:Page) {
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
  },{manifest,urls});
  await page.addScriptTag({content:RUNTIME});
  await expect.poll(async()=>page.evaluate(()=>Boolean(
    (window as unknown as {__HAZEWAVE_TRAVERSAL_V4:{ready:boolean}}).__HAZEWAVE_TRAVERSAL_V4?.ready
  )),{timeout:25000}).toBe(true);
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
  await page.locator("#lightweight-mode").click();
  await expect(page.locator("#stage")).toHaveAttribute("data-quality","lite");
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
