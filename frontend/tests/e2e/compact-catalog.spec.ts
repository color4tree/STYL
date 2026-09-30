import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Fixture = { id: number; name: string; slug?: string; kind: "products" | "accessories" };
const created = new Map<string, Fixture[]>();

test.beforeEach(async ({ page }) => {
  if (!process.env.STYL_E2E_DATA_DIR || !path.basename(process.env.STYL_E2E_DATA_DIR).startsWith("styl-e2e-")) throw new Error("Use the isolated catalog test harness.");
  await page.addInitScript(() => Object.defineProperty(navigator, "doNotTrack", { get: () => "1" }));
});
test.afterEach(async ({ request }, info) => {
  for (const item of created.get(info.testId) ?? []) {
    const response = await request.delete(`${api}/api/${item.kind}/${item.id}`, { headers });
    expect(response.ok()).toBe(true);
  }
  created.delete(info.testId);
});

async function create(request: APIRequestContext, testId: string, kind: Fixture["kind"], extra: Record<string, unknown> = {}) {
  const name = `${kind === "products" ? "Equipment" : "Accessory"} compact ${randomUUID().slice(0, 8)}`;
  const response = await request.post(`${api}/api/${kind}`, { headers, data: {
    name, category: "Racks", publicationStatus: "published", prices: { CAD: 120.50, USD: 99 },
    msrps: { CAD: 250, USD: 150 }, shortDescription: "Short hidden introduction.",
    description: "Full details are hidden until deliberately expanded. ".repeat(30),
    features: ["Adjustable fixture"], material: "Steel", included: "One fixture",
    photos: ["/images/pro-elite.svg"], ...extra,
  } });
  expect(response.status(), await response.text()).toBe(200);
  const item: Fixture = { ...(await response.json()).item, kind };
  created.set(testId, [...created.get(testId) ?? [], item]);
  return item;
}

function card(page: Page, item: Fixture) {
  return page.locator(`article[data-analytics-item-type="${item.kind === "products" ? "product" : "accessory"}"][data-analytics-item-id="${item.id}"]`);
}

test("USR-017: All products is the default ordered catalog; all three views support links, reload and history", async ({ page, request }, info) => {
  const equipment = await create(request, info.testId, "products");
  const accessory = await create(request, info.testId, "accessories");
  const products = (await (await request.get(`${api}/api/products`)).json()).items;
  const accessories = (await (await request.get(`${api}/api/accessories`)).json()).items;
  const expected = [...products.map((item: { id: number }) => `product:${item.id}`), ...accessories.map((item: { id: number }) => `accessory:${item.id}`)];
  await page.goto("/");
  const collection = page.locator("#products");
  await expect(collection).toHaveAttribute("data-catalog-view", "all");
  await expect(collection.locator("article")).toHaveCount(expected.length);
  expect(await collection.locator("article").evaluateAll(items => items.map(item => `${(item as HTMLElement).dataset.analyticsItemType}:${(item as HTMLElement).dataset.analyticsItemId}`))).toEqual(expected);
  const introduction = page.locator("main > section").first();
  await expect(introduction.getByRole("link", { name: "All products", exact: true })).toHaveAttribute("aria-current", "page");
  const nav = page.getByRole("navigation", { name: page.viewportSize()!.width >= 1024 ? "Main navigation" : "Catalog navigation", exact: true });
  await expect(nav.getByRole("link").first()).toHaveText("All products");
  await nav.getByRole("link", { name: "Equipment", exact: true }).click();
  await expect(collection).toHaveAttribute("data-catalog-view", "equipment");
  await expect(card(page, equipment)).toBeVisible();
  await expect(collection.locator('article[data-analytics-item-type="accessory"]')).toHaveCount(0);
  await page.reload();
  await expect(collection).toHaveAttribute("data-catalog-view", "equipment");
  await nav.getByRole("link", { name: "Accessories", exact: true }).click();
  await expect(collection).toHaveAttribute("data-catalog-view", "accessories");
  await expect(card(page, accessory)).toBeVisible();
  await expect(collection.locator('article[data-analytics-item-type="product"]')).toHaveCount(0);
  await page.goBack();
  await expect(collection).toHaveAttribute("data-catalog-view", "equipment");
  await nav.getByRole("link", { name: "All products", exact: true }).click();
  await expect(collection).toHaveAttribute("data-catalog-view", "all");
  await expect(collection.locator("article")).toHaveCount(expected.length);
  await page.goto("/?catalog=unknown#products");
  await expect(collection).toHaveAttribute("data-catalog-view", "all");
  await page.goto("/accessories");
  await expect(card(page, accessory)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Accessories", level: 1, exact: true })).toBeVisible();
});

test("USR-017: equipment and accessories share compact collapsed cards, with mobile Show more but no Details button", async ({ page, request }, info) => {
  const fixtures = [
    await create(request, info.testId, "products"),
    await create(request, info.testId, "accessories", { sellingUnit: "Pair", packageQuantity: 2 }),
  ];
  await page.goto("/");
  for (const item of fixtures) {
    const listing = card(page, item);
    await expect(listing).toBeVisible();
    const details = listing.locator(".catalog-details-preview");
    const more = listing.getByRole("button", { name: "Show more", exact: true });
    await expect(details).toBeHidden();
    await expect(more).toHaveAttribute("aria-expanded", "false");
    await expect(listing.getByText("Short hidden introduction.", { exact: true })).toBeHidden();
    await expect(listing.getByText("Steel", { exact: true })).toBeHidden();
    await expect(listing.getByTestId("catalog-price")).toHaveText(/CAD \$120\.50/);
    await expect(listing.getByTestId("catalog-msrp").locator("s")).toHaveText("CAD $250.00");
    await expect(listing.getByRole("button", { name: "Add to cart", exact: true })).toBeVisible();
    const detailsLink = listing.getByRole("link", { name: "Details", exact: true });
    if (page.viewportSize()!.width < 1024) await expect(detailsLink).toHaveCount(0);
    else await expect(detailsLink).toHaveAttribute("href", item.kind === "products" ? `/products/${item.slug}` : `/accessories/${item.id}`);
    const collapsed = await listing.evaluate(element => element.getBoundingClientRect().height);
    await more.click();
    await expect(details).toBeVisible();
    await expect(listing.getByText("Steel", { exact: true })).toBeVisible();
    await expect(listing.getByRole("button", { name: `Increase quantity for ${item.name}`, exact: true })).toBeVisible();
    expect(await listing.evaluate(element => element.getBoundingClientRect().height)).toBeGreaterThan(collapsed + 100);
    const less = listing.getByRole("button", { name: "Show less", exact: true });
    await less.focus(); await expect(less).toBeFocused(); await less.press("Enter");
    await expect(details).toBeHidden();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
  }
});

test("SYS-020 USR-017: missing/equal/lower MSRP never invents a discount and cart quotes use actual Price", async ({ page, request }, info) => {
  const discounted = await create(request, info.testId, "products");
  const fixtures = [
    await create(request, info.testId, "accessories", { msrps: { CAD: null, USD: 200 } }),
    await create(request, info.testId, "accessories", { msrps: { CAD: 120.50, USD: 200 } }),
    await create(request, info.testId, "products", { msrps: { CAD: 10, USD: 200 } }),
  ];
  await page.goto("/");
  for (const item of fixtures) {
    await expect(card(page, item)).toBeVisible();
    await expect(card(page, item).getByTestId("catalog-msrp")).toHaveCount(0);
  }
  await card(page, discounted).getByRole("button", { name: "Add to cart", exact: true }).click();
  await page.getByRole("link", { name: "Cart (1)", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your selection", exact: true })).toBeVisible();
  await expect(page.locator("main")).toContainText("CAD $120.50");
  await expect(page.locator("main")).not.toContainText("CAD $250.00");
  await page.locator("main").getByRole("link", { name: "Request a quote", exact: true }).first().click();
  const message = page.getByRole("textbox", { name: "Message", exact: true });
  await expect(message).toHaveValue(/CAD \$120\.50/);
  await expect(message).not.toHaveValue(/250\.00/);
});

test("USR-018: accessory detail matches equipment gallery/specifications and supports cart and quote links", async ({ page, request }, info) => {
  const item = await create(request, info.testId, "accessories", {
    notes: "Accessory detail usage note.", compatibility: { uprightSize: "75 x 75 mm" },
    photos: Array.from({ length: 7 }, (_, index) => `/images/pro-elite.svg?accessory=${index}`),
  });
  await page.goto("/?catalog=accessories#products");
  const listing = card(page, item);
  await expect(listing).toBeVisible();
  if (page.viewportSize()!.width >= 1024) await listing.getByRole("link", { name: "Details", exact: true }).click();
  else await listing.getByRole("link", { name: item.name, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/accessories/${item.id}$`));
  await expect(page.getByRole("heading", { name: item.name, level: 1, exact: true })).toBeVisible();
  await expect(page.getByText("Accessory detail usage note.", { exact: true })).toBeVisible();
  await expect(page.getByTestId("catalog-msrp")).toContainText("CAD $250.00");
  const gallery = page.getByRole("group", { name: `${item.name} photos and videos`, exact: true });
  const last = gallery.getByRole("button", { name: `Show ${item.name} photo 7`, exact: true });
  await last.click();
  await expect(last).toHaveAttribute("aria-pressed", "true");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
  await page.getByRole("link", { name: "Request quote", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(new RegExp(item.name));
  await page.goto(`/accessories/${item.id}`);
  await page.locator("main").getByRole("button", { name: "Add to cart", exact: true }).first().click();
  await expect(page.getByRole("link", { name: "Cart (1)", exact: true })).toBeVisible();
  await page.goto("/accessories/999999999");
  await expect(page.getByRole("heading", { name: "Accessory not found", exact: true })).toBeVisible();
});

test("USR-017 AN-009: combined-catalog failure is explicit while an available specific view still works", async ({ page }) => {
  await page.route("**/api/accessories", route => route.fulfill({ status: 503, json: { detail: "Synthetic unavailable accessories" } }));
  await page.goto("/");
  await expect(page.locator("#products").getByRole("alert")).toContainText("complete catalog is unavailable");
  await page.locator("main > section").first().getByRole("link", { name: "Equipment", exact: true }).click();
  await expect(page.locator("#products")).toHaveAttribute("data-catalog-view", "equipment");
  await expect(page.locator('#products article[data-analytics-item-type="product"]').first()).toBeVisible();
  await expect(page.locator("#products").getByRole("alert")).toHaveCount(0);
  await page.unroute("**/api/accessories");
  await page.reload();
  await expect(page.locator("#products")).toHaveAttribute("data-catalog-view", "equipment");
  await expect(page.locator("#products")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator('#products article[data-analytics-item-type="product"]').first()).toBeVisible();
  await page.locator("main > section").first().getByRole("link", { name: "All products", exact: true }).click();
  await expect(page).toHaveURL(/\/#products$/);
  await expect(page.locator("#products")).toHaveAttribute("data-catalog-view", "all");
  await expect(page.locator('#products article[data-analytics-item-type="accessory"]').first()).toBeVisible();
});
