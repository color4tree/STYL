import { test, expect, type Page, type APIRequestContext } from "@playwright/test";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aC1sAAAAASUVORK5CYII=", "base64");
const unique = (prefix: string) => `${prefix} ${Date.now()} ${Math.random().toString(16).slice(2, 8)}`;

async function signIn(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
}

async function accessoryTab(page: Page) {
  await page.getByRole("button", { name: "Accessories", exact: true }).click();
  await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
}

async function save(page: Page, name: string, endpoint: string, method = "POST") {
  const result = page.waitForResponse((response) => response.url().includes(`/api/${endpoint}`) && response.request().method() === method);
  await page.getByRole("button", { name, exact: true }).click();
  const response = await result;
  expect(response.status(), await response.text()).toBe(200);
  await expect(page.getByRole("status").filter({ hasText: "saved successfully" })).toBeVisible();
  return (await response.json()).item;
}

async function createViaApi(request: APIRequestContext, endpoint: string, fields: Record<string, unknown>) {
  const response = await request.post(`${api}/api/${endpoint}`, { headers, data: { name: unique("Fixture"), category: "Handle", price: 19.95, ...fields } });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()).item;
}

test("admin authentication rejects bad tokens and protects private endpoints", async ({ page, request }) => {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill("wrong-token");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Incorrect admin token");
  for (const endpoint of ["products", "accessories", "categories"]) {
    expect((await request.get(`${api}/api/admin/${endpoint}`)).status()).toBe(401);
  }
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "New", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByLabel("Admin token", { exact: true })).toBeVisible();
});

test("accessory create, validation, reload, public detail, selling units, cart and private provenance", async ({ page, request }) => {
  const name = unique("E2E pair");
  await signIn(page);
  await accessoryTab(page);
  await page.getByRole("button", { name: "New", exact: true }).click();
  await page.getByLabel("Accessory name", { exact: true }).fill(name);
  await page.getByRole("combobox", { name: "Category", exact: true }).selectOption("Handle");
  const price = page.getByRole("textbox", { name: "Retail price", exact: true });
  await price.fill("19.955");
  await page.getByRole("button", { name: "Create accessory", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("two decimal places");
  await price.fill("19.5");
  await price.blur();
  await expect(price).toHaveValue("19.50");
  await price.fill("19.95");
  await page.getByRole("combobox", { name: "Selling unit", exact: true }).selectOption("Pair");
  await page.getByRole("spinbutton", { name: /Package quantity/ }).fill("2");
  await page.getByLabel("What's included / package contents", { exact: true }).fill("Two matching handles");
  await page.getByLabel("Colour / options", { exact: true }).fill("Black / steel");
  await page.getByLabel("Short description", { exact: true }).fill("A matched pair.");
  await page.getByRole("textbox", { name: "Full description", exact: true }).fill("Full description distinct from public use.");
  await page.getByRole("textbox", { name: "Public use description", exact: true }).fill("Cable exercise use.");
  await page.getByLabel("Feature 1", { exact: true }).fill("Comfort grip");
  await page.getByLabel("Source type", { exact: true }).fill("Marketplace");
  await page.getByLabel("Marketplace / source URL", { exact: true }).fill("https://example.com/listing/123");
  await page.getByLabel("Listing ID", { exact: true }).fill("123");
  await page.getByLabel("Captured date", { exact: true }).fill("2026-09-25");
  await page.getByLabel("Internal notes", { exact: true }).fill("PRIVATE-E2E-NOTE");
  const item = await save(page, "Create accessory", "accessories");
  expect(item.price).toBe(19.95);
  expect(item.currency).toBe("CAD");
  await page.reload();
  await expect(page.getByRole("button", { name: "Accessories", exact: true })).toBeEnabled();
  await accessoryTab(page);
  await page.getByRole("button").filter({ hasText: name }).click();
  await expect(page.getByLabel("Accessory name", { exact: true })).toHaveValue(name);
  await expect(price).toHaveValue("19.95");
  await expect(page.getByRole("textbox", { name: "Full description", exact: true })).toHaveValue("Full description distinct from public use.");
  await expect(page.getByRole("textbox", { name: "Internal notes", exact: true })).toHaveValue("PRIVATE-E2E-NOTE");
  const publicResponse = await request.get(`${api}/api/accessories`);
  expect(await publicResponse.text()).not.toContain("PRIVATE-E2E-NOTE");
  expect((await publicResponse.json()).items.find((entry: { id: number }) => entry.id === item.id)).not.toHaveProperty("provenance");
  await page.goto("/accessories");
  const card = page.locator("article").filter({ hasText: name });
  await expect(card).toContainText("$19.95 / pair");
  await card.locator("summary").click();
  await expect(card).toContainText("Full description distinct from public use.");
  await expect(card).toContainText("Cable exercise use.");
  await expect(card.getByText("Dimensions", { exact: true })).toHaveCount(0);
  await expect(card.getByText("Weight", { exact: true })).toHaveCount(0);
  await card.getByRole("button", { name: "Add to cart", exact: true }).click();
  await page.getByRole("link", { name: "Cart (1)", exact: true }).click();
  await page.waitForURL("**/cart");
  await expect(page.getByRole("heading", { name: "Your selection", exact: true })).toBeVisible();
  const row = page.locator("article").filter({ hasText: name });
  await expect(row).toContainText("Quantity: 1 pair");
  await row.getByRole("button", { name: `Increase quantity for ${name}` }).click();
  await expect(row).toContainText("$39.90");
  await expect(row).toContainText("Quantity: 2 pairs");
  await page.reload();
  await expect(row).toContainText("$39.90");
  await page.getByRole("link", { name: "Request a quote", exact: true }).last().click();
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(new RegExp(`${name} x 2 pairs`));
});

test("unsaved changes, failed save, retry and delete", async ({ page, request }) => {
  const item = await createViaApi(request, "accessories", { name: unique("Edit guard"), notes: "Original notes" });
  await signIn(page);
  await accessoryTab(page);
  await page.getByRole("button").filter({ hasText: item.name }).click();
  await page.getByRole("textbox", { name: "Full description", exact: true }).fill("Keep my unsaved text");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "Products", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Full description", exact: true })).toHaveValue("Keep my unsaved text");
  await page.route(`**/api/accessories/${item.id}`, (route) => route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Save temporarily unavailable"}' }));
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Save temporarily unavailable");
  await expect(page.getByRole("textbox", { name: "Full description", exact: true })).toHaveValue("Keep my unsaved text");
  await page.unroute(`**/api/accessories/${item.id}`);
  await save(page, "Save changes", "accessories", "PUT");
  await page.getByRole("button", { name: "Delete accessory", exact: true }).click();
  await page.getByRole("button", { name: /Confirm delete/ }).click();
  await expect(page.getByRole("status").filter({ hasText: "deleted" })).toBeVisible();
  const listed = (await (await request.get(`${api}/api/accessories`)).json()).items;
  expect(listed.some((entry: { id: number }) => entry.id === item.id)).toBe(false);
});

test("product media upload, reorder, cover, real video conversion/seek, featured ordering", async ({ page, request }) => {
  const name = unique("E2E equipment");
  await signIn(page);
  await page.getByRole("button", { name: "New", exact: true }).click();
  await page.getByLabel("Product name", { exact: true }).fill(name);
  await page.getByRole("combobox", { name: "Category", exact: true }).selectOption("Racks");
  await page.getByRole("textbox", { name: "Retail price", exact: true }).fill("299.99");
  await page.getByLabel("Show first in the home collection", { exact: true }).check();
  await page.locator('input[type="file"]').setInputFiles([
    { name: "first.png", mimeType: "image/png", buffer: png },
    { name: "second.png", mimeType: "image/png", buffer: png },
  ]);
  await expect(page.getByText(/2 of 2 files uploaded/)).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(path.join(process.env.STYL_E2E_DATA_DIR!, "clip.mov"));
  await expect(page.getByText(/1 of 1 files uploaded/)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Move media 3 earlier", exact: true }).click();
  await page.getByRole("button", { name: "Move media 2 earlier", exact: true }).click();
  const item = await save(page, "Create product", "products");
  expect(item.photos).toHaveLength(3);
  expect(item.photos[0]).toMatch(/\.mp4$/);
  expect(item.image).toBe(item.photos[1]);
  await page.goto("/");
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  const names = await page.locator("#products article h3").allTextContents();
  const publicItems = (await (await request.get(`${api}/api/products`)).json()).items;
  const lastFeatured = names.indexOf(name);
  const unfeatured = publicItems.filter((entry: { featured?: boolean }) => !entry.featured);
  for (const entry of unfeatured) expect(lastFeatured).toBeLessThan(names.indexOf(entry.name));
  await page.goto(`/products/${item.slug}`);
  const video = page.locator("video");
  await expect(video).toBeVisible();
  const seek = await video.evaluate(async (element: HTMLVideoElement) => {
    element.muted = true;
    await element.play();
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Video seek timed out")), 8000);
      element.addEventListener("seeked", () => { clearTimeout(timeout); resolve(); }, { once: true });
      element.currentTime = 2;
    });
    const value = { duration: element.duration, time: element.currentTime };
    element.pause();
    return value;
  });
  expect(seek.duration).toBeGreaterThan(3.8);
  expect(seek.time).toBeGreaterThanOrEqual(2);
  const range = await request.get(`${api}${item.photos[0]}`, { headers: { Range: "bytes=100-199" } });
  expect(range.status()).toBe(206);
  expect((await range.body()).length).toBe(100);
  await page.getByRole("button", { name: `Show ${name} photo 2` }).click();
  await page.getByRole("button", { name: `Enlarge ${name} media 2` }).click();
  const dialog = page.getByRole("dialog", { name: `${name} enlarged media` });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Zoom in", exact: true }).click();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
});

test("upload partial failure retries only failed media and enforces 12-item cap", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "New", exact: true }).click();
  let requests = 0;
  await page.route("**/api/uploads/product-image", async (route) => {
    requests++;
    if (requests === 2) await route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Retry this file"}' });
    else await route.continue();
  });
  await page.locator('input[type="file"]').setInputFiles([
    { name: "success.png", mimeType: "image/png", buffer: png },
    { name: "retry.png", mimeType: "image/png", buffer: png },
  ]);
  await expect(page.getByText(/successful uploads remain/)).toBeVisible();
  await page.getByRole("button", { name: /Retry failed/ }).click();
  await expect(page.getByText(/1 of 1 files uploaded/)).toBeVisible();
  expect(requests).toBe(3);
  for (let index = 0; index < 10; index++) {
    await page.getByLabel("Media URL or path", { exact: true }).fill(`/images/pro-elite.svg?view=${index}`);
    await page.getByRole("button", { name: "Add media URL", exact: true }).click();
    await expect(page.getByLabel("Media URL or path", { exact: true })).toHaveValue("");
  }
  await expect(page.getByRole("group", { name: "Photos & videos (12/12)", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add media URL", exact: true })).toBeDisabled();
  await expect(page.locator('input[type="file"]')).toBeDisabled();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
});

test("quote form retains failed input, prevents duplicate active requests and stores a real inquiry", async ({ page }) => {
  await page.goto("/#contact");
  await page.getByLabel("Name", { exact: true }).fill("E2E customer");
  await page.getByLabel("Email", { exact: true }).fill("e2e@example.com");
  const message = unique("E2E inquiry");
  await page.getByRole("textbox", { name: "Message", exact: true }).fill(message);
  let calls = 0;
  await page.route("**/api/inquiries", async (route) => {
    calls++;
    await new Promise((resolve) => setTimeout(resolve, 300));
    await route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Temporary test failure"}' });
  });
  await page.getByRole("button", { name: "Submit inquiry", exact: true }).click();
  await expect(page.getByRole("button", { name: "Submitting...", exact: true })).toBeDisabled();
  await expect(page.getByRole("alert").filter({ hasText: "Temporary test failure" })).toBeVisible();
  expect(calls).toBe(1);
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toHaveValue(message);
  await page.unroute("**/api/inquiries");
  const response = page.waitForResponse((result) => result.url().endsWith("/api/inquiries") && result.request().method() === "POST");
  await page.getByRole("button", { name: "Submit inquiry", exact: true }).click();
  expect((await response).status()).toBe(200);
  await expect(page.locator("#contact").getByRole("status")).toContainText("Inquiry received");
  const directory = path.join(process.env.STYL_E2E_DATA_DIR!, "inquiries");
  const saved = readdirSync(directory).map((name) => JSON.parse(readFileSync(path.join(directory, name), "utf8")));
  expect(saved.some((item) => item.message === message && item.emailStatus === "unconfigured")).toBe(true);
});

test("responsive navigation, desktop grids, narrow widths and cart quantity limits", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator("#products article").first()).toBeVisible();
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width >= 1024) await expect(page.getByRole("navigation", { name: "Main navigation", exact: true })).toBeVisible();
    else {
      await page.getByRole("button", { name: "Menu", exact: true }).click();
      await expect(page.getByRole("dialog", { name: "Site navigation" })).toBeVisible();
      await page.getByRole("button", { name: "Close", exact: true }).click();
    }
  }
  await page.setViewportSize(testInfo.project.name.startsWith("phone") ? { width: 390, height: 844 } : { width: 1440, height: 1000 });
  const first = page.locator("#products article").first();
  const name = await first.locator("h3").innerText();
  await first.getByRole("button", { name: "Add to cart", exact: true }).click();
  await page.getByRole("link", { name: "Cart (1)", exact: true }).click();
  const plus = page.getByRole("button", { name: `Increase quantity for ${name}` });
  for (let index = 0; index < 9; index++) await plus.click();
  await expect(plus).toBeDisabled();
  await expect(page.getByRole("link", { name: "Cart (10)", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Clear cart", exact: true }).click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(plus).toBeDisabled();
  await page.getByRole("button", { name: "Clear cart", exact: true }).click();
  await page.getByRole("button", { name: "Confirm clear cart", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your cart is empty." })).toBeVisible();
});

test("business principle is prominent in the introduction without delaying mobile shopping", async ({ page }) => {
  await page.goto("/");
  const statement = "Maximize customer value first, then capture a fair share of the value created.";
  const introduction = page.locator("main > section").first();
  const principle = introduction.locator("blockquote");
  await expect(page.getByText(statement, { exact: true })).toHaveCount(1);
  await expect(principle).toContainText(statement);
  await expect(page.locator("#about blockquote")).toHaveCount(0);
  await expect(page.locator("#products article h3").first()).toBeVisible();
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await expect(principle).toBeInViewport({ ratio: 1 });
    await expect(page.getByRole("link", { name: "Shop equipment", exact: true })).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width === 390) {
      const firstProduct = await page.locator("#products article h3").first().boundingBox();
      expect(firstProduct).not.toBeNull();
      expect(firstProduct!.y + firstProduct!.height).toBeLessThanOrEqual(844 * 2);
    }
  }
});

test("home banner is hidden on phones and preserved on tablet and desktop", async ({ page }) => {
  await page.goto("/");
  const introduction = page.locator("main > section").first();
  const banner = introduction.locator('aside[aria-label="Home banner"]');
  for (const width of [320, 390, 767, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    if (width < 768) {
      await expect(banner).toBeHidden();
    } else {
      await expect(banner).toBeVisible();
    }
    await expect(introduction.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(introduction.locator("blockquote")).toBeVisible();
    await expect(introduction.getByRole("link", { name: "Shop equipment", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});

test("home banner save persists and public numeric price uses two decimals", async ({ page, request }) => {
  const original = (await (await request.get(`${api}/api/hero`)).json()).item;
  await signIn(page);
  await page.getByRole("button", { name: "Home banner", exact: true }).click();
  await expect(page.getByRole("button", { name: /Save/ })).toBeEnabled();
  await page.getByLabel("Price text", { exact: true }).fill("$19.5");
  await expect(page.getByText("$19.50", { exact: true })).toBeVisible();
  const response = page.waitForResponse((value) => value.url().endsWith("/api/hero") && value.request().method() === "PUT");
  await page.getByRole("button", { name: /Save/ }).click();
  expect((await response).status()).toBe(200);
  await page.goto("/");
  const banner = page.locator('aside[aria-label="Home banner"]');
  if (page.viewportSize()!.width < 768) await expect(banner).toBeHidden();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(banner).toBeVisible();
  await expect(banner).toContainText("$19.50");
  const restore = await request.put(`${api}/api/hero`, { headers, data: original });
  expect(restore.status()).toBe(200);
});

test("catalog retry, unavailable images and empty cart recover visibly", async ({ page }) => {
  await page.route("**/api/products", (route) => route.fulfill({ status: 503, body: "unavailable" }));
  await page.goto("/");
  await expect(page.locator("#products").getByRole("alert")).toContainText("unavailable");
  await page.unroute("**/api/products");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator("#products article").first()).toBeVisible();
  await page.route("**/api/accessories", (route) => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ items: [{ id: 1999, name: "Missing image fixture", category: "Handle", price: 1, currency: "CAD", photos: ["/missing-test-image.png"], notes: "", dimensions: "", material: "", weight: "" }] }),
  }));
  await page.goto("/accessories");
  await expect(page.getByRole("button", { name: "Retry image", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry image", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry image", exact: true })).toBeVisible();
  await page.goto("/cart");
  await expect(page.getByRole("heading", { name: "Your cart is empty." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Shop equipment", exact: true })).toBeVisible();
});

test("unsupported and oversized upload attempts do not submit files", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "New", exact: true }).click();
  let requests = 0;
  page.on("request", (request) => { if (request.url().includes("/api/uploads/") && request.method() === "POST") requests++; });
  await page.locator('input[type="file"]').setInputFiles({ name: "bad.txt", mimeType: "text/plain", buffer: Buffer.from("not an image") });
  await expect(page.getByRole("alert").filter({ hasText: "bad.txt" })).toContainText("Use JPG");
  await page.locator('input[type="file"]').setInputFiles({ name: "large.png", mimeType: "image/png", buffer: Buffer.alloc(8 * 1024 * 1024 + 1) });
  await expect(page.getByRole("alert").filter({ hasText: "large.png" })).toContainText("8 MiB");
  const oversized = path.join(process.env.STYL_E2E_DATA_DIR!, "large.mp4");
  writeFileSync(oversized, Buffer.alloc(50 * 1024 * 1024 + 1));
  await page.locator('input[type="file"]').setInputFiles(oversized);
  await expect(page.getByRole("alert").filter({ hasText: "large.mp4" })).toContainText("50 MiB");
  expect(requests).toBe(0);
});
