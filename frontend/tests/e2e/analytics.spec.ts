import { test, expect, type Page, type APIRequestContext } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import type { AnalyticsEvent, AnalyticsReport } from "../../src/lib/analyticsTypes";

const api = "http://127.0.0.1:8102";
const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
const legacyKeys = ["styl-analytics-consent", "styl-analytics-session", "styl-analytics-visitor", "styl-analytics-lease"];
test.setTimeout(90_000);

test.beforeEach(async ({ page }) => {
  const directory = process.env.STYL_E2E_DATA_DIR;
  if (!directory || !path.basename(directory).startsWith("styl-e2e-")) throw new Error("Analytics tests require isolated data.");
  const userAgent = await page.evaluate(() => navigator.userAgent.replace("HeadlessChrome", "Chrome"));
  await page.context().setExtraHTTPHeaders({ "User-Agent": userAgent });
});

function reportDate() {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "America/Los_Angeles", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const part = (name: string) => parts.find(value => value.type === name)!.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}
async function report(request: APIRequestContext): Promise<AnalyticsReport> {
  const day = reportDate();
  const result = await request.get(`${api}/api/admin/analytics/report?start=${day}&end=${day}`, { headers });
  expect(result.status(), await result.text()).toBe(200);
  return result.json();
}
async function flush(page: Page) {
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
}
async function admin(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Analytics", exact: true })).toBeEnabled();
}
async function noAgreement(page: Page) {
  await expect(page.getByTestId("analytics-consent-panel")).toHaveCount(0);
  await expect(page.getByTestId("analytics-collection-status")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Accept analytics|Decline analytics|Analytics preferences/ })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Privacy", exact: true })).toBeVisible();
}
async function createProduct(request: APIRequestContext) {
  const name = `Analytics fixture ${randomUUID().slice(0, 8)}`;
  const response = await request.post(`${api}/api/products`, { headers, data: {
    name, category: "Racks", prices: { CAD: 79.25, USD: 61.50 }, publicationStatus: "published",
    shortDescription: "Analytics visibility fixture.", description: "Full public details for analytics. ".repeat(70),
    photos: ["/images/pro-elite.svg"],
  } });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()).item;
}

test("AN-001 AN-007: normal visits count automatically without agreements, browser IDs or query/referrer leakage", async ({ page, request }) => {
  const bodies: Record<string, unknown>[] = [];
  const requestHeaders: Record<string, string>[] = [];
  const sessions: string[] = [];
  page.on("request", value => {
    if (value.url().endsWith("/api/analytics/events")) { bodies.push(value.postDataJSON()); requestHeaders.push(value.headers()); }
    if (value.url().endsWith("/api/analytics/session")) sessions.push(value.method());
  });
  const before = await report(request);
  await page.goto("/?utm_source=google&utm_medium=cpc&utm_campaign=launch&email=PRIVATE_QUERY_MARKER");
  await noAgreement(page);
  await expect.poll(async () => (await report(request)).summary.pageViews).toBeGreaterThan(before.summary.pageViews);
  expect(bodies.length).toBeGreaterThan(0);
  for (const body of bodies) {
    expect(Object.keys(body).sort()).toEqual(["context", "events"]);
    for (const event of body.events as AnalyticsEvent[]) {
      expect(Object.keys(event).sort()).toEqual(["name", "path", "properties"]);
      expect(event).not.toHaveProperty("id");
      expect(event).not.toHaveProperty("occurredAt");
    }
  }
  expect(JSON.stringify(bodies)).not.toContain("PRIVATE_QUERY_MARKER");
  expect(requestHeaders.every(value => !value.cookie && !value.referer)).toBe(true);
  expect(sessions).toEqual([]);
  expect(await page.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith("styl-analytics")))).toEqual([]);
  expect((await page.context().cookies()).filter(cookie => cookie.name.startsWith("styl-analytics"))).toEqual([]);
  const after = await report(request);
  expect(after.coverage.mode).toBe("aggregate-only");
  expect(after.summary).not.toHaveProperty("sessions");
  expect(after.summary).not.toHaveProperty("visitors");
  expect(after).not.toHaveProperty("funnel");
  expect(after).not.toHaveProperty("paths");
});

test("AN-002 AN-003 AN-006: item/media/cart counts and saved inquiry totals stay independent", async ({ page, request }) => {
  const item = await createProduct(request);
  const bodies: string[] = [];
  page.on("request", value => { if (value.url().endsWith("/api/analytics/events")) bodies.push(value.postData() ?? ""); });
  try {
    await page.goto("/");
    await noAgreement(page);
    await page.bringToFront();
    const card = page.locator("#products article").filter({ hasText: item.name });
    await card.locator(":scope > h3").scrollIntoViewIfNeeded();
    await card.locator(":scope > h3").hover();
    await expect.poll(async () => {
      await flush(page);
      return (await report(request)).items.find(row => row.itemType === "product" && row.itemId === item.id)?.impressions ?? 0;
    }, { timeout: 20000, intervals: [1000] }).toBeGreaterThan(0);
    const more = card.getByRole("button", { name: "Show more", exact: true });
    if (await more.isVisible()) await more.click();
    await card.getByRole("link", { name: "Details", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: item.name, exact: true })).toBeVisible();
    await noAgreement(page);
    await page.getByRole("button", { name: `Enlarge ${item.name} media 1`, exact: true }).click();
    await page.getByRole("button", { name: "Close enlarged media", exact: true }).click();
    await page.locator("main").getByRole("button", { name: "Add to cart", exact: true }).first().click();
    await page.getByRole("link", { name: "Cart (1)", exact: true }).click();
    await page.waitForURL("**/cart");
    await noAgreement(page);
    await page.locator("main").getByRole("link", { name: "Request a quote", exact: true }).first().click();
    await page.waitForURL(/#contact$/);
    const marker = `PRIVATE_FORM_${randomUUID()}`;
    await page.getByRole("textbox", { name: "Name", exact: true }).fill(marker);
    await page.getByRole("textbox", { name: "Email", exact: true }).fill("private-analytics-fixture@example.com");
    await page.getByRole("textbox", { name: "Message", exact: true }).fill(`${marker} customer message`);
    const before = await report(request);
    const receipt = page.waitForResponse(response => response.url().endsWith("/api/inquiries") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Submit inquiry", exact: true }).click();
    const saved = await receipt;
    expect(saved.status(), await saved.text()).toBe(200);
    expect(saved.request().postDataJSON()).not.toHaveProperty("analytics");
    await expect(page.getByRole("status").filter({ hasText: "Inquiry received" })).toBeVisible();
    await expect.poll(async () => {
      await flush(page);
      const row = (await report(request)).items.find(value => value.itemType === "product" && value.itemId === item.id);
      return Boolean(row && row.detailViews > 0 && row.cartAdds > 0 && row.mediaOpens > 0);
    }, { timeout: 20000, intervals: [1000] }).toBe(true);
    const after = await report(request);
    expect(after.summary.savedInquiries).toBe((before.summary.savedInquiries ?? 0) + 1);
    expect(after.summary).not.toHaveProperty("attributedInquiries");
    expect(bodies.join("")).not.toContain(marker);
    expect(bodies.join("")).not.toContain("private-analytics-fixture@example.com");
    expect(bodies.join("")).not.toContain("sessionToken");
    const database = path.join(process.env.STYL_E2E_DATA_DIR!, "analytics.sqlite3");
    for (const file of [database, `${database}-wal`]) if (existsSync(file)) {
      expect(readFileSync(file).includes(Buffer.from(marker))).toBe(false);
    }
  } finally {
    await request.delete(`${api}/api/products/${item.id}`, { headers });
  }
});

test("AN-007: standard Privacy link offers opt-out without interrupting storefront or resetting shopping", async ({ page, request }) => {
  await page.goto("/accessories");
  await noAgreement(page);
  const before = await report(request);
  await page.getByRole("link", { name: "Privacy", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Privacy", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Turn off usage measurement", exact: true }).click();
  await expect(page.getByText("Optional usage measurement is turned off for this browser.", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("styl-analytics-exclude"))).toBe("true");
  const events: string[] = [];
  page.on("request", value => { if (value.url().endsWith("/api/analytics/events")) events.push(value.url()); });
  await page.getByRole("link", { name: "Back to STYL", exact: true }).click();
  await noAgreement(page);
  await flush(page);
  expect(events).toEqual([]);
  expect((await report(request)).summary.pageViews).toBeGreaterThanOrEqual(before.summary.pageViews);
  expect(await page.evaluate(keys => keys.map(key => localStorage.getItem(key)), legacyKeys)).toEqual([null, null, null, null]);
  await page.goto("/privacy");
  await page.getByRole("button", { name: "Allow aggregate measurement", exact: true }).click();
  await page.getByRole("link", { name: "Back to STYL", exact: true }).click();
  await expect.poll(() => events.length).toBeGreaterThan(0);
});

test("AN-007 AN-008: legacy decline is respected and old browser/session identifiers are retired", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("styl-analytics-consent", JSON.stringify({ choice: "declined" }));
    for (const key of ["styl-analytics-session", "styl-analytics-visitor", "styl-analytics-lease"]) localStorage.setItem(key, '{"id":"PRIVATE_OLD_IDENTIFIER"}');
  });
  const posts: string[] = [];
  page.on("request", value => { if (/\/api\/analytics\/(events|session)$/.test(value.url())) posts.push(value.postData() ?? ""); });
  await page.goto("/");
  await noAgreement(page);
  await expect.poll(() => page.evaluate(() => localStorage.getItem("styl-analytics-exclude"))).toBe("true");
  expect(await page.evaluate(keys => keys.map(key => localStorage.getItem(key)), legacyKeys)).toEqual([null, null, null, null]);
  await flush(page);
  expect(posts).toEqual([]);
});

test("AN-008: GPC is honored with no agreement UI or behavioral collection", async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(navigator, "globalPrivacyControl", { get: () => true }));
  const events: string[] = [];
  page.on("request", value => { if (value.url().endsWith("/api/analytics/events")) events.push(value.url()); });
  await page.goto("/");
  await noAgreement(page);
  await flush(page);
  expect(events).toEqual([]);
});

test("AN-008 AN-009: same-tab admin exclusion and telemetry outage do not interfere with shopping", async ({ page }) => {
  await admin(page);
  const requests: string[] = [];
  page.on("request", value => { if (value.url().endsWith("/api/analytics/events")) requests.push(value.url()); });
  await page.goto("/");
  await noAgreement(page);
  await flush(page);
  expect(requests).toEqual([]);
  await page.evaluate(() => sessionStorage.removeItem("styl-admin-token"));
  await page.reload();
  await page.route("**/api/analytics/events", route => route.fulfill({ status: 503, json: { detail: "Synthetic analytics outage" } }));
  await page.locator("#products article").first().getByRole("button", { name: "Add to cart", exact: true }).click();
  await flush(page);
  await expect(page.getByRole("link", { name: "Cart (1)", exact: true })).toBeVisible();
  await noAgreement(page);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("styl-cart") ?? "[]").length)).toBe(1);
});

test("AN-010 AN-011 AN-013: aggregate dashboard/CSV/email preserve unsaved editor and show unavailable metrics honestly", async ({ page, request }) => {
  expect((await request.get(`${api}/api/admin/analytics/report?start=${reportDate()}&end=${reportDate()}`)).status()).toBe(401);
  await admin(page);
  await page.getByRole("button", { name: "New", exact: true }).click();
  const name = page.getByRole("textbox", { name: "Product name", exact: true });
  await name.fill("Unsaved analytics fixture");
  await page.getByRole("button", { name: "Analytics", exact: true }).click();
  await expect(page.getByTestId("analytics-page-view-count")).toBeVisible();
  await expect(page.getByTestId("analytics-unavailable-metrics")).toContainText("Not measured");
  await expect(page.getByText("Tracked sessions", { exact: true })).toHaveCount(0);
  await page.getByLabel("Email report date", { exact: true }).fill(reportDate());
  await page.getByRole("button", { name: "Preview daily email", exact: true }).click();
  const preview = page.getByLabel("Daily email preview", { exact: true });
  await expect(preview).toContainText("STYL daily usage");
  await expect(preview).not.toContainText("Tracked sessions:");
  await expect(preview).not.toContainText("opted-in");
  await expect(page.getByText(/Real email: disabled/)).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download aggregate CSV", exact: true }).click();
  const file = await downloaded;
  expect(await file.failure()).toBeNull();
  expect(readFileSync((await file.path())!, "utf8")).not.toContain("convertedSessions");
  await file.delete();
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  await page.getByRole("button", { name: "Products", exact: true }).click();
  await expect(name).toHaveValue("Unsaved analytics fixture");
});

test("AN-009: unavailable or invalid aggregate report never becomes successful zero data", async ({ page }) => {
  await admin(page);
  await page.route("**/api/admin/analytics/report?*", route => route.fulfill({ status: 503, json: { detail: "Analytics storage unavailable" } }));
  await page.getByRole("button", { name: "Analytics", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Analytics storage unavailable");
  await expect(page.getByTestId("analytics-page-view-count")).toHaveCount(0);
  await page.unroute("**/api/admin/analytics/report?*");
  for (const invalid of [{ generatedAt: "invalid-date" }, { timezone: "invalid-zone" }, { coverage: { mode: "raw" } }]) {
    await page.route("**/api/admin/analytics/report?*", async route => {
      const response = await route.fetch();
      const value: AnalyticsReport = await response.json();
      await route.fulfill({ response, json: { ...value, ...invalid, coverage: { ...value.coverage, ...invalid.coverage } } });
    });
    await page.getByRole("button", { name: "Refresh analytics", exact: true }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText("analytics response is invalid");
    await expect(page.getByTestId("analytics-page-view-count")).toHaveCount(0);
    await page.unroute("**/api/admin/analytics/report?*");
  }
  await page.route("**/api/admin/analytics/report?*", async route => {
    const response = await route.fetch();
    const value: AnalyticsReport = await response.json();
    await route.fulfill({ response, json: {
      ...value, summary: { ...value.summary, savedInquiries: null },
      daily: [{ date: reportDate(), pageViews: 1, activeSeconds: 0, inquiries: 0 }],
      coverage: { ...value.coverage, warnings: ["Saved-inquiry reconciliation is unavailable; receipt totals are not confirmed."] },
    } });
  });
  await page.getByRole("button", { name: "Refresh analytics", exact: true }).click();
  await expect(page.getByText(/N\/A inquiries/)).toBeVisible();
  await expect(page.getByText(/receipt totals are not confirmed/)).toBeVisible();
});

test("AN-001 AN-010: normal timed item batch reaches report; zero-state never instructs customers to accept an agreement", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.locator("#products article").first()).toBeVisible();
  const delivered = page.waitForResponse(response => response.url().endsWith("/api/analytics/events") && response.request().method() === "POST" && response.request().postDataJSON().events.some((event: AnalyticsEvent) => event.name === "cart_add"), { timeout: 25000 });
  await page.locator("#products article").first().getByRole("button", { name: "Add to cart", exact: true }).click();
  expect((await delivered).status()).toBe(200);
  expect((await report(request)).actions.some(row => row.name === "cart_add" && row.count > 0)).toBe(true);
  await admin(page);
  await page.getByRole("button", { name: "Analytics", exact: true }).click();
  await page.getByLabel("Analytics start date", { exact: true }).fill("2020-01-01");
  await page.getByLabel("Analytics end date", { exact: true }).fill("2020-01-01");
  await page.getByRole("button", { name: "Apply dates", exact: true }).click();
  const guidance = page.getByTestId("analytics-empty-guidance");
  await expect(guidance).toContainText("No measured page views");
  await expect(guidance).toContainText("starts automatically");
  await expect(guidance).not.toContainText("Accept analytics");
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  await page.route("**/api/admin/analytics/report?*", async route => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...await response.json(), collectionEnabled: false } });
  });
  await page.getByRole("button", { name: "Refresh analytics", exact: true }).click();
  await expect(guidance).toContainText("Server collection is disabled");
});
