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
  const signal = page.locator('[data-artist-signal="hemorragia-cosmica"]');
  await signal.focus();
  await expect(signal).toHaveAttribute("data-revealed", "true");
  await page.locator('[data-primary-action="explore"]').click();
  await expect(page.locator("#journey-artist")).toHaveText(
    "Hemorragia Cósmica",
  );
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
  await expect(page).toHaveURL(/artist=hemorragia-cosmica/);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey-act",
    "arrival",
  );
  await expect(
    page.locator('[data-artist-world="hemorragia-cosmica"]'),
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
  await page.locator('[data-search-artist="hemorragia-cosmica"]').click();
  await expect(page).toHaveURL(/artist=hemorragia-cosmica/);
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
