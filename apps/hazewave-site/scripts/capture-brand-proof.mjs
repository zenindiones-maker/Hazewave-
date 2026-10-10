#!/usr/bin/env node
/**
 * Real Chromium brand-readback and viewport screenshot evidence.
 * Reads the compiled Astro site served on 127.0.0.1:3000.
 * Never invents a screenshot or substitutes DOM/fixture for an actual browser.
 */
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import {resolve} from "node:path";
import {chromium} from "@playwright/test";

const base=process.env.HAZE_VERIFY_URL || "http://127.0.0.1:3000";
const output=resolve(process.env.HAZE_VERIFY_REPORT_DIR || ".verification");
const widths=[360,768,1280];
const summary={schema:"HAZEWAVERealBrandScreenshots/v1",url:base,checks:[],browser:"chromium",artistic_approval:"PENDING"};
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
try {
  for (const width of widths) {
    const context=await browser.newContext({viewport:{width,height:852},deviceScaleFactor:1});
    const page=await context.newPage();
    try {
      const errors=[];
      page.on("pageerror",error=>errors.push(error.message));
      const response=await page.goto(base,{waitUntil:"load",timeout:30000});
      assert.equal(response?.status(),200,"HTML_HTTP_NOT_200");
      await page.evaluate(()=>document.fonts.ready);
      const hero=page.locator(".brand img");
      const signature=page.locator(".logo-reveal img");
      await hero.waitFor({state:"visible"});
      await page.waitForFunction(()=>document.querySelector(".brand img")?.naturalWidth>0);
      await page.waitForFunction(()=>document.querySelector(".logo-reveal img")?.naturalWidth>0);
      for (const progress of [0,.25,.55,.82,.99]) {
        await page.evaluate(p=>{
          const section=document.querySelector("#journey");
          if (!section) throw Error("MISSING_REAL_JOURNEY");
          const extent=Math.max(1,section.offsetHeight-innerHeight);
          window.scrollTo({top:section.getBoundingClientRect().top+scrollY+extent*p,behavior:"instant"});
        },progress);
        await page.waitForFunction(p=>{
          const actual=Number(document.body.dataset.storyProgress);
          return Number.isFinite(actual)&&Math.abs(actual-p)<.015;
        },progress,{timeout:10000});
        const sample=await page.evaluate(()=>{
          const brand=document.querySelector(".brand");
          const image=document.querySelector(".logo-reveal img");
          return {
            brandWidth:brand.getBoundingClientRect().width,
            signatureWidth:image.getBoundingClientRect().width,
            brandOpacity:parseFloat(getComputedStyle(brand).opacity),
            artistOpacity:parseFloat(getComputedStyle(image).opacity),
            overflow:document.documentElement.scrollWidth-innerWidth
          };
        });
        assert.ok(sample.brandOpacity>=.99,"MAIN_BRAND_NOT_PERSISTENT");
        assert.ok(sample.brandWidth>=sample.signatureWidth*3,
          "HAZEWAVE_NOT_THREE_TIMES_ARTIST");
        assert.ok(sample.overflow<=1,"HORIZONTAL_OVERFLOW");
        assert.ok(sample.artistOpacity<=.705 && sample.artistOpacity>=.69,
          "SECONDARY_ARTIST_OPACITY_NOT_70_PERCENT");
      }
      const measure=await page.evaluate(()=>{
        const hero=document.querySelector(".brand");
        const artist=document.querySelector(".logo-reveal img");
        const text=document.querySelector(".copy-reveal p");
        const type=getComputedStyle(text);
        return {
          viewport:innerWidth,
          heroWidth:hero.getBoundingClientRect().width,
          artistWidth:artist.getBoundingClientRect().width,
          artistOpacity:parseFloat(getComputedStyle(artist).opacity),
          labelFontFamily:type.fontFamily,
          labelFontWeight:type.fontWeight,
          labelOpacity:parseFloat(type.opacity),
          activeArtistRoutes:[...document.querySelectorAll('a[href*="/artists/"]')].map(a=>a.getAttribute("href")),
          artLoaded:artist.naturalWidth>0,
        };
      });
      assert.equal(measure.viewport,width);
      assert.equal(measure.artLoaded,true);
      assert.ok(measure.artistOpacity<=.705 && measure.artistOpacity>=.69);
      assert.ok(measure.labelOpacity<=.705 && measure.labelOpacity>=.69);
      assert.ok(Number(measure.labelFontWeight)<=400,"SECONDARY_TYPE_TOO_HEAVY");
      assert.ok(!/georgia|times new roman/i.test(measure.labelFontFamily),
        "ARTIST_LABEL_NOT_LIGHT_SANS");
      assert.ok(measure.activeArtistRoutes.length>0);
      assert.ok(measure.activeArtistRoutes.every(s=>s==="/artists/indionesbala/"),
        "OTHER_ARTIST_ROUTE_EXPOSED");
      assert.deepEqual(errors,[],"JAVASCRIPT_RUNTIME_ERRORS");
      const filename="hazewave-hero-"+width+".png";
      const file=resolve(output,filename);
      await page.screenshot({path:file,animations:"disabled"});
      const bytes=await readFile(file);
      assert.ok(bytes.length>10000,"SCREENSHOT_NOT_RENDERED");
      const hash=createHash("sha256").update(bytes).digest("hex");
      summary.checks.push({width,file:filename,bytes:bytes.length,sha256:hash,...measure,passed:true});
      console.log("REAL_BROWSER_SCREENSHOT="+width+" FILE="+filename+" SHA256="+hash);
    } finally {
      await context.close();
    }
  }
  await writeFile(resolve(output,"brand-browser-receipt.json"),
    JSON.stringify(summary,null,2)+"\n",{flag:"w"});
  assert.equal(summary.checks.length,3);
  console.log("REAL_BRAND_HIERARCHY=PASS VIEWPORTS=360,768,1280");
} finally {
  await browser.close();
}
