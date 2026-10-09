import { expect, test, type Page } from "@playwright/test";

const ids = [
  "barak-ozama-beats",
  "indionesbala",
  "baazu",
  "aquaverno",
  "hemorragia-cosmica",
];

test("motion preference changed during decode never restarts the field", async ({
  page,
}) => {
  let release!: () => void;
  const blocked = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/media/**", async (route) => {
    await blocked;
    await route.continue();
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () =>
      document
        .querySelector("#living-field")
        ?.getAttribute("data-world-ready") === "true",
  );
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.emulateMedia({ reducedMotion: "reduce" });
  release();
  await page.waitForFunction(() =>
    Array.from(
      document.querySelectorAll(".field-origin img,.world-fallback-art"),
    ).every(
      (img) =>
        (img as HTMLImageElement).complete &&
        (img as HTMLImageElement).naturalWidth > 0,
    ),
  );
  await page.waitForTimeout(500);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "css-fallback",
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-motion",
    "reduced",
  );
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await ready(page);
});

test("distant signal is revealed after the wave reaches its location", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/");
  await ready(page);
  const expected = await page.evaluate(() => {
    const x = 15,
      y = 1060;
    const distance = Math.min(
      ...Array.from(document.querySelectorAll("[data-artist-signal]")).map(
        (button) => {
          const b = button.getBoundingClientRect();
          return Math.hypot(
            (b.x + b.width / 2 - x) / innerHeight,
            (b.y + b.height / 2 - y) / innerHeight,
          );
        },
      ),
    );
    return (distance / 0.55) * 1000;
  });
  await page.evaluate(() => {
    const started = performance.now();
    const observer = new MutationObserver(() => {
      if (document.querySelector('[data-revealed="true"]')) {
        (window as Window & { revealDelay?: number }).revealDelay =
          performance.now() - started;
        observer.disconnect();
      }
    });
    observer.observe(document.querySelector(".signal-field")!, {
      subtree: true,
      attributes: true,
      attributeFilter: ["data-revealed"],
    });
    document.querySelector("#living-field")!.dispatchEvent(
      new PointerEvent("pointerdown", {
        bubbles: true,
        clientX: 15,
        clientY: 1060,
        pointerType: "touch",
      }),
    );
  });
  await page.waitForFunction(
    () =>
      (window as Window & { revealDelay?: number }).revealDelay !== undefined,
  );
  const observed = await page.evaluate(
    () => (window as Window & { revealDelay?: number }).revealDelay!,
  );
  expect(observed).toBeGreaterThanOrEqual(expected - 25);
});

test("short portrait retains readable discovery guidance", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.goto("/");
  await ready(page);
  await expect(page.locator(".field-invitation")).toBeVisible();
  const instruction = (await page.locator(".field-invitation").boundingBox())!;
  const navigation = (await page.locator(".primary-paths").boundingBox())!;
  expect(instruction.y + instruction.height).toBeLessThanOrEqual(navigation.y);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
});
async function ready(page: Page) {
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "webgl2",
    { timeout: 15000 },
  );
}
async function settled(page: Page) {
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-world-ready",
    "true",
    { timeout: 5000 },
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-transitioning",
    "false",
  );
}

test("conceptual worlds render and all real artist signals are reachable", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await ready(page);
  await expect(
    page.getByRole("heading", { name: "HAZEWAVE", exact: true }),
  ).toBeVisible();
  await expect(page.locator("[data-artist-signal]")).toHaveCount(5);
  expect(
    await page
      .locator("#hazewave-world-source")
      .evaluate((image) => (image as HTMLImageElement).naturalWidth >= 1000),
  ).toBe(true);
  expect(
    Number(
      await page
        .locator("#living-field")
        .getAttribute("data-field-texture-bytes"),
    ),
  ).toBeLessThan(6_000_000); // Origin plus required canonical source, both capped at 1024px.
  for (const name of ["EXPLORE", "LISTEN", "SEARCH"])
    await expect(
      page.getByRole("button", { name: new RegExp(name) }),
    ).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(
    /AETHER|MONOLITH|FLORA/,
  );
  await expect(
    page.locator("#resonance-deck,#player-wheel,[data-artist-cassette]"),
  ).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("living-field.png") });
  expect(errors).toEqual([]);
});

test("Wave refracts the actual GPU canvas and reveals an artist", async ({
  page,
}, info) => {
  // Freeze ambient time and hide artist previews: the pixel difference must come from the artwork wave itself.
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
      const name = location && names.get(location);
      set.call(
        this,
        location,
        name === "uTime" || name === "uPreviewAmount" ? 0 : value,
      );
    };
  });
  await page.goto("/");
  await ready(page);
  const box = (await page.locator("#living-field").boundingBox())!;
  await page.mouse.move(box.width * 0.54, box.height * 0.51);
  await page.waitForTimeout(3200);
  const before = await page.locator("canvas").screenshot();
  await page.mouse.click(box.width * 0.54, box.height * 0.51);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-wave-active",
    "true",
  );
  await expect(
    page.locator('[data-artist-signal][data-revealed="true"]'),
  ).toHaveCount(1);
  const after = await page.locator("canvas").screenshot();
  expect(before.equals(after)).toBe(false);
  await page.screenshot({ path: info.outputPath("wave-through-haze.png") });
});

test("artist entry, browser back and forward preserve route and world", async ({
  page,
}, info) => {
  await page.goto("/");
  await ready(page);
  await page.locator('[data-artist-signal="aquaverno"]').click();
  await expect(page).toHaveURL(/artist=aquaverno/);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-transitioning",
    "true",
  );
  await page.screenshot({ path: info.outputPath("aquaverno-transition.png") });
  await settled(page);
  await page.screenshot({ path: info.outputPath("aquaverno-world.png") });
  await expect(page.locator('[data-artist-world="aquaverno"]')).toHaveAttribute(
    "data-active",
    "true",
  );
  await page.goBack();
  await settled(page);
  await expect(page.locator('[data-artist-signal="aquaverno"]')).toBeFocused();
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-world-active",
    "false",
  );
  await page.goForward();
  await settled(page);
  await expect(page.locator("html")).toHaveAttribute(
    "data-active-artist",
    "aquaverno",
  );
});

test("direct artist link returns to the field without leaving the site", async ({
  page,
}, info) => {
  await page.goto("/?artist=hemorragia-cosmica");
  await ready(page);
  await settled(page);
  await expect(
    page.locator('[data-artist-world="hemorragia-cosmica"]'),
  ).toHaveAttribute("data-world-system", "pressure-wire");
  await page.screenshot({ path: info.outputPath("hemorragia-world.png") });
  await page.locator("#world-back").click();
  await settled(page);
  expect(new URL(page.url()).searchParams.has("artist")).toBe(false);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-world-active",
    "false",
  );
});

test("search filters accents, empty results and switches between worlds", async ({
  page,
}) => {
  await page.goto("/?artist=aquaverno");
  await ready(page);
  await page.getByRole("button", { name: /SEARCH/ }).click();
  const input = page.getByRole("searchbox");
  await input.fill("cosmica");
  await expect(page.locator("[data-search-artist]:visible")).toHaveCount(1);
  await expect(
    page.locator('[data-search-artist="hemorragia-cosmica"]'),
  ).toBeVisible();
  await input.fill("xyz-unlisted");
  await expect(page.locator("#search-empty")).toBeVisible();
  await input.fill("baazu");
  await page.locator('[data-search-artist="baazu"]').click();
  await settled(page);
  await expect(page.locator("html")).toHaveAttribute(
    "data-active-artist",
    "baazu",
  );
  await expect(page.locator("#world-back")).toBeFocused();
});

test("all artist worlds preserve identity and working direct navigation", async ({
  page,
}) => {
  for (const id of ids) {
    await page.goto(`/?artist=${id}`);
    await ready(page);
    await settled(page);
    await expect(page.locator(`[data-artist-world="${id}"]`)).toHaveAttribute(
      "data-active",
      "true",
    );
    await expect(page.locator("#transport-artist")).not.toHaveText("HAZEWAVE");
  }
});

test("audio remains unavailable honestly, with conventional disabled controls", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  await page.getByRole("button", { name: /LISTEN/ }).click();
  await expect(page.locator("#transport-state")).toHaveText(
    "Nenhuma faixa autorizada disponível.",
  );
  await expect(
    page.getByRole("button", { name: "Tocar", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("slider", { name: "Volume", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Recolher player" }).click();
  await expect(page.getByRole("button", { name: /LISTEN/ })).toBeFocused();
});

test("reduced motion and WebGL loss retain navigation and artwork", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "css-fallback",
  );
  await page.locator('[data-artist-signal="aquaverno"]').click();
  await settled(page);
  await expect(
    page.locator('[data-artist-world="aquaverno"] img'),
  ).toBeVisible();
  await page.locator("#world-back").click();
  await settled(page);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-world-active",
    "false",
  );
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await ready(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "css-fallback",
  );
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await ready(page);
  await page.evaluate(() => {
    const c = document.querySelector("canvas")!;
    c.getContext("webgl2")?.getExtension("WEBGL_lose_context")?.loseContext();
  });
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-field-runtime",
    "css-fallback",
  );
  await page.locator('[data-artist-signal="hemorragia-cosmica"]').click();
  await settled(page);
});

test("keyboard hides inactive worlds and dialog restores focus", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  await expect(page.locator(".artist-world:not([inert])")).toHaveCount(0);
  await page.getByRole("button", { name: /SEARCH/ }).click();
  await expect(page.getByRole("searchbox")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: /SEARCH/ })).toBeFocused();
  await page.locator('[data-artist-signal="aquaverno"]').focus();
  await page.keyboard.press("Enter");
  await settled(page);
  await expect(page.locator(".signal-field")).toHaveAttribute("inert", "");
  await page.keyboard.press("Escape");
  await settled(page);
  await expect(page.locator('[data-artist-signal="aquaverno"]')).toBeFocused();
});

test("mobile touch, readable targets and no horizontal overflow", async ({
  page,
}, info) => {
  test.skip(!info.project.name.includes("mobile"), "mobile proof");
  await page.goto("/");
  await ready(page);
  const viewport = page.viewportSize()!;
  await page.touchscreen.tap(viewport.width * 0.5, viewport.height * 0.52);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-wave-active",
    "true",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  for (const selector of [".primary-paths button", "[data-artist-signal]"]) {
    const boxes = await page.locator(selector).evaluateAll((elements) =>
      elements.map((e) => {
        const r = e.getBoundingClientRect();
        return { w: r.width, h: r.height };
      }),
    );
    expect(boxes.every((b) => b.w >= 44 && b.h >= 44)).toBe(true);
  }
  await page.screenshot({ path: info.outputPath("mobile-touch.png") });
});

test("without JavaScript the conceptual artist gallery is accessible", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("/");
  await expect(
    page.getByRole("region", { name: "Artistas Hazewave" }),
  ).toBeVisible();
  await expect(page.locator(".static-gallery a")).toHaveCount(5);
  await expect(page.locator(".static-gallery img")).toHaveCount(6);
  await context.close();
});

test("short mobile keeps signals above the transport", async ({
  page,
}, info) => {
  test.skip(!info.project.name.includes("mobile"), "mobile-only");
  await page.setViewportSize({ width: 360, height: 640 });
  await page.goto("/");
  await ready(page);
  await expect(page.locator(".field-invitation")).toBeVisible();
  const nav = (await page.locator(".primary-paths").boundingBox())!;
  const instruction = (await page.locator(".field-invitation").boundingBox())!;
  expect(instruction.y + instruction.height).toBeLessThanOrEqual(nav.y);
  for (const signal of await page.locator("[data-artist-signal]").all()) {
    const b = (await signal.boundingBox())!;
    expect(b.y + b.height).toBeLessThan(nav.y);
  }
});

test("native scroll traversal reverses, retains its origin and exits accessibly", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  await page.locator('[data-primary-action="explore"]').click();
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey",
    "true",
  );
  // Discovery remains interactive so visitors can choose a different signal.
  await expect(page.locator(".signal-field")).not.toHaveAttribute("inert", "");
  await page.evaluate(() =>
    scrollTo(
      0,
      document.querySelector<HTMLElement>("#journey-distance")!.offsetHeight *
        0.5,
    ),
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-traversal-progress",
    /^0\.5/,
  );
  const p = await page
    .locator("#living-field")
    .getAttribute("data-traversal-progress");
  await page.mouse.move(200, 250);
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-traversal-progress",
    p!,
  );
  await page.evaluate(() =>
    scrollTo(
      0,
      document.querySelector<HTMLElement>("#journey-distance")!.offsetHeight,
    ),
  );
  await expect(page).toHaveURL(/artist=hemorragia-cosmica/);
  await page.evaluate(() =>
    scrollTo(
      0,
      document.querySelector<HTMLElement>("#journey-distance")!.offsetHeight *
        0.32,
    ),
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-traversal-progress",
    /^0\.6/,
  );
  await expect(page).toHaveURL(/artist=baazu/);
  await page.keyboard.press("Escape");
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey",
    "false",
  );
  await expect(page.locator('[data-primary-action="explore"]')).toBeFocused();
});

test("scroll journey stops cleanly for motion preference and GPU loss", async ({
  page,
}) => {
  await page.goto("/");
  await ready(page);
  await page.locator('[data-primary-action="explore"]').click();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey",
    "false",
  );
  await expect(page.locator('[data-primary-action="explore"]')).toBeFocused();
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await ready(page);
  await page.locator('[data-primary-action="explore"]').click();
  await page.evaluate(() =>
    document
      .querySelector("canvas")!
      .getContext("webgl2")
      ?.getExtension("WEBGL_lose_context")
      ?.loseContext(),
  );
  await expect(page.locator("#living-field")).toHaveAttribute(
    "data-journey",
    "false",
  );
  await expect(page.locator('[data-primary-action="explore"]')).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollHeight <= innerHeight,
    ),
  ).toBe(true);
});

test("all five static artist routes survive refresh and return to origin", async ({ page }) => {
  for (const id of ["baazu", "barak-ozama-beats", "indionesbala", "aquaverno", "hemorragia-cosmica"]) {
    await page.goto(`/artists/${id}/`);
    await expect(page.locator("#living-field")).toHaveAttribute("data-world-ready", "true");
    await expect(page.locator(`[data-artist-world="${id}"]`)).toHaveAttribute("data-active", "true");
    await page.reload();
    await expect(page.locator(`[data-artist-world="${id}"]`)).toHaveAttribute("data-active", "true");
    await page.locator("#world-back").click();
    await expect(page.locator("#living-field")).toHaveAttribute("data-world-active", "false");
    await expect(page).toHaveURL(/\/$/);
  }
});
