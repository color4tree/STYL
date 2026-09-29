import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const api = "http://127.0.0.1:8102";
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Catalog = "products" | "accessories";
type Values = { CAD: number | null; USD: number | null };
type Item = { id: number; name: string; prices: Values; msrps: Values; provenance?: { notes: string } };
const unique = (catalog: Catalog) => `MSRP ${catalog} ${Date.now()} ${Math.random().toString(16).slice(2, 8)}`;
const tabName = (catalog: Catalog) => catalog === "products" ? "Equipment" : "Accessories";
const nameLabel = (catalog: Catalog) => catalog === "products" ? "Equipment name" : "Accessory name";
const msrp = (page: Page, currency: "CAD" | "USD") => page.getByRole("textbox", { name: `${currency} MSRP`, exact: true });

async function signIn(page: Page, catalog: Catalog) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
  if (catalog === "accessories") {
    await page.getByRole("button", { name: "Accessories", exact: true }).click();
    await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
  }
}

async function reloadItem(page: Page, catalog: Catalog, name: string) {
  await page.reload();
  await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
  if (catalog === "accessories") {
    await page.getByRole("button", { name: "Accessories", exact: true }).click();
    await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
  }
  await page.getByRole("button").filter({ hasText: name }).click();
  await expect(page.getByLabel(nameLabel(catalog), { exact: true })).toHaveValue(name);
}

async function openItem(page: Page, catalog: Catalog, name: string) {
  const input = page.getByLabel(nameLabel(catalog), { exact: true });
  if (await input.isVisible() && await input.inputValue() === name) return;
  const back = page.getByRole("button", { name: catalog === "products" ? "← Back to equipment" : "← Back to accessories", exact: true });
  if (await back.isVisible()) await back.click();
  await page.getByRole("button").filter({ hasText: name }).click();
  await expect(input).toHaveValue(name);
}

async function save(page: Page, catalog: Catalog, id?: number): Promise<Item> {
  const url = `${api}/api/${catalog}${id === undefined ? "" : `/${id}`}`;
  const result = page.waitForResponse((response) => response.url() === url && response.request().method() === (id === undefined ? "POST" : "PUT"));
  await page.getByRole("button", { name: id === undefined ? catalog === "products" ? "Create equipment" : "Create accessory" : "Save changes", exact: true }).click();
  const response = await result;
  expect(response.status(), await response.text()).toBe(200);
  const item: Item = (await response.json()).item;
  expect(response.request().postDataJSON().msrps).toEqual(item.msrps);
  await expect(page.getByRole("status").filter({ hasText: "saved successfully" })).toBeVisible();
  await expect(page.getByText("Unsaved changes", { exact: true })).toHaveCount(0);
  return item;
}

async function createFixture(request: APIRequestContext, catalog: Catalog, msrps?: Values): Promise<Item> {
  const response = await request.post(`${api}/api/${catalog}`, {
    headers, data: { name: unique(catalog), category: "Handle", prices: { CAD: 29.95, USD: 19.95 }, msrps, publicationStatus: "published", photos: [] },
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()).item;
}

async function readItem(request: APIRequestContext, catalog: Catalog, id: number): Promise<Item> {
  const response = await request.get(`${api}/api/admin/${catalog}`, { headers });
  expect(response.status()).toBe(200);
  const items: Item[] = (await response.json()).items;
  const item = items.find((entry) => entry.id === id);
  expect(item).toBeDefined();
  return item!;
}

for (const catalog of ["products", "accessories"] as const) {
  test(`ADM-012 ${catalog}: optional MSRP validates cents, saves, reloads and clears each market independently`, async ({ page, request }) => {
    let id: number | undefined;
    try {
      await signIn(page, catalog);
      await page.getByRole("button", { name: "New", exact: true }).click();
      await expect(msrp(page, "CAD")).toHaveValue("");
      await expect(msrp(page, "USD")).toHaveValue("");
      await expect(page.getByText("Optional; shown only when higher than Price. Does not affect checkout/quote pricing.", { exact: true })).toBeVisible();
      const name = unique(catalog);
      await page.getByLabel(nameLabel(catalog), { exact: true }).fill(name);
      await page.getByRole("combobox", { name: "Category", exact: true }).selectOption("Handle");
      await page.getByRole("textbox", { name: "Canada price (CAD)", exact: true }).fill("29.95");
      await page.getByRole("textbox", { name: "US price (USD)", exact: true }).fill("19.95");
      await expect(page.getByRole("status").filter({ hasText: "Needs attention" })).toHaveCount(0);
      for (const [currency, invalid] of [["CAD", "-1"], ["USD", "19.955"], ["CAD", "Infinity"], ["USD", "NaN"]] as const) {
        await msrp(page, currency).fill(invalid);
        await page.getByRole("button", { name: catalog === "products" ? "Create equipment" : "Create accessory", exact: true }).click();
        await expect(msrp(page, currency)).toHaveAttribute("aria-invalid", "true");
        await expect(page.locator("main").getByRole("alert")).toContainText("nonnegative MSRP with no more than two decimal places");
        await expect(msrp(page, currency)).toHaveValue(invalid);
        await msrp(page, currency).fill("");
      }
      await msrp(page, "CAD").fill("49.5");
      await msrp(page, "CAD").blur();
      await expect(msrp(page, "CAD")).toHaveValue("49.50");
      await msrp(page, "USD").fill("39.95");
      const created = await save(page, catalog);
      id = created.id;
      expect(created.msrps).toEqual({ CAD: 49.5, USD: 39.95 });
      expect(created.prices).toEqual({ CAD: 29.95, USD: 19.95 });
      await reloadItem(page, catalog, name);
      await expect(msrp(page, "CAD")).toHaveValue("49.50");
      await expect(msrp(page, "USD")).toHaveValue("39.95");
      await msrp(page, "CAD").fill("");
      expect((await save(page, catalog, id)).msrps).toEqual({ CAD: null, USD: 39.95 });
      await reloadItem(page, catalog, name);
      await expect(msrp(page, "CAD")).toHaveValue("");
      await expect(msrp(page, "USD")).toHaveValue("39.95");
      await page.getByLabel("Internal notes", { exact: true }).fill("Unrelated private note");
      const updated = await save(page, catalog, id);
      expect(updated.msrps).toEqual({ CAD: null, USD: 39.95 });
      expect(updated.provenance?.notes).toBe("Unrelated private note");
      await msrp(page, "CAD").fill("49.95");
      await msrp(page, "USD").fill("");
      expect((await save(page, catalog, id)).msrps).toEqual({ CAD: 49.95, USD: null });
      await reloadItem(page, catalog, name);
      await expect(msrp(page, "CAD")).toHaveValue("49.95");
      await expect(msrp(page, "USD")).toHaveValue("");
      expect((await readItem(request, catalog, id)).prices).toEqual({ CAD: 29.95, USD: 19.95 });
      const viewportWidth = page.viewportSize()!.width;
      const layout = await page.evaluate((width) => ({
        documentWidth: document.documentElement.scrollWidth,
        innerWidth,
        overflowing: [...document.querySelectorAll("body *")].map((element) => {
          const bounds = element.getBoundingClientRect();
          return { tag: element.tagName, id: element.id, type: element.getAttribute("type"), className: element.getAttribute("class"), right: bounds.right, width: bounds.width, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth, overflow: getComputedStyle(element).overflowX };
        }).filter((element) => element.right > width + 0.5 || element.scrollWidth > element.clientWidth + 0.5),
      }), viewportWidth);
      expect(layout.documentWidth, JSON.stringify(layout)).toBeLessThanOrEqual(viewportWidth);
    } finally {
      if (id !== undefined) await request.delete(`${api}/api/${catalog}/${id}`, { headers });
    }
  });

  test(`ADM-012 ${catalog}: missing MSRP stays empty and values below or equal to Price remain valid`, async ({ page, request }) => {
    const item = await createFixture(request, catalog);
    try {
      await signIn(page, catalog);
      await page.getByRole("button").filter({ hasText: item.name }).click();
      await expect(msrp(page, "CAD")).toHaveValue("");
      await expect(msrp(page, "USD")).toHaveValue("");
      await expect(page.getByRole("status").filter({ hasText: "Needs attention" })).toHaveCount(0);
      await page.getByLabel("Internal notes", { exact: true }).fill("Old entry without MSRP");
      expect((await save(page, catalog, item.id)).msrps).toEqual({ CAD: null, USD: null });
      await msrp(page, "CAD").fill("10.25");
      await msrp(page, "USD").fill("19.95");
      expect((await save(page, catalog, item.id)).msrps).toEqual({ CAD: 10.25, USD: 19.95 });
      await reloadItem(page, catalog, item.name);
      await expect(msrp(page, "CAD")).toHaveValue("10.25");
      await expect(msrp(page, "USD")).toHaveValue("19.95");
      await msrp(page, "CAD").fill("0");
      await msrp(page, "USD").fill("");
      expect((await save(page, catalog, item.id)).msrps).toEqual({ CAD: 0, USD: null });
      expect((await readItem(request, catalog, item.id)).prices).toEqual({ CAD: 29.95, USD: 19.95 });
    } finally {
      await request.delete(`${api}/api/${catalog}/${item.id}`, { headers });
    }
  });

  test(`ADM-003 ADM-012 ${catalog}: MSRP-only edits guard navigation, survive failures, retry, reset and delete`, async ({ page, request }) => {
    const item = await createFixture(request, catalog, { CAD: 49.95, USD: 39.95 });
    try {
      await signIn(page, catalog);
      await page.getByRole("button").filter({ hasText: item.name }).click();
      await msrp(page, "CAD").fill("59.95");
      await msrp(page, "CAD").blur();
      await expect(page.getByText("Unsaved changes", { exact: true })).toBeVisible();
      const otherTab = page.getByRole("button", { name: catalog === "products" ? "Accessories" : "Equipment", exact: true });
      const navigation = [
        otherTab,
        page.getByRole("link", { name: catalog === "products" ? "View portal" : "View accessories page", exact: true }),
        page.getByRole("button", { name: "Sign out", exact: true }),
      ];
      const back = page.getByRole("button", { name: catalog === "products" ? "← Back to equipment" : "← Back to accessories", exact: true });
      navigation.push(await back.isVisible() ? back : page.getByRole("button", { name: "New", exact: true }));
      for (const target of navigation) {
        const prompted = page.waitForEvent("dialog");
        page.once("dialog", (dialog) => dialog.dismiss());
        await target.click();
        expect((await prompted).type()).toBe("confirm");
        await expect(msrp(page, "CAD")).toHaveValue("59.95");
      }
      await msrp(page, "CAD").fill("49.95");
      await msrp(page, "CAD").blur();
      await expect(page.getByText("Unsaved changes", { exact: true })).toHaveCount(0);
      await otherTab.click();
      await page.getByRole("button", { name: tabName(catalog), exact: true }).click();
      await expect(page.getByRole("button", { name: tabName(catalog), exact: true })).toHaveAttribute("aria-pressed", "true");
      await openItem(page, catalog, item.name);
      await expect(msrp(page, "CAD")).toBeEnabled();
      await msrp(page, "CAD").fill("59.95");
      await msrp(page, "USD").fill("");
      await page.getByRole("button", { name: "Backup", exact: true }).click();
      await expect(page.getByRole("status").filter({ hasText: "You have unsaved changes" })).toBeVisible();
      await page.getByRole("button", { name: tabName(catalog), exact: true }).click();
      await expect(msrp(page, "CAD")).toHaveValue("59.95");
      await expect(msrp(page, "USD")).toHaveValue("");

      await page.route(`**/api/${catalog}/${item.id}`, (route) => route.fulfill({ status: 503, json: { detail: "MSRP save temporarily unavailable" } }));
      await page.getByRole("button", { name: "Save changes", exact: true }).click();
      await expect(page.locator("main").getByRole("alert")).toContainText("MSRP save temporarily unavailable");
      await expect(msrp(page, "CAD")).toHaveValue("59.95");
      await expect(msrp(page, "USD")).toHaveValue("");
      await expect(page.getByText("Unsaved changes", { exact: true })).toBeVisible();
      expect((await readItem(request, catalog, item.id)).msrps).toEqual({ CAD: 49.95, USD: 39.95 });
      await page.unroute(`**/api/${catalog}/${item.id}`);
      expect((await save(page, catalog, item.id)).msrps).toEqual({ CAD: 59.95, USD: null });

      if (!(await back.isVisible())) {
        await msrp(page, "CAD").fill("69.95");
        await page.getByRole("button", { name: "Arrange listing order", exact: true }).click();
        await page.getByRole("button", { name: `Move ${item.name} up`, exact: true }).click();
        await expect(page.getByRole("status").filter({ hasText: "Listing order saved" })).toBeVisible();
        await page.getByRole("button", { name: "Refresh listing order", exact: true }).click();
        await expect(page.getByRole("status").filter({ hasText: "Listing order refreshed" })).toBeVisible();
        await page.getByRole("button", { name: "Done arranging", exact: true }).click();
        await expect(msrp(page, "CAD")).toHaveValue("69.95");
        expect((await readItem(request, catalog, item.id)).msrps).toEqual({ CAD: 59.95, USD: null });
        await msrp(page, "CAD").fill("59.95");
        await msrp(page, "CAD").blur();
      }
      await msrp(page, "USD").fill("88.95");
      page.once("dialog", (dialog) => dialog.accept());
      if (await back.isVisible()) await back.click();
      else await otherTab.click();
      if (!(await back.isVisible())) {
        await page.getByRole("button", { name: tabName(catalog), exact: true }).click();
        await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
      }
      await page.getByRole("button", { name: "New", exact: true }).click();
      await expect(msrp(page, "CAD")).toHaveValue("");
      await expect(msrp(page, "USD")).toHaveValue("");
      if (await back.isVisible()) await back.click();
      await page.getByRole("button").filter({ hasText: item.name }).click();
      await expect(msrp(page, "CAD")).toHaveValue("59.95");
      await expect(msrp(page, "USD")).toHaveValue("");
      await page.getByRole("button", { name: catalog === "products" ? "Delete equipment" : "Delete accessory", exact: true }).click();
      await page.getByRole("button", { name: "Confirm delete", exact: true }).click();
      await expect(page.getByRole("status").filter({ hasText: "deleted" })).toBeVisible();
      await expect(page.getByText("Unsaved changes", { exact: true })).toHaveCount(0);
      const remaining: Item[] = (await (await request.get(`${api}/api/admin/${catalog}`, { headers })).json()).items;
      expect(remaining.some((entry) => entry.id === item.id)).toBe(false);
      await expect(msrp(page, "CAD")).toHaveValue(remaining[0]?.msrps.CAD?.toFixed(2) ?? "");
      await expect(msrp(page, "USD")).toHaveValue(remaining[0]?.msrps.USD?.toFixed(2) ?? "");
    } finally {
      await request.delete(`${api}/api/${catalog}/${item.id}`, { headers });
    }
  });
}
