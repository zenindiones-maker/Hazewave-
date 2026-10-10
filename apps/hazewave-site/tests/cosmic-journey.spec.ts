import {test,expect,type Page} from "@playwright/test";
import {createHash} from "node:crypto";
import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {fileURLToPath} from "node:url";
const root=resolve(fileURLToPath(new URL("..",import.meta.url)));
async function move(page:Page,p:number){await page.evaluate(progress=>{const j=document.getElementById("journey");if(!j)throw Error("JOURNEY_MISSING");window.scrollTo({top:Math.max(0,j.offsetHeight-innerHeight)*progress,behavior:"instant"})},p);await expect.poll(()=>page.evaluate(()=>Number(document.body.dataset.storyProgress)),{timeout:8000}).toBeCloseTo(p,2)}
test("owner visuals stay byte-identical in source history",()=>{const receipt=JSON.parse(readFileSync(resolve(root,"owner-art-provenance.json"),"utf8"));for(const entry of receipt.assets){const bytes=readFileSync(resolve(root,"public",entry.asset.replace(/^\//,"")));expect(bytes.length).toBe(entry.bytes);expect(createHash("sha256").update(bytes).digest("hex")).toBe(entry.sha256)}});
test("one approved artist, two identity images, no numeric navigation and no five-world cards",async({page})=>{const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));await page.goto("/");await expect(page).toHaveTitle(/HAZEWAVE.*Indionesbala/);await expect(page.locator("body")).toHaveAttribute("data-experience","indionesbala-only");await expect(page.locator("img")).toHaveCount(2);await expect(page.locator("img[alt=HAZEWAVE]")).toHaveCount(1);await expect(page.locator("img[alt=Indionesbala]")).toHaveCount(1);expect(await page.locator(".chapter-nav,.planet,.artist-card,.hw-world,.world-switcher,[data-world-stop]").count()).toBe(0);expect(await page.locator("[aria-label^='Navegação entre']").count()).toBe(0);for(const forbidden of ["Barak Ozama","Baazü","Aquaverno","Hemorragia","Cinco mundos"])expect((await page.locator("body").innerText()).includes(forbidden)).toBe(false);expect(errors).toEqual([])});
test("scroll drives one continuous wave / MPC / Indionesbala reveal and reverses",async({page},info)=>{await page.goto("/");await expect.poll(()=>page.evaluate(()=>Boolean((window as unknown as {__HAZEWAVE_STORY?:{artistCount:number}}).__HAZEWAVE_STORY))).toBe(true);for(const [p,state] of [[0,"silence"],[.31,"interference"],[.55,"machine"],[.83,"handoff"],[.99,"artist"],[.55,"machine"],[0,"silence"]] as const){await move(page,p);await expect(page.locator("body")).toHaveAttribute("data-story-state",state);expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1)}await move(page,.99);await expect(page.locator("#artist-entry")).toHaveAttribute("href","/artists/indionesbala/");await expect(page.locator("#artist-entry")).toHaveCSS("pointer-events","auto");await page.screenshot({path:info.outputPath("single-artist-reveal-"+info.project.name+".png")})});
test("sole artist destination works; other four routes are not emitted",async({page})=>{await page.goto("/artists/indionesbala/");await expect(page.locator("h1")).toHaveText("Indionesbala");await expect(page.locator("img")).toHaveCount(2);await expect(page.locator(".world-switcher,.planet,.artist-card")).toHaveCount(0);await expect.poll(()=>page.locator(".identity").evaluate(e=>(e as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);for(const slug of ["aquaverno","baazu","barak-ozama-beats","hemorragia-cosmica"]){const response=await page.goto("/artists/"+slug+"/");expect(response?.status()).toBe(404)}});
test("reduced motion and no JS preserve artist access",async({browser,page})=>{await page.emulateMedia({reducedMotion:"reduce"});await page.goto("/");await move(page,.92);await expect(page.locator("html")).toHaveAttribute("data-reduced-motion","true");const context=await browser.newContext({javaScriptEnabled:false});const blank=await context.newPage();await blank.goto("/");await expect(blank.locator("#arrival a")).toBeVisible();await context.close()});

test("V10 art direction: Hazewave hero dominates both destinations; Indionesbala stays a supporting signature",async({page})=>{
  await page.goto("/");
  await move(page,0);
  await expect(page.locator(".copy-origin")).toHaveCSS("opacity","1");
  for(const progress of [0,.25,.55,.82,.99]){
    await move(page,progress);
    const rank=await page.evaluate(()=>{
      const brand=document.querySelector(".brand") as HTMLElement;
      const artist=document.querySelector(".logo-reveal img") as HTMLElement;
      return {brand:brand.getBoundingClientRect().width,
        artist:artist.getBoundingClientRect().width,
        visible:Number(getComputedStyle(brand).opacity),
        xOverflow:document.documentElement.scrollWidth-innerWidth};
    });
    expect(rank.visible).toBe(1);
    expect(rank.brand).toBeGreaterThanOrEqual(rank.artist*3);
    expect(rank.xOverflow).toBeLessThanOrEqual(1);
  }
  await move(page,.99);
  await expect(page.locator("#artist-entry")).toContainText("Entrar no universo Hazewave");
  await page.goto("/artists/indionesbala/");
  await expect(page).toHaveTitle(/HAZEWAVE/);
  const hierarchy=await page.evaluate(()=>{
    const brand=document.querySelector(".brand") as HTMLElement;
    const signature=document.querySelector(".identity") as HTMLElement;
    return {brand:brand.getBoundingClientRect().width,signature:signature.getBoundingClientRect().width};
  });
  expect(hierarchy.brand).toBeGreaterThanOrEqual(hierarchy.signature*3);
  await expect(page.locator(".back")).toContainText("Hazewave");
});

test("V10 logo uses only the top ornamental mark, not the full vertical lighthouse poster",async({page})=>{
  await page.goto("/");
  const image=page.locator("#hazewave-logo");
  const d=await image.evaluate(e=>{
    const im=e as HTMLImageElement;const style=getComputedStyle(im);
    const clip=im.parentElement!.getBoundingClientRect();
    return {fit:style.objectFit,position:style.objectPosition,mask:style.maskImage,
      naturalWidth:im.naturalWidth,naturalHeight:im.naturalHeight,
      imageBoxHeight:im.getBoundingClientRect().height,clipHeight:clip.height};
  });
  expect(d.naturalHeight).toBeGreaterThan(d.naturalWidth);
  expect(d.fit).toBe("cover");
  expect(d.position).toBe("50% 0%");
  expect(d.mask).toContain("linear-gradient");
  expect(d.imageBoxHeight).toBeCloseTo(d.clipHeight,0);
});

test("mobile QA: Hazewave 90vw dominates the 18vw, max 110px, 48px and 75% Indionesbala signature",async({page})=>{
  for(const width of [360,393]){
    await page.setViewportSize({width,height:852});
    await page.goto("/");
    await move(page,.99);
    const visual=await page.evaluate(()=>{
      const main=document.querySelector(".brand") as HTMLElement;
      const signature=document.querySelector(".logo-reveal img") as HTMLImageElement;
      const mainStyle=getComputedStyle(main),signatureStyle=getComputedStyle(signature);
      return {
        viewport:innerWidth,brandCssWidth:parseFloat(mainStyle.width),
        signatureCssWidth:parseFloat(signatureStyle.width),
        signatureMaxWidth:parseFloat(signatureStyle.maxWidth),
        signatureMaxHeight:parseFloat(signatureStyle.maxHeight),
        signatureOpacity:parseFloat(signatureStyle.opacity),
        brandVisibleWidth:main.getBoundingClientRect().width,
        signatureVisibleWidth:signature.getBoundingClientRect().width,
        overflow:document.documentElement.scrollWidth-innerWidth,
        signatureLoaded:signature.naturalWidth>0
      };
    });
    expect(visual.brandCssWidth).toBeCloseTo(width*.9,0);
    expect(visual.signatureCssWidth).toBeCloseTo(width*.18,0);
    expect(visual.signatureMaxWidth).toBe(110);
    expect(visual.signatureMaxHeight).toBe(48);
    expect(visual.signatureOpacity).toBeCloseTo(.75,2);
    expect(visual.brandVisibleWidth).toBeGreaterThanOrEqual(visual.signatureVisibleWidth*3);
    expect(visual.signatureLoaded).toBe(true);
    expect(visual.overflow).toBeLessThanOrEqual(1);
  }
  await expect(page.locator("#artist-entry")).toContainText("Entrar no universo Hazewave");
});

test("owner image serves image/jpeg with JFIF magic and unchanged SHA-256",async({page,request})=>{
 await page.goto("/");
 await expect(page.locator("#indionesbala-logo")).toHaveAttribute("src","/media/artists/indionesbala.jpg");
 const response=await request.get("/media/artists/indionesbala.jpg");
 expect(response.status()).toBe(200);
 expect(response.headers()["content-type"]).toMatch(/^image\/jpeg(?:;|$)/);
 const bytes=await response.body();
 expect(bytes.subarray(0,3).equals(Buffer.from([0xff,0xd8,0xff]))).toBe(true);
 const manifest=JSON.parse(readFileSync(resolve(root,"owner-art-provenance.json"),"utf8"));
 const original=manifest.assets.find((a:{asset:string})=>a.asset==="/media/artists/indionesbala.webp");
 expect(original).toBeTruthy();
 expect(bytes.length).toBe(original.bytes);
 expect(createHash("sha256").update(bytes).digest("hex")).toBe(original.sha256);
 const obsolete=await request.get("/media/artists/indionesbala.webp");
 expect(obsolete.status()).toBe(404);
});
