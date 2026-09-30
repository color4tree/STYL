import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const publicApi = `${api}/api/support`;
const adminApi = `${api}/api/admin/support`;
const adminHeaders = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Guest = { id: string; token: string };
type Conversation = {
  id: string; revision: number; state: "ai" | "waiting_human" | "human" | "closed"; processing: boolean;
  needsHuman: boolean; reason: string | null;
  messages: { id: string; role: string; text: string; references: { url: string; label: string; type: string; id: number }[] }[];
};
type Item = { id: number; name: string; slug: string };
const test = base.extend<{ product: Item }>({
  product: [async ({ request }, run) => {
    const directory = process.env.STYL_E2E_DATA_DIR;
    if (!directory || !path.isAbsolute(directory) || !path.basename(directory).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) throw new Error("Support tests must use isolated STYL_E2E_DATA_DIR, never a local profile.");
    const config = await request.get(`${publicApi}/config`);
    expect(config.status(), await config.text()).toBe(200);
    expect(await config.json()).toMatchObject({ enabled: true, provider: "mock", model: "mock", environment: "test", localTestingOnly: true });
    const before = await request.get(`${adminApi}/config`, { headers: adminHeaders });
    expect(before.status(), await before.text()).toBe(200);
    const previous = await before.json();
    const configured = await request.put(`${adminApi}/config`, { headers: adminHeaders, data: { enabled: true, allowedTopics: ["products", "pricing", "compatibility"], expectedRevision: previous.revision } });
    expect(configured.status(), await configured.text()).toBe(200);
    const created = await request.post(`${api}/api/products`, { headers: adminHeaders, data: {
      name: `Synthetic support rack ${randomUUID().slice(0, 8).replace(/\d/g, (digit) => String.fromCharCode(103 + Number(digit)))}`, category: "Racks", publicationStatus: "published",
      prices: { CAD: 125.50, USD: 100.25 }, shortDescription: "Synthetic evidence-only rack for local support tests.",
      description: "Published fixture rack with a steel frame.", photos: ["/images/pro-elite.svg"],
      compatibility: { models: "Synthetic Model Z", limitations: "Synthetic pairing only" },
    } });
    expect(created.status(), await created.text()).toBe(200);
    const product = (await created.json()).item as Item;
    try { await run(product); }
    finally {
      await request.delete(`${api}/api/products/${product.id}`, { headers: adminHeaders });
      const current = await request.get(`${adminApi}/config`, { headers: adminHeaders });
      if (current.ok()) {
        const saved = await current.json();
        const reset = await request.put(`${adminApi}/config`, { headers: adminHeaders, data: { enabled: previous.enabled, allowedTopics: previous.allowedTopics, expectedRevision: saved.revision } });
        expect(reset.status(), await reset.text()).toBe(200);
      }
    }
  }, { auto: true }],
});

async function start(page: Page): Promise<Guest> {
  await page.goto("/support");
  await expect(page.getByRole("heading", { level: 1, name: "Ask STYL", exact: true })).toBeVisible();
  const created = page.waitForResponse((value) => value.url() === `${publicApi}/conversations` && value.request().method() === "POST");
  await page.getByRole("button", { name: "Start guest conversation", exact: true }).click();
  const response = await created;
  expect(response.status(), await response.text()).toBe(201);
  const value = await response.json();
  await expect(page.getByRole("textbox", { name: "Your message", exact: true })).toBeVisible();
  return { id: value.conversation.id, token: value.token };
}
async function thread(request: APIRequestContext, guest: Guest): Promise<Conversation> {
  const response = await request.get(`${publicApi}/conversations/${guest.id}`, { headers: { Authorization: `Bearer ${guest.token}` } });
  expect(response.status(), await response.text()).toBe(200);
  expect(response.headers()["cache-control"]).toContain("no-store");
  return response.json();
}
async function send(page: Page, guest: Guest, message: string) {
  const input = page.getByRole("textbox", { name: "Your message", exact: true });
  await input.fill(message);
  const response = page.waitForResponse((value) => value.url() === `${publicApi}/conversations/${guest.id}/messages` && value.request().method() === "POST");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  const received = await response;
  expect(received.status(), await received.text()).toBe(200);
  expect(received.request().postData()).not.toContain(guest.token);
  expect(new URL(received.url()).search).toBe("");
  await expect(input).toHaveValue("");
}
async function admin(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Support inbox", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Support inbox", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Customer support inbox", exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Enable automatic AI replies", exact: true })).toBeVisible();
}
async function selectThread(page: Page, guest: Guest) {
  await page.getByRole("button").filter({ hasText: `Guest ${guest.id.slice(0, 8)}` }).click();
  await expect(page.getByRole("log", { name: "Selected support messages" })).toBeVisible();
}
async function confirmAction(page: Page, name: string) {
  const dialog = page.waitForEvent("dialog");
  const click = page.getByRole("button", { name, exact: true }).click();
  await (await dialog).accept();
  await click;
}
const log = (page: Page) => page.getByRole("log", { name: "Conversation messages", exact: true });
const humanLog = (page: Page) => page.getByRole("log", { name: "Selected support messages", exact: true });

test("SUP-001: real mock-backed guest answers cite published products, resume privately and isolate two browser profiles", async ({ page, request, browser, product }) => {
  const guest = await start(page);
  await expect(page.getByRole("complementary", { name: "Local testing notice" })).toContainText("synthetic testing only");
  await expect(page.locator("main")).toContainText("Gemini free-tier");
  await send(page, guest, `What is the listed price of ${product.name}?`);
  await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
  await expect(log(page).getByText("STYL AI", { exact: true })).toBeVisible();
  await expect(log(page)).toContainText(product.name);
  await expect(log(page)).toContainText(/(?:125\.50|100\.25)/);
  await expect(log(page).getByRole("link", { name: product.name, exact: true })).toHaveAttribute("href", `/products/${product.slug}`);
  const persisted = await page.evaluate(() => JSON.parse(localStorage.getItem("styl-support-guest")!));
  expect(persisted).toEqual(guest);
  await expect(page.locator("body")).not.toContainText(guest.token);
  expect(page.url()).not.toContain(guest.id);
  expect(page.url()).not.toContain(guest.token);
  await page.reload();
  await expect(log(page)).toContainText(product.name);
  await expect(page.getByRole("button", { name: "Start guest conversation", exact: true })).toHaveCount(0);
  const secondContext = await browser.newContext({ baseURL: "http://127.0.0.1:3102" });
  try {
    const second = await secondContext.newPage();
    const other = await start(second);
    expect(other.id).not.toBe(guest.id);
    expect(other.token).not.toBe(guest.token);
    await expect(log(second)).not.toContainText(product.name);
    const unauthorized = await request.get(`${publicApi}/conversations/${guest.id}`, { headers: { Authorization: `Bearer ${other.token}` } });
    expect(unauthorized.status()).toBe(404);
    expect((await thread(request, other)).messages).toEqual([]);
    const anonymous = await request.get(`${adminApi}/conversations`);
    expect(anonymous.status()).toBe(401);
  } finally { await secondContext.close(); }
});

test("SUP-002: handoff, protected inbox takeover, human reply, explicit AI resume, close and new guest conversation persist", async ({ page, request, browser, product }) => {
  const guest = await start(page);
  await send(page, guest, `Tell me about ${product.name}.`);
  await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
  await page.getByRole("button", { name: "Ask for human help", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Waiting for human help" })).toBeVisible();
  const operatorContext = await browser.newContext({ baseURL: "http://127.0.0.1:3102" });
  try {
    const operator = await operatorContext.newPage();
    await admin(operator);
    await expect(operator.getByRole("button").filter({ hasText: `Guest ${guest.id.slice(0, 8)}` })).toContainText("Needs human attention");
    await selectThread(operator, guest);
    await operator.getByRole("textbox", { name: "Human reply", exact: true }).fill("Synthetic human reply: I will check the documented pairing.");
    await expect(operator.getByRole("button", { name: "Send human reply", exact: true })).toBeDisabled();
    await operator.getByRole("button", { name: "Take over conversation", exact: true }).click();
    await expect(operator.getByRole("button", { name: "Send human reply", exact: true })).toBeEnabled();
    await operator.getByRole("button", { name: "Send human reply", exact: true }).click();
    await expect(humanLog(operator)).toContainText("Synthetic human reply");
    await page.bringToFront();
    await expect(log(page)).toContainText("Synthetic human reply");
    await expect(page.getByRole("status").filter({ hasText: "Human operator joined" })).toBeVisible();
    expect((await thread(request, guest)).state).toBe("human");
    await operator.bringToFront();
    await confirmAction(operator, "Resume AI");
    await expect.poll(async () => (await thread(request, guest)).state).toBe("ai");
    await page.bringToFront();
    await send(page, guest, `What is the price of ${product.name}?`);
    await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
    await operator.bringToFront();
    await operator.getByRole("button", { name: "Refresh selected conversation", exact: true }).click();
    await expect(operator.getByRole("button", { name: "Close conversation", exact: true })).toBeEnabled();
    await confirmAction(operator, "Close conversation");
    await expect.poll(async () => (await thread(request, guest)).state).toBe("closed");
    await page.bringToFront();
    await expect(page.getByRole("status").filter({ hasText: "Conversation closed" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Your message", exact: true })).toHaveCount(0);
    const next = page.waitForResponse((value) => value.url() === `${publicApi}/conversations` && value.request().method() === "POST");
    await page.getByRole("button", { name: "Start a new guest conversation", exact: true }).click();
    const created = await (await next).json();
    expect(created.conversation.id).not.toBe(guest.id);
    expect((await thread(request, guest)).state).toBe("closed");
    await expect(log(page)).not.toContainText("Synthetic human reply");
  } finally { await operatorContext.close(); }
});

test("SUP-003: admin scope choices persist, excluded pricing goes to a human and disabling AI keeps guest handoff available", async ({ page, request, browser, product }) => {
  await admin(page);
  await page.getByRole("checkbox", { name: "Listed pricing", exact: true }).uncheck();
  await page.getByRole("button", { name: "Save AI scope", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "AI scope settings saved" })).toBeVisible();
  const configuration = await request.get(`${adminApi}/config`, { headers: adminHeaders });
  expect((await configuration.json()).allowedTopics).toEqual(["products", "compatibility"]);
  const customerContext = await browser.newContext({ baseURL: "http://127.0.0.1:3102" });
  try {
    const customer = await customerContext.newPage();
    const guest = await start(customer);
    await send(customer, guest, `What is the price of ${product.name}?`);
    await expect.poll(async () => (await thread(request, guest)).state).toBe("waiting_human");
    expect((await thread(request, guest)).reason).toBe("scope_disabled");
    await expect(customer.getByRole("status").filter({ hasText: "Waiting for human help" })).toBeVisible();
    await page.bringToFront();
    await page.getByRole("checkbox", { name: "Enable automatic AI replies", exact: true }).uncheck();
    await page.getByRole("button", { name: "Save AI scope", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "AI scope settings saved" })).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Support inbox", exact: true }).click();
    await expect(page.getByRole("checkbox", { name: "Enable automatic AI replies", exact: true })).not.toBeChecked();
    await expect(page.getByRole("checkbox", { name: "Listed pricing", exact: true })).not.toBeChecked();
    await customer.bringToFront();
    await customer.reload();
    await expect(customer.getByRole("status").filter({ hasText: "Automatic AI replies are off" })).toBeVisible();
    await expect(customer.getByRole("button", { name: "Ask for human help", exact: true })).toBeEnabled();
    await expect(customer.getByRole("link", { name: "Contact STYL instead", exact: true })).toHaveAttribute("href", "/#contact");
  } finally { await customerContext.close(); }
});

test("SUP-004: guest message failures preserve text and reuse idempotency IDs; Enter, IME and length limits are safe", async ({ page, request, product }) => {
  const guest = await start(page);
  const endpoint = `${publicApi}/conversations/${guest.id}/messages`;
  const bodies: { clientMessageId: string; text: string }[] = [];
  let release = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(endpoint, async (route) => {
    bodies.push(route.request().postDataJSON());
    await gate;
    await route.fulfill({ status: 503, json: { detail: "Synthetic support outage. Retry this message." } });
  });
  const input = page.getByRole("textbox", { name: "Your message", exact: true });
  const question = `Tell me about ${product.name}.`;
  try {
    await input.fill(question);
    await input.dispatchEvent("keydown", { key: "Enter", code: "Enter", isComposing: true, keyCode: 229 });
    expect(bodies).toHaveLength(0);
    await input.press("Shift+Enter");
    await expect(input).toHaveValue(`${question}\n`);
    await input.press("Enter");
    await expect(input).toBeDisabled();
    await expect(page.getByRole("button", { name: "Ask for human help", exact: true })).toBeDisabled();
    await expect.poll(() => bodies.length).toBe(1);
    release();
    await expect(page.getByRole("alert").filter({ hasText: "Synthetic support outage" })).toBeVisible();
    await expect(input).toHaveValue(`${question}\n`);
  } finally { release(); await page.unroute(endpoint); }
  let retryBody: { clientMessageId: string; text: string } | undefined;
  await page.route(endpoint, async (route) => { retryBody = route.request().postDataJSON(); await route.continue(); });
  await input.press("Enter");
  await expect(input).toHaveValue("");
  expect(retryBody).toEqual(bodies[0]);
  await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
  expect((await thread(request, guest)).messages.filter((message) => message.role === "customer" && message.text === question)).toHaveLength(1);
  await page.unroute(endpoint);
  const lostQuestion = `What is the price of ${product.name}?`;
  let lostId: string | undefined;
  await page.route(endpoint, async (route) => {
    lostId = route.request().postDataJSON().clientMessageId;
    const committed = await route.fetch();
    expect(committed.status()).toBe(200);
    await route.abort("failed");
  });
  await input.fill(lostQuestion);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
  await expect(input).toHaveValue(lostQuestion);
  await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
  await page.unroute(endpoint);
  const replay = page.waitForResponse((value) => value.url() === endpoint && value.request().method() === "POST");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  const replayed = await replay;
  expect(replayed.status()).toBe(200);
  expect(replayed.request().postDataJSON().clientMessageId).toBe(lostId);
  await expect(input).toHaveValue("");
  expect((await thread(request, guest)).messages.filter((message) => message.role === "customer" && message.text === lostQuestion)).toHaveLength(1);
  const tooLong = await request.post(endpoint, { headers: { Authorization: `Bearer ${guest.token}` }, data: { clientMessageId: randomUUID(), text: "x".repeat(2001) } });
  expect(tooLong.status()).toBe(422);
  await expect(input).toHaveAttribute("maxlength", "2000");
});

test("SUP-005: support reply and catalog drafts survive navigation; write conflicts, stale reads and auth errors do not erase data", async ({ page, request, browser, product }) => {
  const customerContext = await browser.newContext({ baseURL: "http://127.0.0.1:3102" });
  let release = () => {};
  try {
    const customer = await customerContext.newPage();
    const guest = await start(customer);
    await send(customer, guest, `Tell me about ${product.name}.`);
    await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
    await customer.getByRole("button", { name: "Ask for human help", exact: true }).click();
    await expect(customer.getByRole("status").filter({ hasText: "Waiting for human help" })).toBeVisible();
    await admin(page);
    await page.getByRole("button", { name: "Equipment", exact: true }).click();
    await page.getByRole("button", { name: "New", exact: true }).click();
    await page.getByRole("textbox", { name: "Equipment name", exact: true }).fill("Unsaved support catalog draft");
    await page.getByRole("button", { name: "Support inbox", exact: true }).click();
    await selectThread(page, guest);
    await page.getByRole("button", { name: "Take over conversation", exact: true }).click();
    const reply = page.getByRole("textbox", { name: "Human reply", exact: true });
    await reply.fill("Synthetic retained operator reply");
    await page.getByRole("button", { name: "Backup", exact: true }).click();
    await page.getByRole("button", { name: "Support inbox", exact: true }).click();
    await expect(reply).toHaveValue("Synthetic retained operator reply");
    await page.getByRole("button", { name: "Equipment", exact: true }).click();
    await expect(page.getByRole("textbox", { name: "Equipment name", exact: true })).toHaveValue("Unsaved support catalog draft");
    await page.getByRole("button", { name: "Support inbox", exact: true }).click();
    const endpoint = `${adminApi}/conversations/${guest.id}/messages`;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    let original: Record<string, unknown> | undefined;
    await page.route(endpoint, async (route) => { original = route.request().postDataJSON(); await gate; await route.fulfill({ status: 409, json: { detail: "Synthetic revision conflict." } }); });
    await page.getByRole("button", { name: "Send human reply", exact: true }).click();
    for (const name of ["Support inbox", "Equipment", "Sign out", "Resume AI", "Close conversation"]) await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
    release();
    await expect(page.getByRole("alert").filter({ hasText: "Synthetic revision conflict" })).toBeVisible();
    await expect(reply).toHaveValue("Synthetic retained operator reply");
    await expect(page.getByRole("button", { name: "Send human reply", exact: true })).toBeDisabled();
    await page.unroute(endpoint);
    await page.getByRole("button", { name: "Refresh selected conversation", exact: true }).click();
    await expect(page.getByRole("button", { name: "Send human reply", exact: true })).toBeEnabled();
    const retried = page.waitForResponse((value) => value.url() === endpoint && value.request().method() === "POST");
    await page.getByRole("button", { name: "Send human reply", exact: true }).click();
    const saved = await retried;
    expect(saved.status(), await saved.text()).toBe(200);
    expect(saved.request().postDataJSON().clientMessageId).toBe(original!.clientMessageId);
    await expect(reply).toHaveValue("");
    await page.route(`${adminApi}/conversations`, (route) => route.fulfill({ status: 503, json: { detail: "Synthetic inbox offline." } }));
    await page.getByRole("button", { name: "Refresh support inbox", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Synthetic inbox offline" }).first()).toBeVisible();
    await expect(humanLog(page)).toContainText("Synthetic retained operator reply");
    await expect(page.getByText("No support conversations yet.", { exact: true })).toHaveCount(0);
    await page.unroute(`${adminApi}/conversations`);
    await page.route(`${adminApi}/conversations`, (route) => route.fulfill({ status: 401, json: { detail: "Invalid token" } }));
    await page.getByRole("button", { name: "Refresh support inbox", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Private support content hidden" })).toBeVisible();
    await expect(humanLog(page)).toHaveCount(0);
    await expect(page.locator("main")).not.toContainText("Synthetic retained operator reply");
    await page.unroute(`${adminApi}/conversations`);
    await page.getByRole("button", { name: "Refresh support inbox", exact: true }).click();
    await expect(humanLog(page)).toContainText("Synthetic retained operator reply");
    await page.getByRole("button", { name: "Equipment", exact: true }).click();
    await page.getByRole("textbox", { name: "Equipment name", exact: true }).fill("");
  } finally { release(); await customerContext.close(); }
});

test("SUP-006: storage failure is explicit; simulated provider failure and unsafe reference URLs render safely with human help", async ({ page, request, product }) => {
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key === "styl-support-guest") throw new DOMException("Synthetic storage denial", "QuotaExceededError");
      return original.call(this, key, value);
    };
  });
  const guest = await start(page);
  await expect(page.getByRole("alert").filter({ hasText: "guest access could not be saved" })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("styl-support-guest"))).toBeNull();
  const current = await thread(request, guest);
  const unsafeText = '<img src=x onerror="alert(1)"> **not raw HTML**';
  let moreHistory = false;
  await page.route(`${publicApi}/conversations/${guest.id}`, (route) => route.fulfill({ json: {
    ...current, revision: current.revision + (moreHistory ? 2 : 1), state: "waiting_human", needsHuman: true, reason: "provider_unavailable",
    messages: [{
      id: "synthetic-provider-failure", role: "assistant", createdAt: new Date().toISOString(), text: `Synthetic provider unavailable. ${unsafeText}\n${"Older synthetic history.\n".repeat(70)}`,
      references: [
        { type: "product", id: product.id, label: "Unsafe script", url: "javascript:alert(1)" },
        { type: "product", id: product.id, label: "External target", url: "https://example.com/private" },
        { type: "product", id: product.id, label: "Protocol-relative target", url: "//example.com/private" },
        { type: "product", id: product.id, label: product.name, url: `/products/${product.slug}` },
      ],
    }, ...(moreHistory ? [{ id: "synthetic-new-message", role: "system", createdAt: new Date().toISOString(), text: "New synthetic status message.", references: [] }] : [])],
  } }));
  await page.getByRole("button", { name: "Refresh conversation", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Waiting for human help" })).toBeVisible();
  await expect(log(page)).toContainText(unsafeText);
  await expect(log(page).locator("img")).toHaveCount(0);
  await expect(log(page).getByRole("link")).toHaveCount(1);
  await expect(log(page).getByRole("link")).toHaveAttribute("href", `/products/${product.slug}`);
  await expect(page.getByRole("button", { name: "Ask for human help", exact: true })).toBeEnabled();
  await expect(page.getByRole("link", { name: "Contact STYL instead", exact: true })).toBeVisible();
  await log(page).evaluate((element) => { element.scrollTop = 0; element.dispatchEvent(new Event("scroll")); });
  moreHistory = true;
  await page.getByRole("button", { name: "Refresh conversation", exact: true }).click();
  await expect(log(page)).toContainText("New synthetic status message.");
  expect(await log(page).evaluate((element) => element.scrollTop)).toBe(0);
  await expect(page.getByRole("button", { name: "Jump to latest messages", exact: true })).toBeVisible();
});

test("SUP-007: unobtrusive Ask STYL navigation and 320/390 layouts preserve catalog actions; disabled chat leaves commerce available", async ({ page, request }, testInfo) => {
  for (const width of testInfo.project.name.startsWith("phone") ? [320, 390] : [1024, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const footer = page.getByRole("contentinfo");
    await expect(footer.getByRole("link", { name: "Ask STYL", exact: true })).toHaveAttribute("href", "/support");
    const catalog = page.getByRole("navigation", { name: width < 1024 ? "Catalog navigation" : "Main navigation", exact: true });
    for (const name of ["All products", "Equipment", "Accessories"]) await expect(catalog.getByRole("link", { name, exact: true })).toBeVisible();
    if (width < 1024) {
      await expect(catalog.getByRole("link")).toHaveCount(3);
      await expect(page.getByRole("dialog", { name: "Site navigation" })).not.toBeVisible();
      await page.getByRole("button", { name: "Menu", exact: true }).click();
      await page.getByRole("navigation", { name: "Mobile navigation", exact: true }).getByRole("link", { name: "Ask STYL", exact: true }).click();
      await expect(page.getByRole("dialog", { name: "Site navigation" })).not.toBeVisible();
    } else await page.getByRole("navigation", { name: "Main navigation", exact: true }).getByRole("link", { name: "Ask STYL", exact: true }).click();
    await expect(page).toHaveURL(/\/support$/);
    await expect(page.getByRole("button", { name: "Start guest conversation", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const control = await page.getByRole("button", { name: "Start guest conversation", exact: true }).boundingBox();
    expect(control!.height).toBeGreaterThanOrEqual(44);
    expect(control!.x).toBeGreaterThanOrEqual(0);
    expect(control!.x + control!.width).toBeLessThanOrEqual(width);
    const elements = await page.locator("header").getByRole("link").filter({ visible: true }).evaluateAll((links) => links.map((link) => {
      const box = link.getBoundingClientRect(); return { x: box.x, y: box.y, right: box.right, bottom: box.bottom };
    }));
    for (let i = 0; i < elements.length; i++) for (let j = i + 1; j < elements.length; j++) {
      const a = elements[i], b = elements[j];
      expect(a.right <= b.x || b.right <= a.x || a.bottom <= b.y || b.bottom <= a.y).toBe(true);
    }
  }
  const configuration = await request.get(`${publicApi}/config`);
  const value = await configuration.json();
  await page.route(`${publicApi}/config`, (route) => route.fulfill({ json: { ...value, enabled: false, aiEnabled: false } }));
  await page.reload();
  await expect(page.getByRole("heading", { name: "Support chat is unavailable", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start guest conversation", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Continue shopping", exact: true }).click();
  await expect(page.getByRole("link", { name: "Cart (0)", exact: true })).toBeVisible();
});

test("SUP-008: guest polling pauses while hidden, stops on close/unmount, and missing evidence is highlighted for human review", async ({ page, request }) => {
  const guest = await start(page);
  await send(page, guest, "Does the fictitious quuxwobble-991 connect with the nonexistent xyzzy-447?");
  await expect.poll(async () => (await thread(request, guest)).state).toBe("waiting_human");
  await expect(page.getByRole("status").filter({ hasText: "Waiting for human help" })).toBeVisible();
  expect((await thread(request, guest)).needsHuman).toBe(true);
  await page.clock.install();
  let polls = 0;
  await page.route(`${publicApi}/conversations/${guest.id}`, async (route) => { polls++; await route.continue(); });
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  const hiddenCount = polls;
  await page.clock.fastForward(6500);
  expect(polls).toBe(hiddenCount);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => polls).toBeGreaterThan(hiddenCount);
  const current = await thread(request, guest);
  const closed = await request.post(`${adminApi}/conversations/${guest.id}/action`, { headers: adminHeaders, data: { action: "close", expectedRevision: current.revision } });
  expect(closed.status(), await closed.text()).toBe(200);
  await page.clock.runFor(2100);
  await expect(page.getByRole("status").filter({ hasText: "Conversation closed" })).toBeVisible();
  const closedCount = polls;
  await page.clock.fastForward(6500);
  expect(polls).toBe(closedCount);
  await page.clock.resume();
  await page.getByRole("link", { name: "Continue shopping", exact: true }).click();
  await expect(page).toHaveURL("http://127.0.0.1:3102/");
  await page.clock.fastForward(6500);
  expect(polls).toBe(closedCount);
});
