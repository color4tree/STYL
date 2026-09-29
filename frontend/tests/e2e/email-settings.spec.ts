import { test, expect, type Page, type APIRequestContext } from "@playwright/test";
import path from "node:path";
import type { AnalyticsEmailSettings } from "../../src/lib/analyticsTypes";

const api = "http://127.0.0.1:8102";
const endpoint = `${api}/api/admin/analytics/email-settings`;
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };

async function settings(request: APIRequestContext): Promise<AnalyticsEmailSettings> {
  const response = await request.get(endpoint, { headers });
  expect(response.status()).toBe(200);
  return response.json();
}

async function reset(request: APIRequestContext) {
  const current = await settings(request);
  const response = await request.put(endpoint, { headers, data: {
    enabled: false, recipients: [], expectedRevision: current.revision,
  } });
  expect(response.status()).toBe(200);
}

async function openSettings(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Analytics", exact: true }).click();
  return page.getByTestId("daily-email-settings");
}

test.beforeEach(async ({ request }) => {
  const directory = process.env.STYL_E2E_DATA_DIR;
  if (!directory || !path.basename(directory).startsWith("styl-e2e-")) throw new Error("Email settings tests require isolated data.");
  await reset(request);
});
test.afterEach(async ({ request }) => { await reset(request); });

test("AN-017: email on/off and recipients persist, normalize duplicates and never enable real test mail", async ({ page, request }) => {
  expect((await request.get(endpoint)).status()).toBe(401);
  expect((await request.put(endpoint, { data: { enabled: true, recipients: ["owner@example.com"], expectedRevision: 0 } })).status()).toBe(401);
  const panel = await openSettings(page);
  const toggle = panel.getByRole("checkbox", { name: "Enable daily summary emails", exact: true });
  const recipients = panel.getByLabel("Daily email recipients", { exact: true });
  await expect(toggle).not.toBeChecked();
  await recipients.fill("owner@example.com,\nOwner@EXAMPLE.COM\nsales@example.com");
  await toggle.check();
  const saved = page.waitForResponse(response => response.url() === endpoint && response.request().method() === "PUT");
  await panel.getByRole("button", { name: "Save email settings", exact: true }).click();
  expect((await saved).status()).toBe(200);
  await expect(panel.getByRole("status")).toContainText("Daily email settings saved");
  await expect(recipients).toHaveValue("owner@example.com\nsales@example.com");
  await expect(panel.getByTestId("daily-email-effective-state")).toContainText("real emails are never sent");
  expect(await settings(request)).toMatchObject({ enabled: true, effectiveEnabled: false, environment: "test", recipients: ["owner@example.com", "sales@example.com"] });
  await page.getByRole("button", { name: "Preview daily email", exact: true }).click();
  await expect(page.getByLabel("Daily email preview", { exact: true })).toBeVisible();
  await expect(page.getByText(/Real email: disabled/)).toBeVisible();
  await toggle.uncheck();
  await recipients.fill("");
  await panel.getByRole("button", { name: "Save email settings", exact: true }).click();
  await expect(panel.getByRole("status")).toContainText("Daily email settings saved");
  await expect(page.getByLabel("Daily email preview", { exact: true })).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "Analytics", exact: true }).click();
  await expect(toggle).not.toBeChecked();
  await expect(recipients).toHaveValue("");
  expect(await settings(request)).toMatchObject({ enabled: false, recipients: [], effectiveEnabled: false });
});

test("AN-017: validation keeps edits and prevents enabled mail without recipients", async ({ page, request }) => {
  const panel = await openSettings(page);
  const toggle = panel.getByRole("checkbox", { name: "Enable daily summary emails", exact: true });
  const recipients = panel.getByLabel("Daily email recipients", { exact: true });
  await toggle.check();
  await panel.getByRole("button", { name: "Save email settings", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("at least one recipient");
  await recipients.fill("not-an-email");
  await panel.getByRole("button", { name: "Save email settings", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("valid recipient email");
  await expect(recipients).toHaveValue("not-an-email");
  await expect(toggle).toBeChecked();
  await recipients.fill(Array.from({ length: 21 }, (_, index) => `owner${index}@example.com`).join("\n"));
  await panel.getByRole("button", { name: "Save email settings", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("at most 20");
  expect(await settings(request)).toMatchObject({ enabled: false, recipients: [] });
});

test("AN-017: unsaved recipients survive tab changes; a stale save requires an explicit reload", async ({ page, request }) => {
  const panel = await openSettings(page);
  const recipients = panel.getByLabel("Daily email recipients", { exact: true });
  await recipients.fill("my-edit@example.com");
  await page.getByRole("button", { name: "Equipment", exact: true }).click();
  await page.getByRole("button", { name: "Analytics", exact: true }).click();
  await expect(recipients).toHaveValue("my-edit@example.com");
  const current = await settings(request);
  const other = await request.put(endpoint, { headers, data: {
    enabled: false, recipients: ["other-admin@example.com"], expectedRevision: current.revision,
  } });
  expect(other.status()).toBe(200);
  await panel.getByRole("button", { name: "Save email settings", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("changed in another session");
  await expect(recipients).toHaveValue("my-edit@example.com");
  expect((await settings(request)).recipients).toEqual(["other-admin@example.com"]);
  page.once("dialog", dialog => dialog.accept());
  await panel.getByRole("button", { name: "Discard changes and reload", exact: true }).click();
  await expect(recipients).toHaveValue("other-admin@example.com");
  await expect(panel.getByText("Unsaved changes", { exact: true })).toHaveCount(0);
});

test("AN-017: pending and failed saves retain fields, block repeat submits and allow recovery", async ({ page }) => {
  const panel = await openSettings(page);
  const recipients = panel.getByLabel("Daily email recipients", { exact: true });
  await recipients.fill("owner@example.com");
  let release!: () => void;
  let requests = 0;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/admin/analytics/email-settings", async route => {
    if (route.request().method() !== "PUT") return route.continue();
    requests++;
    await waiting;
    await route.fulfill({ status: 503, json: { detail: "Settings storage unavailable. Please retry." } });
  });
  await panel.getByRole("button", { name: "Save email settings", exact: true }).click();
  try {
    await expect.poll(() => requests).toBe(1);
    await expect(panel.getByRole("button", { name: "Saving settings...", exact: true })).toBeDisabled();
    await expect(recipients).toBeDisabled();
  } finally { release(); }
  await expect(panel.getByRole("alert")).toContainText("Settings storage unavailable");
  await expect(recipients).toHaveValue("owner@example.com");
  await expect(panel.getByRole("button", { name: "Save email settings", exact: true })).toBeEnabled();
  await page.unroute("**/api/admin/analytics/email-settings");
  await panel.getByRole("button", { name: "Save email settings", exact: true }).click();
  await expect(panel.getByRole("status")).toContainText("Daily email settings saved");
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
});

test("AN-017: unavailable settings are not shown as disabled defaults and do not hide the report", async ({ page }) => {
  await page.route("**/api/admin/analytics/email-settings", route => route.fulfill({ status: 503, json: { detail: "Email settings are unavailable" } }));
  const panel = await openSettings(page);
  await expect(panel.getByRole("alert")).toContainText("Email settings are unavailable");
  await expect(panel.getByRole("checkbox")).toHaveCount(0);
  await expect(page.getByTestId("analytics-page-view-count")).toBeVisible();
  await page.unroute("**/api/admin/analytics/email-settings");
  await panel.getByRole("button", { name: "Reload email settings", exact: true }).click();
  await expect(panel.getByRole("checkbox", { name: "Enable daily summary emails", exact: true })).toBeEnabled();
});
