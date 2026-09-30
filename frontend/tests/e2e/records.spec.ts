import { test, expect, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { createHash, randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const endpoint = `${api}/api/admin/records`;
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Archive = {
  id: string; filename: string; bytes: number; sha256: string; verifiedAt: string | null; removedAt: string | null; archiveDeletedAt: string | null;
  removalState?: "ready" | "removing" | "complete" | "failed";
  counts: { inquiries: number; analyticsRows: number; websiteLogs: number };
  removal: { inquiries: number; analyticsRows: number; websiteLogs: number; skipped: number } | null;
};
type Database = {
  exec(sql: string): void;
  prepare(sql: string): { run(...values: (string | number)[]): unknown; all(...values: (string | number)[]): Record<string, unknown>[] };
  close(): void;
};
const { DatabaseSync } = createRequire(path.resolve("package.json"))("node:sqlite") as { DatabaseSync: new (file: string) => Database };

function isolatedDirectory() {
  const directory = process.env.STYL_E2E_DATA_DIR;
  if (!directory || !path.isAbsolute(directory) || !path.basename(directory).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) {
    throw new Error("Records tests require the runner's isolated STYL_E2E_DATA_DIR and token, never a local profile.");
  }
  return directory;
}

test.beforeEach(() => { isolatedDirectory(); });

function sql(statement: string, ...values: (string | number)[]) {
  const connection = new DatabaseSync(path.join(isolatedDirectory(), "analytics.sqlite3"));
  try {
    connection.exec("PRAGMA busy_timeout=5000");
    return connection.prepare(statement).all(...values);
  } finally { connection.close(); }
}

async function signIn(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Backup & Records", exact: true })).toBeEnabled();
}

async function openRecords(page: Page) {
  await page.getByRole("button", { name: "Backup & Records", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Backup & Records", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create persistent backup", exact: true })).toBeEnabled();
}

async function createArchive(page: Page): Promise<Archive> {
  const response = page.waitForResponse((value) => value.url() === `${endpoint}/archives` && value.request().method() === "POST");
  await page.getByRole("button", { name: "Create persistent backup", exact: true }).click();
  const result = await response;
  expect(result.status(), await result.text()).toBe(201);
  expect(result.request().postData()).toBeNull();
  const archive: Archive = await result.json();
  await expect(page.getByLabel("Saved server backup", { exact: true })).toHaveValue(archive.id);
  await expect(page.getByRole("button", { name: "Download selected backup", exact: true })).toBeEnabled();
  return archive;
}

async function downloadArchive(page: Page, archive: Archive, testInfo: TestInfo) {
  const [download, response] = await Promise.all([
    page.waitForEvent("download"),
    page.waitForResponse((value) => value.url() === `${endpoint}/archives/${archive.id}/download`),
    page.getByRole("button", { name: "Download selected backup", exact: true }).click(),
  ]);
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("application/zip");
  expect(response.headers()["cache-control"]).toContain("no-store");
  expect(response.headers()["content-disposition"]).toContain(archive.filename);
  expect(response.request().headers()["authorization"]).toBe(headers.Authorization);
  expect(new URL(response.url()).search).toBe("");
  expect(download.suggestedFilename()).toBe(archive.filename);
  expect(download.url()).toMatch(/^blob:/);
  const saved = testInfo.outputPath(archive.filename);
  await download.saveAs(saved);
  expect(await download.failure()).toBeNull();
  const content = readFileSync(saved);
  expect(content.subarray(0, 4).toString("hex")).toBe("504b0304");
  expect(content.byteLength).toBe(archive.bytes);
  expect(createHash("sha256").update(content).digest("hex")).toBe(archive.sha256);
  await expect(page.getByRole("status").filter({ hasText: "does not confirm a saved local copy" })).toBeVisible();
  await download.delete();
  return saved;
}

async function verifySaved(page: Page, archive: Archive, saved: string) {
  await page.getByLabel("Saved local backup ZIP", { exact: true }).setInputFiles(saved);
  const response = page.waitForResponse((value) => value.url() === `${endpoint}/archives/${archive.id}/verify` && value.request().method() === "POST");
  await page.getByRole("button", { name: "Verify saved file", exact: true }).click();
  const result = await response;
  expect(result.status()).toBe(200);
  expect(result.request().headers()["content-type"]).toBe("application/zip");
  expect(result.request().headers()["authorization"]).toBe(headers.Authorization);
  await expect(page.getByRole("status").filter({ hasText: "Saved local backup verified" })).toBeVisible();
  // Chromium may evict File-upload response bodies from DevTools; verify durable server state instead.
  const persisted = await page.request.get(endpoint, { headers });
  expect(persisted.status()).toBe(200);
  const verified: Archive = (await persisted.json()).archives.find((value: Archive) => value.id === archive.id);
  expect(verified.verifiedAt).not.toBeNull();
  expect(verified.sha256).toBe(createHash("sha256").update(readFileSync(saved)).digest("hex"));
  return verified;
}

async function inquiry(request: APIRequestContext, name: string) {
  const response = await request.post(`${api}/api/inquiries`, { data: { name, email: "records-fixture@example.com", message: "Synthetic records preservation fixture." } });
  expect(response.status(), await response.text()).toBe(200);
  const { id } = await response.json();
  const file = path.join(isolatedDirectory(), "inquiries", `${id}.json`);
  expect(existsSync(file)).toBe(true);
  return file;
}

async function seedSources(request: APIRequestContext) {
  const directory = isolatedDirectory();
  const inquiryDirectory = path.join(directory, "inquiries");
  mkdirSync(inquiryDirectory, { recursive: true });
  const originals = readdirSync(inquiryDirectory).filter((name) => name.endsWith(".json")).map((name) => ({ file: path.join(inquiryDirectory, name), content: readFileSync(path.join(inquiryDirectory, name)) }));
  const files: string[] = [];
  const marker = randomUUID().replaceAll("-", "");
  const oldHour = "2000-01-01T00:00:00.000000+00:00";
  const now = new Date();
  now.setUTCMinutes(0, 0, 0);
  const currentHour = now.toISOString().replace(".000Z", ".000000+00:00");
  const label = `/records-fixture-${marker}`;
  const recipient = `records-${marker}@example.com`;
  const snapshotVersion = Number.parseInt(marker.slice(0, 7), 16) + 1;
  const settings = await request.get(`${api}/api/admin/analytics/email-settings`, { headers });
  expect(settings.status()).toBe(200);
  const savedSettings = await settings.json();
  const catalog = ["products.json", "accessories.json", "hero.json"].map((name) => path.join(directory, name)).filter(existsSync).map((file) => ({ file, content: readFileSync(file) }));
  const saved = await inquiry(request, `Old unchanged ${marker}`);
  const changed = await inquiry(request, `Changed after backup ${marker}`);
  const pending = await inquiry(request, `Pending ${marker}`);
  files.push(saved, changed, pending);
  writeFileSync(saved, JSON.stringify({ ...JSON.parse(readFileSync(saved, "utf8")), createdAt: oldHour }));
  writeFileSync(pending, JSON.stringify({ ...JSON.parse(readFileSync(pending, "utf8")), emailStatus: "pending" }));
  const sealed = path.join(directory, "website-logs", `${marker}.log`);
  const active = path.join(directory, "website-logs", `${marker}.active`);
  writeFileSync(sealed, "Synthetic sealed access log, preserved until verified removal.\n");
  writeFileSync(active, "Synthetic active runtime log prefix.\n");
  files.push(sealed, active);
  sql("INSERT INTO analytics_aggregate_counts VALUES(?,?,?,?,?,?)", oldHour, "page", label, "pageViews", 7, 0);
  sql("INSERT INTO analytics_aggregate_counts VALUES(?,?,?,?,?,?)", currentHour, "page", label, "pageViews", 3, 0);
  sql("INSERT INTO analytics_meta VALUES(?,?)", marker, "Protected duplicate-prevention metadata");
  sql("INSERT INTO analytics_report_snapshot VALUES(?,?,?,?,?,?,?)", "2000-01-01", "America/Los_Angeles", snapshotVersion, "Protected email history", "Original retry body must stay unchanged.", "<p>Original retry body must stay unchanged.</p>", oldHour);
  sql("INSERT INTO analytics_report_delivery(report_date,timezone,version,recipient,status,attempts,updated_at) VALUES(?,?,?,?,?,?,?)", "2000-01-01", "America/Los_Angeles", snapshotVersion, recipient, "sent", 1, oldHour);
  const snapshots = sql("SELECT * FROM analytics_report_snapshot WHERE report_date=? AND version=?", "2000-01-01", snapshotVersion);
  return {
    directory, files, saved, changed, pending, sealed, active, label, marker, recipient, oldHour, currentHour, savedSettings, catalog, snapshotVersion, snapshots,
    cleanup() {
      for (const file of files) rmSync(file, { force: true });
      for (const original of originals) writeFileSync(original.file, original.content);
      sql("DELETE FROM analytics_aggregate_counts WHERE label=?", label);
      sql("DELETE FROM analytics_meta WHERE key=?", marker);
      sql("DELETE FROM analytics_report_delivery WHERE recipient=?", recipient);
      sql("DELETE FROM analytics_report_snapshot WHERE report_date=? AND version=?", "2000-01-01", snapshotVersion);
    },
  };
}

const removeButton = (page: Page) => page.getByRole("button", { name: "Remove selected source records", exact: true });
const confirmInput = (page: Page) => page.getByRole("textbox", { name: /^Removal confirmation/ });
const errorNotice = (page: Page) => page.getByRole("alert").filter({ has: page.getByText("Error", { exact: true }) });

test("REC-001 REC-002 REC-003: persistent real backup, local-file verification and exact source removal preserve newer and protected records", async ({ page, request }, testInfo) => {
  const fixture = await seedSources(request);
  let local: string | undefined;
  try {
    await signIn(page);
    await openRecords(page);
    const archive = await createArchive(page);
    expect(archive.counts.inquiries).toBeGreaterThanOrEqual(3);
    expect(archive.counts.analyticsRows).toBeGreaterThanOrEqual(2);
    expect(archive.counts.websiteLogs).toBeGreaterThanOrEqual(2);
    const serverArchive = path.join(fixture.directory, "records", archive.filename);
    expect(existsSync(serverArchive)).toBe(true);
    local = await downloadArchive(page, archive, testInfo);
    await expect(removeButton(page)).toBeDisabled();
    await expect(page.getByRole("button", { name: "Delete server backup ZIP", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Verify saved file", exact: true })).toBeDisabled();
    for (const file of [fixture.saved, fixture.changed, fixture.pending, fixture.sealed, fixture.active]) expect(existsSync(file)).toBe(true);
    await verifySaved(page, archive, local);
    await expect(removeButton(page)).toBeDisabled();
    await expect(page.getByRole("button", { name: "Delete server backup ZIP", exact: true })).toBeDisabled();
    for (const name of ["Saved inquiries", "Analytics history", "Sealed website logs"]) await expect(page.getByRole("checkbox", { name, exact: true })).not.toBeChecked();

    await page.reload();
    await openRecords(page);
    await page.getByLabel("Saved server backup", { exact: true }).selectOption(archive.id);
    await expect(page.getByRole("checkbox", { name: "Saved inquiries", exact: true })).toBeEnabled();
    const list = await request.get(endpoint, { headers });
    const persisted: Archive = (await list.json()).archives.find((value: Archive) => value.id === archive.id);
    expect(persisted.verifiedAt).not.toBeNull();
    expect(persisted.removedAt).toBeNull();
    expect(createHash("sha256").update(readFileSync(serverArchive)).digest("hex")).toBe(archive.sha256);

    writeFileSync(fixture.changed, JSON.stringify({ ...JSON.parse(readFileSync(fixture.changed, "utf8")), message: "Newer change must survive." }));
    const newer = await inquiry(request, `New since backup ${fixture.marker}`);
    fixture.files.push(newer);
    writeFileSync(fixture.active, `${readFileSync(fixture.active, "utf8")}New runtime writes after backup.\n`);
    const preserved = [fixture.changed, fixture.pending, newer, fixture.active].map((file) => ({ file, content: readFileSync(file) }));
    for (const name of ["Saved inquiries", "Analytics history", "Sealed website logs"]) await page.getByRole("checkbox", { name, exact: true }).check();
    await confirmInput(page).fill(`REMOVE ${archive.id} `);
    await expect(removeButton(page)).toBeDisabled();
    await confirmInput(page).fill(`REMOVE ${archive.id}`);
    const removedResponse = page.waitForResponse((value) => value.url() === `${endpoint}/archives/${archive.id}/remove`);
    await removeButton(page).click();
    const result = await removedResponse;
    expect(result.status(), await result.text()).toBe(200);
    expect(result.request().postDataJSON()).toEqual({ confirmation: `REMOVE ${archive.id}`, categories: ["inquiries", "analytics", "websiteLogs"] });
    const removed: Archive = await result.json();
    expect(removed.removal!.inquiries).toBeGreaterThanOrEqual(1);
    expect(removed.removal!.analyticsRows).toBeGreaterThanOrEqual(1);
    expect(removed.removal!.websiteLogs).toBeGreaterThanOrEqual(1);
    expect(removed.removal!.skipped).toBeGreaterThanOrEqual(3);
    expect(existsSync(fixture.saved)).toBe(false);
    expect(existsSync(fixture.sealed)).toBe(false);
    for (const value of [...preserved, ...fixture.catalog]) expect(readFileSync(value.file)).toEqual(value.content);
    expect(sql("SELECT * FROM analytics_aggregate_counts WHERE hour=? AND label=?", fixture.oldHour, fixture.label)).toHaveLength(0);
    expect(sql("SELECT * FROM analytics_aggregate_counts WHERE hour=? AND label=?", fixture.currentHour, fixture.label)).toHaveLength(1);
    expect(sql("SELECT * FROM analytics_meta WHERE key=?", fixture.marker)).toHaveLength(1);
    expect(sql("SELECT * FROM analytics_report_delivery WHERE recipient=? AND status='sent'", fixture.recipient)).toHaveLength(1);
    expect(sql("SELECT * FROM analytics_report_snapshot WHERE report_date=? AND version=?", "2000-01-01", fixture.snapshotVersion)).toEqual(fixture.snapshots);
    const settings = await request.get(`${api}/api/admin/analytics/email-settings`, { headers });
    expect(await settings.json()).toEqual(fixture.savedSettings);
    expect(existsSync(serverArchive)).toBe(true);
    const repeated = await request.post(`${endpoint}/archives/${archive.id}/remove`, { headers, data: { confirmation: `REMOVE ${archive.id}`, categories: ["inquiries"] } });
    expect(repeated.status()).toBe(409);
    await page.reload();
    await openRecords(page);
    await page.getByLabel("Saved server backup", { exact: true }).selectOption(archive.id);
    await expect(page.getByRole("status").filter({ hasText: "This archive cannot request removal again" })).toBeVisible();
    await expect(removeButton(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Download selected backup", exact: true })).toBeEnabled();
  } finally {
    if (local) rmSync(local, { force: true });
    fixture.cleanup();
  }
});

test("REC-003: category choice is explicit and unselected analytics and website logs remain unchanged", async ({ page, request }, testInfo) => {
  const fixture = await seedSources(request);
  let local: string | undefined;
  try {
    await signIn(page);
    await openRecords(page);
    const archive = await createArchive(page);
    local = await downloadArchive(page, archive, testInfo);
    await verifySaved(page, archive, local);
    const analytics = sql("SELECT * FROM analytics_aggregate_counts WHERE label=? ORDER BY hour", fixture.label);
    const log = readFileSync(fixture.sealed);
    await confirmInput(page).fill(`REMOVE ${archive.id}`);
    await expect(removeButton(page)).toBeDisabled();
    await page.getByRole("checkbox", { name: "Saved inquiries", exact: true }).check();
    const response = page.waitForResponse((value) => value.url() === `${endpoint}/archives/${archive.id}/remove`);
    await removeButton(page).click();
    const result = await response;
    expect(result.status()).toBe(200);
    expect(result.request().postDataJSON().categories).toEqual(["inquiries"]);
    const removed: Archive = await result.json();
    expect(removed.removal!.analyticsRows).toBe(0);
    expect(removed.removal!.websiteLogs).toBe(0);
    expect(readFileSync(fixture.sealed)).toEqual(log);
    expect(sql("SELECT * FROM analytics_aggregate_counts WHERE label=? ORDER BY hour", fixture.label)).toEqual(analytics);
    expect(existsSync(fixture.saved)).toBe(false);
    expect(existsSync(fixture.pending)).toBe(true);
  } finally {
    if (local) rmSync(local, { force: true });
    fixture.cleanup();
  }
});

test("REC-002: a corrupt same-sized ZIP fails full verification, retains the choice and keeps removal locked until retry succeeds", async ({ page, request }, testInfo) => {
  await signIn(page);
  await openRecords(page);
  const archive = await createArchive(page);
  const local = await downloadArchive(page, archive, testInfo);
  try {
    await verifySaved(page, archive, local);
    const corrupt = Buffer.from(readFileSync(local));
    corrupt[Math.floor(corrupt.length / 2)] ^= 1;
    await page.getByLabel("Saved local backup ZIP", { exact: true }).setInputFiles({ name: archive.filename, mimeType: "application/zip", buffer: corrupt });
    await expect(removeButton(page)).toBeDisabled();
    const response = page.waitForResponse((value) => value.url() === `${endpoint}/archives/${archive.id}/verify`);
    await page.getByRole("button", { name: "Verify saved file", exact: true }).click();
    const failed = await response;
    expect(failed.ok()).toBe(false);
    await expect(errorNotice(page)).toContainText("Selected file does not match this backup");
    await expect(page.getByLabel("Saved server backup", { exact: true })).toHaveValue(archive.id);
    expect(await page.getByLabel("Saved local backup ZIP", { exact: true }).evaluate((input: HTMLInputElement) => input.files?.[0]?.name)).toBe(archive.filename);
    await expect(removeButton(page)).toBeDisabled();
    await expect(page.getByRole("button", { name: "Verify saved file", exact: true })).toBeEnabled();
    const listed = await request.get(endpoint, { headers });
    expect((await listed.json()).archives.find((value: Archive) => value.id === archive.id).removedAt).toBeNull();
    await verifySaved(page, archive, local);
    await expect(page.getByRole("checkbox", { name: "Saved inquiries", exact: true })).toBeEnabled();
    await expect(removeButton(page)).toBeDisabled();
  } finally { rmSync(local, { force: true }); }
});

test("REC-004: unauthenticated routes and expired access expose no private archive; retry preserves selection", async ({ page, request }) => {
  await page.goto("/admin");
  await expect(page.getByRole("button", { name: "Backup & Records", exact: true })).toHaveCount(0);
  for (const authorization of [undefined, "Bearer invalid-records-token"]) {
    const options: { headers: Record<string, string> } = { headers: authorization ? { Authorization: authorization } : {} };
    for (const route of [endpoint, `${endpoint}/archives/${"0".repeat(32)}/download`]) {
      const response = await request.get(route, options);
      expect(response.status()).toBe(401);
      expect(response.headers()["content-disposition"]).toBeUndefined();
    }
    const create = await request.post(`${endpoint}/archives`, options);
    expect(create.status()).toBe(401);
    const deletion = await request.delete(`${endpoint}/archives/${"0".repeat(32)}`, { ...options, data: { confirmation: `DELETE BACKUP ${"0".repeat(32)}` } });
    expect(deletion.status()).toBe(401);
    for (const action of ["verify", "remove"]) {
      const response = await request.post(`${endpoint}/archives/${"0".repeat(32)}/${action}`, {
        ...options, data: action === "remove" ? { confirmation: `REMOVE ${"0".repeat(32)}`, categories: ["inquiries"] } : Buffer.from("not-a-zip"),
      });
      expect(response.status()).toBe(401);
    }
  }
  await signIn(page);
  await openRecords(page);
  const archive = await createArchive(page);
  let downloads = 0;
  page.on("download", () => { downloads++; });
  const downloadUrl = `${endpoint}/archives/${archive.id}/download`;
  await page.route(downloadUrl, (route) => route.continue({ headers: { ...route.request().headers(), authorization: "Bearer expired-records-token" } }));
  await page.getByRole("button", { name: "Download selected backup", exact: true }).click();
  await expect(errorNotice(page)).toContainText("Check your admin access");
  await expect(page.getByLabel("Saved server backup", { exact: true })).toHaveValue(archive.id);
  expect(downloads).toBe(0);
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeEnabled();
  await page.unroute(downloadUrl);
  await page.getByRole("button", { name: "Refresh records", exact: true }).click();
  await expect(errorNotice(page)).toHaveCount(0);
  await expect(page.getByLabel("Saved server backup", { exact: true })).toHaveValue(archive.id);
  await expect(page.locator("main")).not.toContainText(process.env.STYL_E2E_TOKEN!);
  expect(page.url()).not.toContain(process.env.STYL_E2E_TOKEN!);
});

test("REC-004: busy operations block navigation and duplicate actions; failed removal retains confirmation and categories for retry", async ({ page }, testInfo) => {
  await signIn(page);
  await openRecords(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let creates = 0;
  await page.route(`${endpoint}/archives`, async (route) => { creates++; await gate; await route.continue(); });
  let archive: Archive;
  try {
    const response = page.waitForResponse((value) => value.url() === `${endpoint}/archives`);
    await page.getByRole("button", { name: "Create persistent backup", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "Creating persistent backup" })).toBeVisible();
    for (const name of ["Create persistent backup", "Refresh records", "Equipment", "Accessories", "Home banner", "Backup", "Analytics", "Backup & Records", "Sign out"]) {
      await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
    }
    await page.getByRole("button", { name: "Create persistent backup", exact: true }).evaluate((element: HTMLButtonElement) => element.click());
    await expect.poll(() => creates).toBe(1);
    release();
    const result = await response;
    expect(result.status()).toBe(201);
    archive = await result.json();
    await expect(page.getByRole("button", { name: "Download selected backup", exact: true })).toBeEnabled();
  } finally { release(); await page.unroute(`${endpoint}/archives`); }
  const local = await downloadArchive(page, archive!, testInfo);
  try {
    await verifySaved(page, archive!, local);
    await page.getByRole("checkbox", { name: "Saved inquiries", exact: true }).check();
    await confirmInput(page).fill(`REMOVE ${archive!.id}`);
    const removeUrl = `${endpoint}/archives/${archive!.id}/remove`;
    await page.route(removeUrl, (route) => route.fulfill({ status: 409, json: { detail: "Synthetic conflict: source state changed. Refresh and retry." } }));
    await removeButton(page).click();
    await expect(errorNotice(page)).toContainText("Synthetic conflict");
    await expect(page.getByRole("checkbox", { name: "Saved inquiries", exact: true })).toBeChecked();
    await expect(confirmInput(page)).toHaveValue(`REMOVE ${archive!.id}`);
    await expect(page.getByLabel("Saved server backup", { exact: true })).toHaveValue(archive!.id);
    await expect(removeButton(page)).toBeEnabled();
    await page.unroute(removeUrl);
    await removeButton(page).click();
    await expect(page.getByRole("status").filter({ hasText: "Selected source-record removal completed" })).toBeVisible();
  } finally { rmSync(local, { force: true }); }
});

test("REC-004 REC-005: invalid/service/network responses recover, disk and absent log coverage warn clearly, and phone controls fit", async ({ page, request }, testInfo) => {
  await signIn(page);
  await openRecords(page);
  const archive = await createArchive(page);
  for (const failure of ["shape", "service", "network"]) {
    await page.route(endpoint, (route) => failure === "network" ? route.abort("failed") : route.fulfill(failure === "service"
      ? { status: 503, json: { detail: "Synthetic records storage unavailable. Please retry." } }
      : { status: 200, json: { archives: [{ id: "not-a-valid-archive" }] } }));
    await page.getByRole("button", { name: "Refresh records", exact: true }).click();
    await expect(errorNotice(page)).toBeVisible();
    if (failure === "shape") await expect(errorNotice(page)).toContainText("records response is invalid");
    await expect(page.getByLabel("Saved server backup", { exact: true })).toHaveValue(archive.id);
    await expect(page.getByRole("button", { name: "Refresh records", exact: true })).toBeEnabled();
    await page.unroute(endpoint);
    await page.getByRole("button", { name: "Refresh records", exact: true }).click();
    await expect(errorNotice(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Refresh records", exact: true })).toBeEnabled();
  }
  const response = await request.get(endpoint, { headers });
  const index = await response.json();
  await page.route(endpoint, (route) => route.fulfill({ json: {
    ...index, storage: { totalBytes: 1000, freeBytes: 200, usedPercent: 80 },
    websiteLogs: { configured: false, activeFiles: 0, sealedFiles: 0, bytes: 0 },
    warnings: ["Synthetic missing website log configuration warning."],
  } }));
  await page.getByRole("button", { name: "Refresh records", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Disk usage" })).toContainText("at or above 80%");
  await expect(page.getByText(/Website log coverage is NOT configured/)).toBeVisible();
  await expect(page.getByRole("list", { name: "Records warnings" })).toContainText("missing website log configuration");
  await expect(page.getByText("Confidential, unencrypted backup", { exact: true })).toBeVisible();
  await expect(page.getByText(/are not automatically deleted by age or size/)).toBeVisible();
  await expect(page.getByText(/the upload is not stored/)).toBeVisible();
  await expect(page.getByText(/Current-hour analytics, pending inquiries, mail duplicate-prevention metadata/)).toBeVisible();
  await expect(page.getByText(/Email report history and safety metadata stay/)).toBeVisible();
  for (const width of testInfo.project.name.startsWith("phone") ? [320, 390] : [1440]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    for (const name of ["Create persistent backup", "Refresh records", "Download selected backup"]) {
      const bounds = await page.getByRole("button", { name, exact: true }).boundingBox();
      expect(bounds!.height).toBeGreaterThanOrEqual(44);
      expect(bounds!.x).toBeGreaterThanOrEqual(0);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    }
  }
});

test("REC-005: records navigation preserves unsaved editor data and existing catalog recovery stays separate", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "New", exact: true }).click();
  const input = page.getByRole("textbox", { name: "Equipment name", exact: true });
  await input.fill("Unsaved records navigation fixture");
  await openRecords(page);
  await expect(page.getByRole("status").filter({ hasText: "You have unsaved editor changes" })).toBeVisible();
  await page.getByRole("button", { name: "Backup", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Catalog recovery backup", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download catalog backup", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create persistent backup", exact: true })).toBeHidden();
  await page.getByRole("button", { name: "Equipment", exact: true }).click();
  await expect(input).toHaveValue("Unsaved records navigation fixture");
  const dialog = page.waitForEvent("dialog");
  const signingOut = page.getByRole("button", { name: "Sign out", exact: true }).click();
  const confirmation = await dialog;
  expect(confirmation.message()).toContain("Discard your unsaved changes");
  await confirmation.dismiss();
  await signingOut;
  await expect(input).toHaveValue("Unsaved records navigation fixture");
  await input.fill("");
});

test("REC-006: explicit verified server-ZIP deletion reclaims only that archive, keeps audit history and permanently locks source removal", async ({ page, request }, testInfo) => {
  const fixture = await seedSources(request);
  let local: string | undefined;
  let release = () => {};
  try {
    await signIn(page);
    await openRecords(page);
    const archive = await createArchive(page);
    const archiveUrl = `${endpoint}/archives/${archive.id}`;
    const serverArchive = path.join(fixture.directory, "records", archive.filename);
    const deleteButton = page.getByRole("button", { name: "Delete server backup ZIP", exact: true });
    const deletionConfirmation = page.getByRole("textbox", { name: "Server-backup deletion confirmation", exact: true });
    await expect(deleteButton).toBeDisabled();
    const unverified = await request.delete(archiveUrl, { headers, data: { confirmation: `DELETE BACKUP ${archive.id}` } });
    expect(unverified.ok()).toBe(false);
    expect(existsSync(serverArchive)).toBe(true);
    local = await downloadArchive(page, archive, testInfo);
    await expect(deleteButton).toBeDisabled();
    await verifySaved(page, archive, local);
    await expect(deleteButton).toBeDisabled();
    const sources = [fixture.saved, fixture.changed, fixture.pending, fixture.sealed, fixture.active].map((file) => ({ file, content: readFileSync(file) }));
    const analytics = sql("SELECT * FROM analytics_aggregate_counts WHERE label=? ORDER BY hour", fixture.label);
    await page.getByRole("checkbox", { name: "Saved inquiries", exact: true }).check();
    await confirmInput(page).fill(`REMOVE ${archive.id}`);
    await expect(removeButton(page)).toBeEnabled();
    await deletionConfirmation.fill(`DELETE BACKUP ${archive.id} `);
    await expect(deleteButton).toBeDisabled();
    await deletionConfirmation.fill(`DELETE BACKUP ${archive.id}`);
    await page.route(archiveUrl, (route) => route.fulfill({ status: 503, json: { detail: "Synthetic backup deletion failure. Retry." } }));
    await deleteButton.click();
    await expect(errorNotice(page)).toContainText("Synthetic backup deletion failure");
    await expect(deletionConfirmation).toHaveValue(`DELETE BACKUP ${archive.id}`);
    await expect(page.getByLabel("Saved server backup", { exact: true })).toHaveValue(archive.id);
    expect(existsSync(serverArchive)).toBe(true);
    await page.unroute(archiveUrl);

    const gate = new Promise<void>((resolve) => { release = resolve; });
    let deletes = 0;
    let sourceRemovals = 0;
    page.on("request", (value) => { if (value.url() === `${archiveUrl}/remove`) sourceRemovals++; });
    await page.route(archiveUrl, async (route) => { deletes++; await gate; await route.continue(); });
    const deletedResponse = page.waitForResponse((value) => value.url() === archiveUrl && value.request().method() === "DELETE");
    await deleteButton.click();
    await expect(page.getByRole("status").filter({ hasText: "Deleting only the verified server backup ZIP" })).toBeVisible();
    for (const name of ["Delete server backup ZIP", "Remove selected source records", "Download selected backup", "Verify saved file", "Sign out", "Equipment"]) {
      await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
    }
    await deleteButton.evaluate((element: HTMLButtonElement) => element.click());
    await expect.poll(() => deletes).toBe(1);
    release();
    const response = await deletedResponse;
    expect(response.status(), await response.text()).toBe(200);
    expect(response.request().postDataJSON()).toEqual({ confirmation: `DELETE BACKUP ${archive.id}` });
    const deleted: Archive = await response.json();
    expect(deleted.archiveDeletedAt).not.toBeNull();
    expect(deleted.removedAt).toBeNull();
    expect(sourceRemovals).toBe(0);
    expect(existsSync(serverArchive)).toBe(false);
    expect(createHash("sha256").update(readFileSync(local)).digest("hex")).toBe(archive.sha256);
    for (const source of sources) expect(readFileSync(source.file)).toEqual(source.content);
    expect(sql("SELECT * FROM analytics_aggregate_counts WHERE label=? ORDER BY hour", fixture.label)).toEqual(analytics);
    expect(sql("SELECT * FROM analytics_report_delivery WHERE recipient=? AND status='sent'", fixture.recipient)).toHaveLength(1);
    await page.unroute(archiveUrl);

    await page.reload();
    await openRecords(page);
    await page.getByLabel("Saved server backup", { exact: true }).selectOption(archive.id);
    await expect(page.getByRole("status").filter({ hasText: "This history remains available" })).toBeVisible();
    await expect(page.getByText(/Source removal is disabled because this archive's server backup ZIP was deleted/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Download selected backup", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Verify saved file", exact: true })).toBeDisabled();
    await expect(page.getByLabel("Saved local backup ZIP", { exact: true })).toBeDisabled();
    await expect(removeButton(page)).toHaveCount(0);
    await expect(deleteButton).toHaveCount(0);
    const history = await request.get(endpoint, { headers });
    const persisted: Archive = (await history.json()).archives.find((value: Archive) => value.id === archive.id);
    expect(persisted.archiveDeletedAt).toBe(deleted.archiveDeletedAt);
    expect(persisted.removedAt).toBeNull();
    expect((await request.get(`${archiveUrl}/download`, { headers })).ok()).toBe(false);
    expect((await request.post(`${archiveUrl}/verify`, { headers: { ...headers, "Content-Type": "application/zip" }, data: readFileSync(local) })).ok()).toBe(false);
    expect((await request.post(`${archiveUrl}/remove`, { headers, data: { confirmation: `REMOVE ${archive.id}`, categories: ["inquiries"] } })).ok()).toBe(false);
    for (const source of sources) expect(readFileSync(source.file)).toEqual(source.content);
  } finally {
    release();
    if (local) rmSync(local, { force: true });
    fixture.cleanup();
  }
});

test("REC-007: uncertain and failed partial removal refresh status, preserve choices and lock cleanup for recovery without automatic retries", async ({ page, request }, testInfo) => {
  await signIn(page);
  await openRecords(page);
  const archive = await createArchive(page);
  const local = await downloadArchive(page, archive, testInfo);
  try {
    await verifySaved(page, archive, local);
    const indexResponse = await request.get(endpoint, { headers });
    const index = await indexResponse.json();
    const removeUrl = `${endpoint}/archives/${archive.id}/remove`;
    let removalRequests = 0;
    let statusRequests = 0;
    let state: "unknown" | "failed" | "removing" = "unknown";
    await page.route(removeUrl, (route) => {
      removalRequests++;
      return route.fulfill({ status: 503, json: { detail: "Some selected records may already have been removed. The verified backup is retained and locked for recovery" } });
    });

    await page.route(endpoint, (route) => {
      statusRequests++;
      if (state === "unknown") return route.abort("failed");
      return route.fulfill({ json: {
        ...index,
        archives: index.archives.map((value: Archive) => value.id === archive.id ? {
          ...value, removalState: state,
          removal: state === "failed" ? { inquiries: 1, analyticsRows: 2, websiteLogs: 0, skipped: 3 } : null,
        } : value),
      } });
    });
    await page.getByRole("checkbox", { name: "Saved inquiries", exact: true }).check();
    await confirmInput(page).fill(`REMOVE ${archive.id}`);
    const deletionConfirmation = page.getByRole("textbox", { name: "Server-backup deletion confirmation", exact: true });
    const deleteButton = page.getByRole("button", { name: "Delete server backup ZIP", exact: true });
    await deletionConfirmation.fill(`DELETE BACKUP ${archive.id}`);
    await expect(deleteButton).toBeEnabled();
    await removeButton(page).click();
    await expect(errorNotice(page)).toContainText("Some selected records may already have been removed");
    const recovery = page.getByRole("alert").filter({ hasText: "Recovery review required" });
    await expect(recovery).toContainText("The removal outcome could not be confirmed");
    expect(statusRequests).toBe(1);
    await expect(removeButton(page)).toBeDisabled();
    await expect(deleteButton).toBeDisabled();
    await expect(page.getByRole("checkbox", { name: "Saved inquiries", exact: true })).toBeChecked();
    await expect(confirmInput(page)).toHaveValue(`REMOVE ${archive.id}`);
    await expect(deletionConfirmation).toHaveValue(`DELETE BACKUP ${archive.id}`);
    await expect(page.getByLabel("Saved server backup", { exact: true })).toHaveValue(archive.id);
    await expect(page.getByRole("button", { name: "Download selected backup", exact: true })).toBeEnabled();
    expect(existsSync(path.join(isolatedDirectory(), "records", archive.filename))).toBe(true);
    for (const next of ["failed", "removing"] as const) {
      state = next;
      await page.getByRole("button", { name: "Refresh records", exact: true }).click();
      await expect(recovery).toContainText(next === "failed" ? "A source-removal attempt failed" : "Source removal is in progress");
      if (next === "failed") await expect(recovery).toContainText("1 inquiries, 2 analytics rows, 0 website log files, 0 support conversations removed; 3 skipped");
      await expect(removeButton(page)).toBeDisabled();
      await expect(deleteButton).toBeDisabled();
      await expect(page.getByRole("button", { name: "Download selected backup", exact: true })).toBeEnabled();
    }
    await removeButton(page).evaluate((element: HTMLButtonElement) => element.click());
    await deleteButton.evaluate((element: HTMLButtonElement) => element.click());
    expect(removalRequests).toBe(1);
    expect(statusRequests).toBe(3);
    await page.unroute(removeUrl);
    await page.unroute(endpoint);
  } finally { rmSync(local, { force: true }); }
});

test("REC-008 SUP-009: chat backup cleanup removes only verified closed conversations and preserves active guest access", async ({ page, request }, testInfo) => {
  const create = async () => {
    const response = await request.post(`${api}/api/support/conversations`, { data: {} });
    expect(response.status()).toBe(201);
    return response.json() as Promise<{ conversation: { id: string; revision: number }; token: string }>;
  };
  const closed = await create();
  const active = await create();
  const conversationUrl = `${api}/api/admin/support/conversations/${closed.conversation.id}`;
  const close = await request.post(`${conversationUrl}/action`, {
    headers, data: { action: "close", expectedRevision: closed.conversation.revision },
  });
  expect(close.status()).toBe(200);
  await signIn(page);
  await openRecords(page);
  const archive = await createArchive(page);
  await expect(page.locator("dd").filter({ hasText: "support conversations" })).toBeVisible();
  const local = await downloadArchive(page, archive, testInfo);
  try {
    await verifySaved(page, archive, local);
    await page.getByRole("checkbox", { name: "Closed support conversations", exact: true }).check();
    await confirmInput(page).fill(`REMOVE ${archive.id}`);
    const response = page.waitForResponse((value) => value.url() === `${endpoint}/archives/${archive.id}/remove`);
    await removeButton(page).click();
    expect((await response).status()).toBe(200);
    await expect(page.getByRole("status").filter({ hasText: "This archive cannot request removal again" })).toContainText("support conversations");
    expect((await request.get(conversationUrl, { headers })).status()).toBe(404);
    const stillActive = await request.get(`${api}/api/support/conversations/${active.conversation.id}`, {
      headers: { Authorization: `Bearer ${active.token}` },
    });
    expect(stillActive.status()).toBe(200);
    expect((await stillActive.json()).state).toBe("ai");
  } finally { rmSync(local, { force: true }); }
});
