import { test, expect, type Page } from "@playwright/test";

// Acceptance contract for Site 01: scroll ACTUALLY creates the stroke.
// Unlike parallax or pre-rendered PNG swaps, every path must paint its own
// progressively revealed SVG length, with exact reverse-scroll restoration.
async function strokeState(page: Page, key: string) {
  return page.locator('[data-ink-stroke="' + key + '"]').evaluate((el) => {
    const p = el as SVGPathElement;
    const length = p.getTotalLength();
    return {length, offset: Number.parseFloat(p.style.strokeDashoffset)};
  });
}
async function go(page: Page, p: number) {
  await page.evaluate((value) => {
    const host = document.getElementById("ink-journey");
    if (!host) throw new Error("INK_STORY_MISSING");
    const top = host.getBoundingClientRect().top + scrollY;
    const distance = Math.max(1, host.offsetHeight - innerHeight);
    window.scrollTo({top: top + distance * value, behavior: "instant"});
  }, p);
  await expect.poll(() => page.evaluate(() => Number(document.body.dataset.inkProgress)),
    {timeout: 8000}).toBeCloseTo(p, 2);
}
test("Site 01 rejects the old static/parallax-only format and draws actual SVG in 7 meaningful chapters", async ({page}) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  const response = await page.goto("/site-01/");
  expect(response?.status()).toBe(200);
  await expect(page.locator("body")).toHaveAttribute("data-experience", "hazewave-site-01-ink");
  await expect(page.locator("[data-ink-chapter]")).toHaveCount(7);
  await expect(page.locator("path[data-ink-stroke]")).toHaveCount(16);
  await expect(page.locator("canvas,video,.planet,.world-switcher")).toHaveCount(0);
  await expect(page.locator("img")).toHaveCount(2);
  await expect(page.locator("img[alt='HAZEWAVE']")).toHaveCount(1);
  await expect(page.locator("img[alt='Indionesbala']")).toHaveCount(1);
  await expect(page.locator("#brush-owner-mask")).toHaveCount(1);
  await expect(page.locator("#ink-revealed-original")).toHaveAttribute("href", "/media/hazewave-world.jpg");
  const head = await page.locator("#ink-story-engine").getAttribute("data-renderer");
  expect(head).toBe("svg-stroke");
  for (const forbidden of ["Aquaverno","Baazü","Barak Ozama","Hemorragia Cósmica"]) {
    expect((await page.locator("body").innerText()).includes(forbidden)).toBe(false);
  }
  expect(errors).toEqual([]);
});
test("the brush paints progressively and erases identically on reverse scroll, including the original-art mask", async ({page}, info) => {
  await page.goto("/site-01/");
  await expect.poll(() => page.evaluate(() => Boolean((window as any).__HAZEWAVE_SITE_01?.ready))).toBe(true);
  await go(page, 0);
  const initial = await strokeState(page,"origin");
  expect(initial.length).toBeGreaterThan(200);
  expect(initial.offset / initial.length).toBeCloseTo(1, 3);
  await go(page, .105);
  const partial=await strokeState(page,"origin");
  expect(partial.offset).toBeLessThan(initial.offset * .9);
  expect(partial.offset).toBeGreaterThan(0);
  const future=await strokeState(page,"nebula");
  expect(future.offset / future.length).toBeCloseTo(1, 3);
  await go(page,.45);
  const handoff=await strokeState(page,"interference");
  expect(handoff.offset / handoff.length).toBeLessThan(.05);
  const nebulous=await strokeState(page,"nebula");
  expect(nebulous.offset).toBeLessThan(nebulous.length);
  await go(page,.75);
  const ownerMask=await strokeState(page,"owner-mask");
  expect(ownerMask.offset).toBeLessThan(ownerMask.length);
  expect(ownerMask.offset).toBeGreaterThanOrEqual(0);
  await go(page,.99);
  const finished=await strokeState(page,"signature");
  expect(finished.offset / finished.length).toBeLessThan(.01);
  await expect(page.locator("#ink-arrival-link")).toHaveAttribute("href","/artists/indionesbala/");
  await expect(page.locator("#ink-arrival-link")).toHaveCSS("pointer-events","auto");
  expect(Number(await page.locator("#ink-arrival-link").evaluate(el=>getComputedStyle(el).opacity))).toBeGreaterThan(.95);
  await go(page,0);
  const reversed=await strokeState(page,"origin");
  const revertedMask=await strokeState(page,"owner-mask");
  expect(reversed.offset / reversed.length).toBeCloseTo(1,3);
  expect(revertedMask.offset / revertedMask.length).toBeCloseTo(1,3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({path:info.outputPath("site01-ink-erased-"+info.project.name+".png")});
});
test("mobile story reveals original owned identity without cropping the main brand or inventing media", async({page},info)=>{
  await page.goto("/site-01/");
  for (const p of [.18,.54,.90]) {
    await go(page,p);
    const metrics=await page.evaluate(()=>{
      const master=document.querySelector(".site01-brand") as HTMLElement;
      const artist=document.querySelector(".site01-artist-mark") as HTMLElement;
      return {
        masterWidth:master.getBoundingClientRect().width,
        artistWidth:artist.getBoundingClientRect().width,
        overflow:document.documentElement.scrollWidth-innerWidth,
      };
    });
    expect(metrics.masterWidth).toBeGreaterThanOrEqual(3*metrics.artistWidth);
    expect(metrics.overflow).toBeLessThanOrEqual(1);
    await page.screenshot({path:info.outputPath("site01-p"+String(p)+"-"+info.project.name+".png"),animations:"disabled"});
  }
  await expect(page.locator("#ink-arrival-link")).toBeVisible();
});
test("reduced motion keeps exact reversible brush and no-JS maintains artist access",async({page,browser})=>{
  await page.emulateMedia({reducedMotion:"reduce"});
  await page.goto("/site-01/");
  await go(page,.64);
  expect((await strokeState(page,"nebula")).offset).toBeLessThan((await strokeState(page,"nebula")).length);
  await go(page,0);
  const origin=await strokeState(page,"origin");
  expect(origin.offset).toBeCloseTo(origin.length,2);
  const context=await browser.newContext({javaScriptEnabled:false});
  const accessible=await context.newPage();
  await accessible.goto("/site-01/");
  await expect(accessible.locator("#ink-noscript a")).toHaveAttribute("href","/artists/indionesbala/");
  await context.close();
});
