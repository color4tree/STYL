import { test, expect } from "@playwright/test";

test("Canadian display and saved-cart reprice use CAD without converting USD", async ({ page }) => {
  const item = { id: 9901, name: "Canada priced rack", slug: "canada-priced-rack", category: "Racks", price: 4005.25, currency: "CAD", image: "/images/pro-elite.svg" };
  const body = { items: [item], market: { countryCode: "CA", currency: "CAD", locationStatus: "located" } };
  await page.route("**/api/products", (route) => route.fulfill({ json: body }));
  await page.route("**/api/catalog/selection", (route) => route.fulfill({ json: body }));
  await page.goto("/");
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
