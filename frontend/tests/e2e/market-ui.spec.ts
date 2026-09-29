import { test, expect } from "@playwright/test";

test("GEO-008: compact GeoLite attribution is readable on desktop and mobile", async ({ page }) => {
  for (const route of ["/", "/accessories"]) {
    await page.goto(route);
    const footer = page.getByRole("contentinfo");
    await expect(footer).toContainText("GeoLite data by");
    await expect(footer.getByRole("link", { name: "MaxMind", exact: true })).toHaveAttribute("href", "https://www.maxmind.com/");
    await expect(footer.getByRole("link", { name: "GeoNames", exact: true })).toHaveAttribute("href", "https://www.geonames.org/");
    await expect(footer).toHaveCSS("font-size", "12px");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
  }
});

test("GEO-007: unknown visitors see configured CAD prices across catalog, detail and cart", async ({ page, request }) => {
  const api = "http://127.0.0.1:8102";
  const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
  const market = await request.get(`${api}/api/market`);
  expect(await market.json()).toEqual({ countryCode: null, currency: "CAD", locationStatus: "unknown" });
  const name = `CAD fallback ${Date.now()}`;
  const created = await request.post(`${api}/api/products`, {
    headers, data: { name, category: "Racks", prices: { CAD: 4005.25, USD: 4000.95 }, publicationStatus: "published", photos: [] },
  });
  expect(created.status()).toBe(200);
  const item = (await created.json()).item;
  await page.goto("/");
  await expect(page.locator("#products article").filter({ hasText: name })).toContainText("CAD $4,005.25");
  await page.goto(`/products/${item.slug}`);
  await expect(page.locator("main")).toContainText("CAD $4,005.25");
  await page.getByRole("button", { name: "Add to cart", exact: true }).first().click();
  await page.getByRole("link", { name: "Cart (1)", exact: true }).click();
  await page.waitForURL("**/cart");
  await expect(page.locator("article").filter({ hasText: name })).toContainText("CAD $4,005.25");
  await expect(page.locator("main")).not.toContainText("USD $");
});

test("USR-011: mobile top links filter All products, Equipment and Accessories without opening the menu", async ({ page }) => {
  await page.goto("/");
  const mobile = page.getByRole("navigation", { name: "Catalog navigation", exact: true });
  for (const width of [320, 390, 767, 768, 1023]) {
    await page.setViewportSize({ width, height: 844 });
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await expect(mobile.getByRole("link", { name: "All products", exact: true })).toBeInViewport({ ratio: 1 });
    await expect(mobile.getByRole("link", { name: "Equipment", exact: true })).toBeInViewport({ ratio: 1 });
    await expect(mobile.getByRole("link", { name: "Accessories", exact: true })).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await mobile.getByRole("link", { name: "Accessories", exact: true }).click();
  await page.waitForURL("**/?catalog=accessories#products");
  await expect(page.locator("#products")).toHaveAttribute("data-catalog-view", "accessories");
  await expect(page.locator('#products article[data-analytics-item-type="accessory"]').first()).toBeVisible();
  await expect(page.locator('#products article[data-analytics-item-type="product"]')).toHaveCount(0);
  await mobile.getByRole("link", { name: "Equipment", exact: true }).click();
  await page.waitForURL("**/?catalog=equipment#products");
  await expect(page.locator("#products")).toHaveAttribute("data-catalog-view", "equipment");
  await expect(page.locator('#products article[data-analytics-item-type="accessory"]')).toHaveCount(0);
  await expect(page.locator("#products article").first()).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Site navigation" })).not.toBeVisible();
  await expect.poll(async () => {
    const heading = await page.getByRole("heading", { name: "Precision-built for real routines.", exact: true }).boundingBox();
    const header = await page.locator("header").boundingBox();
    return heading && header ? heading.y - header.y - header.height : -1;
  }).toBeGreaterThanOrEqual(0);
  await mobile.getByRole("link", { name: "All products", exact: true }).click();
  await page.waitForURL("**/#products");
  await expect(page.locator("#products")).toHaveAttribute("data-catalog-view", "all");
  await expect(page.locator('#products article[data-analytics-item-type="product"]').first()).toBeVisible();
  await expect(page.locator('#products article[data-analytics-item-type="accessory"]').first()).toBeVisible();
  for (const width of [1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(mobile).toBeHidden();
    const desktop = page.getByRole("navigation", { name: "Main navigation", exact: true });
    await expect(desktop.getByRole("link", { name: "All products", exact: true })).toBeVisible();
    await expect(desktop.getByRole("link", { name: "Equipment", exact: true })).toBeVisible();
    await expect(desktop.getByRole("link", { name: "Accessories", exact: true })).toBeVisible();
  }
});

test("Canadian display and saved-cart reprice use CAD without converting USD", async ({ page }) => {
  const item = { id: 9901, name: "Canada priced rack", slug: "canada-priced-rack", category: "Racks", price: 4005.25, currency: "CAD", image: "/images/pro-elite.svg" };
  const body = { items: [item], market: { countryCode: "CA", currency: "CAD", locationStatus: "located" } };
  await page.route("**/api/products", (route) => route.fulfill({ json: body }));
  await page.route("**/api/catalog/selection", (route) => route.fulfill({ json: body }));
  await page.goto("/?catalog=equipment");
  await expect(page.locator("#products article")).toContainText("CAD $4,005.25");
  await page.evaluate(() => localStorage.setItem("styl-cart", JSON.stringify([
    { id: 9901, name: "Canada priced rack", price: 4000.95, currency: "USD", quantity: 2 },
    { id: 9902, name: "Not sold in Canada", price: 99, currency: "USD", quantity: 1 },
  ])));
  await page.goto("/cart");
  await expect(page.locator("article")).toHaveCount(1);
  await expect(page.locator("article")).toContainText("CAD $8,010.50");
  await expect(page.getByRole("status").filter({ hasText: "unavailable for your location" })).toBeVisible();
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("styl-cart")!));
  expect(stored[0].price).toBe(4005.25);
  expect(stored[0].currency).toBe("CAD");
});

test("a successful new upload batch separates earlier failures from current results", async ({ page }) => {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "New", exact: true }).click();
  const input = page.locator('input[type="file"]');
  await input.setInputFiles({ name: "earlier.txt", mimeType: "text/plain", buffer: Buffer.from("invalid") });
  await expect(page.getByRole("alert", { name: "Failed uploads" })).toContainText("earlier.txt");
  await input.setInputFiles({ name: "now.png", mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aC1sAAAAASUVORK5CYII=", "base64") });
  await expect(page.getByRole("status").filter({ hasText: "Batch 2: 1 of 1 files uploaded" })).toBeVisible();
  await expect(page.getByRole("alert", { name: "Failed uploads" })).toHaveCount(0);
  await expect(page.getByText("earlier.txt", { exact: false })).not.toBeVisible();
  await page.getByText("Earlier upload attempts (1 unresolved files)", { exact: true }).click();
  await expect(page.getByText(/Batch 1, earlier.txt/)).toBeVisible();
});
