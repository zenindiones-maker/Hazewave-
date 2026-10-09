import { test, expect, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));

async function travel(page: Page, progress: number) {
  await page.evaluate((value) => {
    document.documentElement.style.scrollBehavior = "auto";
    const max = document.documentElement.scrollHeight - window.innerHeight;
    window.scrollTo(0, max * value);
  }, progress);
}

test("owner artwork remains byte-for-byte unchanged", async () => {
  const manifest = JSON.parse(readFileSync(resolve(appRoot, "owner-art-provenance.json"), "utf8"));
  expect(manifest.assets).toHaveLength(6);
  for (const item of manifest.assets) {
    const bytes = readFileSync(resolve(appRoot, "public", item.asset.replace(/^\//, "")));
    expect(bytes.length, item.asset).toBe(item.bytes);
    expect(createHash("sha256").update(bytes).digest("hex"), item.asset).toBe(item.sha256);
  }
});

test("cosmic home renders three acts and five original artists", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/HAZEWAVE/);
  await expect(page.locator("h1")).toContainText("universo");
  await expect(page.locator("#cosmos")).toHaveCount(1);
  await expect(page.locator("#origin")).toHaveCount(1);
  await expect(page.locator("#crossing")).toHaveCount(1);
  await expect(page.locator("#revelation")).toHaveCount(1);
  await expect(page.locator(".artist-card")).toHaveCount(5);
  await expect(page.locator("#listen")).toHaveAttribute("aria-pressed", "false");
  const metrics = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: innerWidth,
    documentHeight: document.documentElement.scrollHeight,
    viewportHeight: innerHeight,
  }));
  expect(metrics.documentWidth).toBeLessThanOrEqual(metrics.viewportWidth + 1);
  expect(metrics.documentHeight).toBeGreaterThan(metrics.viewportHeight * 3);
  await page.screenshot({ path: "test-results/cosmic-origin-" + testInfo.project.name + ".png", animations: "disabled" });
});

test("scroll reveals and reverses the same narrative", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-act", "birth");
  await travel(page, 0.5);
  await expect(page.locator("body")).toHaveAttribute("data-act", "traversal");
  await expect(page.locator("body")).toHaveAttribute("data-logo", "hidden");
  await travel(page, 1);
  await expect(page.locator("body")).toHaveAttribute("data-logo", "revealed");
  await expect(page.locator("body")).toHaveAttribute("data-act", "revelation");
  await expect(page.locator("#network")).toBeVisible();
  await page.screenshot({ path: "test-results/cosmic-revelation-" + testInfo.project.name + ".png", animations: "disabled" });
  await travel(page, 0);
  await expect(page.locator("body")).toHaveAttribute("data-act", "birth");
  await expect(page.locator("body")).toHaveAttribute("data-logo", "hidden");
  await expect(page.locator("#network")).toBeHidden();
});

test("original artwork and artist navigation remain accessible without JavaScript", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto("/");
    await expect(page.locator("#logo-plate img")).toBeVisible();
    await expect(page.locator(".artist-card")).toHaveCount(5);
    await expect(page.locator("noscript")).toHaveCount(1);
  } finally {
    await context.close();
  }
});

test("audio is opt-in and never claims to play an artist release", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-audio", "off");
  await expect(page.locator("#listen")).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByText(/SINAL SINTÉTICO/)).toHaveCount(1);
  await expect(page.getByText(/Nenhum lançamento foi inventado/)).toHaveCount(1);
});

test("reduced motion keeps the journey navigable", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-reduced", "yes");
  await travel(page, 1);
  await expect(page.locator("body")).toHaveAttribute("data-logo", "revealed");
});


test("all five original artist pages are directly navigable", async ({ page }) => {
  const entries = [
    ["indionesbala", "Indionesbala"],
    ["barak-ozama-beats", "Barak Ozama Beats"],
    ["baazu", "Baazü"],
    ["aquaverno", "Aquaverno"],
    ["hemorragia-cosmica", "Hemorragia Cósmica"],
  ] as const;
  for (const [slug, name] of entries) {
    const response = await page.goto("/artists/" + slug + "/");
    expect(response?.status()).toBe(200);
    await expect(page.locator("h1")).toHaveText(name);
    await expect(page.locator(".artist-detail-art img")).toHaveAttribute("alt", "Arte original de " + name);
    await expect.poll(async () => page.locator(".artist-detail-art img").evaluate(
      (element) => (element as HTMLImageElement).naturalWidth,
    )).toBeGreaterThan(0);
    await expect(page.locator('a[href="/#artists"]')).toHaveCount(1);
  }
});

test("canvas initializes or clearly exposes the original-art fallback", async ({ page }) => {
  await page.goto("/");
  await expect.poll(async () => page.locator("body").getAttribute("data-gl")).not.toBe("pending");
  const graphicsState = await page.locator("body").getAttribute("data-gl");
  expect(["live", "unavailable"]).toContain(graphicsState);
  if (graphicsState === "live") {
    await expect.poll(async () => page.locator("body").getAttribute("data-logo-ready")).toBe("yes");
    await expect(page.locator("#cosmos")).toBeVisible();
  } else {
    await expect(page.locator("#logo-plate img")).toBeVisible();
  }
});
