import { test as base, expect, type Download, type Page, type Response } from "@playwright/test";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const endpoint = `${api}/api/admin/catalog-backup`;
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aC1sAAAAASUVORK5CYII=", "base64");
const productName = "Recovery fixture product";
const accessoryName = "Recovery fixture accessory";
const hero = { tag: "Recovery", number: "01", eyebrow: "Catalog backup", title: "Recovery fixture banner", image: "/images/brand/frame-badge.jpg" };

type CatalogFixture = { directory: string; productFile: string };
type BackupWindow = Window & { backupUrls: { created: string[]; revoked: string[] } };

// The runner uses one worker. Replace only its isolated seed files: copied user
// records can reference unavailable uploads and must not determine backup success.
const test = base.extend<{ catalog: CatalogFixture }>({
  catalog: [async ({ request }, run) => {
    const directory = process.env.STYL_E2E_DATA_DIR;
    if (!directory || !path.isAbsolute(directory) || !path.basename(directory).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) {
      throw new Error("Catalog backup tests require the isolated Playwright API/data directory.");
    }
    const files = ["products.json", "accessories.json", "hero.json"].map((name) => path.join(directory, name));
    const originals = files.map((file) => existsSync(file) ? readFileSync(file) : null);
    let uploadedFile: string | undefined;
    try {
      writeFileSync(files[0], "[]");
      writeFileSync(files[1], "[]");
      writeFileSync(files[2], JSON.stringify(hero));
      const uploaded = await request.post(`${api}/api/uploads/product-image`, {
        headers, multipart: { image: { name: "catalog-recovery.png", mimeType: "image/png", buffer: png } },
      });
      expect(uploaded.status(), await uploaded.text()).toBe(200);
      const image: string = (await uploaded.json()).image;
      expect(image).toMatch(/^\/api\/uploads\/[^/\\]+$/);
      uploadedFile = path.join(directory, "uploads", image.slice("/api/uploads/".length));
      const common = {
        category: "Handle", prices: { CAD: 19.95, USD: 14.25 }, publicationStatus: "draft",
        image, photos: [image], description: "Saved recovery fixture",
        provenance: { notes: "Private synthetic recovery note", capturedDate: "2026-09-28" },
      };
      for (const [catalog, name] of [["products", productName], ["accessories", accessoryName]]) {
        const created = await request.post(`${api}/api/${catalog}`, { headers, data: { ...common, name } });
        expect(created.status(), await created.text()).toBe(200);
      }
      const banner = await request.put(`${api}/api/hero`, { headers, data: { ...hero, image } });
      expect(banner.status(), await banner.text()).toBe(200);
      await run({ directory, productFile: files[0] });
    } finally {
      for (const [index, file] of files.entries()) {
        if (originals[index] !== null) writeFileSync(file, originals[index]!);
        else rmSync(file, { force: true });
      }
      if (uploadedFile) rmSync(uploadedFile, { force: true });
    }
  }, { auto: true }],
});

async function signIn(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Backup", exact: true })).toBeEnabled();
}

async function openBackup(page: Page) {
  await page.getByRole("button", { name: "Backup", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Catalog recovery backup" })).toBeVisible();
}

function backupResponse(page: Page) {
  return page.waitForResponse((response) => response.url() === endpoint && response.request().method() === "GET");
}

async function validateDownload(download: Download, response: Response) {
  expect(response.status()).toBe(200);
  const responseHeaders = response.headers();
  expect(responseHeaders["content-type"]).toContain("application/zip");
  expect(responseHeaders["cache-control"]).toContain("no-store");
  expect(responseHeaders["cache-control"]).toContain("private");
  expect(responseHeaders["content-disposition"]).toMatch(/^attachment;/i);
  const filename = responseHeaders["content-disposition"].match(/filename="?([^";]+)"?/i)?.[1];
  expect(filename).toMatch(/^styl-catalog-backup-[a-z0-9_.-]+\.zip$/i);
  expect(download.suggestedFilename()).toBe(filename);
  expect(download.url()).toMatch(/^blob:/);
  expect(new URL(response.url()).search).toBe("");
  expect(response.request().headers()["authorization"]).toBe(headers.Authorization);
  const stream = await download.createReadStream();
  if (!stream) throw new Error("The browser did not provide the downloaded archive.");
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  const archive = Buffer.concat(chunks);
  expect(archive.subarray(0, 4).toString("hex")).toBe("504b0304");
  expect(archive.length).toBeGreaterThan(100);
  expect(archive.length).toBe(Number(responseHeaders["content-length"]));
  expect(await download.failure()).toBeNull();
  await download.delete();
}

async function successfulDownload(page: Page, button = "Download catalog backup") {
  const [download, response] = await Promise.all([
    page.waitForEvent("download"), backupResponse(page),
    page.getByRole("button", { name: button, exact: true }).click(),
  ]);
  await validateDownload(download, response);
  await expect(page.getByRole("status").filter({ hasText: "Download started:" })).toBeVisible();
}

async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

test("ADM-010 SYS-017: real private ZIP download, progress, duplicate guard, filename and URL cleanup", async ({ page }, testInfo) => {
  await signIn(page);
  await openBackup(page);
  await expect(page.getByText("Private, unencrypted archive", { exact: true })).toBeVisible();
  await expect(page.getByText(/Saved changes only\./)).toBeVisible();
  await expect(page.getByText(/Browser upload\/import is not implemented/)).toBeVisible();
  await expect(page.getByText(/not a machine or full website backup/)).toBeVisible();
  await expect(page.getByText(/No admin tokens, secrets, customer inquiries, or AWS configuration/)).toBeVisible();
  await expect(page.locator('input[type="file"]:visible')).toHaveCount(0);
  if (testInfo.project.name.startsWith("phone")) {
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 844 });
      await noOverflow(page);
      const button = await page.getByRole("button", { name: "Download catalog backup", exact: true }).boundingBox();
      expect(button!.height).toBeGreaterThanOrEqual(44);
    }
  } else {
    await noOverflow(page);
  }
  await page.clock.install();
  await page.evaluate(() => {
    const state = { created: [] as string[], revoked: [] as string[] };
    (window as unknown as BackupWindow).backupUrls = state;
    const create = URL.createObjectURL.bind(URL);
    const revoke = URL.revokeObjectURL.bind(URL);
    URL.createObjectURL = (object) => {
      const url = create(object);
      state.created.push(url);
      return url;
    };
    URL.revokeObjectURL = (url) => { state.revoked.push(url); revoke(url); };
  });
  let requests = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(endpoint, async (route) => {
    requests++;
    await gate;
    await route.continue();
  });
  try {
    const downloaded = page.waitForEvent("download");
    const response = backupResponse(page);
    await page.getByRole("button", { name: "Download catalog backup", exact: true }).evaluate((element) => {
      (element as HTMLButtonElement).click();
      (element as HTMLButtonElement).click();
    });
    await expect.poll(() => requests).toBe(1);
    await expect(page.getByRole("button", { name: "Preparing backup…", exact: true })).toBeDisabled();
    await expect(page.getByRole("status").filter({ hasText: "Preparing the catalog and media ZIP" })).toBeVisible();
    for (const name of ["Backup", "Products", "Accessories", "Home banner", "Sign out"]) {
      await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
    }
    release();
    await validateDownload(await downloaded, await response);
    await expect(page.getByRole("button", { name: "Download catalog backup", exact: true })).toBeEnabled();
    expect(requests).toBe(1);
    const urls = await page.evaluate(() => (window as unknown as BackupWindow).backupUrls);
    expect(urls.created).toHaveLength(1);
    expect(urls.revoked).toEqual([]);
    await page.clock.fastForward(60_000);
    expect(await page.evaluate(() => (window as unknown as BackupWindow).backupUrls.revoked)).toEqual(urls.created);
  } finally {
    release();
    await page.unroute(endpoint);
  }
});

test("ADM-010 SYS-017: real missing-media rejection stays visible and retries after fixture repair", async ({ page, catalog }) => {
  await signIn(page);
  await openBackup(page);
  const saved = readFileSync(catalog.productFile);
  const products = JSON.parse(saved.toString());
  products[0].image = "/api/uploads/catalog-backup-missing-fixture.png";
  products[0].photos = [products[0].image];
  let downloads = 0;
  page.on("download", () => { downloads++; });
  try {
    writeFileSync(catalog.productFile, JSON.stringify(products));
    const response = backupResponse(page);
    await page.getByRole("button", { name: "Download catalog backup", exact: true }).click();
    const rejected = await response;
    expect(rejected.status()).toBe(409);
    const detail = (await rejected.json()).detail;
    expect(typeof detail).toBe("string");
    await expect(page.locator("main").getByRole("alert")).toContainText(detail);
    await expect(page.getByRole("heading", { level: 1, name: "Catalog recovery backup" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry backup download", exact: true })).toBeEnabled();
    expect(downloads).toBe(0);
    await noOverflow(page);
  } finally {
    writeFileSync(catalog.productFile, saved);
  }
  await successfulDownload(page, "Retry backup download");
  expect(downloads).toBe(1);
});

test("ADM-010 SYS-017: sign-in and real expired-token rejection never expose a ZIP or clear the page", async ({ page, request }) => {
  await page.goto("/admin");
  await expect(page.getByRole("button", { name: "Backup", exact: true })).toHaveCount(0);
  for (const authorization of [undefined, "Bearer wrong-token"]) {
    const response = await request.get(endpoint, { headers: authorization ? { Authorization: authorization } : {} });
    expect(response.status()).toBe(401);
    expect(response.headers()["content-type"]).toContain("application/json");
    expect(response.headers()["content-disposition"]).toBeUndefined();
  }
  await page.getByLabel("Admin token", { exact: true }).fill("wrong-token");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Incorrect admin token");
  await expect(page.getByRole("button", { name: "Backup", exact: true })).toHaveCount(0);
  await signIn(page);
  await openBackup(page);
  let downloads = 0;
  page.on("download", () => { downloads++; });
  await page.route(endpoint, (route) => route.continue({
    headers: { ...route.request().headers(), authorization: "Bearer expired-token" },
  }));
  const failed = backupResponse(page);
  await page.getByRole("button", { name: "Download catalog backup", exact: true }).click();
  const rejected = await failed;
  expect(rejected.status()).toBe(401);
  await expect(page.locator("main").getByRole("alert")).toContainText((await rejected.json()).detail);
  await expect(page.locator("main").getByRole("alert")).toContainText("Your open editor has not been cleared");
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeEnabled();
  expect(downloads).toBe(0);
  await page.unroute(endpoint);
  await successfulDownload(page, "Retry backup download");
  expect(downloads).toBe(1);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByLabel("Admin token", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Backup", exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("Admin token", { exact: true })).toBeVisible();
});

test("ADM-010: Backup preserves all three unsaved editors and their navigation guards without saving", async ({ page, catalog }) => {
  await signIn(page);
  const files = ["products.json", "accessories.json", "hero.json"].map((name) => path.join(catalog.directory, name));
  const saved = files.map((file) => readFileSync(file));
  let writes = 0;
  page.on("request", (request) => {
    if (request.url().startsWith(api) && ["POST", "PUT", "DELETE", "PATCH"].includes(request.method())) writes++;
  });
  for (const editor of [
    { tab: "Products", name: productName, label: "Product name" },
    { tab: "Accessories", name: accessoryName, label: "Accessory name" },
    { tab: "Home banner", name: hero.title, label: "Title" },
  ]) {
    await page.getByRole("button", { name: editor.tab, exact: true }).click();
    if (editor.tab !== "Home banner") await page.getByRole("button").filter({ hasText: editor.name }).click();
    const input = page.getByRole("textbox", { name: editor.label, exact: true });
    await expect(input).toHaveValue(editor.name);
    await input.fill(`Unsaved ${editor.name}`);
    await openBackup(page);
    await expect(page.getByRole("status").filter({ hasText: "You have unsaved changes" })).toBeVisible();
    if (editor.tab === "Products") await successfulDownload(page);
    const dialog = page.waitForEvent("dialog");
    const signingOut = page.getByRole("button", { name: "Sign out", exact: true }).click();
    const confirmation = await dialog;
    expect(confirmation.message()).toContain("Discard your unsaved changes");
    await confirmation.dismiss();
    await signingOut;
    await expect(page.getByRole("heading", { level: 1, name: "Catalog recovery backup" })).toBeVisible();
    await page.getByRole("button", { name: editor.tab, exact: true }).click();
    await expect(input).toHaveValue(`Unsaved ${editor.name}`);
    await input.fill(editor.name);
    for (const [index, file] of files.entries()) expect(readFileSync(file)).toEqual(saved[index]);
  }
  expect(writes).toBe(0);
});

for (const failure of ["service", "network", "invalid archive"] as const) {
  test(`ADM-010: simulated ${failure} failure is actionable and retries against the real API`, async ({ page }) => {
    await signIn(page);
    await openBackup(page);
    await page.route(endpoint, (route) => {
      if (failure === "network") return route.abort("failed");
      return route.fulfill(failure === "service"
        ? { status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Catalog backup generation is busy. Retry shortly." }) }
        : { status: 200, contentType: "application/json", body: JSON.stringify({ detail: "Not an archive" }) });
    });
    let downloads = 0;
    page.on("download", () => { downloads++; });
    await page.getByRole("button", { name: "Download catalog backup", exact: true }).click();
    await expect(page.locator("main").getByRole("alert")).toBeVisible();
    if (failure === "service") await expect(page.locator("main").getByRole("alert")).toContainText("Catalog backup generation is busy. Retry shortly.");
    if (failure === "invalid archive") await expect(page.locator("main").getByRole("alert")).toContainText("The server did not return a ZIP archive");
    await expect(page.getByRole("button", { name: "Retry backup download", exact: true })).toBeEnabled();
    await expect(page.getByRole("heading", { level: 1, name: "Catalog recovery backup" })).toBeVisible();
    expect(downloads).toBe(0);
    await noOverflow(page);
    await page.unroute(endpoint);
    await successfulDownload(page, "Retry backup download");
    expect(downloads).toBe(1);
    await expect(page.locator("main").getByRole("alert")).toHaveCount(0);
  });
}
