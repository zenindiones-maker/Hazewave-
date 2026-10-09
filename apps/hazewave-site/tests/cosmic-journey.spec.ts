import { test, expect, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
async function travel(page: Page, p: number) {
  await page.evaluate((progress) => {
    document.documentElement.style.scrollBehavior = "auto";
    const film = document.getElementById("film");
    if (!film) throw new Error("ILLUSTRATED_FILM_NOT_FOUND");
    const top = film.getBoundingClientRect().top + scrollY;
    const max = film.offsetHeight - innerHeight;
    window.scrollTo(0, top + Math.max(0, max) * progress);
  }, p);
}

test("six original owner visual assets remain byte-identical", async () => {
  const manifest = JSON.parse(readFileSync(resolve(root,"owner-art-provenance.json"),"utf8"));
  expect(manifest.assets).toHaveLength(6);
  for (const item of manifest.assets) {
    const bytes = readFileSync(resolve(root, "public", item.asset.replace(/^\//, "")));
    expect(bytes.length, item.asset).toBe(item.bytes);
    expect(createHash("sha256").update(bytes).digest("hex"), item.asset).toBe(item.sha256);
  }
});

test("opening is original illustrated universe, never the legacy giant poster", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Uma onda, muitos universos/i);
  await expect(page.locator("body")).toHaveAttribute("data-phase","origin");
  await expect(page.getByRole("heading", { name: /Antes da matéria/i })).toBeVisible();
  await expect(page.locator("#interference-art .ink-landscape")).toHaveCount(3);
  await expect(page.locator(".signal-core")).toHaveCount(1);
  await expect(page.locator("#cosmos")).toHaveCount(0);
  await expect(page.locator("#logo-plate")).toHaveCount(0);
  await expect(page.locator(".artist-card")).toHaveCount(0);
  await expect(page.locator(".identity-seal")).toHaveCSS("opacity","0");
  await page.screenshot({ path: "test-results/illustrated-opening-"+testInfo.project.name+".png", animations:"disabled" });
});

test("scroll travels to ink wave, rupture and revelation — and reverses", async ({ page }, testInfo) => {
  await page.goto("/");
  await travel(page,0.4);
  await expect(page.locator("body")).toHaveAttribute("data-phase","crossing");
  await expect(page.locator(".signal-engraving")).not.toHaveCSS("opacity","0");
  await page.screenshot({ path:"test-results/illustrated-crossing-"+testInfo.project.name+".png", animations:"disabled" });
  await travel(page,0.7);
  await expect(page.locator("body")).toHaveAttribute("data-phase","rupture");
  await page.screenshot({ path:"test-results/illustrated-rupture-"+testInfo.project.name+".png", animations:"disabled" });
  await travel(page,1);
  await expect(page.locator("body")).toHaveAttribute("data-phase","reveal");
  await expect(page.locator(".identity-seal")).toHaveCSS("opacity","1");
  await page.screenshot({ path:"test-results/illustrated-revelation-"+testInfo.project.name+".png", animations:"disabled" });
  await travel(page,0);
  await expect(page.locator("body")).toHaveAttribute("data-phase","origin");
  await expect(page.locator(".identity-seal")).toHaveCSS("opacity","0");
});

test("five artist worlds appear as constellations, not cards", async ({ page }, testInfo) => {
  await page.goto("/#worlds");
  await expect(page.locator("#worlds")).toBeVisible();
  await expect(page.locator(".planet")).toHaveCount(5);
  await expect(page.locator(".artist-card")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /Cinco mundos/i })).toBeVisible();
  const path="test-results/illustrated-worlds-"+testInfo.project.name+".png";
  try {
    await page.screenshot({ path, animations:"disabled", fullPage:false });
  } catch (error) {
    // Huge GPU/illustrated layers can sporadically lose the screenshot surface
    // after hash navigation. Do not erase the visual gate: capture from the
    // browser view via Chromium's alternate compositor path and validate PNG.
    if (!(error instanceof Error) || !error.message.includes("Unable to capture screenshot")) throw error;
    const cdp=await page.context().newCDPSession(page);
    try {
      const capture=await cdp.send("Page.captureScreenshot",{
        format:"png",captureBeyondViewport:false,fromSurface:false
      });
      const pixels=Buffer.from(capture.data,"base64");
      expect(pixels.length).toBeGreaterThan(10000);
      expect(pixels.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))).toBe(true);
      const width=pixels.readUInt32BE(16),height=pixels.readUInt32BE(20);
      const vp=page.viewportSize();
      expect(vp).not.toBeNull();
      const dpr=await page.evaluate(()=>window.devicePixelRatio);
      const cssPixelMatch=width===vp?.width && height===vp?.height;
      const devicePixelMatch=vp!==null &&
        Math.abs(width-vp.width*dpr)<=2 && Math.abs(height-vp.height*dpr)<=2;
      expect(cssPixelMatch||devicePixelMatch).toBe(true);
      writeFileSync(path,pixels);
      testInfo.annotations.push({type:"browser-compositor-fallback",description:"CDP fromSurface=false PNG verified"});
    } finally {
      await cdp.detach();
    }
  }
});

test("each artist destination uses authentic image inside orbital world", async ({ page }) => {
  const artists = [
    ["indionesbala","Indionesbala"],
    ["barak-ozama-beats","Barak Ozama Beats"],
    ["baazu","Baazü"],
    ["aquaverno","Aquaverno"],
    ["hemorragia-cosmica","Hemorragia Cósmica"],
  ] as const;
  for (const [slug,name] of artists) {
    const response = await page.goto("/artists/"+slug+"/");
    expect(response?.status()).toBe(200);
    await expect(page.locator("h1")).toHaveText(name);
    await expect(page.locator(".artist-world-orb img")).toHaveAttribute("alt","Arte original de "+name);
    await expect.poll(() => page.locator(".artist-world-orb img").evaluate((img)=> (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    await expect(page.locator(".world-switcher a")).toHaveCount(5);
  }
});

test("mobile and desktop do not overflow the viewport", async ({ page }) => {
  await page.goto("/");
  const width = await page.evaluate(() => ({actual:document.documentElement.scrollWidth,expected:innerWidth}));
  expect(width.actual).toBeLessThanOrEqual(width.expected+1);
  await page.goto("/artists/aquaverno/");
  const artistWidth = await page.evaluate(() => ({actual:document.documentElement.scrollWidth,expected:innerWidth}));
  expect(artistWidth.actual).toBeLessThanOrEqual(artistWidth.expected+1);
});

test("reduced motion disables parallax without blocking scroll", async ({ page }) => {
  await page.emulateMedia({ reducedMotion:"reduce" });
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-motion","reduced");
  await travel(page,.7);
  await expect(page.locator("body")).toHaveAttribute("data-phase","rupture");
  await expect.poll(() => page.locator("html").evaluate((root)=>root.style.getPropertyValue("--shift"))).toBe("0");
});

test("no JS retains artist navigation and illustration", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled:false });
  try {
    const page = await context.newPage();
    await page.goto("/");
    await expect(page.locator("#interference-art")).toBeVisible();
    await expect(page.locator(".planet")).toHaveCount(5);
    await expect(page.getByRole("heading", { name:/Antes da matéria/i })).toBeVisible();
  } finally {
    await context.close();
  }
});
