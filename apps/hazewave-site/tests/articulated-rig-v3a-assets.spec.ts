import { test, expect, type Page } from "@playwright/test";

// Regression gate for the owner-approved illustrated source: a pass requires
// decoded source art plus real independent hardware motion, not just changing labels.
const route = "/experimental/articulated-rig-v3a.html";
type PhysicalState = {
  progress: number;
  activePads: number;
  activeKnobs: number;
  activeSpeakers: number;
  stroke: number;
  mounted: number;
};
async function at(page: Page, progress: number) {
  await page.evaluate((p) => {
    const stage = document.querySelector<HTMLElement>("#journey");
    if (!stage) throw Error("RIG_MISSING_STORY_STAGE");
    const start = stage.getBoundingClientRect().top + scrollY;
    scrollTo({ top: start + (stage.offsetHeight - innerHeight) * p, behavior: "instant" });
  }, progress);
  await expect.poll(async () => page.evaluate(
    () => (window as Window & { __HAZEWAVE_RIG_V3: PhysicalState }).__HAZEWAVE_RIG_V3.progress
  )).toBeGreaterThanOrEqual(progress - 0.018);
}
async function measured(page: Page) {
  return page.evaluate(() => {
    const state = (window as Window & { __HAZEWAVE_RIG_V3: PhysicalState }).__HAZEWAVE_RIG_V3;
    const node = (selector: string) => document.querySelector<HTMLElement>(selector);
    return {
      state: { ...state },
      knob: node('img[data-rig-id="knob_00"]')?.style.transform ?? "",
      speaker: node('img[data-rig-id="speaker_00"]')?.style.transform ?? "",
      padOverlay: node('img[data-pad-id="pad_00"]')?.style.opacity ?? "",
      trace: node("#soundpath")?.style.strokeDashoffset ?? "",
      overflow: document.documentElement.scrollWidth - innerWidth,
    };
  });
}

for (const viewport of [{ width: 360, height: 800 }, { width: 393, height: 852 }]) {
  test(`V3A original artwork decoded and hardware physically articulated at ${viewport.width}x${viewport.height}`, async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.setViewportSize(viewport);
    await page.goto(route);
    await expect.poll(async () => page.evaluate(
      () => Boolean((window as Window & { __HAZEWAVE_RIG_V3?: { ready: boolean } }).__HAZEWAVE_RIG_V3?.ready)
    )).toBe(true);

    // A fully broken data URL must fail even if the JS claims 'mounted:24'.
    const decoded = await page.locator("img").evaluateAll(images => images.map(img => {
      const element = img as HTMLImageElement;
      return { src: element.currentSrc.slice(0, 40), ready: element.complete && element.naturalWidth > 0 };
    }));
    expect(decoded.length).toBeGreaterThanOrEqual(38);
    expect(decoded.filter(image => !image.ready)).toEqual([]);
    await expect(page.locator("img[data-rig-id]")).toHaveCount(24);
    await expect(page.locator("img[data-pad-id]")).toHaveCount(12);

    const idle = await measured(page);
    expect(idle.state.activePads).toBe(0);
    expect(idle.state.activeKnobs).toBe(0);
    expect(idle.state.activeSpeakers).toBe(0);

    await at(page, .7);
    const mid = await measured(page);
    expect(mid.state.activePads).toBeGreaterThan(8);
    expect(mid.state.activeKnobs).toBeGreaterThan(4);
    expect(mid.knob).not.toBe(idle.knob);
    expect(mid.padOverlay).not.toBe(idle.padOverlay);

    await at(page, 1);
    const full = await measured(page);
    expect(full.state.activePads).toBe(12);
    expect(full.state.activeKnobs).toBe(8);
    expect(full.state.activeSpeakers).toBe(4);
    expect(full.speaker).not.toBe(idle.speaker);
    expect(full.state.stroke).toBeGreaterThan(.99);

    await at(page, 0);
    const reset = await measured(page);
    expect(reset.state.activePads).toBe(0);
    expect(reset.state.activeKnobs).toBe(0);
    expect(reset.state.activeSpeakers).toBe(0);
    expect(reset.trace).toBe(idle.trace);
    expect(reset.knob).toBe(idle.knob);
    expect(reset.padOverlay).toBe(idle.padOverlay);
    expect(reset.overflow).toBeLessThanOrEqual(1);
    expect(errors).toEqual([]);
    await page.screenshot({
      path: `test-results/v3a-articulation-${viewport.width}-${info.project.name}.png`,
      animations: "disabled",
    });
  });
}
