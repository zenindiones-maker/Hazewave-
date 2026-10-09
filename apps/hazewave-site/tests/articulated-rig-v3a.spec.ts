import { test, expect, type Page } from "@playwright/test";

const URL = "/experimental/articulated-rig-v3a.html";
type RigState = { ready: boolean; mounted: number; progress: number; activePads: number; activeKnobs: number; activeSpeakers: number; stroke: number; ambient: number };
async function state(page: Page): Promise<RigState> {
  return page.evaluate(() => (window as Window & { __HAZEWAVE_RIG_V3: RigState }).__HAZEWAVE_RIG_V3);
}
async function toProgress(page: Page, p: number) {
  await page.evaluate((value) => {
    const el = document.getElementById("journey");
    if (!el) throw Error("ARTICULATED_RIG_JOURNEY_MISSING");
    const top = el.getBoundingClientRect().top + window.scrollY;
    window.scrollTo(0, top + Math.max(1, el.offsetHeight - innerHeight) * value);
  }, p);
  await expect.poll(async () => (await state(page)).progress, { timeout: 5000 }).toBeGreaterThanOrEqual(Math.max(0, p - .015));
}

test("real approved MPC cutouts are present and reverse to idle", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto(URL);
  await expect.poll(async () => (await state(page))?.ready).toBe(true);
  expect((await state(page)).mounted).toBe(24);
  await expect(page.locator("#machine img.rig-part")).toHaveCount(36);
  const start = await state(page);
  expect(start.activePads).toBe(0);
  await toProgress(page, .45);
  const mid = await state(page);
  expect(mid.activePads).toBeGreaterThan(3);
  expect(mid.activeKnobs).toBeGreaterThan(0);
  await page.screenshot({ path: `test-results/rig-v3a-mid-${testInfo.project.name}.png`, animations: "disabled" });
  await toProgress(page, .99);
  const end = await state(page);
  expect(end.activePads).toBe(12);
  expect(end.activeKnobs).toBe(8);
  expect(end.activeSpeakers).toBe(4);
  expect(end.stroke).toBeGreaterThan(.98);
  await page.screenshot({ path: `test-results/rig-v3a-end-${testInfo.project.name}.png`, animations: "disabled" });
  await toProgress(page, 0);
  const reset = await state(page);
  expect(reset.activePads).toBe(0);
  expect(reset.activeKnobs).toBe(0);
  expect(reset.activeSpeakers).toBe(0);
  expect(reset.stroke).toBe(0);
  expect(errors).toEqual([]);
});

test("rig is touch-friendly, horizontal overflow zero and ambient motion independent", async ({ page }) => {
  await page.goto(URL);
  await expect.poll(async () => (await state(page))?.ready).toBe(true);
  const o = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  expect(o).toBeLessThanOrEqual(1);
  const first = await state(page);
  await page.waitForTimeout(250);
  const next = await state(page);
  expect(next.progress).toBe(first.progress);
  expect(next.ambient).toBeGreaterThan(first.ambient);
});

test("reduced-motion disables idle motion but scroll narrative stays usable", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(URL);
  await expect.poll(async () => (await state(page))?.ready).toBe(true);
  await page.waitForTimeout(200);
  expect((await state(page)).ambient).toBe(0);
  await toProgress(page, .9);
  expect((await state(page)).activePads).toBe(12);
});
