import { expect, test, type Page } from "@playwright/test";

const REAL_ARTISTS = [
  "Barak Ozama Beats",
  "Indionesbala",
  "Baazü",
  "Aquaverno",
  "Hemorragia Cósmica"
] as const;

async function fireWave(page: Page, xRatio = 0.7, yRatio = 0.52) {
  const field = page.locator("#living-field");
  const box = await field.boundingBox();
  expect(box).not.toBeNull();
  const x = box!.x + box!.width * xRatio;
  const y = box!.y + box!.height * yRatio;
  await page.mouse.click(x, y);
  await expect(field).toHaveAttribute("data-wave-active", "true", { timeout: 2_000 });
}

test("Living Resonance Field owns the first viewport and old primary UI is absent", async ({ page }, testInfo) => {
  await page.goto("/");

  await expect(page.locator("#living-field")).toBeVisible();
  await expect(page.locator("#hazewave-world-source")).toHaveAttribute(
    "src",
    "/media/hazewave-world.jpg.webp"
  );
  await expect(page.getByRole("heading", { name: "HAZEWAVE" })).toBeVisible();
  await expect(page.getByText("Núcleo Sonoro Independente", { exact: true })).toBeVisible();
  await expect(page.getByText("Santos", { exact: true })).toBeVisible();

  await expect(page.getByRole("button", { name: "EXPLORE" })).toBeVisible();
  await expect(page.getByRole("button", { name: "LISTEN" })).toBeVisible();
  await expect(page.getByRole("button", { name: "SEARCH" })).toBeVisible();

  await expect(page.locator("#resonance-deck")).toHaveCount(0);
  await expect(page.locator("#player-wheel")).toHaveCount(0);
  await expect(page.locator("[data-artist-cassette='true']")).toHaveCount(0);

  await page.screenshot({ path: testInfo.outputPath("living-field-desktop.png"), fullPage: false });
});

test("production discovery exposes the five real owner-supplied artists and no DEMO authority", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("[data-artist-signal]")).toHaveCount(5);

  for (const artist of REAL_ARTISTS) {
    await expect(page.getByRole("button", { name: new RegExp(artist, "i") })).toBeAttached();
  }

  const body = await page.locator("body").innerText();
  expect(body).not.toContain("AETHER");
  expect(body).not.toContain("MONOLITH");
  expect(body).not.toContain("FLORA");
  expect(body).not.toContain("DEMO CONTENT");
});

test("Wave-through-Haze disturbs the owner artwork and reveals a real artist signal", async ({ page }, testInfo) => {
  await page.goto("/");
  const field = page.locator("#living-field");
  await expect(field).toHaveAttribute("data-field-runtime", /webgl2|css-fallback/, { timeout: 4_000 });

  await fireWave(page, 0.62, 0.48);
  await expect(page.locator("[data-artist-signal][data-revealed='true']")).toHaveCount(1, {
    timeout: 2_000
  });

  await page.screenshot({ path: testInfo.outputPath("wave-through-haze.png"), fullPage: false });
});

test("Aquaverno emerges from the field and browser back restores Hazewave", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.locator("[data-artist-signal='aquaverno']").click();

  await expect(page.locator("html")).toHaveAttribute("data-active-artist", "aquaverno");
  await expect(page.locator("[data-artist-world='aquaverno']")).toHaveAttribute("data-active", "true");
  await expect(page.locator("[data-artist-world='aquaverno'] img")).toHaveAttribute(
    "src",
    "/media/artists/aquaverno.webp"
  );
  expect(new URL(page.url()).searchParams.get("artist")).toBe("aquaverno");

  await expect(page.locator("#living-field")).toHaveAttribute("data-world-ready", "true", { timeout: 2_500 });
  await expect(page.locator("#living-field")).toHaveAttribute("data-transitioning", "false", { timeout: 2_500 });
  await page.screenshot({ path: testInfo.outputPath("artist-world-aquaverno.png"), fullPage: false });

  await page.goBack();
  await expect(page.locator("html")).not.toHaveAttribute("data-active-artist", "aquaverno");
  expect(new URL(page.url()).searchParams.get("artist")).toBeNull();
});

test("Hemorragia Cósmica is a materially different artist world, not a skin", async ({ page }, testInfo) => {
  await page.goto("/?artist=hemorragia-cosmica");

  await expect(page.locator("html")).toHaveAttribute("data-active-artist", "hemorragia-cosmica");
  const world = page.locator("[data-artist-world='hemorragia-cosmica']");
  await expect(world).toHaveAttribute("data-active", "true");
  await expect(world).toHaveAttribute("data-world-system", "pressure-wire");
  await expect(world.locator("img")).toHaveAttribute(
    "src",
    "/media/artists/hemorragia-cosmica.webp"
  );
  await expect(world.locator(".hemorragia-wire")).toHaveCount(3);

  await expect(page.locator("#living-field")).toHaveAttribute("data-world-ready", "true", { timeout: 2_500 });
  await page.screenshot({ path: testInfo.outputPath("artist-world-hemorragia-cosmica.png"), fullPage: false });
});

test("direct Aquaverno deep link bypasses exploration and resolves the correct world", async ({ page }) => {
  await page.goto("/?artist=aquaverno");
  await expect(page.locator("html")).toHaveAttribute("data-active-artist", "aquaverno");
  await expect(page.locator("[data-artist-world='aquaverno']")).toHaveAttribute("data-active", "true");
});

test("minimal transport is conventional and fail-closed without authorized audio", async ({ page }) => {
  await page.goto("/?artist=aquaverno");
  const transport = page.locator("#persistent-transport");
  await expect(transport).toBeVisible();
  await expect(transport.getByRole("button", { name: "Anterior" })).toBeVisible();
  await expect(transport.getByRole("button", { name: "Tocar" })).toBeDisabled();
  await expect(transport.getByRole("button", { name: "Próxima" })).toBeVisible();
  await expect(transport.getByText("Áudio ainda não materializado", { exact: true })).toBeVisible();
  await expect(page.locator("#player-wheel")).toHaveCount(0);
});

test("search reaches a real artist without traversing the field", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "SEARCH" }).click();
  const dialog = page.getByRole("dialog", { name: "Buscar artista" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Hemorragia Cósmica" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-active-artist", "hemorragia-cosmica");
});

test("reduced motion keeps field, discovery and artist entry authored and functional", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("#living-field")).toHaveAttribute("data-motion", "reduced");
  await page.locator("[data-artist-signal='aquaverno']").click();
  await expect(page.locator("html")).toHaveAttribute("data-active-artist", "aquaverno");
});

test("mobile field is separately composed, touchable and overflow-free", async ({ page }, testInfo) => {
  const viewport = page.viewportSize();
  test.skip(!viewport || viewport.width > 700, "mobile-only proof");

  await page.goto("/");
  const field = page.locator("#living-field");
  const box = await field.boundingBox();
  expect(box).not.toBeNull();
  await page.touchscreen.tap(box!.x + box!.width * 0.48, box!.y + box!.height * 0.56);
  await expect(field).toHaveAttribute("data-wave-active", "true", { timeout: 2_000 });

  const overflow = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.width + 1);

  const actions = page.locator(".primary-paths button");
  for (let index = 0; index < await actions.count(); index += 1) {
    const target = actions.nth(index);
    const rect = await target.boundingBox();
    expect(rect).not.toBeNull();
    expect(rect!.height).toBeGreaterThanOrEqual(44);
  }

  await page.screenshot({ path: testInfo.outputPath("living-field-mobile.png"), fullPage: false });
});
