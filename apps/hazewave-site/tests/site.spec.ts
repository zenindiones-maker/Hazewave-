import { expect, test } from "@playwright/test";

test("renders semantic catalog and reaches PLAYING from one click", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator("#experience-title")).toHaveText("Escolha a fita.");
  await expect(page.locator("[data-track-id]")).toHaveCount(6);

  await page.locator("[data-track-id='aether-01']").dispatchEvent("click");
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

  await page.waitForTimeout(280);

  const box = await clone.boundingBox();
  const sourceBox = await page.locator(".artifact-field > [data-track-id='aether-01']").boundingBox();
  expect(box).not.toBeNull();
  expect(sourceBox).not.toBeNull();
  expect(box!.width).toBeGreaterThan(40);
  expect(box!.height).toBeGreaterThan(40);
  expect(box!.x + box!.width).toBeGreaterThan(0);
  expect(box!.x).toBeLessThan(await page.evaluate(() => window.innerWidth));
  expect(box!.y + box!.height).toBeGreaterThan(0);
  expect(box!.y).toBeLessThan(await page.evaluate(() => window.innerHeight));

  const cloneCenter = { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2 };
  const sourceCenter = {
    x: sourceBox!.x + sourceBox!.width / 2,
    y: sourceBox!.y + sourceBox!.height / 2
  };
  expect(Math.hypot(cloneCenter.x - sourceCenter.x, cloneCenter.y - sourceCenter.y)).toBeGreaterThan(28);

  await page.screenshot({ path: testInfo.outputPath("travel-visible.png"), fullPage: false });
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });
});


test("archive track re-enters the same physical playback flow", async ({ page }) => {
  await page.goto("/");
  const archiveButton = page.locator(".artist-index [data-archive-track-id='flora-02']");
  await archiveButton.scrollIntoViewIfNeeded();
  await archiveButton.click();

  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 7_000 });
  await expect(page.locator("#player-title")).toHaveText("Root Signal");
  await expect(page.locator("#premium-stage")).toHaveAttribute("data-artist", "flora");
  await expect(page.locator("#deck-slot .deck-loaded-artifact")).toHaveCount(1);
});


test("semantic section map follows typed track structure", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });
  await expect(page.locator("#player-sections .player-section-marker")).toHaveCount(3);
  await expect(page.locator("#player-section-label")).toHaveText(/INTRO|CHORUS|OUTRO/);
});


test("mobile object selection keeps the stage viewport stable", async ({ page }) => {
  const viewport = page.viewportSize();
  test.skip(!viewport || viewport.width > 600, "mobile-only viewport stability proof");

  await page.goto("/");
  const archive = page.locator("#archive");
  await archive.scrollIntoViewIfNeeded();
  await page.waitForTimeout(120);

  const artifact = page.locator("[data-track-id='aether-01']");
  const shell = artifact.locator(".artifact-shell");
  await expect(shell).toBeVisible();

  const box = await shell.boundingBox();
  expect(box).not.toBeNull();

  const x = box!.x + box!.width / 2;
  const y = box!.y + box!.height / 2;

  expect(x).toBeGreaterThan(0);
  expect(x).toBeLessThan(viewport!.width);
  expect(y).toBeGreaterThan(0);
  expect(y).toBeLessThan(viewport!.height);

  const hitTarget = await page.evaluate(({ x, y }) => {
    const hit = document.elementFromPoint(x, y);
    return Boolean(hit?.closest("[data-track-id='aether-01']"));
  }, { x, y });
  expect(hitTarget).toBe(true);

  const before = await page.evaluate(() => window.scrollY);
  await page.touchscreen.tap(x, y);
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });

  const after = await page.evaluate(() => window.scrollY);
  expect(Math.abs(after - before)).toBeLessThan(4);
});


test("mobile premium composition has no debug beacon or page overflow", async ({ page }) => {
  const viewport = page.viewportSize();
  test.skip(!viewport || viewport.width > 600, "mobile-only composition proof");

  await page.goto("/");
  await expect(page.locator(".deck-beacon")).toBeHidden();

  const overflow = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth
  }));

  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.width + 1);
  await expect(page.locator(".artifact-field")).toBeVisible();
  await expect(page.locator("[data-track-id='aether-01'] .artifact-contacts i")).toHaveCount(5);
  await expect(page.locator("#deck-slot .slot-contact-rail i")).toHaveCount(5);
});


test("keyboard arrows navigate physical music objects", async ({ page }) => {
  await page.goto("/");
  const first = page.locator("[data-track-id='aether-01']");
  const second = page.locator("[data-track-id='aether-02']");
  const last = page.locator("[data-track-id='flora-02']");

  await first.focus();
  await page.keyboard.press("ArrowRight");
  await expect(second).toBeFocused();

  await page.keyboard.press("End");
  await expect(last).toBeFocused();

  await page.keyboard.press("Home");
  await expect(first).toBeFocused();
});


test("track end becomes replayable without desynchronizing the Deck", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });

  const seek = page.locator("#player-seek");
  await seek.fill("23.85");
  await seek.dispatchEvent("change");

  await expect(page.locator("#state-label")).toHaveText("ENDED", { timeout: 2_000 });
  await expect(page.locator("#toggle-play")).toHaveText("REPLAY");
  await expect(page.locator("#deck-slot .deck-loaded-artifact")).toHaveCount(1);

  await page.locator("#toggle-play").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 2_000 });
  await expect(page.locator("#toggle-play")).toHaveText("PAUSE");
});


test("seeking while paused does not restart playback", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-track-id='aether-02']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });

  await page.locator("#toggle-play").click();
  await expect(page.locator("#state-label")).toHaveText("PAUSED");

  const seek = page.locator("#player-seek");
  await seek.fill("8");
  await seek.dispatchEvent("change");
  await page.waitForTimeout(180);

  await expect(page.locator("#state-label")).toHaveText("PAUSED");
  await expect(page.locator("#toggle-play")).toHaveText("PLAY");
  expect(Number(await seek.inputValue())).toBeGreaterThan(7.8);
});


test("diagnostics report real selection and audio-start latency", async ({ page }) => {
  await page.goto("/?diagnostics=1");
  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });

  const panel = page.locator("#hazewave-diagnostics");
  await expect(panel).toContainText("selectionToContactMs");
  await expect(panel).toContainText("contactToAudioMs");
  await expect(panel).toContainText("selectionToPlayingMs");
  await expect(page.locator("#premium-stage")).toHaveAttribute("data-selection-to-playing-ms", /\d+(\.\d+)?/);
});


test("three artist worlds remain visually reviewable in PLAYING", async ({ page }, testInfo) => {
  await page.goto("/");

  const worlds = [
    { trackId: "aether-01", artist: "aether" },
    { trackId: "monolith-01", artist: "monolith" },
    { trackId: "flora-01", artist: "flora" }
  ] as const;

  for (const world of worlds) {
    await page.locator(`[data-track-id='${world.trackId}']`).click();
    await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 7_000 });
    await expect(page.locator("#premium-stage")).toHaveAttribute("data-artist", world.artist);
    await page.waitForTimeout(220);
    await page.screenshot({
      path: testInfo.outputPath(`playing-world-${world.artist}.png`),
      fullPage: false
    });
  }
});


test("persistent owner artwork drives one reversible story world", async ({ page }) => {
  await page.goto("/");
  const backdrop = page.locator(".site-backdrop img");
  await expect(backdrop).toHaveAttribute("src", "/media/hazewave-world.jpg.webp");

  await page.locator(".dossier-zone").scrollIntoViewIfNeeded();
  await expect(page.locator("html")).toHaveAttribute("data-story-chapter", /artists|dossiers/, { timeout: 2_000 });

  await page.locator(".social-footer").scrollIntoViewIfNeeded();
  await expect(page.locator("html")).toHaveAttribute("data-story-chapter", "network", { timeout: 2_000 });

  await page.locator(".archive-hero").scrollIntoViewIfNeeded();
  await expect(page.locator("html")).toHaveAttribute("data-story-chapter", /threshold|archive/, { timeout: 2_000 });
});

test("physical wheel controls volume and track navigation", async ({ page }) => {
  await page.goto("/");
  await page.locator("#archive").scrollIntoViewIfNeeded();

  const volume = page.locator("#wheel-ring-control");
  await volume.focus();
  await expect(volume).toHaveAttribute("aria-valuenow", "82");
  await page.keyboard.press("ArrowRight");
  await expect(volume).toHaveAttribute("aria-valuenow", "87");

  await page.locator("[data-wheel-action='next']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });
  await expect(page.locator("#player-title")).toHaveText("Pale Current");

  await page.locator("[data-wheel-action='next']").click();
  await expect(page.locator("#player-title")).toHaveText("Soft Voltage", { timeout: 7_000 });
});

test("merch and social surfaces preserve direct-contact architecture", async ({ page }) => {
  await page.goto("/");
  await page.locator(".merch-zone").scrollIntoViewIfNeeded();
  await expect(page.locator(".merch-object")).toHaveCount(3);
  await expect(page.locator("[data-merch-id='collective-cap'] [data-merch-message]"))
    .toHaveAttribute("data-merch-message", "Fala Hazewave, quero o boné Collective");

  await expect(page.locator(".social-footer a")).toHaveText([
    "@virundun",
    "@barakozamabeats",
    "@indionesbala"
  ]);
});
