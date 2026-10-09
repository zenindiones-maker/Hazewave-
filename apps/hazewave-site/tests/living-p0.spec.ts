import { test, expect, type Page } from "@playwright/test";
const path="/living-universe-p0/";

async function moveTo(page:Page, progress:number){
  await page.evaluate((p)=>{
    document.documentElement.style.scrollBehavior="auto";
    const element=document.getElementById("living-p0-scroll");
    if(!element)throw new Error("P0_SECTION_MISSING");
    const start=element.getBoundingClientRect().top+scrollY;
    const distance=element.offsetHeight-innerHeight;
    window.scrollTo({top:start+Math.max(0,distance)*p,behavior:"auto"});
  },progress);
}
const state=(page:Page)=>page.evaluate(()=> (window as typeof window & {
  __hazewaveP0State?:{ready:boolean;progress:number;phase:string;activePads:number;ambientSeconds:number}
}).__hazewaveP0State ?? null);

test("isolated P0 renders Pixi canvas, not the rejected composite poster", async ({page}, info)=>{
  await page.goto(path);
  await expect(page).toHaveTitle(/Living Universe P0/);
  await expect(page.locator("#living-p0-canvas canvas")).toHaveCount(1);
  await expect(page.locator("body")).toHaveAttribute("data-p0-status","running");
  await expect(page.locator("body")).toHaveAttribute("data-p0-phase","sleep");
  await expect(page.locator('img[src="/media/hazewave-world.jpg"]')).toHaveCount(0);
  await expect(page.locator('img[src="/media/artists/indionesbala.webp"]')).toHaveCount(1);
  await expect(page.locator(".artist-card")).toHaveCount(0);
  await page.screenshot({path:"test-results/living-p0-start-"+info.project.name+".png",animations:"disabled"});
});

test("the signal reaches MPC pads and reverses when scrolling back",async({page}, info)=>{
  await page.goto(path);
  await expect.poll(async()=> (await state(page))?.ready).toBe(true);
  const initial=await state(page);
  expect(initial?.progress).toBeLessThan(.03);
  await moveTo(page,.55);
  await expect.poll(async()=> (await state(page))?.progress).toBeGreaterThan(.5);
  const mid=await state(page);
  expect(mid?.activePads??0).toBeGreaterThan(0);
  await page.screenshot({path:"test-results/living-p0-mid-"+info.project.name+".png",animations:"disabled"});
  await moveTo(page,1);
  await expect.poll(async()=> (await state(page))?.progress).toBeGreaterThan(.98);
  await expect(page.locator("body")).toHaveAttribute("data-p0-phase","awake");
  const end=await state(page);
  expect(end?.activePads).toBeGreaterThan(mid?.activePads??0);
  await page.screenshot({path:"test-results/living-p0-end-"+info.project.name+".png",animations:"disabled"});
  await moveTo(page,0);
  await expect.poll(async()=> (await state(page))?.progress).toBeLessThan(.02);
  const back=await state(page);
  expect(back?.activePads).toBe(0);
  await expect(page.locator("body")).toHaveAttribute("data-p0-phase","sleep");
});

test("ambient clock continues with stationary scroll; it is not driven by scroll",async({page})=>{
  await page.goto(path);
  await expect.poll(async()=> (await state(page))?.ready).toBe(true);
  const first=await state(page);
  await page.waitForTimeout(400);
  const second=await state(page);
  expect(second?.progress).toBeCloseTo(first?.progress??0,2);
  expect(second?.ambientSeconds??0).toBeGreaterThan(first?.ambientSeconds??0);
});

test("respect reduced motion while keeping reversible narrative",async({page})=>{
  await page.emulateMedia({reducedMotion:"reduce"});
  await page.goto(path);
  await expect.poll(async()=> (await state(page))?.ready).toBe(true);
  const first=await state(page);
  await page.waitForTimeout(300);
  const second=await state(page);
  expect(second?.ambientSeconds).toBe(first?.ambientSeconds);
  await moveTo(page,.7);
  await expect.poll(async()=> (await state(page))?.progress).toBeGreaterThan(.68);
  await moveTo(page,.0);
  await expect.poll(async()=> (await state(page))?.progress).toBeLessThan(.02);
});

test("mobile keeps native scroll, no horizontal overflow, with reachable artist entry",async({page})=>{
  await page.goto(path);
  const data=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,height:document.documentElement.scrollHeight,screen:innerHeight}));
  expect(data.width).toBeLessThanOrEqual(data.viewport+1);
  expect(data.height).toBeGreaterThan(data.screen*4);
  await page.locator("#p0-destination").scrollIntoViewIfNeeded();
  await expect(page.locator('a[href="/artists/indionesbala/"]')).toHaveCount(1);
});

test("fallback remains useful without JavaScript",async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false});
  try{
    const page=await context.newPage();
    await page.goto(path);
    await expect(page.locator(".p0-fallback")).toHaveCount(1);
    await expect(page.getByRole("link",{name:/abrir artista/i})).toBeVisible();
  }finally{await context.close();}
});
