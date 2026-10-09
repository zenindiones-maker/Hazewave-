import { expect, test } from "@playwright/test";

test("a missing artist texture preserves the origin and reports the missing art", async ({
  page,
}) => {
  await page.route("**/media/worlds/hemorragia-cosmica-v6.webp", (route) =>
    route.abort(),
  );
  await page.goto("/?artist=hemorragia-cosmica");
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "webgl2",
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-asset-unavailable",
    "true",
  );
  await expect(page.locator("#world-art-error")).toBeVisible();
  await page.locator("#world-back").click();
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-world-ready",
    "true",
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-world-active",
    "false",
  );
  expect(
    await page
      .locator("canvas")
      .evaluate((canvas) => (canvas as HTMLCanvasElement).width),
  ).toBeGreaterThan(0);
});

test("the drawing buffer stays within its pixel budget on large high density displays", async ({
  page,
}) => {
  await page.setViewportSize({ width: 3840, height: 2160 });
  await page.goto("/");
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "webgl2",
  );
  const pixels = await page
    .locator("canvas")
    .evaluate(
      (canvas) =>
        (canvas as HTMLCanvasElement).width *
        (canvas as HTMLCanvasElement).height,
    );
  expect(pixels).toBeLessThanOrEqual(1_405_000);
  expect(
    Number(
      await page
        .locator("#living-field")
        .getAttribute("data-field-texture-bytes"),
    ),
  ).toBeLessThan(6_000_000);
});
