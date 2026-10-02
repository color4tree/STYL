import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { createHash, randomUUID } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Catalog = "products" | "accessories";
type Item = { id: number; slug?: string; name: string; category: string; revision: string; schemaVersion: number; catalogFacts?: { reviewed: boolean; measurements: { amount: string }[] }; catalogFactsReviewedAt?: string };
const nameLabel = (catalog: Catalog) => catalog === "products" ? "Equipment name" : "Accessory name";

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

async function savedItem(request: APIRequestContext, catalog: Catalog, id: number): Promise<Item> {
  const response = await request.get(`${api}/api/admin/${catalog}`, { headers });
  expect(response.ok(), await response.text()).toBe(true);
  const item = (await response.json()).items.find((value: Item) => value.id === id);
  expect(item).toBeDefined();
  expect(item.revision).toMatch(/^[a-f0-9]{64}$/);
  return item;
}

async function save(page: Page, catalog: Catalog, id?: number) {
  const pending = page.waitForResponse(response => response.url() === `${api}/api/${catalog}${id ? `/${id}` : ""}` && response.request().method() === (id ? "PUT" : "POST"));
  await page.getByRole("button", { name: id ? "Save changes" : catalog === "products" ? "Create equipment" : "Create accessory", exact: true }).click();
  const response = await pending;
  expect(response.status(), await response.text()).toBe(200);
  await expect(page.getByRole("status").filter({ hasText: "saved successfully" })).toBeVisible();
  return { item: (await response.json()).item as Item, payload: response.request().postDataJSON() };
}

function pdf() {
  const stream = "BT /F1 12 Tf 50 750 Td (Synthetic source: do not infer typed product facts.) Tj ET\n";
  const objects = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>", "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}endstream`];
  let document = "%PDF-1.4\n";
  const offsets: number[] = [];
  for (const [i, content] of objects.entries()) { offsets.push(Buffer.byteLength(document)); document += `${i + 1} 0 obj\n${content}\nendobj\n`; }
  const xref = Buffer.byteLength(document);
  return Buffer.from(`${document}xref\n0 6\n0000000000 65535 f \n${offsets.map(offset => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
}

function pdfSnapshot() {
  const directory = process.env.STYL_E2E_DATA_DIR;
  if (!directory || !path.isAbsolute(directory) || path.dirname(directory) !== tmpdir() || !process.env.STYL_E2E_TOKEN || !path.basename(directory).startsWith("styl-e2e-")) {
    throw new Error("Catalog facts E2E requires the existing isolated test directory and credentials.");
  }
  const hashes: Record<string, string> = {};
  const scan = (folder: string) => {
    for (const entry of readdirSync(folder, { withFileTypes: true })) {
      if (entry.isSymbolicLink()) continue;
      const file = path.join(folder, entry.name);
      if (entry.isDirectory()) scan(file);
      else if (entry.name.toLowerCase().endsWith(".pdf")) hashes[path.relative(directory, file)] = createHash("sha256").update(readFileSync(file)).digest("hex");
    }
  };
  scan(directory);
  return hashes;
}

for (const catalog of ["products", "accessories"] as const) {
  test(`FACT-013 ${catalog}: create/omit, typed draft/review/public, 409 preservation, 320px and untouched source PDF`, async ({ page, request }) => {
    const name = `Facts ${catalog} ${randomUUID().slice(0, 8).replace(/\d/g, (digit) => String.fromCharCode(103 + Number(digit)))}`;
    let item: Item | undefined;
    let sourceId: string | undefined;
    try {
      await signIn(page, catalog);
      await page.getByRole("button", { name: "New", exact: true }).click();
      await page.getByLabel(nameLabel(catalog), { exact: true }).fill(name);
      await page.getByRole("combobox", { name: "Category", exact: true }).selectOption("Handle");
      await page.getByRole("textbox", { name: "Canada price (CAD)", exact: true }).fill("29.95");
      await page.getByRole("textbox", { name: "US price (USD)", exact: true }).fill("19.95");
      await page.getByRole("combobox", { name: "Publication status", exact: true }).selectOption("published");
      await page.getByLabel("Dimensions", { exact: true }).fill("Raw legacy dimensions");
      await page.getByLabel("Colour / options", { exact: true }).fill("Raw legacy combined options");
      await page.getByLabel("Full description", { exact: true }).fill("Presentation text remains unchanged.");
      const first = await save(page, catalog);
      item = first.item;
      expect(first.payload.schemaVersion).toBe(2);
      expect(first.payload).not.toHaveProperty("catalogFacts");
      expect(item.revision).toMatch(/^[a-f0-9]{64}$/);

      const uploaded = await request.post(`${api}/api/admin/support/knowledge/documents`, { headers, multipart: {
        file: { name: `${name}.pdf`, mimeType: "application/pdf", buffer: pdf() }, title: name,
        itemRefs: JSON.stringify([`${catalog === "products" ? "product" : "accessory"}:${item.id}`]),
      } });
      expect(uploaded.status(), await uploaded.text()).toBe(201);
      sourceId = (await uploaded.json()).id;
      const beforeIndex = await request.get(`${api}/api/admin/support/knowledge`, { headers });
      expect(beforeIndex.status()).toBe(200);
      const sourceBefore = (await beforeIndex.json()).sources.find((source: { id: string }) => source.id === sourceId);
      const rawPDFs = pdfSnapshot();
      expect(Object.keys(rawPDFs).length).toBeGreaterThan(0);

      const panel = page.getByTestId("catalog-facts-editor");
      await panel.locator("summary").click();
      await expect(page.getByText("Unsaved changes", { exact: true })).toHaveCount(0);
      await panel.getByRole("button", { name: "Add product facts", exact: true }).click();
      await panel.getByLabel("Colors (one per line)", { exact: true }).fill("Black\nWhite");
      await panel.getByLabel("Sizes (one per line)", { exact: true }).fill("Small\nLarge");
      await panel.getByLabel("Finish", { exact: true }).fill("Powder coat");
      await panel.getByRole("button", { name: "Add measurement", exact: true }).click();
      await panel.getByLabel("Measurement 1 kind", { exact: true }).selectOption("width");
      await panel.getByLabel("Measurement 1 scope", { exact: true }).selectOption("overall");
      await panel.getByLabel("Measurement 1 amount", { exact: true }).fill("-2");
      await page.getByRole("button", { name: "Save changes", exact: true }).click();
      await expect(panel.getByLabel("Measurement 1 amount", { exact: true })).toBeFocused();
      await expect(panel.getByLabel("Measurement 1 amount", { exact: true })).toHaveValue("-2");
      await panel.getByLabel("Measurement 1 amount", { exact: true }).fill("1200.50");
      await panel.getByRole("button", { name: "Add component", exact: true }).click();
      const componentName = "Synthetic".repeat(18);
      await panel.getByLabel("Component 1 name", { exact: true }).fill(componentName);
      await panel.getByLabel("Component 1 quantity (optional)", { exact: true }).fill("1.5");
      await page.getByRole("button", { name: "Save changes", exact: true }).click();
      await expect(panel.getByLabel("Component 1 quantity (optional)", { exact: true })).toHaveValue("1.5");
      await expect(panel.getByLabel("Component 1 quantity (optional)", { exact: true })).toBeFocused();
      await panel.getByLabel("Component 1 quantity (optional)", { exact: true }).fill("2");
      await panel.getByLabel("Component 1 status", { exact: true }).selectOption("included");
      await panel.getByLabel("Add interface (choose kind)", { exact: true }).selectOption("socket_drive");
      await panel.getByRole("button", { name: "Add interface 1 constraint", exact: true }).click();
      await panel.getByLabel("Interface 1 constraint 1 value", { exact: true }).fill("0.5");
      await panel.getByLabel("Interface 1 constraint 1 comparison", { exact: true }).selectOption("eq");
      await panel.getByLabel("Interface 1 constraint 1 unit", { exact: true }).selectOption("in");

      await page.setViewportSize({ width: 320, height: 844 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
      for (const button of await panel.getByRole("button").all()) {
        if (await button.isVisible()) expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(48);
      }
      const draft = await save(page, catalog, item.id);
      expect(draft.payload.expectedRevision).toBe(item.revision);
      expect(draft.item.catalogFacts?.reviewed).toBe(false);
      item = draft.item;
      const publicUrl = `${api}/api/${catalog}/${catalog === "products" ? item.slug : item.id}`;
      expect((await (await request.get(publicUrl)).json()).item).not.toHaveProperty("catalogFacts");

      await panel.locator("summary").click();
      const reviewed = panel.getByRole("checkbox", { name: "Merchant-reviewed for customer answers", exact: true });
      await reviewed.check();
      await panel.getByLabel("Measurement 1 amount", { exact: true }).fill("1250.50");
      await expect(reviewed).not.toBeChecked();
      await reviewed.check();
      const approved = await save(page, catalog, item.id);
      expect(approved.payload).not.toHaveProperty("catalogFactsReviewedAt");
      expect(approved.item.catalogFactsReviewedAt).toBeTruthy();
      item = approved.item;
      const currentPublic = (await (await request.get(publicUrl)).json()).item;
      expect(currentPublic.catalogFacts.reviewed).toBe(true);
      expect(currentPublic.dimensions).toBe("Raw legacy dimensions");
      expect(currentPublic.colourOptions).toBe("Raw legacy combined options");
      const customer = await page.context().newPage();
      try {
        await customer.setViewportSize({ width: 320, height: 844 });
        await customer.goto(catalog === "products" ? `/products/${item.slug}` : `/accessories/${item.id}`);
        await expect(customer.getByRole("heading", { name, exact: true })).toBeVisible();
        await expect(customer.locator("dt").filter({ hasText: /^Overall width$/ })).toHaveCount(1);
        await expect(customer.getByText("1250.50 mm", { exact: true })).toBeVisible();
        await expect(customer.locator("dt").filter({ hasText: /^Original listing dimensions$/ })).toHaveCount(1);
        await expect(customer.getByText("Raw legacy dimensions", { exact: true })).toBeVisible();
        await expect(customer.getByText("Reviewed values above take precedence.", { exact: true })).toBeVisible();
        for (const label of ["Colors", "Sizes", "Finish", "Socket drive interface (requires)"]) await expect(customer.locator("dt").filter({ hasText: new RegExp(`^${label.replace(/[()]/g, "\\$&")}$`) })).toHaveCount(1);
        await expect(customer.getByText("Presentation text remains unchanged.", { exact: true })).toBeVisible();
        expect(await customer.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
      } finally { await customer.close(); }

      await panel.locator("summary").click();
      await panel.getByLabel("Measurement 1 amount", { exact: true }).fill("1300");
      const remote = await request.put(`${api}/api/${catalog}/${item.id}`, { headers, data: { name: item.name, category: item.category, schemaVersion: 2, expectedRevision: item.revision, shortDescription: "Another admin changed this." } });
      expect(remote.status(), await remote.text()).toBe(200);
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.getByRole("button", { name: "Arrange listing order", exact: true }).click();
      await page.getByRole("button", { name: "Refresh listing order", exact: true }).click();
      await expect(page.getByText("Listing order refreshed. Open form edits were kept.", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Done arranging", exact: true }).click();
      const conflict = page.waitForResponse(response => response.url() === `${api}/api/${catalog}/${item!.id}` && response.request().method() === "PUT");
      await page.getByRole("button", { name: "Save changes", exact: true }).click();
      const stale = await conflict;
      expect(stale.status()).toBe(409);
      expect(stale.request().postDataJSON().expectedRevision).toBe(item.revision);
      await expect(panel.getByLabel("Measurement 1 amount", { exact: true })).toHaveValue("1300");
      await expect(page.getByText(/This item changed elsewhere. Your draft has been kept./)).toBeVisible();
      page.once("dialog", dialog => dialog.accept());
      await page.getByRole("button", { name: "Reload saved item", exact: true }).click();
      await expect(page.getByLabel("Short description", { exact: true })).toHaveValue("Another admin changed this.");
      await panel.locator("summary").click();
      await expect(panel.getByLabel("Measurement 1 amount", { exact: true })).toHaveValue("1250.50");
      await panel.getByRole("button", { name: "Clear typed facts", exact: true }).click();
      await panel.getByRole("button", { name: "Keep facts", exact: true }).click();
      await expect(panel.getByLabel("Measurement 1 amount", { exact: true })).toHaveValue("1250.50");
      await panel.getByRole("button", { name: "Clear typed facts", exact: true }).click();
      await panel.getByRole("button", { name: "Confirm clear facts", exact: true }).click();
      const cleared = await save(page, catalog, item.id);
      expect(cleared.payload.catalogFacts).toBeNull();
      expect((await (await request.get(publicUrl)).json()).item).not.toHaveProperty("catalogFacts");
      expect(pdfSnapshot()).toEqual(rawPDFs);
      const sources = (await (await request.get(`${api}/api/admin/support/knowledge`, { headers })).json()).sources;
      expect(sources.find((source: { id: string }) => source.id === sourceId)).toEqual(sourceBefore);
    } finally {
      if (item) {
        const latest = await savedItem(request, catalog, item.id);
        const removed = await request.delete(`${api}/api/${catalog}/${item.id}?expectedRevision=${latest.revision}`, { headers });
        expect(removed.ok(), await removed.text()).toBe(true);
      }
      // The isolated harness removes the synthetic private PDF with its owned data directory.
    }
  });

  test(`FACT-014 ${catalog}: missing mock revision safely blocks update and delete without losing the draft`, async ({ page }) => {
    const legacy = { id: 987654, slug: "legacy-fixture", name: "No revision fixture", category: "Handle", prices: { CAD: 10, USD: 10 }, price: 10, currency: "CAD", photos: [], features: [], publicationStatus: "published" };
    await page.route(`${api}/api/admin/${catalog}`, route => route.fulfill({ json: { items: [legacy] } }));
    let writes = 0;
    await page.route(`${api}/api/${catalog}/${legacy.id}*`, route => { writes++; return route.fulfill({ status: 500, json: { detail: "Must not send unsafe mutation" } }); });
    await signIn(page, catalog);
    await page.getByRole("button").filter({ hasText: legacy.name }).click();
    await page.getByLabel(nameLabel(catalog), { exact: true }).fill("Keep this draft");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(page.getByText(/This item has no usable revision/)).toBeVisible();
    await expect(page.getByLabel(nameLabel(catalog), { exact: true })).toHaveValue("Keep this draft");
    await page.getByRole("button", { name: catalog === "products" ? "Delete equipment" : "Delete accessory", exact: true }).click();
    await page.getByRole("button", { name: "Confirm delete", exact: true }).click();
    expect(writes).toBe(0);
    await expect(page.getByRole("button", { name: "Reload saved item", exact: true })).toBeVisible();
  });
}
