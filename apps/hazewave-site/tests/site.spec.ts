import { expect, test } from "@playwright/test";

test("renders semantic catalog and reaches PLAYING from one click", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Toque\. Conecte\. Escute\./ })).toBeVisible();
  await expect(page.locator("[data-track-id]")).toHaveCount(6);

  await page.getByRole("button", { name: /Tocar Pale Current/ }).click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });
  await expect(page.locator("#player-title")).toHaveText("Pale Current");
  await expect(page.locator("[data-track-id='aether-01']")).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({ path: testInfo.outputPath("playing.png"), fullPage: true });
});

test("pause, resume and track replacement preserve coherent UI state", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Tocar Soft Voltage/ }).click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });

  await page.locator("#toggle-play").click();
  await expect(page.locator("#state-label")).toHaveText("PAUSED");
  await expect(page.locator("#toggle-play")).toHaveText("PLAY");

  await page.locator("#toggle-play").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING");
  await expect(page.locator("#toggle-play")).toHaveText("PAUSE");

  await page.getByRole("button", { name: /Tocar Weightless Iron/ }).click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 7_000 });
  await expect(page.locator("#player-title")).toHaveText("Weightless Iron");
});

test("reduced motion keeps selection and playback functional", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByRole("button", { name: /Tocar Moss Circuit/ }).click();
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
  await expect(page.getByRole("button", { name: /Tocar Pale Current/ })).toBeVisible();
});


test("premium stage replaces WebGL hero with cinematic resonance objects", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#premium-stage")).toBeVisible();
  await expect(page.locator("#resonance-deck")).toBeVisible();
  await expect(page.locator(".resonance-artifact")).toHaveCount(6);
  await expect(page.locator("#resonance-canvas")).toHaveCount(0);
  await expect(page.locator("#runtime-label")).toContainText("CINEMATIC DOM");
});
