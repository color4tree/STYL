import { test, expect } from "@playwright/test";

const api = "http://127.0.0.1:8102";
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };

for (const endpoint of ["products", "accessories"] as const) {
  test(`${endpoint}: new Draft, missing market warning, publishing and unpublishing`, async ({ page, request }) => {
    await page.goto("/admin");
    await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
    if (endpoint === "accessories") {
      await page.getByRole("button", { name: "Accessories", exact: true }).click();
      await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
    }
    await page.getByRole("button", { name: "New", exact: true }).click();
    const name = `Missing market ${endpoint} ${Date.now()}`;
    await page.getByLabel(endpoint === "products" ? "Product name" : "Accessory name", { exact: true }).fill(name);
    const category = page.getByRole("combobox", { name: "Category", exact: true });
    await expect(category.locator('option[value="Bench"]')).toHaveCount(0);
    await category.selectOption("Benches");
    const status = page.getByRole("combobox", { name: "Publication status", exact: true });
    await expect(status).toHaveValue("draft");
    await page.getByRole("textbox", { name: "Canada price (CAD)", exact: true }).fill("4005.25");
    await page.getByRole("textbox", { name: "Weight", exact: true }).fill("35.5 kg");
    const createdResponse = page.waitForResponse((response) => response.url() === `${api}/api/${endpoint}` && response.request().method() === "POST");
    await page.getByRole("button", { name: endpoint === "products" ? "Create product" : "Create accessory", exact: true }).click();
    const created = await createdResponse;
    expect(created.status()).toBe(200);
    const item = (await created.json()).item;
    expect(item.publicationStatus).toBe("draft");
    expect(item.weight).toBe("35.5 kg");
    expect(item.prices).toEqual({ CAD: 4005.25, USD: null });
    await expect(page.getByRole("status").filter({ hasText: "Needs attention" })).toContainText("US / other countries");
    await status.selectOption("published");
    let savedResponse = page.waitForResponse((response) => response.url() === `${api}/api/${endpoint}/${item.id}` && response.request().method() === "PUT");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    expect((await savedResponse).status()).toBe(200);
    let listed = (await (await request.get(`${api}/api/${endpoint}`)).json()).items;
    expect(listed.some((entry: { id: number }) => entry.id === item.id)).toBe(false);
    if (endpoint === "products") expect((await request.get(`${api}/api/products/${item.slug}`)).status()).toBe(404);
    await page.getByRole("textbox", { name: "US price (USD)", exact: true }).fill("4000.95");
    savedResponse = page.waitForResponse((response) => response.url() === `${api}/api/${endpoint}/${item.id}` && response.request().method() === "PUT");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    expect((await savedResponse).status()).toBe(200);
    listed = (await (await request.get(`${api}/api/${endpoint}`)).json()).items;
    expect(listed.find((entry: { id: number }) => entry.id === item.id).price).toBe(4000.95);
    await expect(page.getByRole("status").filter({ hasText: "Needs attention" })).toHaveCount(0);
    await status.selectOption("draft");
    savedResponse = page.waitForResponse((response) => response.url() === `${api}/api/${endpoint}/${item.id}` && response.request().method() === "PUT");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    expect((await savedResponse).status()).toBe(200);
    listed = (await (await request.get(`${api}/api/${endpoint}`)).json()).items;
    expect(listed.some((entry: { id: number }) => entry.id === item.id)).toBe(false);
  });

  test(`${endpoint}: captured date survives editing notes, save and reload`, async ({ browser }, testInfo) => {
    const context = await browser.newContext({
      viewport: testInfo.project.use.viewport,
      isMobile: testInfo.project.use.isMobile,
      hasTouch: testInfo.project.use.hasTouch,
      timezoneId: testInfo.project.name.startsWith("phone") ? "Pacific/Auckland" : "America/Toronto",
      baseURL: "http://127.0.0.1:3102",
    });
    const page = await context.newPage();
    try {
      await page.goto("/admin");
      await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
      if (endpoint === "accessories") {
        await page.getByRole("button", { name: "Accessories", exact: true }).click();
        await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
      }

      await page.getByRole("button", { name: "New", exact: true }).click();
      const name = `Date trace ${endpoint} ${Date.now()}`;
      await page.getByLabel(endpoint === "products" ? "Product name" : "Accessory name", { exact: true }).fill(name);
      await page.getByRole("combobox", { name: "Category", exact: true }).selectOption("Handle");
      await page.getByRole("textbox", { name: "Canada price (CAD)", exact: true }).fill("29.95");
      await page.getByRole("textbox", { name: "US price (USD)", exact: true }).fill("19.95");
      const date = page.getByLabel("Captured date", { exact: true });
      await date.fill("2026-09-26");
      await expect(date).toHaveValue("2026-09-26");
      await page.getByRole("textbox", { name: "Internal notes", exact: true }).fill("Private note entered after the date.");
      await expect(date).toHaveValue("2026-09-26");
      await date.focus();
      await page.keyboard.press("Tab");
      await expect(date).toHaveValue("2026-09-26");
      await date.fill("");
      await page.getByRole("textbox", { name: "Internal notes", exact: true }).fill("");
      await page.evaluate(() => {
        const dateInput = document.querySelector<HTMLInputElement>('input[type="date"]')!;
        const notes = [...document.querySelectorAll<HTMLTextAreaElement>("textarea")].find((element) =>
          element.closest("label")?.textContent?.trim().startsWith("Internal notes"))!;
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(dateInput, "2026-09-26");
        dateInput.dispatchEvent(new Event("input", { bubbles: true }));
        dateInput.dispatchEvent(new Event("change", { bubbles: true }));
        Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(notes, "Private note entered after the date.");
        notes.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await expect(date).toHaveValue("2026-09-26");
      const savedResponse = page.waitForResponse((response) =>
        response.url() === `${api}/api/${endpoint}` && response.request().method() === "POST");
      await page.getByRole("button", { name: endpoint === "products" ? "Create product" : "Create accessory", exact: true }).click();
      const saved = await savedResponse;
      expect(saved.status(), await saved.text()).toBe(200);
      expect(saved.request().postDataJSON().provenance.capturedDate).toBe("2026-09-26");
      const item = (await saved.json()).item;
      expect(item.provenance.capturedDate).toBe("2026-09-26");
      await page.reload();
      await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
      if (endpoint === "accessories") {
        await page.getByRole("button", { name: "Accessories", exact: true }).click();
        await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
      }
      await page.getByRole("button").filter({ hasText: name }).click();
      await expect(date).toHaveValue("2026-09-26");
      await expect(page.getByRole("textbox", { name: "Internal notes", exact: true })).toHaveValue("Private note entered after the date.");
      await page.getByRole("combobox", { name: "Publication status", exact: true }).selectOption("published");
      const publishedResponse = page.waitForResponse((response) =>
        response.url() === `${api}/api/${endpoint}/${item.id}` && response.request().method() === "PUT");
      await page.getByRole("button", { name: "Save changes", exact: true }).click();
      expect((await publishedResponse).status()).toBe(200);
      const adminItems = (await (await context.request.get(`${api}/api/admin/${endpoint}`, { headers })).json()).items;
      expect(adminItems.find((entry: { id: number }) => entry.id === item.id).provenance.capturedDate).toBe("2026-09-26");
      const publicResponse = await context.request.get(`${api}/api/${endpoint}`);
      expect(await publicResponse.text()).not.toContain("Private note entered after the date.");
      expect(await publicResponse.text()).not.toContain("capturedDate");
    } finally {
      await context.close();
    }
  });
}
