import { test, expect, type Locator } from "@playwright/test";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

const longSummary = "A long training summary with full setup and use information. ".repeat(8);
const items = [
  { id: 1, name: "Compact bench", shortDescription: "A short summary.", description: "Complete short details.", material: "Steel", photos: ["/images/pro-elite.svg"] },
  {
    id: 2, name: "Adjustable training equipment with an intentionally longer name",
    category: "Rack attachments with model-specific fit requirements",
    shortDescription: longSummary, photos: ["/images/pro-elite.svg", "/images/bench.jpg", "/images/pro-elite.svg?third", "/images/pro-elite.svg?fourth"],
    description: "Complete overview.", features: ["Adjustable setup"], notes: "Distinct public use.",
    dimensions: "120 x 50 cm", material: "Steel", weight: "25 kg", colourOptions: "Black",
    included: "Two matching parts", sellingUnit: "Pair", packageQuantity: 2,
    modelSku: "LAYOUT-002", warranty: "One year", stockStatus: "In stock",
    compatibility: { uprightSize: "75 x 75 mm", holeDiameter: "1 inch", limitations: "Fit must be confirmed for the exact model. ".repeat(8) },
  },
  { id: 3, name: "Basic item", shortDescription: "", photos: [] },
  { id: 4, name: "Another item", shortDescription: "A second row summary.", description: "Training notes for a compact setup. ".repeat(6), photos: ["/images/pro-elite.svg"] },
].map((item) => ({ category: "Equipment", price: 19.95, currency: "CAD", slug: `layout-${item.id}`, ...item }));

async function expectAlignedRows(cards: Locator) {
  const geometry = await cards.evaluateAll((cards) => cards.map((card) => {
    const rect = card.getBoundingClientRect();
    const heading = card.querySelector(":scope > h2, :scope > h3")!.getBoundingClientRect();
    const button = [...card.querySelectorAll("button")].find((button) => button.textContent === "Add to cart")!.getBoundingClientRect();
    const price = [...card.querySelectorAll("p, span")].find((element) => element.textContent?.startsWith("CAD $19.95"))!.getBoundingClientRect();
    const details = card.querySelector(".catalog-details")?.getBoundingClientRect();
    const actions = card.lastElementChild!.getBoundingClientRect();
    return { top: rect.top, bottom: rect.bottom, heading: heading.top, price: price.top, action: button.top, detailsBottom: details?.bottom, actionsTop: actions.top };
  }));
  const width = await cards.first().page().evaluate(() => innerWidth);
  expect(geometry.filter((card) => Math.abs(card.top - geometry[0].top) < 1)).toHaveLength(width >= 1280 ? 3 : width >= 768 ? 2 : 1);
  for (const card of geometry) {
    if (card.detailsBottom !== undefined) expect(card.actionsTop, "purchase controls do not overlap the details preview").toBeGreaterThanOrEqual(card.detailsBottom);
    for (const peer of geometry.filter((other) => Math.abs(other.top - card.top) < 1)) {
      expect(Math.abs(card.bottom - peer.bottom), "card bottoms align within each row").toBeLessThanOrEqual(1);
      expect(Math.abs(card.heading - peer.heading), "names align despite different media counts").toBeLessThanOrEqual(1);
      expect(Math.abs(card.price - peer.price), "prices align despite different category/name lengths").toBeLessThanOrEqual(1);
      expect(Math.abs(card.action - peer.action), "purchase controls align within each row").toBeLessThanOrEqual(1);
    }
  }
}

test("USR-003: equipment detail contains seven and twelve thumbnails without widening the page", async ({ page }) => {
  for (const count of [7, 12]) {
    const name = "Heavy-duty equipment with multiple gallery images";
    const item = { ...items[0], name, slug: `detail-gallery-${count}`, photos: Array.from({ length: count }, (_, index) => `/images/pro-elite.svg?gallery=${index}`) };
    await page.route(`**/api/products/${item.slug}`, route => route.fulfill({ json: { item } }));
    await page.goto(`/products/${item.slug}`);
    const gallery = page.getByRole("group", { name: `${name} photos and videos`, exact: true });
    await expect(gallery).toBeVisible();
    await expect.poll(() => gallery.locator("img").first().evaluate(image => (image as HTMLImageElement).complete)).toBe(true);
    for (const width of [390, 320, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth), `${count} images at ${width}px`).toBeLessThanOrEqual(width);
      const last = gallery.getByRole("button", { name: `Show ${name} photo ${count}`, exact: true });
      await last.click();
      await expect(last).toHaveAttribute("aria-pressed", "true");
      await expect(gallery.getByRole("status")).toHaveText(`${count} / ${count}`);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      await gallery.getByRole("button", { name: `Enlarge ${name} media ${count}`, exact: true }).click();
      await expect(page.getByRole("dialog", { name: `${name} enlarged media`, exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Close enlarged media", exact: true }).click();
    }
  }
});

for (const catalog of ["products", "accessories"] as const) {
  test(`USR-014: ${catalog} use taller desktop previews and show all details below desktop width`, async ({ page }) => {
    await page.route(`**/api/${catalog}`, (route) => route.fulfill({ json: { items } }));
    await page.goto(catalog === "products" ? "/" : "/accessories");
    const cards = page.locator(catalog === "products" ? "#products article" : "article");
    await expect(cards).toHaveCount(4);
    const longCard = cards.nth(1);
    await expect(cards.first().getByText("Complete short details.", { exact: true })).toBeVisible();
    await expect(cards.first().getByText("Steel", { exact: true })).toBeVisible();
    await expect(cards.first().getByRole("button", { name: "Show more", exact: true })).toHaveCount(0);
    for (const width of [1440, 1280, 1024, 1023, 768, 767, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      const more = longCard.getByRole("button", { name: "Show more", exact: true });
      if (width >= 1024) await expect(more).toBeVisible();
      else await expect(more).not.toBeVisible();
      await expectAlignedRows(cards);
      const preview = longCard.locator(".catalog-details-preview");
      const size = await preview.evaluate((element) => ({
        height: element.clientHeight, full: element.scrollHeight,
        limit: getComputedStyle(element).maxHeight,
        mask: getComputedStyle(element).maskImage,
      }));
      expect(size.height).toBeGreaterThan(100);
      if (width >= 1024) {
        expect(size.limit).toBe("336px");
        expect(size.height).toBe(336);
        expect(size.full).toBeGreaterThan(size.height);
      } else {
        expect(size.limit).toBe("none");
        expect(size.mask).toBe("none");
        expect(Math.abs(size.full - size.height)).toBeLessThanOrEqual(1);
        await expect(preview.getByText("Two matching parts", { exact: true })).toBeVisible();
      }
      await expect(longCard.getByText(longSummary.trim(), { exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    const toggle = longCard.getByRole("button", { name: /Show more|Show less/ });
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(toggle).toHaveAccessibleName("Show more");
    const overflowCue = toggle.getByText("...", { exact: true });
    await expect(overflowCue).toBeVisible();
    await expect(overflowCue).toHaveAttribute("aria-hidden", "true");
    await expect(toggle.getByText("Show more", { exact: true })).toHaveCSS("font-weight", "400");
    await expect(toggle.getByText("Show more", { exact: true })).toHaveCSS("font-style", "italic");
    await expect(toggle.getByText("Show more", { exact: true })).toHaveCSS("text-decoration-line", "underline");
    await expect(toggle).toHaveCSS("background-color", /^(?:rgba\(0, 0, 0, 0\.02\)|oklab\(0 0 0 \/ 0\.02\))$/);
    await expect(toggle).toHaveCSS("border-top-color", "rgba(22, 22, 22, 0.08)");
    expect((await toggle.boundingBox())!.height).toBeGreaterThanOrEqual(48);
    await expect(toggle.locator("svg")).toBeVisible();
    await expect(longCard.getByText("Includes compatibility - check fit", { exact: true })).toBeVisible();
    expect(await toggle.getAttribute("aria-controls")).toBe(await longCard.locator(".catalog-details-preview").getAttribute("id"));
    await toggle.focus();
    await page.keyboard.press("Enter");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(toggle).toHaveText("Show less");
    await expect(toggle.getByText("Show less", { exact: true })).toHaveCSS("font-style", "italic");
    await expect(overflowCue).toHaveCount(0);
    const expanded = longCard.locator(".catalog-details-preview");
    expect(await expanded.evaluate((element) => Math.abs(element.clientHeight - element.scrollHeight))).toBeLessThanOrEqual(1);
    for (const text of [longSummary.trim(), "Complete overview.", "Adjustable setup", "75 x 75 mm", "120 x 50 cm", "Steel", "25 kg", "Black", "Two matching parts"]) {
      await expect(expanded.getByText(text, { exact: true })).toBeVisible();
    }
    await expect(expanded.getByText(/Fit must be confirmed/)).toBeVisible();
    if (catalog === "accessories") await expect(longCard.getByText("Distinct public use.", { exact: true })).toBeVisible();
    else for (const text of ["LAYOUT-002", "One year", "In stock"]) await expect(expanded.getByText(text, { exact: true })).toBeVisible();
    await expectAlignedRows(cards);
    await expect(cards.first().getByRole("button", { name: "Show less", exact: true })).toHaveCount(0);
    await page.setViewportSize({ width: 1023, height: 1000 });
    await expect(toggle).not.toBeVisible();
    expect(await expanded.evaluate((element) => Math.abs(element.clientHeight - element.scrollHeight))).toBeLessThanOrEqual(1);
    await page.setViewportSize({ width: 1024, height: 1000 });
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await toggle.focus();
    await page.keyboard.press("Space");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(toggle).toBeFocused();
    await expect(overflowCue).toBeVisible();
    await expectAlignedRows(cards);
    await expect(cards.nth(2).locator(".catalog-details")).toHaveCount(0);
    await expect(cards.nth(2).getByRole("button", { name: /Show more|Show less/ })).toHaveCount(0);
    await expect(cards.nth(2).getByRole("button", { name: "Add to cart", exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(toggle).not.toBeVisible();
    await expect(expanded.getByText("Complete overview.", { exact: true })).toBeVisible();
    await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await expanded.evaluate((element) => Math.abs(element.clientHeight - element.scrollHeight))).toBeLessThanOrEqual(1);
    await expect(toggle).not.toBeVisible();
    const mediumToggle = cards.nth(3).getByRole("button", { name: "Show more", exact: true });
    await expect(mediumToggle).not.toBeVisible();
    await page.setViewportSize({ width: 1440, height: 1000 });
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(expanded).toHaveCSS("max-height", "672px");
    await expect(mediumToggle).toBeVisible();
    await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await expect(mediumToggle).toHaveCount(0);
  });
}

test("USR-013: multiline quote prefill preserves current units/prices, edits, and saved line breaks", async ({ page }) => {
  const selection = [
    { id: 1, name: "Bench", price: 750, currency: "CAD", quantity: 1 },
    { id: 1001, name: "Grips", price: 39, currency: "CAD", quantity: 2, sellingUnit: "Pair", packageQuantity: 2 },
  ];
  await page.addInitScript((items) => localStorage.setItem("styl-cart", JSON.stringify(items.map((item) => ({ ...item, price: 999, currency: "USD" })))), selection);
  await page.route("**/api/catalog/selection", (route) => route.fulfill({ json: {
    items: selection, market: { currency: "CAD", countryCode: null, source: "unknown" },
  } }));
  await page.goto("/?quote=cart#contact");
  const message = page.getByRole("textbox", { name: "Message", exact: true });
  const expected = "Interested in:\n\n1. Bench\n   Quantity: 1 sale unit\n   Unit price: CAD $750.00 per sale unit\n\n2. Grips\n   Quantity: 2 pairs\n   Contents: 2 pieces per pair\n   Unit price: CAD $39.00 per pair\n\nPlease share final pricing and delivery details.";
  await expect(message).toHaveValue(expected);
  expect(Number(await message.getAttribute("rows"))).toBeGreaterThanOrEqual(8);
  const edited = `${expected}\n\nDelivery note:\nPlease contact me first.`;
  await message.fill(edited);
  const customer = `Multiline E2E ${Date.now()}`;
  await page.getByRole("textbox", { name: "Name", exact: true }).fill(customer);
  await page.getByRole("textbox", { name: "Email", exact: true }).fill("e2e@example.com");
  await page.route("**/api/inquiries", (route) => route.fulfill({ status: 503, json: { detail: "Temporary test failure" } }));
  await page.getByRole("button", { name: "Submit inquiry", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Temporary test failure" })).toBeVisible();
  await expect(message).toHaveValue(edited);
  await page.unroute("**/api/inquiries");
  const saved = page.waitForResponse((response) => response.url().endsWith("/api/inquiries") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Submit inquiry", exact: true }).click();
  const response = await saved;
  expect(response.status()).toBe(200);
  expect(response.request().postDataJSON().message).toBe(edited);
  const directory = path.join(process.env.STYL_E2E_DATA_DIR!, "inquiries");
  const records = readdirSync(directory).map((file) => JSON.parse(readFileSync(path.join(directory, file), "utf8")));
  expect(records.some((record) => record.name === customer && record.message === edited && record.emailStatus === "unconfigured")).toBe(true);
});

test("USR-013: empty selections and product-only quote links use separate request paragraphs", async ({ page }) => {
  await page.goto("/?quote=cart#contact");
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(
    "No items selected yet.\n\nPlease share final pricing and delivery details.",
  );
  await page.goto("/?quote=product&product=Adjustable%20bench#contact");
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(
    "Interested in:\n\n1. Adjustable bench\n\nPlease share options, pricing, and lead time.",
  );
});
