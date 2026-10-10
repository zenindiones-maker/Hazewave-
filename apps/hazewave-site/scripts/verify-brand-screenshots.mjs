import assert from "node:assert/strict";
import {mkdir} from "node:fs/promises";
import {resolve} from "node:path";
import {chromium} from "@playwright/test";
const folder=resolve(process.cwd(),"../../verification/screenshots");
await mkdir(folder,{recursive:true});
const browser=await chromium.launch({headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
try {
 for(const width of [360,768,1280]){
  const page=await browser.newPage({viewport:{width,height:width===1280?800:852},deviceScaleFactor:1});
  const errors=[];
  page.on("pageerror",e=>errors.push(e.message));
  const response=await page.goto("http://127.0.0.1:3000/",{waitUntil:"networkidle"});
  assert.equal(response?.status(),200);
  await page.evaluate(()=>{
   const journey=document.querySelector("#journey");
   if(!journey)throw Error("JOURNEY_MISSING");
   window.scrollTo(0,Math.max(0,journey.offsetHeight-innerHeight)*.99);
  });
  await page.waitForFunction(()=>Number(document.body.dataset.storyProgress)>=.985);
  for(const id of ["#hazewave-logo","#indionesbala-logo"])await page.locator(id).evaluate(img=>img.decode());
  const observed=await page.evaluate(()=>{
   const brand=document.querySelector(".brand"),artist=document.querySelector("#indionesbala-logo");
   return {brandWidth:brand.getBoundingClientRect().width,
    artistWidth:artist.getBoundingClientRect().width,
    brandOpacity:Number(getComputedStyle(brand).opacity),
    artistOpacity:Number(getComputedStyle(artist).opacity),
    overflow:document.documentElement.scrollWidth-innerWidth,
    artLoaded:brand.querySelector("img").naturalWidth>0&&artist.naturalWidth>0,
    unrelatedRig:document.querySelectorAll(".machine-field,.rig-wing,#pads").length};
  });
  assert.ok(observed.brandWidth>=3*observed.artistWidth,JSON.stringify(observed));
  assert.equal(observed.brandOpacity,1);
  assert.ok(Math.abs(observed.artistOpacity-.7)<.012,"INDIONESBALA_OPACITY");
  assert.ok(observed.overflow<=1,"HORIZONTAL_OVERFLOW");
  assert.ok(observed.artLoaded,"IMAGE_NOT_LOADED");
  assert.equal(observed.unrelatedRig,0);
  assert.deepEqual(errors,[]);
  const path=resolve(folder,`hazewave-${width}.png`);
  await page.screenshot({path,animations:"disabled"});
  console.log(`HAZEWAVE_SCREENSHOT_${width}=PASS ratio=${(observed.brandWidth/observed.artistWidth).toFixed(2)} opacity=${observed.artistOpacity}`);
  await page.close();
 }
}finally{await browser.close();}
