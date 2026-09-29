import { test, expect, type Page, type APIRequestContext } from "@playwright/test";
import { randomUUID } from "node:crypto";

const api = "http://127.0.0.1:8102";
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };

async function signIn(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
  await expect(page.getByRole("heading", { level: 1, name: "Equipment management", exact: true })).toBeVisible();
}

async function create(request: APIRequestContext, catalog: string, name: string, featured = false, extra: Record<string, unknown> = {}) {
  const response = await request.post(`${api}/api/${catalog}`, {
    headers, data: { name, category: "Racks", prices: { CAD: 19.95, USD: 14.50 }, publicationStatus: "published", photos: [], ...(catalog === "products" ? { featured } : {}), ...extra },
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()).item;
}

async function expectToolbar(page: Page, catalog: "products" | "accessories", arranging = false) {
  const toolbar = page.getByRole("group", { name: `${catalog === "products" ? "Equipment" : "Accessories"} catalog controls`, exact: true });
  await expect(toolbar).toBeVisible();
  await expect(toolbar.locator(":scope > h2, :scope > button")).toHaveText(["Catalog", arranging ? "Done arranging" : "Arrange listing order", "New"]);
  const toggle = toolbar.getByRole("button", { name: arranging ? "Done arranging" : "Arrange listing order", exact: true });
  await expect(toggle).toHaveAttribute("aria-pressed", String(arranging));
  await expect(page.getByRole("list", { name: catalog === "products" ? "Equipment listings" : "Accessory listings", exact: true })).toHaveAttribute("id", (await toggle.getAttribute("aria-controls"))!);
  for (const button of await toolbar.getByRole("button").all()) {
    const bounds = await button.boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.height).toBeGreaterThanOrEqual(48);
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
  }
}

for (const catalog of ["products", "accessories"] as const) {
  test(`USR-016: ${catalog} Add to cart confirms immediately and respects the quantity cap`, async ({ page }) => {
    await page.goto(catalog === "products" ? "/?catalog=equipment" : "/accessories");
    const card = page.locator(catalog === "products" ? "#products article" : "main article").first();
    const add = card.locator("[data-cart-feedback]");
    await expect(add).toBeEnabled();
    await page.clock.install();
    await add.click();
    await expect(add).toHaveAttribute("data-cart-feedback", "added", { timeout: 500 });
    await expect(add).toContainText("Added");
    await expect(page.getByRole("link", { name: "Cart (1)", exact: true })).toBeVisible();
    await page.clock.fastForward(2501);
    await expect(add).toHaveText("Add to cart");
    for (let quantity = 2; quantity <= 10; quantity++) {
      await add.click();
      await expect(page.getByRole("link", { name: `Cart (${quantity})`, exact: true })).toBeVisible();
      await expect(add).toHaveAttribute("data-cart-feedback", "added");
    }
    await expect(add).toBeDisabled();
    await page.clock.fastForward(2501);
    await expect(add).toHaveText("Maximum 10 in cart");
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("styl-cart")!)[0].quantity)).toBe(10);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
  });
}

test("USR-016: failed cart storage never displays an Added confirmation", async ({ page }) => {
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (this === window.localStorage && key === "styl-cart") throw new Error("Synthetic cart storage failure");
      return original.call(this, key, value);
    };
  });
  await page.goto("/");
  const add = page.locator("#products article").first().locator("[data-cart-feedback]");
  await expect(add).toBeEnabled();
  await add.click();
  await expect(add).toHaveAttribute("data-cart-feedback", "failed", { timeout: 500 });
  await expect(add).toHaveText("Not added");
  await expect(page.locator("#products").getByRole("alert")).toContainText("Your cart was not saved");
  await expect(page.getByRole("link", { name: "Cart (0)", exact: true })).toBeVisible();
});

test("USR-016: product detail and mobile sticky action confirm their own add", async ({ page, request }, testInfo) => {
  const item = await create(request, "products", `Feedback detail ${randomUUID().slice(0, 8)}`, false, { description: "Detailed training equipment information. ".repeat(100) });
  await page.goto(`/products/${item.slug}`);
  const inline = page.locator('main section [data-cart-feedback]').first();
  await expect(inline).toBeEnabled();
  await inline.click();
  await expect(inline).toHaveAttribute("data-cart-feedback", "added", { timeout: 500 });
  if (testInfo.project.use.isMobile) {
    await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" }));
    const sticky = page.locator(".safe-action [data-cart-feedback]");
    await expect(sticky).toBeVisible();
    await sticky.click();
    await expect(sticky).toContainText("Added");
    await expect(page.getByRole("link", { name: "Cart (2)", exact: true })).toBeVisible();
  }
});

test("USR-016 ADM-011: long listing names wrap in feedback and the cart without widening the viewport", async ({ page, request }) => {
  const item = await create(request, "products", `Long ${randomUUID().slice(0, 8)} ${"X".repeat(140)}`);
  await page.goto("/");
  const card = page.locator("#products article").filter({ hasText: item.name });
  await card.getByRole("button", { name: "Add to cart", exact: true }).click();
  await expect(card.locator("[data-cart-feedback]")).toHaveAttribute("data-cart-feedback", "added");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
  await page.getByRole("link", { name: "Cart (1)", exact: true }).click();
  await page.waitForURL("**/cart");
  await expect(page.locator("main article")).toContainText(item.name);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
  await page.getByRole("button", { name: "Clear cart", exact: true }).click();
  await page.getByRole("button", { name: "Confirm clear cart", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your cart is empty.", exact: true })).toBeVisible();
});

for (const catalog of ["products", "accessories"] as const) {
  test(`ADM-011 SYS-019: ${catalog} arrange mode moves the actual cards and preserves editor fields`, async ({ page, request }) => {
    const suffix = randomUUID().slice(0, 8);
    const first = await create(request, catalog, `Order first ${suffix} ${"X".repeat(140)}`, true);
    const target = await create(request, catalog, `Order promoted ${suffix}`);
    const initial = (await (await request.get(`${api}/api/admin/${catalog}`, { headers })).json()).items;
    const expectedIds = initial.map((item: { id: number }) => item.id);
    const ids = [first.id, target.id, ...expectedIds.filter((id: number) => id !== first.id && id !== target.id)];
    expect((await request.put(`${api}/api/admin/${catalog}/order`, { headers, data: { ids, expectedIds } })).status()).toBe(200);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await signIn(page);
    if (catalog === "accessories") await page.getByRole("button", { name: "Accessories", exact: true }).click();
    const field = page.getByRole("textbox", { name: catalog === "products" ? "Equipment name" : "Accessory name", exact: true });
    await expect(field).not.toHaveValue("");
    const original = await field.inputValue();
    await field.fill("Unsaved edit retained during ordering");
    const cards = page.locator("[data-catalog-card]");
    await expect(cards).toHaveCount(ids.length);
    const targetCard = page.locator(`[data-catalog-card="${target.id}"]`);
    await expectToolbar(page, catalog);
    await expect(page.getByRole("button", { name: `Move ${target.name} up`, exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Arrange listing order", exact: true }).click();
    await expect(page.getByRole("button", { name: "Done arranging", exact: true })).toBeVisible();
    await expectToolbar(page, catalog, true);
    await expect(cards).toHaveCount(ids.length);
    await expect(targetCard.locator("img")).toHaveCount(1);
    await expect(targetCard).toContainText("CAD $19.95");
    await expect(targetCard).toContainText("USD $14.50");
    await expect(page.getByRole("combobox", { name: /^Listing position for/ })).toHaveCount(0);
    await expect(targetCard).toHaveAttribute("data-position", "2");
    const response = page.waitForResponse((value) => value.url().endsWith(`/api/admin/${catalog}/order`) && value.request().method() === "PUT");
    await targetCard.getByRole("button", { name: `Move ${target.name} up`, exact: true }).click();
    expect((await response).status()).toBe(200);
    await expect(page.getByRole("status").filter({ hasText: "Listing order saved" })).toBeVisible();
    await expect(cards.first()).toHaveAttribute("data-catalog-card", String(target.id));
    await expect(targetCard).toBeFocused();
    await expect(field).toHaveValue("Unsaved edit retained during ordering");
    const saved = (await (await request.get(`${api}/api/admin/${catalog}`, { headers })).json()).items;
    expect(saved[0].id).toBe(target.id);
    expect(saved.some((item: { name: string }) => item.name === "Unsaved edit retained during ordering")).toBe(false);
    const moveDown = targetCard.getByRole("button", { name: `Move ${target.name} down`, exact: true });
    await expect(moveDown).toBeEnabled();
    await moveDown.focus();
    await expect(moveDown).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(targetCard).toHaveAttribute("data-position", "2");
    await expect(targetCard).toBeFocused();
    await targetCard.getByRole("button", { name: `Move ${target.name} up`, exact: true }).click();
    await expect(targetCard).toHaveAttribute("data-position", "1");
    await page.getByRole("button", { name: "Done arranging", exact: true }).click();
    await expectToolbar(page, catalog);
    await expect(page.getByRole("button", { name: `Move ${target.name} up`, exact: true })).toHaveCount(0);
    await expect(field).toHaveValue("Unsaved edit retained during ordering");
    await expect(targetCard.getByRole("button").first()).toBeEnabled();
    await field.fill(original);
    await page.reload();
    if (catalog === "accessories") await page.getByRole("button", { name: "Accessories", exact: true }).click();
    await page.getByRole("button", { name: "Arrange listing order", exact: true }).click();
    await expect(targetCard).toHaveAttribute("data-position", "1");
    await expect(page.getByRole("button", { name: `Move ${target.name} up`, exact: true })).toBeDisabled();
    await expect(cards.last().getByRole("button", { name: / down$/ })).toBeDisabled();
    await page.setViewportSize({ width: 320, height: 844 });
    await expectToolbar(page, catalog, true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    await targetCard.getByRole("button", { name: `Move ${target.name} down`, exact: true }).click();
    await expect(targetCard).toHaveAttribute("data-position", "2");
    await targetCard.getByRole("button", { name: `Move ${target.name} up`, exact: true }).click();
    await expect(targetCard).toHaveAttribute("data-position", "1");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    const doneArranging = page.getByRole("button", { name: "Done arranging", exact: true });
    await expect(doneArranging).toBeEnabled();
    await doneArranging.focus();
    await expect(doneArranging).toBeFocused();
    await page.keyboard.press("Enter");
    await expectToolbar(page, catalog);
    await expect(targetCard.getByRole("button")).toHaveCount(1);
    await targetCard.getByRole("button").click();
    await expect(field).toBeVisible();
    await expect(field).toHaveValue(target.name);
    await expect(page.getByRole("button", { name: "Save changes", exact: true })).toBeEnabled();
    await expect(page.getByRole("button", { name: catalog === "products" ? "Delete equipment" : "Delete accessory", exact: true })).toBeEnabled();
    await page.goto(catalog === "products" ? "/?catalog=equipment" : "/accessories");
    const publicCards = page.locator(catalog === "products" ? "#products article" : "main article");
    await expect(publicCards.first().locator(catalog === "products" ? ":scope > h3" : ":scope > h2")).toHaveText(target.name);
    if (catalog === "products") {
      const publicItems = (await (await request.get(`${api}/api/products`)).json()).items;
      expect(publicItems.find((item: { id: number }) => item.id === first.id).featured).toBe(true);
      expect(publicItems[0].id).toBe(target.id);
    }
  });
}

for (const catalog of ["products", "accessories"] as const) {
for (const status of [503, 409]) {
test(`ADM-011: ${catalog} failed listing-order save (${status}) keeps the existing cards and permits refresh`, async ({ page, request }) => {
  const rows = (await (await request.get(`${api}/api/admin/${catalog}`, { headers })).json()).items;
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signIn(page);
  if (catalog === "accessories") await page.getByRole("button", { name: "Accessories", exact: true }).click();
  await expectToolbar(page, catalog);
  await page.getByRole("button", { name: "Arrange listing order", exact: true }).click();
  await page.route(`**/api/admin/${catalog}/order`, (route) => route.fulfill({ status, json: { detail: "Order storage temporarily unavailable" } }));
  await page.getByRole("button", { name: `Move ${rows[1].name} up`, exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Order storage temporarily unavailable");
  await expect(page.locator(`[data-catalog-card="${rows[1].id}"]`)).toHaveAttribute("data-position", "2");
  const saved = (await (await request.get(`${api}/api/admin/${catalog}`, { headers })).json()).items;
  expect(saved.map((item: { id: number }) => item.id)).toEqual(rows.map((item: { id: number }) => item.id));
  await page.getByRole("button", { name: "Refresh listing order", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Listing order refreshed" })).toBeVisible();
});
}
}

for (const catalog of ["products", "accessories"] as const) {
test(`ADM-011: empty ${catalog} keeps the Catalog, Arrange, New toolbar without enabling ordering`, async ({ page }) => {
  await page.route(`**/api/admin/${catalog}`, (route) => route.fulfill({ json: { items: [] } }));
  await signIn(page);
  if (catalog === "accessories") await page.getByRole("button", { name: "Accessories", exact: true }).click();
  await expectToolbar(page, catalog);
  await expect(page.getByRole("button", { name: "Arrange listing order", exact: true })).toBeDisabled();
  await expect(page.getByText("No saved items to arrange.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "New", exact: true }).click();
  await expect(page.getByRole("textbox", { name: catalog === "products" ? "Equipment name" : "Accessory name", exact: true })).toHaveValue("");
  await expect(page.getByRole("button", { name: catalog === "products" ? "Create equipment" : "Create accessory", exact: true })).toBeEnabled();
});

test(`ADM-011: ${catalog} catalog toolbar and moves are disabled while saving`, async ({ page, request }) => {
  const rows = (await (await request.get(`${api}/api/admin/${catalog}`, { headers })).json()).items;
  await signIn(page);
  if (catalog === "accessories") await page.getByRole("button", { name: "Accessories", exact: true }).click();
  await expectToolbar(page, catalog);
  await page.getByRole("button", { name: "Arrange listing order", exact: true }).click();
  let release!: () => void;
  let count = 0;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**/api/admin/${catalog}/order`, async (route) => { count++; await gate; await route.continue(); });
  try {
    await page.getByRole("button", { name: `Move ${rows[1].name} up`, exact: true }).click();
    await expect(page.getByRole("button", { name: "Done arranging", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "New", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Refresh listing order", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: `Move ${rows[0].name} down`, exact: true })).toBeDisabled();
    await expect(page.locator(`[data-catalog-card="${rows[1].id}"]`)).toHaveAttribute("data-position", "2");
    expect(count).toBe(1);
    release();
    await expect(page.locator(`[data-catalog-card="${rows[1].id}"]`)).toHaveAttribute("data-position", "1");
    await expect(page.getByRole("button", { name: "Done arranging", exact: true })).toBeEnabled();
    await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
    await expectToolbar(page, catalog, true);
  } finally { release(); }
});
}
