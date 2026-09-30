import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { defaultEngineering, type Hero } from "../../src/lib/hero";

const api = "http://127.0.0.1:8102";
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aC1sAAAAASUVORK5CYII=", "base64");
const originals = new Map<string, Hero>();
test.beforeEach(async ({ request }, info) => {
  if (!process.env.STYL_E2E_DATA_DIR || !path.basename(process.env.STYL_E2E_DATA_DIR).startsWith("styl-e2e-")) throw new Error("Engineering tests require isolated data.");
  const response = await request.get(`${api}/api/admin/hero`, { headers });
  expect(response.status()).toBe(200);
  originals.set(info.testId, (await response.json()).item);
});
test.afterEach(async ({ request }, info) => {
  const original = originals.get(info.testId);
  if (original) expect((await request.put(`${api}/api/hero`, { headers, data: original })).status()).toBe(200);
  originals.delete(info.testId);
});

async function openEditor(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Home banner", exact: true }).click();
  await expect(page.getByLabel("Engineering section heading", { exact: true })).toBeEnabled();
}

test("ADM-013: clear photo buttons open the picker by pointer and keyboard without publishing", async ({ page, request }) => {
  await openEditor(page);
  const buttons = page.getByRole("button", { name: /^Choose (banner photo|photo for engineering card [1-4])$/ });
  await expect(buttons).toHaveCount(5);
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const button of await buttons.all()) {
      await expect(button).toBeVisible();
      expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(48);
      await expect(button).toHaveText("Choose photo");
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  const previous = await page.getByLabel("Banner image URL or path", { exact: true }).inputValue();
  const cancelled = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Choose banner photo", exact: true }).click();
  await (await cancelled).setFiles([]);
  await expect(page.getByLabel("Banner image URL or path", { exact: true })).toHaveValue(previous);

  const before = (await (await request.get(`${api}/api/admin/hero`, { headers })).json()).item;
  for (const [buttonName, field, keyboard] of [
    ["Choose banner photo", "Banner image URL or path", false],
    ["Choose photo for engineering card 2", "Card 2 image URL or path", true],
  ] as const) {
    const button = page.getByRole("button", { name: buttonName, exact: true });
    const chosen = page.waitForEvent("filechooser");
    if (keyboard) { await button.focus(); await expect(button).toBeFocused(); await button.press("Enter"); }
    else await button.click();
    const upload = page.waitForResponse(response => response.url().endsWith("/api/uploads/product-image") && response.request().method() === "POST");
    await (await chosen).setFiles({ name: "chosen-photo.png", mimeType: "image/png", buffer: png });
    const response = await upload;
    expect(response.status()).toBe(200);
    const image = (await response.json()).image;
    await expect(page.getByLabel(field, { exact: true })).toHaveValue(image);
    await expect(button).toBeEnabled();
  }
  expect((await (await request.get(`${api}/api/admin/hero`, { headers })).json()).item).toEqual(before);
});

test("ADM-013 USR-019: engineering text and uploaded photo save, reload and render in the existing public layout", async ({ page, request }, info) => {
  const original = originals.get(info.testId)!;
  await openEditor(page);
  const heading = `Engineering ${randomUUID().slice(0, 8)}`;
  await page.getByLabel("Engineering section heading", { exact: true }).fill(heading);
  await page.getByLabel("Engineering introduction", { exact: true }).fill("Our configurable section.\nLine two.");
  for (let index = 1; index <= 4; index++) {
    await page.getByLabel(`Card ${index} title`, { exact: true }).fill(`Custom card ${index}`);
    await page.getByLabel(`Card ${index} description`, { exact: true }).fill(`Card ${index} explanation.\nAnother line.`);
  }
  const upload = page.waitForResponse(response => response.url().endsWith("/api/uploads/product-image") && response.request().method() === "POST");
  await page.getByLabel("Card 2 photo", { exact: true }).setInputFiles({ name: "engineering.png", mimeType: "image/png", buffer: png });
  const uploaded = await upload;
  expect(uploaded.status()).toBe(200);
  const image = (await uploaded.json()).image;
  await expect(page.getByLabel("Card 2 image URL or path", { exact: true })).toHaveValue(image);
  const save = page.waitForResponse(response => response.url().endsWith("/api/hero") && response.request().method() === "PUT");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  const saved = await save;
  expect(saved.status()).toBe(200);
  const item = (await saved.json()).item;
  expect(item.title).toBe(original.title);
  expect(item.image).toBe(original.image);
  expect(item.engineering.items[1].image).toBe(image);
  await expect(page.locator("main").getByRole("status").filter({ hasText: "saved successfully" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Home banner", exact: true }).click();
  await expect(page.getByLabel("Engineering section heading", { exact: true })).toHaveValue(heading);
  await expect(page.getByLabel("Card 2 image URL or path", { exact: true })).toHaveValue(image);
  await page.goto("/");
  const section = page.locator("#gallery");
  await expect(section.locator("summary")).toHaveText(heading);
  await section.locator("summary").click();
  await expect(section.locator("article")).toHaveCount(4);
  await expect(section).toContainText("Our configurable section.");
  for (let index = 1; index <= 4; index++) await expect(section.getByRole("heading", { name: `Custom card ${index}`, exact: true })).toBeVisible();
  await expect(section.getByAltText("Custom card 2", { exact: true })).toHaveAttribute("src", `${api}${image}`);
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
  expect((await request.get(`${api}/api/admin/hero`)).status()).toBe(401);
});

test("ADM-013: engineering-only changes are dirty, retained after save errors, and preserved when visiting Backup", async ({ page }) => {
  await openEditor(page);
  const input = page.getByLabel("Card 1 title", { exact: true });
  await input.fill("Unsaved engineering title");
  page.once("dialog", dialog => dialog.dismiss());
  await page.getByRole("button", { name: "Equipment", exact: true }).click();
  await expect(input).toHaveValue("Unsaved engineering title");
  await page.getByRole("button", { name: "Backup", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Catalog recovery backup", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Home banner", exact: true }).click();
  await expect(input).toHaveValue("Unsaved engineering title");
  await page.route("**/api/hero", route => route.request().method() === "PUT"
    ? route.fulfill({ status: 503, json: { detail: "Synthetic content storage unavailable" } }) : route.continue());
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Synthetic content storage unavailable");
  await expect(input).toHaveValue("Unsaved engineering title");
  await page.unroute("**/api/hero");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.locator("main").getByRole("status").filter({ hasText: "saved successfully" })).toBeVisible();
});

test("ADM-013: invalid engineering fields and uploads are explicit, without publishing partial edits", async ({ page }) => {
  await openEditor(page);
  const requests: string[] = [];
  page.on("request", request => { if (request.method() === "PUT" || request.method() === "POST") requests.push(request.url()); });
  await page.getByLabel("Card 1 image URL or path", { exact: true }).fill("h");
  await expect(page.getByText("Enter an image path or upload a photo to preview this card.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("HTTP/HTTPS image URL");
  await page.getByLabel("Card 1 image URL or path", { exact: true }).fill(defaultEngineering.items[0].image);
  await page.getByLabel("Card 1 title", { exact: true }).fill(" ");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("title and image");
  await page.getByLabel("Card 1 photo", { exact: true }).setInputFiles({ name: "not-photo.txt", mimeType: "text/plain", buffer: Buffer.from("not an image") });
  await expect(page.locator("main").getByRole("alert")).toContainText("up to 8 MiB");
  await page.getByLabel("Card 1 photo", { exact: true }).setInputFiles({ name: "too-large.png", mimeType: "image/png", buffer: Buffer.alloc(8 * 1024 * 1024 + 1) });
  await expect(page.locator("main").getByRole("alert")).toContainText("up to 8 MiB");
  expect(requests).toEqual([]);
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
});

test("ADM-013: pending engineering save blocks overlapping edits and unavailable content can be retried", async ({ page }) => {
  await page.route("**/api/hero", route => route.fulfill({ status: 503, json: { detail: "Synthetic load failure" } }));
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Home banner", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("Card 1 title", { exact: true })).toBeDisabled();
  await page.unroute("**/api/hero");
  await page.getByRole("button", { name: "Retry loading banner", exact: true }).click();
  await expect(page.getByLabel("Card 1 title", { exact: true })).toBeEnabled();
  let release!: () => void;
  let count = 0;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/hero", async route => {
    if (route.request().method() !== "PUT") return route.continue();
    count++;
    await gate;
    await route.continue();
  });
  await page.getByLabel("Card 1 title", { exact: true }).fill("Delayed saved title");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  try {
    await expect.poll(() => count).toBe(1);
    await expect(page.getByLabel("Card 1 title", { exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Equipment", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Saving...", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Choose banner photo", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Choose photo for engineering card 1", exact: true })).toBeDisabled();
  } finally { release(); }
  await expect(page.locator("main").getByRole("status").filter({ hasText: "saved successfully" })).toBeVisible();
});
