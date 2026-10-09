import { expect, test } from "@playwright/test";

test("a missing master texture retains the canonical artist fallback and navigation", async ({
  page,
}) => {
  await page.route("**/media/worlds/living-illustrated-v7.webp", (route) =>
    route.abort(),
  );
  await page.goto("/?artist=indionesbala");
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "css-fallback",
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-world-ready",
    "true",
  );
  const fallback = page.locator(
    '[data-artist-world="indionesbala"] .world-fallback-art',
  );
  await expect(fallback).toBeVisible();
  expect(
    await fallback.evaluate(
      (image) =>
        (image as HTMLImageElement).complete &&
        (image as HTMLImageElement).naturalWidth > 0,
    ),
  ).toBe(true);
  await page.locator("#world-back").click();
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-world-active",
    "false",
  );
  await page.locator('[data-primary-action="search"]').click();
  await page.locator('[data-search-artist="indionesbala"]').click();
  await expect(page).toHaveURL(/artist=indionesbala/);
  await expect(page.locator("#world-back")).toBeFocused();
});

test("the drawing buffer and sole master decode remain within their budgets", async ({
  page,
}, info) => {
  if (!info.project.name.includes("mobile"))
    await page.setViewportSize({ width: 3840, height: 2160 });
  await page.addInitScript(() => {
    const original = window.createImageBitmap;
    const records: { src: string; width: number; height: number }[] = [];
    Object.assign(window, { masterDecodes: records });
    window.createImageBitmap = (async (
      ...args: Parameters<typeof createImageBitmap>
    ) => {
      const bitmap = await Reflect.apply(original, window, args);
      const image = args[0];
      if (image instanceof HTMLImageElement)
        records.push({
          src: image.src,
          width: bitmap.width,
          height: bitmap.height,
        });
      return bitmap;
    }) as typeof createImageBitmap;
  });
  await page.goto("/");
  const field = page.locator("#living-field");
  await expect(field).toHaveAttribute("data-field-runtime", "webgl2");
  const pixels = await page
    .locator("canvas")
    .evaluate(
      (canvas) =>
        (canvas as HTMLCanvasElement).width *
        (canvas as HTMLCanvasElement).height,
    );
  expect(pixels).toBeLessThanOrEqual(1_405_000);
  const expected = await page
    .locator("#hazewave-world-source")
    .evaluate((image) => {
      const img = image as HTMLImageElement;
      const cap = innerWidth < 700 ? 1536 : 2048;
      const ratio = Math.min(
        1,
        cap / Math.max(img.naturalWidth, img.naturalHeight),
      );
      return (
        Math.round(img.naturalWidth * ratio) *
        Math.round(img.naturalHeight * ratio) *
        4
      );
    });
  expect(expected).toBeGreaterThan(0);
  await expect(field).toHaveAttribute(
    "data-field-texture-bytes",
    String(expected),
  );
  await page.locator('[data-primary-action="explore"]').click();
  await page.evaluate(() =>
    scrollTo(
      0,
      document.querySelector<HTMLElement>("#journey-distance")!.offsetHeight,
    ),
  );
  await expect(page).toHaveURL(/artist=indionesbala/);
  await expect(field).toHaveAttribute(
    "data-field-texture-bytes",
    String(expected),
  );
  const records = await page.evaluate(
    () =>
      (
        window as unknown as Window & {
          masterDecodes: { src: string; width: number; height: number }[];
        }
      ).masterDecodes,
  );
  expect(records).toHaveLength(1);
  expect(records[0].src).toContain("living-illustrated-v7.webp");
  expect(records[0].width * records[0].height * 4).toBe(expected);
  expect(Math.max(records[0].width, records[0].height)).toBeLessThanOrEqual(
    info.project.name.includes("mobile") ? 1536 : 2048,
  );
});
