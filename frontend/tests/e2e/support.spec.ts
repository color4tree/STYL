import { test as base, expect, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const publicApi = `${api}/api/support`;
const adminApi = `${api}/api/admin/support`;
const adminHeaders = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Guest = { id: string; token: string };
type Conversation = {
  id: string; revision: number; state: "ai" | "waiting_human" | "human" | "closed"; processing: boolean;
  needsHuman: boolean; needsHumanQuestions: number; reason: string | null;
  messages: { id: string; role: string; text: string; needsHuman: boolean; humanReason: string | null; answeredBy: string | null; replyTo: { id: string; text: string } | null; references: { url: string; label: string; type: string; id: number }[] }[];
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
  await expect(page.getByRole("dialog", { name: "STYL Assistant", exact: true })).toBeVisible();
  const created = page.waitForResponse((value) => value.url() === `${publicApi}/conversations` && value.request().method() === "POST");
  await page.getByRole("button", { name: "Start conversation", exact: true }).click();
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
  await expect(page.getByRole("button", { name: "Customer support", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Customer support", exact: true }).click();
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
const customerDialog = (page: Page) => page.getByRole("dialog", { name: "STYL Assistant", exact: true });
async function closedProductSource(page: Page, bubble: Locator, product: Item) {
  const sources = bubble.locator("details").filter({ has: page.locator("summary", { hasText: /^Sources$/ }) });
  await expect(sources.locator("summary")).toBeVisible();
  await expect(sources).not.toHaveAttribute("open");
  const link = sources.getByRole("link", { name: product.name, exact: true, includeHidden: true });
  await expect(link).toHaveAttribute("href", `/products/${product.slug}`);
  await expect(link).toBeHidden();
  return sources;
}
async function expectProfessionalCopy(page: Page) {
  const ordinaryText = await customerDialog(page).evaluate((element) => {
    const copy = element.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("details").forEach((details) => details.remove());
    return copy.textContent;
  });
  expect(ordinaryText).not.toMatch(/provider|Gemini|model|environment|scope_disabled|customer_request|missing_evidence|STYL_SUPPORT_|HTTP\s*\d|AI replies are paused|AI paused|Guest chat|AI \/ human|Reason:/i);
}

test("SUP-001: real mock-backed guest answers cite published products, resume privately and isolate two browser profiles", async ({ page, request, browser, product }) => {
  const guest = await start(page);
  await expect(customerDialog(page).getByRole("link", { name: "Privacy", exact: true })).toHaveAttribute("href", "/privacy");
  await expect(customerDialog(page)).not.toContainText(/Local preview|do not share personal information/i);
  await expect(customerDialog(page).getByRole("button", { name: /Ask for human help|Refresh conversation/ })).toHaveCount(0);
  await expectProfessionalCopy(page);
  await send(page, guest, `What is the listed price of ${product.name}?`);
  await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
  await expect(log(page).getByText("STYL Assistant", { exact: true })).toBeVisible();
  await expect(log(page)).toContainText(product.name);
  await expect(log(page)).toContainText(/(?:125\.50|100\.25)/);
  const answer = log(page).locator('[data-support-role="assistant"]').last();
  await closedProductSource(page, answer, product);
  expect((await answer.innerText()).split(product.name)).toHaveLength(2);
  expect((await thread(request, guest)).messages.at(-1)?.references).toContainEqual({
    type: "product", id: product.id, label: product.name, url: `/products/${product.slug}`,
  });
  const persisted = await page.evaluate(() => JSON.parse(localStorage.getItem("styl-support-guest")!));
  expect(persisted).toEqual(guest);
  await expect(page.locator("body")).not.toContainText(guest.token);
  expect(page.url()).not.toContain(guest.id);
  expect(page.url()).not.toContain(guest.token);
  await page.reload();
  await expect(log(page)).toContainText(product.name);
  await expect(page.getByRole("button", { name: "Start conversation", exact: true })).toHaveCount(0);
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

test("SUP-027 CAT-009: legacy assistant prose is displayed unchanged for customers and admins without rewriting saved messages", async ({ page, request, product }) => {
  const guest = await start(page);
  await send(page, guest, `What is the price of ${product.name}?`);
  await expect.poll(async () => (await thread(request, guest)).messages.filter((message) => message.role === "assistant").length).toBe(1);
  const stored = await thread(request, guest);
  const legacyText = `Here's the published information for ${product.name}:\nPrice: CAD $125.50\nCompatible hole diameter: 1"`;
  const legacy = { ...stored.messages.find((message) => message.role === "assistant")!, text: legacyText };
  const displayed = {
    ...stored, revision: stored.revision + 1,
    messages: stored.messages.map((message) => message.id === legacy.id ? legacy : message),
  };
  const legacySnapshot = structuredClone(displayed);
  const customerUrl = `${publicApi}/conversations/${guest.id}`;
  const operator = await page.context().newPage();
  const operatorUrl = `${adminApi}/conversations/${guest.id}`;
  // Hydrate historical assistant text, without writing old prose into the current API.
  await page.route(customerUrl, (route) => route.fulfill({ json: displayed }));
  await operator.route(operatorUrl, (route) => route.fulfill({ json: displayed }));
  try {
    await page.reload();
    const customerReply = log(page).locator(`#support-message-${legacy.id}`);
    await expect(customerReply.locator("p").nth(1)).toHaveText(legacyText, { useInnerText: true });
    expect(await customerReply.locator("p").nth(1).textContent()).toBe(legacyText);
    const customerSources = await closedProductSource(page, customerReply, product);
    expect((await customerReply.innerText()).split(product.name)).toHaveLength(2);
    await customerSources.locator("summary").click();
    await expect(customerSources.getByRole("link", { name: product.name, exact: true })).toBeVisible();
    await expect(customerReply.locator("p").nth(1)).toHaveText(legacyText, { useInnerText: true });
    await customerSources.locator("summary").click();

    await admin(operator);
    await selectThread(operator, guest);
    const adminReply = humanLog(operator).locator(`#admin-support-message-${legacy.id}`);
    await expect(adminReply.getByText("STYL Assistant", { exact: true })).toBeVisible();
    await expect(adminReply.locator("p").nth(1)).toHaveText(legacyText, { useInnerText: true });
    expect(await adminReply.locator("p").nth(1).textContent()).toBe(legacyText);
    const adminSources = await closedProductSource(operator, adminReply, product);
    expect((await adminReply.innerText()).split(product.name)).toHaveLength(2);
    await adminSources.locator("summary").click();
    await expect(adminSources.getByRole("link", { name: product.name, exact: true })).toBeVisible();
    await expect(adminReply.locator("p").nth(1)).toHaveText(legacyText, { useInnerText: true });
    await adminSources.locator("summary").click();
    await operator.getByRole("button", { name: "Refresh selected conversation", exact: true }).click();
    await expect(adminReply.locator("p").nth(1)).toHaveText(legacyText, { useInnerText: true });
    expect(displayed).toEqual(legacySnapshot);
    expect((await thread(request, guest)).messages).toEqual(stored.messages);
  } finally {
    await page.unroute(customerUrl);
    await operator.unroute(operatorUrl);
    await operator.close();
  }
});

test("SUP-002 SUP-017: question-based team replies quote the older question, keep other requests pending and let AI answer new prices", async ({ page, request, browser, product }) => {
  const guest = await start(page);
  const firstQuestion = "Can I talk to a human about shipping?";
  const secondQuestion = "What is your delivery policy?";
  await send(page, guest, firstQuestion);
  await expect.poll(async () => (await thread(request, guest)).needsHumanQuestions).toBe(1);
  await expect(page.getByRole("button", { name: "Ask for human help", exact: true })).toHaveCount(0);
  await expect(customerDialog(page).getByText("Your request has been sent to our team.", { exact: true }).first()).toBeVisible();
  await expect(customerDialog(page)).toContainText("You can keep asking questions.");
  await expect(customerDialog(page).getByRole("status")).toHaveText("STYL Assistant");
  await send(page, guest, secondQuestion);
  await expect.poll(async () => (await thread(request, guest)).needsHumanQuestions).toBe(2);
  const beforePrice = (await thread(request, guest)).messages.filter((message) => message.role === "assistant").length;
  await send(page, guest, `what is price of ${product.name}`);
  await expect.poll(async () => (await thread(request, guest)).messages.filter((message) => message.role === "assistant").length).toBe(beforePrice + 1);
  await expect(log(page).locator('[data-support-role="assistant"]').last()).toContainText(/(?:125\.50|100\.25)/);
  await closedProductSource(page, log(page).locator('[data-support-role="assistant"]').last(), product);
  const pending = await thread(request, guest);
  expect(pending).toMatchObject({ state: "waiting_human", needsHuman: true, needsHumanQuestions: 2, reason: null, processing: false });
  const first = pending.messages.find((message) => message.text === firstQuestion)!;
  const second = pending.messages.find((message) => message.text === secondQuestion)!;
  expect(first).toMatchObject({ needsHuman: true, humanReason: null, answeredBy: null, replyTo: null });
  expect(second).toMatchObject({ needsHuman: true, humanReason: null, answeredBy: null });
  const pendingAdmin = await request.get(`${adminApi}/conversations/${guest.id}`, { headers: adminHeaders });
  expect(pendingAdmin.status()).toBe(200);
  expect(await pendingAdmin.json()).toMatchObject({ needsHuman: true, needsHumanQuestions: 2 });
  await expectProfessionalCopy(page);
  const operatorContext = await browser.newContext({ baseURL: "http://127.0.0.1:3102" });
  try {
    const operator = await operatorContext.newPage();
    await admin(operator);
    await expect(operator.getByRole("button").filter({ hasText: `Guest ${guest.id.slice(0, 8)}` })).toContainText("2 questions need a team reply");
    await selectThread(operator, guest);
    await expect(operator.getByRole("button", { name: /Take over conversation|Resume AI|Clear human request/ })).toHaveCount(0);
    const firstRow = operator.locator(`#admin-support-message-${first.id}`);
    const secondRow = operator.locator(`#admin-support-message-${second.id}`);
    const priceQuestion = pending.messages.find((message) => message.role === "customer" && message.text === `what is price of ${product.name}`)!;
    await expect(operator.locator(`#admin-support-message-${priceQuestion.id}`)).toContainText("Answered by STYL Assistant");
    await expect(operator.locator(`#admin-support-message-${priceQuestion.id}`)).not.toContainText("Answered by STYL team");
    await expect(firstRow).toContainText("Needs a team reply");
    await expect(secondRow).toContainText("Needs a team reply");
    await expect(operator.getByRole("region", { name: "Replying to customer question" })).toContainText(firstQuestion);
    const reply = operator.getByRole("textbox", { name: "Your reply", exact: true });
    await expect(reply).toHaveAttribute("placeholder", "Write a helpful message…");
    await reply.fill("Synthetic team reply: Shipping needs a team review; no delivery estimate is confirmed.");
    await expect(operator.getByRole("button", { name: "Send reply", exact: true })).toBeEnabled();
    const replyEndpoint = `${adminApi}/conversations/${guest.id}/messages`;
    let newerRevision = 0;
    await operator.route(replyEndpoint, async (route) => {
      const newerQuestion = await request.post(`${publicApi}/conversations/${guest.id}/messages`, {
        headers: { Authorization: `Bearer ${guest.token}` },
        data: { text: `What is the listed price of ${product.name}?`, clientMessageId: randomUUID() },
      });
      expect(newerQuestion.status(), await newerQuestion.text()).toBe(200);
      await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
      newerRevision = (await thread(request, guest)).revision;
      await route.continue();
    });
    const saved = operator.waitForResponse((value) => value.url() === replyEndpoint && value.request().method() === "POST");
    await operator.getByRole("button", { name: "Send reply", exact: true }).click();
    const saveResponse = await saved;
    expect(saveResponse.status(), await saveResponse.text()).toBe(200);
    expect(saveResponse.request().postDataJSON()).toMatchObject({ replyToMessageId: first.id, expectedAnsweredBy: null });
    expect(saveResponse.request().postDataJSON().expectedRevision).toBeLessThan(newerRevision);
    await operator.unroute(replyEndpoint);
    expect(new URL(saveResponse.url()).search).toBe("");
    const adminReply = humanLog(operator).locator('[data-support-role="human"]').last();
    await expect(adminReply).toContainText("STYL team");
    await expect(adminReply.getByRole("blockquote")).toContainText(firstQuestion);
    await expect(firstRow).toContainText("Answered by STYL team");
    await expect(firstRow).not.toContainText("Needs a team reply");
    await expect(secondRow).toContainText("Needs a team reply");
    await expect(operator.getByRole("status").filter({ hasText: /^1 question needs a team reply$/ })).toBeVisible();
    await page.bringToFront();
    await expect(log(page)).toContainText("Synthetic team reply");
    await expect(customerDialog(page).getByRole("status")).toHaveText("STYL Assistant");
    const customerReply = log(page).locator('[data-support-role="human"]').last();
    await expect(customerReply).toContainText("STYL team");
    await expect(customerReply.getByRole("blockquote").locator("p").last()).toHaveText(firstQuestion);
    await expect(customerReply.getByRole("blockquote")).not.toContainText(secondQuestion);
    expect((await thread(request, guest))).toMatchObject({ state: "waiting_human", needsHuman: true, needsHumanQuestions: 1 });
    const recordedReply = (await thread(request, guest)).messages.find((message) => message.role === "human")!;
    expect(recordedReply.replyTo).toEqual({ id: first.id, text: firstQuestion });
    expect((await thread(request, guest)).messages.find((message) => message.id === first.id)?.answeredBy).toBe(recordedReply.id);
    await send(page, guest, `what is price of ${product.name}`);
    await expect.poll(async () => (await thread(request, guest)).messages.filter((message) => message.role === "assistant").length).toBe(beforePrice + 3);
    await expect(log(page).locator('[data-support-role="assistant"]').last()).toContainText(/(?:125\.50|100\.25)/);
    expect((await thread(request, guest)).needsHumanQuestions).toBe(1);
    await expectProfessionalCopy(page);
    await operator.bringToFront();
    await operator.getByRole("button", { name: "Refresh selected conversation", exact: true }).click();
    await secondRow.getByRole("button", { name: "Reply", exact: true }).click();
    await reply.fill("Synthetic team reply: Delivery policy details need verification.");
    await operator.getByRole("button", { name: "Send reply", exact: true }).click();
    await expect(reply).toHaveValue("");
    await expect(secondRow).toContainText("Answered by STYL team");
    await expect(operator.getByRole("status").filter({ hasText: /^0 questions need a team reply$/ })).toBeVisible();
    await expect.poll(async () => (await thread(request, guest)).state).toBe("ai");
    expect((await thread(request, guest)).needsHuman).toBe(false);
    await expect(operator.getByRole("button", { name: "Close conversation", exact: true })).toBeEnabled();
    await confirmAction(operator, "Close conversation");
    await expect.poll(async () => (await thread(request, guest)).state).toBe("closed");
    await page.bringToFront();
    await expect(page.getByRole("status").filter({ hasText: "Conversation closed" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Your message", exact: true })).toHaveCount(0);
    const next = page.waitForResponse((value) => value.url() === `${publicApi}/conversations` && value.request().method() === "POST");
    await page.getByRole("button", { name: "New conversation", exact: true }).click();
    const created = await (await next).json();
    expect(created.conversation.id).not.toBe(guest.id);
    expect((await thread(request, guest)).state).toBe("closed");
    await expect(log(page)).not.toContainText("Synthetic team reply");
  } finally { await operatorContext.close(); }
});

test("SUP-002 SUP-017: closing retains unanswered question history without actionable attention or reply controls", async ({ page, request }) => {
  const guest = await start(page);
  const question = "Can I talk to a human about shipping?";
  await send(page, guest, question);
  await expect.poll(async () => (await thread(request, guest)).needsHumanQuestions).toBe(1);
  const pending = await thread(request, guest);
  const original = pending.messages.find((message) => message.role === "customer")!;
  await admin(page);
  await selectThread(page, guest);
  const row = page.locator(`#admin-support-message-${original.id}`);
  await expect(row).toContainText("Needs a team reply");
  await confirmAction(page, "Close conversation");
  await expect(page.getByRole("status").filter({ hasText: /^0 questions need a team reply$/ })).toBeVisible();
  await expect(row).toContainText(question);
  await expect(row).toHaveAttribute("data-needs-team-reply", "false");
  await expect(row).not.toContainText("Needs a team reply");
  await expect(row.getByRole("button", { name: "Reply", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Send reply", exact: true })).toBeDisabled();
  const closed = await thread(request, guest);
  expect(closed).toMatchObject({ state: "closed", needsHuman: false, needsHumanQuestions: 0, reason: null });
  expect(closed.messages.find((message) => message.id === original.id)).toMatchObject({ text: question, needsHuman: true, answeredBy: null });
});

test("SUP-003: admin scope choices persist, excluded pricing goes to a human and disabling AI keeps guest questions available", async ({ page, request, browser, product }) => {
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
    expect((await thread(request, guest)).reason).toBeNull();
    const diagnostic = await request.get(`${adminApi}/conversations/${guest.id}`, { headers: adminHeaders });
    expect(diagnostic.status()).toBe(200);
    expect((await diagnostic.json()).reason).toBe("scope_disabled");
    await expect(customerDialog(customer).getByText("Your request has been sent to our team.", { exact: true }).first()).toBeVisible();
    await expect(customerDialog(customer).getByRole("status")).toHaveText("STYL Assistant");
    await expectProfessionalCopy(customer);
    await page.bringToFront();
    await page.getByRole("checkbox", { name: "Enable automatic AI replies", exact: true }).uncheck();
    await page.getByRole("button", { name: "Save AI scope", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "AI scope settings saved" })).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Customer support", exact: true }).click();
    await expect(page.getByRole("checkbox", { name: "Enable automatic AI replies", exact: true })).not.toBeChecked();
    await expect(page.getByRole("checkbox", { name: "Listed pricing", exact: true })).not.toBeChecked();
    await customer.bringToFront();
    await customer.reload();
    await expect(customer.getByRole("status").filter({ hasText: "The STYL Assistant is unavailable right now" })).toBeVisible();
    await expect(customer.getByRole("button", { name: "Ask for human help", exact: true })).toHaveCount(0);
    await send(customer, guest, "Can your team help with delivery?");
    await expect.poll(async () => (await thread(request, guest)).needsHumanQuestions).toBe(2);
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
    await expect(input).toHaveAttribute("readonly", "");
    await expect(input).toBeFocused();
    await expect(page.getByRole("button", { name: "Sending…", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Ask for human help", exact: true })).toHaveCount(0);
    await expect.poll(() => bodies.length).toBe(1);
    release();
    await expect(page.getByRole("alert").filter({ hasText: "We couldn't complete your request. Please try again." })).toBeVisible();
    await expect(customerDialog(page)).not.toContainText("Synthetic support outage");
    await expectProfessionalCopy(page);
    await expect(input).toHaveValue(`${question}\n`);
    await expect(input).toBeFocused();
  } finally { release(); await page.unroute(endpoint); }
  let retryBody: { clientMessageId: string; text: string } | undefined;
  await page.route(endpoint, async (route) => { retryBody = route.request().postDataJSON(); await route.continue(); });
  await input.press("Enter");
  await expect(input).toHaveValue("");
  await expect(input).toBeFocused();
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
  await expect(customerDialog(page).getByRole("alert").filter({ hasText: "Connection lost" })).toBeVisible();
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
    await expect(customer.getByRole("button", { name: "Ask for human help", exact: true })).toHaveCount(0);
    const handoff = await request.post(`${publicApi}/conversations/${guest.id}/handoff`, { headers: { Authorization: `Bearer ${guest.token}` }, data: {} });
    expect(handoff.status(), await handoff.text()).toBe(200);
    await expect(customerDialog(customer).getByText("Your request has been sent to our team.", { exact: true }).first()).toBeVisible();
    await admin(page);
    await page.getByRole("button", { name: "Equipment", exact: true }).click();
    await page.getByRole("button", { name: "New", exact: true }).click();
    await page.getByRole("textbox", { name: "Equipment name", exact: true }).fill("Unsaved support catalog draft");
    await page.getByRole("button", { name: "Customer support", exact: true }).click();
    await selectThread(page, guest);
    const reply = page.getByRole("textbox", { name: "Your reply", exact: true });
    await reply.fill("Synthetic retained operator reply");
    await page.getByRole("button", { name: "Backup", exact: true }).click();
    await page.getByRole("button", { name: "Customer support", exact: true }).click();
    await expect(reply).toHaveValue("Synthetic retained operator reply");
    await page.getByRole("button", { name: "Equipment", exact: true }).click();
    await expect(page.getByRole("textbox", { name: "Equipment name", exact: true })).toHaveValue("Unsaved support catalog draft");
    await page.getByRole("button", { name: "Customer support", exact: true }).click();
    const endpoint = `${adminApi}/conversations/${guest.id}/messages`;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    let original: Record<string, unknown> | undefined;
    await page.route(endpoint, async (route) => { original = route.request().postDataJSON(); await gate; await route.fulfill({ status: 409, json: { detail: "Synthetic revision conflict." } }); });
    await page.getByRole("button", { name: "Send reply", exact: true }).click();
    for (const name of ["Customer support", "Equipment", "Sign out", "Close conversation"]) await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
    release();
    await expect(page.getByRole("alert").filter({ hasText: "Synthetic revision conflict" })).toBeVisible();
    await expect(reply).toHaveValue("Synthetic retained operator reply");
    await expect(page.getByRole("button", { name: "Send reply", exact: true })).toBeDisabled();
    await page.unroute(endpoint);
    await page.getByRole("button", { name: "Refresh selected conversation", exact: true }).click();
    await expect(page.getByRole("button", { name: "Send reply", exact: true })).toBeEnabled();
    const retried = page.waitForResponse((value) => value.url() === endpoint && value.request().method() === "POST");
    await page.getByRole("button", { name: "Send reply", exact: true }).click();
    const saved = await retried;
    expect(saved.status(), await saved.text()).toBe(200);
    expect(saved.request().postDataJSON().clientMessageId).toBe(original!.clientMessageId);
    expect(saved.request().postDataJSON().replyToMessageId).toBe(original!.replyToMessageId);
    expect(saved.request().postDataJSON().expectedAnsweredBy).toBe(original!.expectedAnsweredBy);
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

test("SUP-005 SUP-018: question drafts survive polling and switching; CAS and lost acknowledgements retry the same text, UUID and target exactly once", async ({ page, request, browser, product }) => {
  const customerContext = await browser.newContext({ baseURL: "http://127.0.0.1:3102" });
  let release = () => {};
  try {
    const customer = await customerContext.newPage();
    const guest = await start(customer);
    const firstQuestion = "Can I talk to a human about shipping?";
    const secondQuestion = "What is your delivery policy?";
    await send(customer, guest, firstQuestion);
    await expect.poll(async () => (await thread(request, guest)).needsHumanQuestions).toBe(1);
    await send(customer, guest, secondQuestion);
    await expect.poll(async () => (await thread(request, guest)).needsHumanQuestions).toBe(2);
    const initial = await thread(request, guest);
    const first = initial.messages.find((message) => message.text === firstQuestion)!;
    const second = initial.messages.find((message) => message.text === secondQuestion)!;
    await admin(page);
    await selectThread(page, guest);
    const reply = page.getByRole("textbox", { name: "Your reply", exact: true });
    const preview = page.getByRole("region", { name: "Replying to customer question", exact: true });
    const firstRow = page.locator(`#admin-support-message-${first.id}`);
    const secondRow = page.locator(`#admin-support-message-${second.id}`);
    const text = "Synthetic reply: There is no verified information for that question.";
    await reply.fill(text);
    await secondRow.getByRole("button", { name: "Reply", exact: true }).click();
    await expect(reply).toHaveValue("");
    await expect(preview).toContainText(secondQuestion);
    await reply.fill(text);
    await firstRow.getByRole("button", { name: "Reply", exact: true }).click();
    await expect(reply).toHaveValue(text);
    await expect(preview).toContainText(firstQuestion);

    const postQuestion = async (message: string) => {
      const response = await request.post(`${publicApi}/conversations/${guest.id}/messages`, {
        headers: { Authorization: `Bearer ${guest.token}` }, data: { text: message, clientMessageId: randomUUID() },
      });
      expect(response.status(), await response.text()).toBe(200);
      await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
    };
    const priceQuestion = `What is the price of ${product.name}?`;
    await postQuestion(priceQuestion);
    await expect(humanLog(page)).toContainText(priceQuestion);
    await expect(humanLog(page).locator('[data-support-role="assistant"]').last()).toContainText(/(?:125\.50|100\.25)/);
    await expect(preview).toContainText(firstQuestion);
    await expect(preview).not.toContainText(priceQuestion);
    await expect(reply).toHaveValue(text);
    await expect(firstRow.getByRole("button", { name: "Reply", exact: true })).toHaveAttribute("aria-pressed", "true");
    const endpoint = `${adminApi}/conversations/${guest.id}/messages`;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    const attempts: { text: string; clientMessageId: string; replyToMessageId: string; expectedRevision: number; expectedAnsweredBy: string | null }[] = [];
    await page.route(endpoint, async (route) => {
      attempts.push(route.request().postDataJSON());
      await gate;
      await route.fulfill({ status: 409, json: { detail: "Synthetic reply conflict." } });
    });
    await page.getByRole("button", { name: "Send reply", exact: true }).click();
    await expect.poll(() => attempts.length).toBe(1);
    await postQuestion(`Tell me about ${product.name}.`);
    release();
    await expect(page.getByRole("alert").filter({ hasText: "Synthetic reply conflict" })).toBeVisible();
    await expect(reply).toHaveValue(text);
    await expect(preview).toContainText(firstQuestion);
    await expect(page.getByRole("button", { name: "Send reply", exact: true })).toBeDisabled();
    expect(attempts[0].replyToMessageId).toBe(first.id);
    expect(attempts[0].expectedAnsweredBy).toBeNull();
    await page.unroute(endpoint);
    await page.getByRole("button", { name: "Refresh selected conversation", exact: true }).click();
    await expect(page.getByRole("button", { name: "Send reply", exact: true })).toBeEnabled();
    await page.route(endpoint, async (route) => {
      attempts.push(route.request().postDataJSON());
      const saved = await route.fetch();
      expect(saved.status(), await saved.text()).toBe(200);
      await route.abort("failed");
    });
    await page.getByRole("button", { name: "Send reply", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "The last write could not be confirmed" })).toBeVisible();
    await expect(reply).toHaveValue(text);
    await expect(preview).toContainText(firstQuestion);
    expect(attempts[1]).toMatchObject({ text, clientMessageId: attempts[0].clientMessageId, replyToMessageId: first.id, expectedAnsweredBy: null });
    expect(attempts[1].expectedRevision).toBeGreaterThan(attempts[0].expectedRevision);
    expect((await thread(request, guest)).messages.filter((message) => message.role === "human")).toHaveLength(1);
    await page.unroute(endpoint);
    await postQuestion(`What is the listed price of ${product.name}?`);
    await page.getByRole("button", { name: "Refresh selected conversation", exact: true }).click();
    await expect(page.getByRole("button", { name: "Send reply", exact: true })).toBeDisabled();
    await expect(page.getByRole("region", { name: "Review updated answer", exact: true })).toContainText(text);
    await confirmAction(page, "Review latest answer and continue");
    await expect(page.getByRole("button", { name: "Send reply", exact: true })).toBeEnabled();
    await expect(preview).toContainText(firstQuestion);
    await expect(reply).toHaveValue(text);
    const resent = page.waitForResponse((response) => response.url() === endpoint && response.request().method() === "POST");
    await page.getByRole("button", { name: "Send reply", exact: true }).click();
    const acknowledged = await resent;
    expect(acknowledged.status(), await acknowledged.text()).toBe(200);
    const replay = acknowledged.request().postDataJSON();
    const savedAnswerId = (await thread(request, guest)).messages.find((message) => message.role === "human")!.id;
    expect(replay).toMatchObject({ text, clientMessageId: attempts[0].clientMessageId, replyToMessageId: first.id, expectedAnsweredBy: savedAnswerId });
    expect(replay.expectedRevision).toBeGreaterThan(attempts[1].expectedRevision);
    await expect(reply).toHaveValue("");
    await expect(secondRow).toContainText("Needs a team reply");
    await expect(firstRow).toContainText("Answered by STYL team");
    const persisted = await thread(request, guest);
    expect(persisted.messages.filter((message) => message.role === "human")).toHaveLength(1);
    expect(persisted.messages.find((message) => message.role === "human")?.replyTo).toEqual({ id: first.id, text: firstQuestion });
    await secondRow.getByRole("button", { name: "Reply", exact: true }).click();
    await expect(reply).toHaveValue(text);
    await expect(preview).toContainText(secondQuestion);
    const another = page.waitForResponse((response) => response.url() === endpoint && response.request().method() === "POST");
    await page.getByRole("button", { name: "Send reply", exact: true }).click();
    const secondReply = await another;
    expect(secondReply.status(), await secondReply.text()).toBe(200);
    expect(secondReply.request().postDataJSON()).toMatchObject({ text, replyToMessageId: second.id, expectedAnsweredBy: null });
    expect(secondReply.request().postDataJSON().clientMessageId).not.toBe(attempts[0].clientMessageId);
    await expect(reply).toHaveValue("");
    expect((await thread(request, guest)).messages.filter((message) => message.role === "human")).toHaveLength(2);
    expect((await thread(request, guest)).needsHumanQuestions).toBe(0);
    expect(new URL(secondReply.url()).search).toBe("");
    await expect(page.locator("main")).not.toContainText(guest.token);
  } finally { release(); await customerContext.close(); }
});

test("SUP-018: real competing answer requires explicit review after refresh and keeps the same draft, target and retry UUID", async ({ page, request }) => {
  const guest = await start(page);
  const question = "Can I talk to a human about shipping?";
  await send(page, guest, question);
  await expect.poll(async () => (await thread(request, guest)).needsHumanQuestions).toBe(1);
  const initial = await thread(request, guest);
  const original = initial.messages.find((message) => message.role === "customer")!;
  await admin(page);
  await selectThread(page, guest);
  const reply = page.getByRole("textbox", { name: "Your reply", exact: true });
  const sendReply = page.getByRole("button", { name: "Send reply", exact: true });
  const preview = page.getByRole("region", { name: "Replying to customer question", exact: true });
  const draft = "Synthetic follow-up: I reviewed the earlier team answer and will verify the details.";
  const competingText = "Synthetic concurrent team answer: Shipping details need confirmation.";
  await reply.fill(draft);
  const endpoint = `${adminApi}/conversations/${guest.id}/messages`;
  let attempt: { text: string; clientMessageId: string; replyToMessageId: string; expectedAnsweredBy: string | null } | undefined;
  let competingAnswerId = "";
  await page.route(endpoint, async (route) => {
    attempt = route.request().postDataJSON();
    const current = await thread(request, guest);
    const competing = await request.post(endpoint, {
      headers: adminHeaders,
      data: { text: competingText, clientMessageId: randomUUID(), expectedRevision: current.revision, replyToMessageId: original.id, expectedAnsweredBy: null },
    });
    expect(competing.status(), await competing.text()).toBe(200);
    const updated = await competing.json() as Conversation;
    competingAnswerId = updated.messages.find((message) => message.role === "human")!.id;
    await route.continue();
  });
  const rejected = page.waitForResponse((response) => response.url() === endpoint && response.request().method() === "POST");
  await sendReply.click();
  expect((await rejected).status()).toBe(409);
  await expect(page.getByRole("alert").filter({ hasText: "The last write could not be confirmed" })).toBeVisible();
  expect(attempt).toMatchObject({ text: draft, replyToMessageId: original.id, expectedAnsweredBy: null });
  await page.unroute(endpoint);
  await page.getByRole("button", { name: "Refresh selected conversation", exact: true }).click();
  const review = page.getByRole("region", { name: "Review updated answer", exact: true });
  await expect(review).toContainText(competingText);
  await expect(review).toContainText("STYL team");
  await expect(sendReply).toBeDisabled();
  await expect(reply).toHaveValue(draft);
  await expect(preview.getByRole("blockquote").locator("p").last()).toHaveText(question);
  expect((await thread(request, guest)).messages.filter((message) => message.role === "human")).toHaveLength(1);
  const dismissed = page.waitForEvent("dialog");
  const reviewClick = page.getByRole("button", { name: "Review latest answer and continue", exact: true }).click();
  await (await dismissed).dismiss();
  await reviewClick;
  await expect(sendReply).toBeDisabled();
  await expect(reply).toHaveValue(draft);
  await confirmAction(page, "Review latest answer and continue");
  await expect(review).toHaveCount(0);
  await expect(sendReply).toBeEnabled();
  const retried = page.waitForResponse((response) => response.url() === endpoint && response.request().method() === "POST");
  await sendReply.click();
  const accepted = await retried;
  expect(accepted.status(), await accepted.text()).toBe(200);
  expect(accepted.request().postDataJSON()).toMatchObject({
    text: draft, clientMessageId: attempt!.clientMessageId, replyToMessageId: original.id, expectedAnsweredBy: competingAnswerId,
  });
  await expect(reply).toHaveValue("");
  const saved = await thread(request, guest);
  const replies = saved.messages.filter((message) => message.role === "human");
  expect(replies).toHaveLength(2);
  expect(replies.filter((message) => message.text === draft)).toHaveLength(1);
  expect(replies.every((message) => message.replyTo?.id === original.id && message.replyTo.text === question)).toBe(true);
  await expect(humanLog(page).locator('[data-support-role="human"]').last().getByRole("blockquote").locator("p").last()).toHaveText(question);
  await page.goto("/support");
  const customerReply = log(page).locator('[data-support-role="human"]').last();
  await expect(customerReply).toContainText(draft);
  await expect(customerReply.getByRole("blockquote").locator("p").last()).toHaveText(question);
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
      id: "synthetic-provider-failure", role: "assistant", createdAt: new Date().toISOString(), text: `I couldn't find an answer to that question. ${unsafeText}\n${"Older synthetic history.\n".repeat(70)}`,
      references: [
        { type: "product", id: product.id, label: "Unsafe script", url: "javascript:alert(1)" },
        { type: "product", id: product.id, label: "External target", url: "https://example.com/private" },
        { type: "product", id: product.id, label: "Protocol-relative target", url: "//example.com/private" },
        { type: "product", id: product.id, label: product.name, url: `/products/${product.slug}` },
      ],
    }, ...(moreHistory ? [{ id: "synthetic-new-message", role: "system", createdAt: new Date().toISOString(), text: "New synthetic status message.", references: [] }] : [])],
  } }));
  await expect(page.getByRole("button", { name: "Refresh conversation", exact: true })).toHaveCount(0);
  await expect(customerDialog(page).getByRole("status")).toHaveText("STYL Assistant");
  await expect(customerDialog(page)).toContainText("Your request has been sent to our team.");
  await expectProfessionalCopy(page);
  await expect(log(page)).toContainText(unsafeText);
  await expect(log(page).locator("img")).toHaveCount(0);
  const sources = await closedProductSource(page, log(page).locator("#support-message-synthetic-provider-failure"), product);
  expect(await log(page).innerText()).not.toContain(product.name);
  await expect(log(page).getByRole("link", { includeHidden: true })).toHaveCount(1);
  await sources.locator("summary").click();
  await expect(log(page).getByRole("link")).toHaveCount(1);
  await expect(log(page).getByRole("link")).toHaveAttribute("href", `/products/${product.slug}`);
  await expect(page.getByRole("button", { name: "Ask for human help", exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Contact STYL instead", exact: true })).toBeVisible();
  await log(page).evaluate((element) => { element.scrollTop = 0; element.dispatchEvent(new Event("scroll")); });
  moreHistory = true;
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
    await expect(page).toHaveURL("http://127.0.0.1:3102/");
    await expect(customerDialog(page)).toBeVisible();
    await expect(page.getByRole("button", { name: "Start conversation", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const control = await page.getByRole("button", { name: "Start conversation", exact: true }).boundingBox();
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
  await page.getByRole("button", { name: "Ask STYL chat", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Support chat is unavailable", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start conversation", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Continue shopping", exact: true }).click();
  await expect(page.getByRole("link", { name: "Cart (0)", exact: true })).toBeVisible();
});

test("SUP-008: guest polling pauses while hidden, remains stopped after closed-thread navigation, and missing evidence is highlighted for human review", async ({ page, request }) => {
  const guest = await start(page);
  await send(page, guest, "Does the fictitious quuxwobble-991 connect with the nonexistent xyzzy-447?");
  await expect.poll(async () => (await thread(request, guest)).state).toBe("waiting_human");
  await expect(customerDialog(page).getByRole("status")).toHaveText("STYL Assistant");
  await expect(log(page).locator('[data-support-role="system"]').last()).toContainText("Your request has been sent to our team.");
  await expect(customerDialog(page)).toContainText("Your request has been sent to our team.");
  await expectProfessionalCopy(page);
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
