import { expect, test } from "@playwright/test";

test("renders semantic catalog and reaches PLAYING from one click", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator("#experience-title")).toHaveText("Toque. Conecte. Escute.");
  await expect(page.locator("[data-track-id]")).toHaveCount(6);

  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });
  await expect(page.locator("#player-title")).toHaveText("Pale Current");
  await expect(page.locator("[data-track-id='aether-01']")).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({ path: testInfo.outputPath("playing.png"), fullPage: true });
});

test("pause, resume and track replacement preserve coherent UI state", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-track-id='aether-02']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });

  await page.locator("#toggle-play").click();
  await expect(page.locator("#state-label")).toHaveText("PAUSED");
  await expect(page.locator("#toggle-play")).toHaveText("PLAY");

  await page.locator("#toggle-play").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING");
  await expect(page.locator("#toggle-play")).toHaveText("PAUSE");

  await page.locator("[data-track-id='monolith-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 7_000 });
  await expect(page.locator("#player-title")).toHaveText("Weightless Iron");
});

test("reduced motion keeps selection and playback functional", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.locator("[data-track-id='flora-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 3_000 });
  await expect(page.locator("#player-title")).toHaveText("Moss Circuit");
});


test("opt-in diagnostics exposes real runtime proof fields", async ({ page }) => {
  await page.goto("/?diagnostics=1");
  const panel = page.locator("#hazewave-diagnostics");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("HAZEWAVE_WAVE_SITE_V1");
  await expect(panel).toContainText("frameP95Ms");
  await page.waitForTimeout(1200);
  await expect(page.locator("html")).toHaveAttribute("data-quality-tier", /LOW|MEDIUM|HIGH|ULTRA/);
});


test("normal experience keeps diagnostics opt-in", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#hazewave-diagnostics")).toHaveCount(0);
  await expect(page.locator(".artifact-field")).toBeVisible();
  await expect(page.locator("[data-track-id='aether-01']")).toBeVisible();
});


test("premium stage replaces WebGL hero with cinematic resonance objects", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#premium-stage")).toBeVisible();
  await expect(page.locator("#resonance-deck")).toBeVisible();
  await expect(page.locator(".resonance-artifact")).toHaveCount(6);
  await expect(page.locator("#resonance-canvas")).toHaveCount(0);
  await expect(page.locator("#runtime-label")).toContainText("CINEMATIC DOM");
});


test("premium idle composition is reviewable", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator("#resonance-deck")).toBeVisible();
  await expect(page.locator(".resonance-artifact")).toHaveCount(6);
  await page.waitForTimeout(900);
  await page.screenshot({ path: testInfo.outputPath("idle-premium.png"), fullPage: true });
});


test("artist world and physical dock remain coherent", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });
  await expect(page.locator("#premium-stage")).toHaveAttribute("data-artist", "aether");
  await expect(page.locator("#world-release")).toHaveText("GLASS SIGNAL");
  await expect(page.locator("#world-track")).toHaveText("PALE CURRENT");
  await expect(page.locator("#deck-slot .deck-loaded-artifact")).toHaveCount(1);
  await expect(page.locator(".artist-index-card")).toHaveCount(3);
});


test("seek transport is wired to audio state", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });

  const seek = page.locator("#player-seek");
  await expect(seek).toBeEnabled();
  await seek.fill("5");
  await seek.dispatchEvent("change");
  await page.waitForTimeout(180);

  const value = Number(await seek.inputValue());
  expect(value).toBeGreaterThan(4.8);
  await expect(page.locator("#player-time-total")).toHaveText("0:24");
});


test("cinematic object remains visible during mobile travel", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.locator("[data-track-id='aether-01']").click();

  await expect(page.locator("#state-label")).toHaveText("TRAVEL", { timeout: 2_000 });
  const clone = page.locator(".cinematic-artifact-clone");
  await expect(clone).toHaveCount(1);
  await expect(clone).toBeVisible();

  const box = await clone.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThan(40);
  expect(box!.height).toBeGreaterThan(40);
  expect(box!.x + box!.width).toBeGreaterThan(0);
  expect(box!.x).toBeLessThan(await page.evaluate(() => window.innerWidth));
  expect(box!.y + box!.height).toBeGreaterThan(0);
  expect(box!.y).toBeLessThan(await page.evaluate(() => window.innerHeight));

  await page.screenshot({ path: testInfo.outputPath("travel-visible.png"), fullPage: false });
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });
});


test("archive track re-enters the same physical playback flow", async ({ page }) => {
  await page.goto("/");
  const archiveButton = page.getByRole("button", { name: /Tocar Root Signal no Resonance Deck/ });
  await archiveButton.scrollIntoViewIfNeeded();
  await archiveButton.click();

  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 7_000 });
  await expect(page.locator("#player-title")).toHaveText("Root Signal");
  await expect(page.locator("#premium-stage")).toHaveAttribute("data-artist", "flora");
  await expect(page.locator("#deck-slot .deck-loaded-artifact")).toHaveCount(1);
});
