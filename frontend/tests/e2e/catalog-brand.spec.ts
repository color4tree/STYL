import { test, expect, type Locator, type Page } from "@playwright/test";

const api = "http://127.0.0.1:8102";
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Catalog = "products" | "accessories";

async function openAdmin(page: Page, catalog: Catalog) {
  await page.goto("/admin");
  const token = page.getByLabel("Admin token", { exact: true });
  await expect(token.or(page.getByRole("button", { name: "New", exact: true }))).toBeVisible();
  if (await token.isVisible()) {
    await token.fill(process.env.STYL_E2E_TOKEN!);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
  }
  await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
  if (catalog === "accessories") {
    await page.getByRole("button", { name: "Accessories", exact: true }).click();
    await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
  }
}

async function expectCategory(label: Locator, brand: string | null) {
  await expect(label).toHaveText(brand ? `${brand} Strength` : "Strength");
  await expect(label).not.toContainText("·");
  const parts = label.locator(":scope > span");
  await expect(parts).toHaveCount(brand ? 2 : 1);
  if (brand) {
    await expect(parts.first()).toHaveText(brand);
    await expect(parts.last()).toHaveText("Strength");
    const gap = await label.evaluate(node => getComputedStyle(node).columnGap);
    expect(gap).toBe("12px");
    if (brand === "STYL") {
      const [first, last] = await Promise.all([parts.first().boundingBox(), parts.last().boundingBox()]);
      expect(first).not.toBeNull();
      expect(last).not.toBeNull();
      expect(Math.abs(last!.x - first!.x - first!.width - 12)).toBeLessThanOrEqual(1);
    }
  }
}

async function editor(page: Page, catalog: Catalog, name: string, expectedBrand?: string | null) {
  await openAdmin(page, catalog);
  const entry = page.getByRole("button").filter({ hasText: name });
  if (expectedBrand !== undefined) await expectCategory(entry.getByTestId("catalog-category"), expectedBrand);
  await entry.click();
  await expect(page.getByLabel("Brand (optional)", { exact: true })).toBeVisible();
}

async function save(page: Page, catalog: Catalog, id: number) {
  const result = page.waitForResponse(response => response.url() === `${api}/api/${catalog}/${id}` && response.request().method() === "PUT");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  const response = await result;
  expect(response.status(), await response.text()).toBe(200);
  await expect(page.getByRole("status").filter({ hasText: "saved successfully" })).toBeVisible();
  await expect(page.getByText("Unsaved changes", { exact: true })).toHaveCount(0);
  return (await response.json()).item;
}

for (const catalog of ["products", "accessories"] as const) {
  test(`ADM-015 ${catalog}: new item saves an optional brand without prefixing the name`, async ({ page, request }) => {
    await openAdmin(page, catalog);
    await page.getByRole("button", { name: "New", exact: true }).click();
    const brand = page.getByLabel("Brand (optional)", { exact: true });
    await expect(brand).toHaveValue("");
    const name = `New branded ${catalog} ${Date.now()}`;
    await page.getByLabel(catalog === "products" ? "Equipment name" : "Accessory name", { exact: true }).fill(name);
    await page.getByRole("combobox", { name: "Category", exact: true }).selectOption("Strength");
    await brand.fill(" STYL ");
    const pending = page.waitForResponse(response => response.url() === `${api}/api/${catalog}` && response.request().method() === "POST");
    await page.getByRole("button", { name: catalog === "products" ? "Create equipment" : "Create accessory", exact: true }).click();
    const response = await pending;
    expect(response.status(), await response.text()).toBe(200);
    const item = (await response.json()).item;
    try {
      expect(item.name).toBe(name);
      expect(item.brand).toBe("STYL");
      expect(item.publicationStatus).toBe("draft");
      await expect(page.getByText("Unsaved changes", { exact: true })).toHaveCount(0);
      await editor(page, catalog, name, "STYL");
      await expect(brand).toHaveValue("STYL");
    } finally {
      expect((await request.delete(`${api}/api/${catalog}/${item.id}`, { headers })).status()).toBe(200);
    }
  });

  test(`SYS-024 ADM-015 USR-020 ${catalog}: optional brand saves, reloads, retains failures and displays beside category`, async ({ page, request }) => {
    const name = `Brand fixture ${catalog} ${Date.now()}`;
    const response = await request.post(`${api}/api/${catalog}`, {
      headers, data: { name, category: "Strength", prices: { CAD: 125, USD: 100 }, publicationStatus: "published", photos: [] },
    });
    expect(response.status()).toBe(200);
    const item = (await response.json()).item;
    const href = catalog === "products" ? `/products/${item.slug}` : `/accessories/${item.id}`;
    const brand = page.getByLabel("Brand (optional)", { exact: true });
    try {
      await editor(page, catalog, name, null);
      await expect(brand).toHaveValue("");
      await expect(brand).toHaveAttribute("maxlength", "200");
      await brand.fill("  STYL  ");
      expect((await save(page, catalog, item.id)).brand).toBe("STYL");
      await editor(page, catalog, name, "STYL");
      await expect(brand).toHaveValue("STYL");

      await brand.fill("Other brand");
      await expect(page.getByText("Unsaved changes", { exact: true })).toBeVisible();
      page.once("dialog", dialog => dialog.dismiss());
      await page.getByRole("button", { name: "Home banner", exact: true }).click();
      await expect(brand).toHaveValue("Other brand");
      await page.route(`**/api/${catalog}/${item.id}`, route => route.fulfill({ status: 503, json: { detail: "Brand save temporarily unavailable" } }));
      await page.getByRole("button", { name: "Save changes", exact: true }).click();
      await expect(page.locator("main").getByRole("alert")).toContainText("Brand save temporarily unavailable");
      await expect(brand).toHaveValue("Other brand");
      const stored = await request.get(`${api}/api/admin/${catalog}`, { headers });
      expect((await stored.json()).items.find((row: { id: number }) => row.id === item.id).brand).toBe("STYL");
      await page.unroute(`**/api/${catalog}/${item.id}`);
      await brand.fill("STYL");
      await save(page, catalog, item.id);

      await page.goto("/#products");
      const card = page.locator(`article[data-analytics-item-id="${item.id}"]`);
      await expectCategory(card.getByTestId("catalog-category"), "STYL");
      await expect(card.getByRole("heading")).toHaveText(name);
      await card.getByRole("link", { name, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`${href}$`));
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
      await expectCategory(page.getByTestId("catalog-category"), "STYL");

      await editor(page, catalog, name);
      const longBrand = "B".repeat(200);
      await brand.fill(longBrand);
      await save(page, catalog, item.id);
      for (const route of ["/#products", href]) {
        await page.goto(route);
        const surface = route === href ? page.locator("main") : page.locator(`article[data-analytics-item-id="${item.id}"]`);
        await expectCategory(surface.getByTestId("catalog-category"), longBrand);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
      }
      await editor(page, catalog, name, longBrand);
      await brand.fill("");
      const cleared = await save(page, catalog, item.id);
      expect(cleared.brand).toBeNull();
      expect(cleared.id).toBe(item.id);
      expect(cleared.slug).toBe(item.slug);
      await editor(page, catalog, name, null);
      await expect(brand).toHaveValue("");
      for (const route of ["/#products", href]) {
        await page.goto(route);
        const surface = route === href ? page.locator("main") : page.locator(`article[data-analytics-item-id="${item.id}"]`);
        await expectCategory(surface.getByTestId("catalog-category"), null);
      }
    } finally {
      expect((await request.delete(`${api}/api/${catalog}/${item.id}`, { headers })).status()).toBe(200);
    }
  });
}
