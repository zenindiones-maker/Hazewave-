import { expect, test, type Page } from "@playwright/test";
import { ownerConfirmedSocialHandles, productionArtists, productionIdentity } from "../src/data/productionAuthority";

async function focusStorySection(page: Page, selector: string): Promise<void> {
  const locator = page.locator(selector);
  await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const top = window.scrollY + rect.top;
    const probeInside = Math.min(
      Math.max(rect.height * 0.32, 24),
      window.innerHeight * 0.38
    );
    const target = top + probeInside - window.innerHeight * 0.5;
    window.scrollTo({ top: Math.max(0, target), behavior: "auto" });
  });

  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
      )
  );
}

async function focusStoryFraction(
  page: Page,
  selector: string,
  fraction: number
): Promise<void> {
  const locator = page.locator(selector);
  await locator.evaluate((element, rawFraction) => {
    const fraction = Math.max(0, Math.min(1, Number(rawFraction)));
    const rect = element.getBoundingClientRect();
    const top = window.scrollY + rect.top;
    const probeInside = Math.max(1, rect.height * fraction);
    const target = top + probeInside - window.innerHeight * 0.5;
    window.scrollTo({ top: Math.max(0, target), behavior: "auto" });
  }, fraction);

  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
      )
  );
}

test("renders semantic catalog and reaches PLAYING from one click", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator("#experience-title")).toHaveText("Escolha a fita.");
  await expect(page.locator("[data-artist-cassette='true']")).toHaveCount(3);

  await page.locator("[data-track-id='aether-01']").dispatchEvent("click");
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });
  await expect(page.locator("#player-title")).toHaveText("Pale Current");
  await expect(page.locator("[data-track-id='aether-01']")).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({ path: testInfo.outputPath("playing.png"), fullPage: true });
});

test("pause, resume and track replacement preserve coherent UI state", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 6_000 });

  await page.locator("#toggle-play").click();
  await expect(page.locator("#state-label")).toHaveText("PAUSED");
  await expect(page.locator("#toggle-play")).toHaveText("PLAY");

  await page.locator("#toggle-play").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING");
  await expect(page.locator("#toggle-play")).toHaveText("PAUSE");

  await page.locator("[data-wheel-action='next']").click();
  await expect(page.locator("#player-title")).toHaveText("Soft Voltage", { timeout: 6_000 });
  await expect(page.locator("[data-track-id='aether-01']")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#deck-slot .deck-loaded-artifact")).toHaveCount(1);

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
  await expect(page.locator(".resonance-artifact")).toHaveCount(3);
  await expect(page.locator("#resonance-canvas")).toHaveCount(0);
  await expect(page.locator("#runtime-label")).toContainText("CINEMATIC DOM");
});


test("premium idle composition is reviewable", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator("#resonance-deck")).toBeVisible();
  await expect(page.locator(".resonance-artifact")).toHaveCount(3);
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
  await expect(page.locator("[data-artist-chapter]")).toHaveCount(3);
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

  const sourceBox = await page.locator(".artifact-field > [data-track-id='aether-01']").boundingBox();
  expect(sourceBox).not.toBeNull();

  const sourceCenter = {
    x: sourceBox!.x + sourceBox!.width / 2,
    y: sourceBox!.y + sourceBox!.height / 2
  };

  await expect.poll(
    async () => {
      const movingBox = await clone.boundingBox();
      if (!movingBox) return 0;
      const cloneCenter = {
        x: movingBox.x + movingBox.width / 2,
        y: movingBox.y + movingBox.height / 2
      };
      return Math.hypot(cloneCenter.x - sourceCenter.x, cloneCenter.y - sourceCenter.y);
    },
    {
      message: "selected cassette must visibly leave its shelf position during TRAVEL",
      timeout: 1_200,
      intervals: [60, 80, 100]
    }
  ).toBeGreaterThan(28);

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
  const second = page.locator("[data-track-id='monolith-01']");
  const last = page.locator("[data-track-id='flora-01']");

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
  const secondary = page.locator(".artist-index [data-archive-track-id='aether-02']");
  await secondary.scrollIntoViewIfNeeded();
  await secondary.click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 7_000 });

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

  await focusStorySection(page, "#dossiers");
  await expect(page.locator("html")).toHaveAttribute("data-story-chapter", "dossiers", { timeout: 2_000 });

  await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "auto" }));
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.locator("html")).toHaveAttribute("data-story-chapter", "network", { timeout: 2_000 });

  await focusStorySection(page, "#threshold");
  await expect(page.locator("html")).toHaveAttribute("data-story-chapter", /threshold|archive/, { timeout: 2_000 });
});

test("physical wheel controls volume and track navigation", async ({ page }) => {
  await page.goto("/");
  await page.locator("#archive").scrollIntoViewIfNeeded();
  await page.locator("#player-wheel").scrollIntoViewIfNeeded();

  const nextButton = page.locator("[data-wheel-action='next']");
  const nextBox = await nextButton.boundingBox();
  expect(nextBox).not.toBeNull();

  const nextHit = await page.evaluate(({ x, y }) => {
    const hit = document.elementFromPoint(x, y);
    return Boolean(hit?.closest("[data-wheel-action='next']"));
  }, {
    x: nextBox!.x + nextBox!.width / 2,
    y: nextBox!.y + nextBox!.height / 2
  });
  expect(nextHit).toBe(true);

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

test("merch remains fail-closed while owner-authorized social handles stay usable", async ({ page }) => {
  await page.goto("/");
  await page.locator(".merch-zone").scrollIntoViewIfNeeded();
  await expect(page.locator(".merch-object")).toHaveCount(2);
  await expect(page.locator("[data-merch-id='hazewave-cap'] .merch-contact")).toBeDisabled();
  await expect(page.locator("[data-merch-id='hazewave-tee'] .merch-contact")).toBeDisabled();

  await expect(page.locator(".social-footer a")).toHaveText([
    "@virundun",
    "@barakozamabeats",
    "@indionesbala"
  ]);
});


test("archive exposes one physical cassette per artist while wheel owns tracklist", async ({ page }) => {
  await page.goto("/");
  await page.locator("#archive").scrollIntoViewIfNeeded();

  const cassettes = page.locator("[data-artist-cassette='true']");
  await expect(cassettes).toHaveCount(3);
  expect(await cassettes.evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-loaded"))
  )).toEqual(["false", "false", "false"]);

  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#player-title")).toHaveText("Pale Current", { timeout: 6_000 });
  await expect(page.locator("#deck-slot .deck-loaded-artifact")).toHaveCount(1);

  await page.locator("[data-wheel-action='next']").click();
  await expect(page.locator("#player-title")).toHaveText("Soft Voltage", { timeout: 6_000 });
  await expect(page.locator("#premium-stage")).toHaveAttribute("data-artist", "aether");
  await expect(page.locator("#deck-slot .deck-loaded-artifact")).toHaveCount(1);
  await expect(page.locator("[data-track-id='aether-01']")).toHaveAttribute("aria-pressed", "true");
});


test("production content stays fail-closed until owner-authorized assets arrive", () => {
  expect(productionIdentity.projectName.state).toBe("OWNER_CONFIRMED");
  expect(productionIdentity.worldArtwork.state).toBe("OWNER_CONFIRMED");
  expect(productionIdentity.finalArtistRoster.state).toBe("UNSET");
  expect(productionIdentity.finalAudioCatalog.state).toBe("UNSET");
  expect(productionIdentity.whatsappDestination.state).toBe("UNSET");
  expect(productionArtists).toHaveLength(0);
  expect(ownerConfirmedSocialHandles.map((entry) => entry.handle)).toEqual([
    "@virundun",
    "@barakozamabeats",
    "@indionesbala"
  ]);
});


test("wheel LIST mode exposes the loaded artist tracklist", async ({ page }) => {
  await page.goto("/");
  await page.locator("#archive").scrollIntoViewIfNeeded();
  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 7_000 });

  await page.locator("[data-wheel-action='archive']").click();
  await expect(page.locator("#player-wheel")).toHaveAttribute("data-mode", "tracks");
  await expect(page.locator("#deck-screen")).toHaveAttribute("data-view", "list");
  await expect(page.locator("#deck-tracklist button")).toHaveCount(2);
  await expect(page.locator("#deck-tracklist [data-deck-track-id='aether-01']")).toHaveAttribute("data-active", "true");

  await page.locator("[data-wheel-action='next']").click();
  await expect(page.locator("#player-title")).toHaveText("Soft Voltage", { timeout: 7_000 });
  await expect(page.locator("#deck-tracklist [data-deck-track-id='aether-02']")).toHaveAttribute("data-active", "true");

  await page.locator("[data-wheel-action='archive']").click();
  await expect(page.locator("#player-wheel")).toHaveAttribute("data-mode", "volume");
  await expect(page.locator("#deck-screen")).toHaveAttribute("data-view", "now");
});


test("rapid wheel input keeps the latest requested track instead of erroring", async ({ page }) => {
  await page.goto("/");
  await page.locator("#archive").scrollIntoViewIfNeeded();

  await page.locator("[data-track-id='aether-01']").click();
  await expect(page.locator("#player-title")).toHaveText("Pale Current", { timeout: 3_000 });

  await page.locator("[data-wheel-action='next']").click();
  await expect(page.locator("#player-title")).toHaveText("Soft Voltage", { timeout: 8_000 });
  await expect(page.locator("#state-label")).toHaveText("PLAYING", { timeout: 8_000 });
  await expect(page.locator("#runtime-label")).not.toContainText("ERROR");
});


test("story rail follows the persistent-world chapter conductor", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".story-rail a")).toHaveCount(6);

  await page.locator(".story-rail [data-story-link='dossiers']").click();
  await expect(page.locator("html")).toHaveAttribute("data-story-chapter", "dossiers", { timeout: 3_000 });
  await expect(page.locator(".story-rail [data-story-link='dossiers']")).toBeVisible();

  await page.locator(".story-rail [data-story-link='archive']").click();
  await expect(page.locator("#archive")).toBeInViewport({ ratio: 0.3 });
  await expect(page.locator("html")).toHaveAttribute("data-story-chapter", "archive", { timeout: 2_500 });
});


test("living world scroll state is reversible and deterministic", async ({ page }) => {
  await page.goto("/");

  const progress = async () =>
    Number(
      await page.locator("html").evaluate((element) =>
        getComputedStyle(element).getPropertyValue("--story-global-progress").trim()
      )
    );

  await focusStorySection(page, "#threshold");
  await expect(page.locator("html")).toHaveAttribute("data-story-beat", "WORLD_SLEEP");
  const start = await progress();

  await focusStorySection(page, "#artist-worlds");
  await expect(page.locator("html")).toHaveAttribute(
    "data-story-beat",
    /ARTIST_DISCOVERY|ARTIST_FOCUS/,
    { timeout: 2_500 }
  );
  const middle = await progress();
  expect(middle).toBeGreaterThan(start);

  await focusStorySection(page, "#objects");
  await expect(page.locator("html")).toHaveAttribute(
    "data-story-beat",
    /MERCH_APPROACH|FINAL_DESCENT/,
    { timeout: 2_500 }
  );
  const end = await progress();
  expect(end).toBeGreaterThan(middle);

  await focusStorySection(page, "#threshold");
  await expect(page.locator("html")).toHaveAttribute(
    "data-story-beat",
    "WORLD_SLEEP",
    { timeout: 2_500 }
  );
  const reversed = await progress();
  expect(reversed).toBeLessThan(middle);
});

test("living world keeps the owner artwork as authoritative fallback", async ({ page }) => {
  await page.goto("/");

  const host = page.locator(".site-backdrop");
  const image = host.locator("img");

  await expect(image).toHaveAttribute("src", "/media/hazewave-world.jpg.webp");
  await expect(host).toHaveAttribute(
    "data-world-runtime",
    /webgl2|css-fallback|fallback/
  );

  const viewport = page.viewportSize();
  if (viewport && viewport.width <= 430) {
    await expect(host).toHaveAttribute("data-world-runtime", "css-fallback");
  }
});

test("WebGL world context loss falls back and restores without blanking essential content", async ({ page }) => {
  const viewport = page.viewportSize();
  test.skip(!viewport || viewport.width <= 430, "WebGL world is intentionally disabled on LOW mobile tier");

  await page.goto("/");
  const host = page.locator(".site-backdrop");

  await expect(host).toHaveAttribute(
    "data-world-runtime",
    /webgl2|fallback/,
    { timeout: 4_000 }
  );

  const canvas = page.locator(".living-world-canvas");
  if (await canvas.count() === 0) test.skip(true, "WebGL2 unavailable in this browser runtime");

  const extensionAvailable = await canvas.evaluate((element) => {
    const gl = (element as HTMLCanvasElement).getContext("webgl2");
    return Boolean(gl?.getExtension("WEBGL_lose_context"));
  });

  test.skip(!extensionAvailable, "WEBGL_lose_context unavailable in this browser runtime");

  await canvas.evaluate((element) => {
    const gl = (element as HTMLCanvasElement).getContext("webgl2");
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
  });

  await expect(host).toHaveAttribute("data-world-runtime", "fallback-context-lost", {
    timeout: 3_000
  });
  await expect(host.locator("img")).toBeVisible();

  await canvas.evaluate((element) => {
    const gl = (element as HTMLCanvasElement).getContext("webgl2");
    gl?.getExtension("WEBGL_lose_context")?.restoreContext();
  });

  await expect(host).toHaveAttribute(
    "data-world-runtime",
    /webgl2|fallback-restore-failed/,
    { timeout: 4_000 }
  );
  await expect(host.locator("img")).toBeVisible();
});

test("living world checkpoints produce the full narrative visual proof matrix", async ({ page }, testInfo) => {
  const capture = async (name: string) => {
    await page.screenshot({
      path: testInfo.outputPath(`${testInfo.project.name}-${name}.png`),
      fullPage: false
    });
  };

  const runBeatSequence = async (prefix: string) => {
    await focusStorySection(page, "#threshold");
    await capture(`${prefix}-world-sleep`);

    await focusStoryFraction(page, "#archive", 0.36);
    await capture(`${prefix}-world-awakening`);

    await focusStoryFraction(page, "[data-artist-chapter='aether']", 0.28);
    await capture(`${prefix}-artist-01-enter`);

    const aetherFocus = page.locator("[data-artist-focus='aether']");
    await aetherFocus.click();
    await expect(page.locator("[data-artist-focus-panel='aether']")).toHaveAttribute("data-open", "true");
    await capture(`${prefix}-artist-01-focus`);

    await aetherFocus.click();
    await expect(page.locator("[data-artist-focus-panel='aether']")).toHaveAttribute("data-open", "false");

    await focusStoryFraction(page, "[data-artist-chapter='aether']", 0.88);
    await capture(`${prefix}-artist-transition`);

    await focusStoryFraction(page, "[data-artist-chapter='monolith']", 0.3);
    await capture(`${prefix}-artist-02-enter`);

    await focusStoryFraction(page, "[data-artist-chapter='flora']", 0.3);
    await capture(`${prefix}-artist-03-enter`);

    await focusStoryFraction(page, "#objects", 0.24);
    await capture(`${prefix}-merch-approach`);

    await page.evaluate(() =>
      window.scrollTo({
        top: document.documentElement.scrollHeight,
        behavior: "auto"
      })
    );
    await page.evaluate(
      () =>
        new Promise<void>((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
        )
    );
    await capture(`${prefix}-merch-final`);
  };

  await page.goto("/");

  const viewport = page.viewportSize();
  if (!viewport) throw new Error("VIEWPORT_UNAVAILABLE");

  if (testInfo.project.name === "chromium-desktop") {
    await page.setViewportSize({ width: 1440, height: 900 });
    await runBeatSequence("desktop-standard");

    await page.setViewportSize({ width: 1920, height: 1080 });
    await runBeatSequence("desktop-wide");
  } else {
    await runBeatSequence("mobile-portrait");
  }
});


test("artist journey resolves one deterministic world at a time", async ({ page }) => {
  await page.goto("/");

  const chapters = [
    { id: "aether", locator: "[data-artist-chapter='aether']" },
    { id: "monolith", locator: "[data-artist-chapter='monolith']" },
    { id: "flora", locator: "[data-artist-chapter='flora']" }
  ] as const;

  for (const chapter of chapters) {
    await page.locator(chapter.locator).scrollIntoViewIfNeeded();
    await expect(page.locator("html")).toHaveAttribute(
      "data-scroll-artist",
      chapter.id,
      { timeout: 2_500 }
    );
    await expect(page.locator(chapter.locator)).toHaveAttribute(
      "data-authority",
      "DEMO_ONLY"
    );
  }
});


test("artist focus portal is reversible and preserves keyboard focus", async ({ page }) => {
  await page.goto("/");

  const chapter = page.locator("[data-artist-chapter='aether']");
  await focusStorySection(page, "[data-artist-chapter='aether']");

  const trigger = chapter.locator("[data-artist-focus='aether']");
  const panel = chapter.locator("[data-artist-focus-panel='aether']");

  await trigger.focus();
  await trigger.press("Enter");

  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await expect(panel).toHaveAttribute("data-open", "true");
  await expect(chapter).toHaveAttribute("data-focused", "true");
  await expect(page.locator("html")).toHaveAttribute("data-focused-artist", "aether");

  await page.keyboard.press("Escape");

  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(panel).toHaveAttribute("data-open", "false");
  await expect(chapter).toHaveAttribute("data-focused", "false");
  await expect(page.locator("html")).not.toHaveAttribute("data-focused-artist", /.+/);
  await expect(trigger).toBeFocused();
});

test("video portals remain fail-closed and lazy while production video authority is unset", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator("[data-video-source]")).toHaveCount(0);
  await expect(page.locator("[data-video-portal]")).toHaveCount(3);
  await expect(page.locator("[data-video-portal] button:disabled")).toHaveCount(3);
  await expect(page.locator("[data-video-mount] iframe")).toHaveCount(0);
  await expect(page.locator("[data-video-mount] video")).toHaveCount(0);
});
