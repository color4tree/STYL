import { test, expect, type Page } from "@playwright/test";

async function expectQuoteLanding(page: Page) {
  await expect.poll(async () => {
    const form = await page.locator("#contact").boundingBox();
    const header = await page.locator("header").boundingBox();
    return form && header ? Math.round(form.y - header.y - header.height) : -1;
  }, { message: "Quote form should land immediately below the sticky header" }).toBeGreaterThanOrEqual(8);
  await expect.poll(async () => {
    const form = await page.locator("#contact").boundingBox();
    const header = await page.locator("header").boundingBox();
    return form && header ? Math.round(form.y - header.y - header.height) : Infinity;
  }).toBeLessThanOrEqual(32);
  await expect(page.getByRole("textbox", { name: "Name", exact: true })).toBeInViewport({ ratio: 1 });
}

test("USR-011 USR-012: Equipment and Shop accessories preserve catalog links and the quote journey", async ({ page }) => {
  const initialViewport = page.viewportSize()!;
  await page.goto("/");
  await expect(page.locator("#products article").first()).toBeVisible();
  const introduction = page.locator("main > section").first();
  const shopEquipment = introduction.getByRole("link", { name: "Shop equipment", exact: true });
  const shopAccessories = introduction.getByRole("link", { name: "Shop accessories", exact: true });
  await expect(shopEquipment).toHaveAttribute("href", "#products");
  await expect(shopAccessories).toHaveAttribute("href", "/accessories");
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    const navigation = page.getByRole("navigation", { name: width < 1024 ? "Catalog navigation" : "Main navigation", exact: true });
    const equipment = navigation.getByRole("link", { name: "Equipment", exact: true });
    const accessories = navigation.getByRole("link", { name: "Accessories", exact: true });
    await expect(equipment).toHaveAttribute("href", "/#products");
    await expect(accessories).toHaveAttribute("href", "/accessories");
    await expect(page.getByRole("link", { name: "Products", exact: true })).toHaveCount(0);
    for (const link of [shopEquipment, shopAccessories, equipment, accessories]) {
      await expect(link).toBeVisible();
      const bounds = await link.boundingBox();
      expect(bounds).not.toBeNull();
      expect(bounds!.height).toBeGreaterThanOrEqual(48);
      expect(bounds!.x).toBeGreaterThanOrEqual(0);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.setViewportSize(initialViewport);
  await shopAccessories.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/accessories$/);
  await expect(page.getByRole("heading", { level: 1, name: "Accessories", exact: true })).toBeVisible();
  if (initialViewport.width < 1024) {
    await page.getByRole("button", { name: "Menu", exact: true }).click();
    const menu = page.getByRole("navigation", { name: "Mobile navigation", exact: true });
    await expect(menu.getByRole("link", { name: "Equipment", exact: true })).toHaveAttribute("href", "/#products");
    await expect(menu.getByRole("link", { name: "Request a quote", exact: true })).toHaveAttribute("href", "/#contact");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Menu", exact: true })).toBeFocused();
  }
  const navigation = page.getByRole("navigation", { name: initialViewport.width < 1024 ? "Catalog navigation" : "Main navigation", exact: true });
  await navigation.getByRole("link", { name: "Equipment", exact: true }).click();
  await expect(page).toHaveURL(/\/#products$/);
  const card = page.locator("#products article").first();
  const name = await card.locator(":scope > h3").innerText();
  const details = card.getByRole("link", { name: "Details", exact: true });
  await expect(details).toHaveAttribute("href", /^\/products\/[^/]+$/);
  await details.click();
  await expect(page).toHaveURL(/\/products\/[^/]+$/);
  await expect(page.getByRole("heading", { level: 1, name, exact: true })).toBeVisible();
  await page.locator("main").getByRole("link", { name: "Request quote", exact: true }).click();
  await expect(page).toHaveURL(/\/\?quote=product&product=.+#contact$/);
  await expectQuoteLanding(page);
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(`Interested in:\n\n1. ${name}\n\nPlease share options, pricing, and lead time.`);
});

test("USR-011: equipment empty, failure and missing-detail labels keep compatible API routes", async ({ page }) => {
  await page.route("**/api/products", (route) => route.fulfill({ json: { items: [] } }));
  await page.goto("/");
  await expect(page.locator("#products")).toContainText("No equipment is currently available.");
  await page.unroute("**/api/products");
  await page.route("**/api/products", (route) => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
  await page.reload();
  await expect(page.locator("#products").getByRole("alert")).toContainText("Equipment is unavailable right now.");
  await page.route("**/api/products/equipment-label-unavailable", (route) => route.fulfill({ status: 404, json: { detail: "Product not found" } }));
  await page.goto("/products/equipment-label-unavailable");
  await expect(page.getByRole("heading", { level: 1, name: "Equipment not found", exact: true })).toBeVisible();
});

for (const origin of ["cart", "product", "header"] as const) {
  for (const reducedMotion of ["no-preference", "reduce"] as const) {
    test(`USR-015: ${origin} quote transition stays aligned during loading (${reducedMotion})`, async ({ page, request }) => {
      await page.emulateMedia({ reducedMotion });
      const items = (await (await request.get("http://127.0.0.1:8102/api/products")).json()).items;
      const product = items[0];
      await page.addInitScript((item) => localStorage.setItem("styl-cart", JSON.stringify([{ ...item, quantity: 2 }])), product);
      await page.goto(origin === "product" ? `/products/${product.slug}` : "/cart");
      await expect(page.locator("main").getByRole("link", { name: "Request quote", exact: true })
        .or(page.locator("main").getByRole("link", { name: "Request a quote", exact: true }).first())).toBeVisible();

      let releaseCatalog!: () => void;
      let releaseCart!: () => void;
      const catalogGate = new Promise<void>((resolve) => { releaseCatalog = resolve; });
      const cartGate = new Promise<void>((resolve) => { releaseCart = resolve; });
      await page.route("**/api/products", async (route) => { await catalogGate; await route.continue(); });
      await page.route("**/api/catalog/selection", async (route) => { await cartGate; await route.continue(); });
      await page.evaluate(() => {
        const samples: number[] = [];
        document.documentElement.dataset.quotePaintGaps = "[]";
        const sample = () => {
          const form = document.getElementById("contact");
          const header = document.querySelector("header");
          if (form && header) {
            samples.push(Math.round(form.getBoundingClientRect().top - header.getBoundingClientRect().bottom));
            document.documentElement.dataset.quotePaintGaps = JSON.stringify(samples);
          }
          if (document.documentElement.dataset.stopQuoteSampling !== "true") requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
      });
      try {
        if (origin === "product") {
          await page.locator("main").getByRole("link", { name: "Request quote", exact: true }).click();
        } else if (origin === "cart") {
          await page.locator("main").getByRole("link", { name: "Request a quote", exact: true }).first().click();
        } else {
          const desktop = page.getByRole("navigation", { name: "Main navigation", exact: true });
          if (await desktop.isVisible()) await desktop.getByRole("link", { name: "Request a quote", exact: true }).click();
          else {
            await page.getByRole("button", { name: "Menu", exact: true }).click();
            await page.getByRole("navigation", { name: "Mobile navigation", exact: true }).getByRole("link", { name: "Request a quote", exact: true }).click();
          }
        }
        await expect(page).toHaveURL(/#contact$/);
        await expect(page.getByText("Loading equipment...", { exact: true })).toBeVisible();
        await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
        releaseCart();
        await expect(page.getByRole("link", { name: "Review your cart", exact: true })).toBeVisible();
        await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
        releaseCatalog();
        await expect(page.locator("#products article")).toHaveCount(items.length);
        await expectQuoteLanding(page);
        await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => {
          document.documentElement.dataset.stopQuoteSampling = "true";
          resolve();
        }))));
        const gaps: number[] = JSON.parse(await page.locator("html").getAttribute("data-quote-paint-gaps") ?? "[]");
        expect(gaps.length).toBeGreaterThan(2);
        expect(Math.min(...gaps), "No painted frame puts the form under the sticky header").toBeGreaterThanOrEqual(8);
        expect(Math.max(...gaps), "No early anchor jump or late correction is painted").toBeLessThanOrEqual(32);
        if (origin !== "header") await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(new RegExp(product.name));
      } finally {
        releaseCart();
        releaseCatalog();
      }
    });
  }
}

for (const origin of ["cart", "product", "direct"] as const) {
  test(`USR-012: ${origin} quote link lands on the form after a delayed catalog`, async ({ page, request }) => {
    const items = (await (await request.get("http://127.0.0.1:8102/api/products")).json()).items;
    const product = items[0];
    await page.addInitScript((item) => localStorage.setItem("styl-cart", JSON.stringify([{ ...item, quantity: 2 }])), product);
    let release!: () => void;
    const ready = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/api/products", async (route) => {
      await ready;
      await route.continue();
    });
    try {
      if (origin === "cart") {
        await page.goto("/cart");
        await page.locator("main").getByRole("link", { name: "Request a quote", exact: true }).first().click();
      } else if (origin === "product") {
        await page.goto(`/products/${product.slug}`);
        await page.locator("main").getByRole("link", { name: "Request quote", exact: true }).click();
      } else {
        await page.goto("/?quote=cart#contact");
      }
      await expect(page).toHaveURL(/#contact$/);
      await expect(page.getByText("Loading equipment...", { exact: true })).toBeVisible();
      await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(new RegExp(product.name));
      release();
      await expect(page.locator("#products article")).toHaveCount(items.length);
      await expectQuoteLanding(page);
      await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(new RegExp(product.name));
    } finally {
      release();
    }
  });
}

test("USR-012: same-page quote navigation can be repeated without a reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#products article").first()).toBeVisible();
  const desktop = page.getByRole("navigation", { name: "Main navigation", exact: true });
  const mobile = page.getByRole("navigation", { name: "Mobile navigation", exact: true });
  for (let attempt = 0; attempt < 2; attempt++) {
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    if (await desktop.isVisible()) {
      await desktop.getByRole("link", { name: "Request a quote", exact: true }).click();
    } else {
      await page.getByRole("button", { name: "Menu", exact: true }).click();
      await mobile.getByRole("link", { name: "Request a quote", exact: true }).click();
    }
    await expectQuoteLanding(page);
  }
});

test("USR-012: late banner and cart content settle before the final quote landing", async ({ page }) => {
  let release!: () => void;
  const ready = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/hero", async (route) => {
    await ready;
    await route.fulfill({ json: { item: {
      tag: "Training equipment", number: "01", eyebrow: "Equipment for your space",
      title: "A longer banner title that wraps across multiple lines", image: "/images/pro-elite.svg",
    } } });
  });
  await page.route("**/api/catalog/selection", async (route) => { await ready; await route.continue(); });
  try {
    await page.goto("/?quote=cart#contact");
    await expect(page.locator("#products article").first()).toBeVisible();
    release();
    await expect(page.getByRole("textbox", { name: "Message", exact: true })).not.toHaveValue("");
    await expectQuoteLanding(page);
  } finally { release(); }
});

test("USR-012: catalog and banner failures still land on the quote form", async ({ page }) => {
  await page.route("**/api/products", (route) => route.fulfill({ status: 503, body: "Unavailable" }));
  await page.route("**/api/hero", (route) => route.fulfill({ status: 503, body: "Unavailable" }));
  await page.goto("/#contact");
  await expect(page.locator("#products").getByRole("alert")).toBeVisible();
  await expectQuoteLanding(page);
});

test("USR-012: ordinary visits and later price refreshes do not trigger quote scrolling", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#products article").first()).toBeVisible();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.goto("/#contact");
  await expect(page.locator("#products article").first()).toBeVisible();
  await expectQuoteLanding(page);
  await page.getByRole("textbox", { name: "Name", exact: true }).fill("Keep my name");
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  const refreshed = page.waitForResponse("**/api/catalog/selection");
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await refreshed;
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.getByRole("textbox", { name: "Name", exact: true })).toHaveValue("Keep my name");
});

for (const interaction of ["typing", "scrolling"] as const) {
  test(`USR-012: loading content does not pull the user back after ${interaction}`, async ({ page }, testInfo) => {
    let release!: () => void;
    const ready = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/api/products", async (route) => { await ready; await route.continue(); });
    try {
      const catalogRequested = page.waitForRequest("**/api/products");
      await page.goto("/#contact");
      await catalogRequested;
      await expect(page.getByText("Loading equipment...", { exact: true })).toBeVisible();
      if (interaction === "typing") {
        await page.getByRole("textbox", { name: "Name", exact: true }).fill("Keep my input");
      } else if (testInfo.project.use.isMobile) {
        await page.locator("main").dispatchEvent("touchstart", { touches: [{ identifier: 1, clientX: 100, clientY: 200 }] });
        await page.evaluate(() => window.scrollBy({ top: -300, behavior: "instant" }));
      } else {
        await page.evaluate(() => {
          window.addEventListener("wheel", () => { document.documentElement.dataset.quoteWheelReceived = "true"; }, { once: true, passive: true });
        });
        await page.mouse.wheel(0, -300);
        await expect(page.locator("html")).toHaveAttribute("data-quote-wheel-received", "true");
      }
      await page.evaluate(() => {
        const original = window.scrollTo.bind(window);
        document.documentElement.dataset.programmaticScrolls = "0";
        window.scrollTo = (x: number | ScrollToOptions = {}, y?: number) => {
          document.documentElement.dataset.programmaticScrolls = String(Number(document.documentElement.dataset.programmaticScrolls) + 1);
          if (typeof x === "number") original(x, y ?? 0);
          else original(x);
        };
      });
      release();
      await expect(page.locator("#products article").first()).toBeVisible();
      await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
      expect(await page.evaluate(() => document.documentElement.dataset.programmaticScrolls)).toBe("0");
      if (interaction === "typing") {
        await expect(page.getByRole("textbox", { name: "Name", exact: true })).toHaveValue("Keep my input");
        await expect(page.getByRole("textbox", { name: "Name", exact: true })).toBeFocused();
      }
    } finally { release(); }
  });
}
