import {test,expect,type Browser,type Page} from "@playwright/test";
import {readFileSync,statSync,writeFileSync} from "node:fs";
import {execFileSync} from "node:child_process";
import {resolve} from "node:path";

const route="/experimental/articulated-rig-v3a.html";
const manifest=JSON.parse(readFileSync(
  resolve("..","..","docs","prototypes","wave-articulated-rig-v3a","rig-manifest.json"),"utf8"));
type Rig={ready:boolean;progress:number;activePads:number;activeKnobs:number;activeSpeakers:number;stroke:number};
const sequence=[0,.2,.45,.7,1,.45,0] as const;

async function toProgress(page:Page, p:number) {
  await page.evaluate((value)=>{
    const journey=document.getElementById("journey");
    if(!journey)throw Error("V3A_JOURNEY_MISSING");
    const top=journey.getBoundingClientRect().top+window.scrollY;
    const travel=journey.offsetHeight-window.innerHeight;
    document.documentElement.style.scrollBehavior="auto";
    window.scrollTo({top:top+Math.max(1,travel)*value,behavior:"instant"});
  },p);
  await expect.poll(async()=>Math.abs(await page.evaluate(
    ()=>(window as unknown as Window & {__HAZEWAVE_RIG_V3:Rig}).__HAZEWAVE_RIG_V3.progress) - p),
    {timeout:6000}).toBeLessThanOrEqual(.018);
}
async function snapshot(page:Page){
  return page.evaluate(()=>{
    const r=(window as unknown as Window & {__HAZEWAVE_RIG_V3:Rig}).__HAZEWAVE_RIG_V3;
    const machine=document.getElementById("machine");
    const knob=document.querySelector<HTMLElement>('img[data-rig-id="knob_00"]');
    const speaker=document.querySelector<HTMLElement>('img[data-rig-id="speaker_00"]');
    return {...r,machineTransform:machine?.style.transform||"",
      knobTransform:knob?.style.transform||"",
      speakerTransform:speaker?.style.transform||""};
  });
}
for (const viewport of [{width:393,height:852},{width:360,height:800}]) {
 test("V3A exact-SHA actual portrait owner review "+viewport.width+"x"+viewport.height,
 async ({browser}: {browser:Browser}, info)=>{
   test.skip(info.project.name!=="chromium-desktop","one actual portrait recording per viewport");
   test.setTimeout(90_000);
   const context=await browser.newContext({
     viewport,screen:viewport,deviceScaleFactor:1,isMobile:true,hasTouch:true,
     serviceWorkers:"block",
     recordVideo:{dir:info.outputPath("raw-video"),size:viewport}
   });
   const page=await context.newPage();
   const jsErrors:string[]=[];
   page.on("pageerror",e=>jsErrors.push(e.message));
   let video=page.video();
   let states: Array<Rig & {machineTransform:string;knobTransform:string;speakerTransform:string}> = [];
   try{
     await page.goto(route,{waitUntil:"load"});
     await expect.poll(async()=> (await snapshot(page)).ready).toBe(true);
     expect(await page.locator("img[data-rig-id]").count()).toBe(24);
     expect(await page.locator("img[data-pad-id]").count()).toBe(12);
     expect(manifest.pieces.filter((p:{type:string})=>p.type==="pad")).toHaveLength(12);
     expect(manifest.pieces.filter((p:{type:string})=>p.type==="knob")).toHaveLength(8);
     expect(manifest.pieces.filter((p:{type:string})=>p.type==="speaker")).toHaveLength(4);
     for (let i=0;i<sequence.length;i++){
       await toProgress(page,sequence[i]);
       await page.waitForTimeout(320);
       const sample=await snapshot(page);
       states.push(sample);
       if ([0,2,4,6].includes(i)){
         await page.screenshot({path:info.outputPath(
           "v3a-portrait-"+viewport.width+"-step-"+i+".png"),
           animations:"disabled"});
       }
     }
     expect(states[0].activePads).toBe(0);
     expect(states[4].activePads).toBe(12);
     expect(states[4].activeKnobs).toBe(8);
     expect(states[4].activeSpeakers).toBe(4);
     expect(states[6].activePads).toBe(0);
     expect(states[6].activeKnobs).toBe(0);
     expect(states[6].activeSpeakers).toBe(0);
     expect(states[6].stroke).toBeLessThan(.02);
     expect(states[4].knobTransform).not.toBe(states[0].knobTransform);
     expect(states[4].speakerTransform).not.toBe(states[0].speakerTransform);
     expect(jsErrors).toEqual([]);
     const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
     expect(overflow).toBeLessThanOrEqual(1);
     const actualSha=execFileSync("git",["rev-parse","HEAD"],{encoding:"utf8"}).trim();
     const receipt={
       schema:"HazewaveV3APortraitBrowserCapture/v1",
       reviewedSha:actualSha,
       route,
       viewport,
       ownerArtSha256:manifest.source_sha256,
       detectedPieces:{pads:12,knobs:8,speakers:4},
       sampledStates:states,
       javascriptErrors:jsErrors,
       horizontalOverflow:overflow,
       source:"real_browser",
       videoRecorded:true,
       videoFileBytes:0,
       claimsProductionApproval:false,
       claimsCinematicTraversal:false
     };
     writeFileSync(info.outputPath("v3a-portrait-"+viewport.width+"-receipt.json"),
       JSON.stringify(receipt,null,2)+"\n");
     await page.waitForTimeout(400);
   }finally{
     await context.close();
   }
   if(!video)throw Error("RECORDING_WAS_NOT_INITIALIZED");
   const destination=info.outputPath("v3a-portrait-"+viewport.width+"x"+viewport.height+".webm");
   await video.saveAs(destination);
   expect(statSync(destination).size).toBeGreaterThan(1000);
 });
}
