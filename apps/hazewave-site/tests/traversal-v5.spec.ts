import { expect, test, type Page } from "@playwright/test";

async function ready(page: Page) {
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "webgl2",
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-world-ready",
    "true",
  );
}

async function scrub(page: Page, progress: number) {
  await page.evaluate((p) => {
    const distance = document.querySelector<HTMLElement>("#journey-distance")!;
    window.scrollTo(0, distance.offsetHeight * p);
  }, progress);
}

test("Explore traverses the discovered real artist and reverses to its signal", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  const signal = page.locator('[data-artist-signal="indionesbala"]');
  await signal.focus();
  await expect(signal).toHaveAttribute("data-revealed", "true");
  await page.locator('[data-primary-action="explore"]').click();
  await expect(page.locator("#journey-artist")).toHaveText("Indionesbala");
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey-act",
    "discover",
  );
  await scrub(page, 0.45);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey-act",
    "traverse",
  );
  await expect(page).not.toHaveURL(/artist=/);
  await scrub(page, 1);
  await expect(page).toHaveURL(/artist=indionesbala/);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey-act",
    "arrival",
  );
  await expect(
    page.locator('[data-artist-world="indionesbala"]'),
  ).toHaveAttribute("data-active", "true");
  await scrub(page, 0);
  await expect(page).not.toHaveURL(/artist=/);
  await expect(signal).toHaveAttribute("data-revealed", "true");
  await page.locator("#journey-exit").click();
  await expect(page.locator('[data-primary-action="explore"]')).toBeFocused();
});

test("explicit motion control stops traversal and honors system reduction", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  const motion = page.locator("#motion-toggle");
  await expect(motion).toHaveAttribute("aria-pressed", "false");
  await page.locator('[data-primary-action="explore"]').click();
  await scrub(page, 0.45);
  await motion.click();
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey",
    "false",
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-motion",
    "reduced",
  );
  await expect(motion).toHaveAttribute("aria-pressed", "true");
  await motion.click();
  await ready(page);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-motion",
    "full",
  );
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-motion",
    "reduced",
  );
  await motion.click();
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-motion",
    "reduced",
  );
  await expect(motion).toHaveAttribute("aria-pressed", "true");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-motion",
    "reduced",
  );
  await motion.click();
  await ready(page);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-motion",
    "full",
  );
});

test("resuming movement loads a world selected while movement was paused", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  await page.locator("#motion-toggle").click();
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "css-fallback",
  );
  await page.locator('[data-primary-action="search"]').click();
  await page.locator('[data-search-artist="indionesbala"]').click();
  await expect(page).toHaveURL(/artist=indionesbala/);
  await page.locator("#motion-toggle").click();
  await ready(page);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-asset-unavailable",
    "false",
  );
  expect(
    Number(
      await page
        .locator("#living-field")
        .getAttribute("data-field-texture-bytes"),
    ),
  ).toBeGreaterThan(3_000_000);
});

test("native scrolling starts the journey without an Explore click or focus steal", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  const field = page.locator("#living-field");
  await expect(field).toHaveAttribute("data-scroll-ready", "true");
  await expect(page.locator("#journey-distance")).toBeVisible();
  const searchButton = page.locator('[data-primary-action="search"]');
  await searchButton.focus();
  const before = await page.evaluate(() => history.length);
  await scrub(page, 0.08);
  await expect(field).toHaveAttribute("data-journey", "true");
  await expect(field).toHaveAttribute("data-journey-act", "traverse");
  await expect(searchButton).toBeFocused();
  expect(await page.evaluate(() => history.length)).toBe(before);
  await scrub(page, 1);
  await expect(page).toHaveURL(/artist=indionesbala/);
  expect(await page.evaluate(() => history.length)).toBe(before + 1);
  await scrub(page, 0);
  await expect(page).not.toHaveURL(/artist=/);
  expect(
    await page
      .locator(".signal-field")
      .evaluate((element) => (element as HTMLElement).inert),
  ).toBe(false);
  await expect(
    page.locator('[data-artist-signal="indionesbala"]'),
  ).toHaveAttribute("data-revealed", "true");
  await page.locator('[data-artist-signal="indionesbala"]').focus();
  await expect(page.locator("#journey-artist")).toHaveText("Indionesbala");
  await scrub(page, 1);
  await expect(page).toHaveURL(/artist=indionesbala/);
  expect(await page.evaluate(() => history.length)).toBe(before + 1);
});

test("native descent holds the public artist and reverses through the same chapter", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  const order = ["indionesbala"];
  const historyBefore = await page.evaluate(() => history.length);
  for (const [chapter, id] of order.entries()) {
    await scrub(page, 0.045 + ((chapter + 0.84) / order.length) * 0.955);
    await expect(page.locator("#living-field")).toHaveAttribute(
      "data-journey-phase",
      "hold",
    );
    await expect(page.locator("#living-field")).toHaveAttribute(
      "data-journey-chapter",
      String(chapter + 1),
    );
    await expect(page).toHaveURL(new RegExp(`artist=${id}`));
    await expect(page.locator(`[data-artist-world="${id}"]`)).toHaveAttribute(
      "data-active",
      "true",
    );
  }
  expect(await page.evaluate(() => history.length)).toBe(historyBefore + 1);
  for (let chapter = order.length - 1; chapter >= 0; chapter--) {
    await scrub(page, 0.045 + ((chapter + 0.84) / order.length) * 0.955);
    await expect(page).toHaveURL(new RegExp(`artist=${order[chapter]}`));
    await expect(page.locator("#living-field")).toHaveAttribute(
      "data-journey-phase",
      "hold",
    );
  }
  await scrub(page, 0);
  await expect(page).not.toHaveURL(/artist=/);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey-phase",
    "origin",
  );
  expect(await page.evaluate(() => history.length)).toBe(historyBefore + 1);
});

test("the continuous environment moves with native depth and returns to the same climate without another texture", async ({
  page,
}) => {
  // Suppress ambient time so the two canvas captures isolate scroll-driven travel.
  await page.addInitScript(() => {
    const names = new WeakMap<WebGLUniformLocation, string>();
    const get = WebGL2RenderingContext.prototype.getUniformLocation;
    const set = WebGL2RenderingContext.prototype.uniform1f;
    WebGL2RenderingContext.prototype.getUniformLocation = function (
      program,
      name,
    ) {
      const location = get.call(this, program, name);
      if (location) names.set(location, name);
      return location;
    };
    WebGL2RenderingContext.prototype.uniform1f = function (location, value) {
      set.call(
        this,
        location,
        location && names.get(location) === "uTime" ? 0 : value,
      );
    };
  });
  await page.goto("/");
  await ready(page);
  const field = page.locator("#living-field");
  const bytes = await field.getAttribute("data-field-texture-bytes");
  await page.locator('[data-primary-action="explore"]').click();
  await scrub(page, 0.2);
  await expect
    .poll(async () => Number(await field.getAttribute("data-field-travel")))
    .toBeCloseTo(0.2, 2);
  const initialClimate = Number(await field.getAttribute("data-field-climate"));
  const before = await page.locator("#living-field-canvas").screenshot();
  await scrub(page, 0.55);
  await expect
    .poll(async () => Number(await field.getAttribute("data-field-travel")))
    .toBeCloseTo(0.55, 2);
  await expect
    .poll(async () => Number(await field.getAttribute("data-field-climate")))
    .toBeGreaterThan(initialClimate + 0.1);
  const after = await page.locator("#living-field-canvas").screenshot();
  expect(before.equals(after)).toBe(false);
  await expect(field).toHaveAttribute("data-field-texture-bytes", bytes!);
  await scrub(page, 0.2);
  await expect
    .poll(async () => Number(await field.getAttribute("data-field-travel")))
    .toBeCloseTo(0.2, 2);
  await expect
    .poll(async () => Number(await field.getAttribute("data-field-climate")))
    .toBeCloseTo(initialClimate, 2);
  await expect(field).toHaveAttribute("data-field-texture-bytes", bytes!);
  await expect(page).not.toHaveURL(/artist=/);
});
