import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const support = `${api}/api/support`;
const adminApi = `${api}/api/admin/support`;
const adminHeaders = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Guest = { id: string; token: string };
type Contact = { name: string; email: string; revision: number; updatedAt: string };
type Thread = {
  id: string; revision: number; state: string; createdAt: string; updatedAt: string; currency: string;
  needsHuman: boolean; processing: boolean; reason: string | null; contact?: Contact | null;
  messages: { id: string; role: string; text: string; createdAt: string; references: unknown[] }[];
};
const test = base.extend<{ supportReady: void }>({
  supportReady: [async ({ request }, run) => {
    const directory = process.env.STYL_E2E_DATA_DIR;
    if (!directory || !path.isAbsolute(directory) || !path.basename(directory).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) throw new Error("Contact tests require isolated E2E storage.");
    const config = await request.get(`${support}/config`);
    expect(await config.json()).toMatchObject({ provider: "mock", environment: "test", localTestingOnly: true });
    const before = await request.get(`${adminApi}/config`, { headers: adminHeaders });
    expect(before.status()).toBe(200);
    const original = await before.json();
    const enabled = await request.put(`${adminApi}/config`, { headers: adminHeaders, data: { enabled: true, allowedTopics: ["products", "pricing", "compatibility"], expectedRevision: original.revision } });
    expect(enabled.status()).toBe(200);
    try { await run(); } finally {
      const current = await request.get(`${adminApi}/config`, { headers: adminHeaders });
      expect(current.status()).toBe(200);
      const reset = await request.put(`${adminApi}/config`, { headers: adminHeaders, data: { enabled: original.enabled, allowedTopics: original.allowedTopics, expectedRevision: (await current.json()).revision } });
      expect(reset.status()).toBe(200);
    }
  }, { auto: true }],
});
const panel = (page: Page) => page.getByRole("dialog", { name: "STYL Assistant", exact: true });
const composer = (page: Page) => page.getByRole("textbox", { name: "Your message", exact: true });
const contactForm = (page: Page) => panel(page).getByRole("form", { name: "Follow-up contact details" });
const messages = (page: Page) => panel(page).getByRole("log", { name: "Conversation messages", exact: true });
const headers = (guest: Guest) => ({ Authorization: `Bearer ${guest.token}` });
async function thread(request: APIRequestContext, guest: Guest): Promise<Thread> {
  const response = await request.get(`${support}/conversations/${guest.id}`, { headers: headers(guest) });
  expect(response.status(), await response.text()).toBe(200);
  return response.json();
}
async function start(page: Page): Promise<Guest> {
  await page.goto("/support");
  await expect(panel(page)).toBeVisible();
  await expect(panel(page).getByRole("button", { name: /Ask for human help|Refresh conversation/ })).toHaveCount(0);
  await expect(panel(page)).not.toContainText(/Local preview|do not share personal information/i);
  const created = page.waitForResponse((response) => response.url() === `${support}/conversations` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Start conversation", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const value = await response.json();
  await expect(composer(page)).toBeVisible();
  return { id: value.conversation.id, token: value.token };
}
async function send(page: Page, text: string) {
  await composer(page).fill(text);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(composer(page)).toHaveValue("");
}
async function escalate(page: Page, guest: Guest, request: APIRequestContext) {
  await send(page, "What is your delivery policy for a fictional destination?");
  await expect.poll(async () => (await thread(request, guest)).needsHuman).toBe(true);
  await expect(panel(page)).toContainText("Your request has been sent to our team.");
  await expect(contactForm(page)).toBeVisible();
}
async function fillContact(page: Page, name: string, email: string) {
  await contactForm(page).getByRole("textbox", { name: "Your name", exact: true }).fill(name);
  await contactForm(page).getByRole("textbox", { name: "Email address", exact: true }).fill(email);
}
async function saveContact(page: Page) {
  await contactForm(page).getByRole("button", { name: "Share contact details", exact: true }).click();
}
async function openAdmin(page: Page, guest: Guest) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Customer support", exact: true }).click();
  await page.getByRole("button").filter({ hasText: `Guest ${guest.id.slice(0, 8)}` }).click();
  await expect(page.getByRole("log", { name: "Selected support messages" })).toBeVisible();
}

test("SUP-019 CONTACT-001: automatic fallback offers optional private contact; validation, retry, update, reload and selected-admin display", async ({ page, request, browser }) => {
  const guest = await start(page);
  const endpoint = `${support}/conversations/${guest.id}/contact`;
  const writes: { url: string; authorization: string | undefined; body: Record<string, unknown> }[] = [];
  const messageBodies: Record<string, unknown>[] = [];
  page.on("request", (req) => {
    if (req.url() === endpoint && req.method() === "PUT") writes.push({ url: req.url(), authorization: req.headers().authorization, body: req.postDataJSON() });
    if (req.url().endsWith(`/conversations/${guest.id}/messages`) && req.method() === "POST") messageBodies.push(req.postDataJSON());
  });
  await expect(contactForm(page)).toHaveCount(0);
  await escalate(page, guest, request);
  await expect(contactForm(page)).toContainText("This is optional");
  await expect(contactForm(page).getByRole("textbox", { name: "Your name", exact: true })).toHaveCSS("font-size", "16px");
  await expect(contactForm(page).getByRole("textbox", { name: "Email address", exact: true })).toHaveCSS("font-size", "16px");
  expect(await contactForm(page).evaluate((element) => element.parentElement?.closest("form") === null)).toBe(true);
  await send(page, "Hello");
  await expect(messages(page).locator('[data-support-role="assistant"]')).not.toHaveCount(0);
  expect((await thread(request, guest)).contact).toBeNull();
  await fillContact(page, "Synthetic Guest", "invalid-address");
  await saveContact(page);
  expect(writes).toHaveLength(0);
  expect(await contactForm(page).getByRole("textbox", { name: "Email address" }).evaluate((element: HTMLInputElement) => element.validity.valid)).toBe(false);
  await fillContact(page, "Synthetic Guest", "synthetic.guest@example.com");
  const before = await thread(request, guest);
  expect(writes).toHaveLength(0);
  expect(before.messages.map((message) => message.text).join("\n")).not.toContain("synthetic.guest");
  for (const status of [422, 503]) {
    await page.route(endpoint, (route) => route.fulfill({ status, json: { detail: "Private backend diagnostic" } }));
    await saveContact(page);
    await expect(contactForm(page).getByRole("alert")).toContainText(status === 422 ? "valid email address" : "We couldn't save your contact details.");
    await expect(contactForm(page).getByRole("textbox", { name: "Your name" })).toHaveValue("Synthetic Guest");
    await expect(contactForm(page).getByRole("textbox", { name: "Email address" })).toHaveValue("synthetic.guest@example.com");
    await expect(panel(page)).not.toContainText("Private backend diagnostic");
    await expect(panel(page)).not.toContainText("Thank you. Our team can follow up using these details.");
    await page.unroute(endpoint);
  }
  await composer(page).fill("Unsent synthetic message stays in the composer");
  const messageCountBeforeContact = messageBodies.length;
  await contactForm(page).getByRole("textbox", { name: "Email address", exact: true }).press("Enter");
  await expect(panel(page).getByRole("status").filter({ hasText: "Thank you. Our team can follow up using these details." })).toBeVisible();
  await expect(contactForm(page)).toHaveCount(0);
  expect(messageBodies).toHaveLength(messageCountBeforeContact);
  await expect(composer(page)).toHaveValue("Unsent synthetic message stays in the composer");
  await composer(page).fill("");
  const saved = await thread(request, guest);
  expect(saved.contact).toMatchObject({ name: "Synthetic Guest", email: "synthetic.guest@example.com", revision: 1 });
  expect(saved.messages).toEqual(before.messages);
  for (const write of writes) {
    expect(write.authorization).toBe(`Bearer ${guest.token}`);
    expect(new URL(write.url).search).toBe("");
    expect(write.body).toEqual({ name: "Synthetic Guest", email: "synthetic.guest@example.com", expectedRevision: 0 });
    expect(JSON.stringify(write.body)).not.toContain(guest.token);
  }
  for (const body of messageBodies) expect(Object.keys(body).sort()).toEqual(["clientMessageId", "pageContextVersion", "text"]);
  await expect(messages(page)).not.toContainText("synthetic.guest@example.com");
  await expect(panel(page)).not.toContainText(/email (?:has been )?sent|team is online|human is online/i);
  await panel(page).getByRole("button", { name: "Edit contact details", exact: true }).click();
  await expect(contactForm(page).getByRole("textbox", { name: "Email address" })).toHaveValue("synthetic.guest@example.com");
  await fillContact(page, "Updated Synthetic Guest", "updated.synthetic@example.com");
  await saveContact(page);
  await expect(contactForm(page)).toHaveCount(0);
  expect((await thread(request, guest)).contact).toMatchObject({ name: "Updated Synthetic Guest", email: "updated.synthetic@example.com", revision: 2 });
  await page.reload();
  await panel(page).getByRole("button", { name: "Edit contact details", exact: true }).click();
  await expect(contactForm(page).getByRole("textbox", { name: "Your name" })).toHaveValue("Updated Synthetic Guest");
  await expect(contactForm(page).getByRole("textbox", { name: "Email address" })).toHaveValue("updated.synthetic@example.com");
  await panel(page).getByRole("button", { name: "Cancel contact edit", exact: true }).click();
  const otherContext = await browser.newContext({ baseURL: "http://127.0.0.1:3102" });
  try {
    const other = await otherContext.newPage();
    const stranger = await start(other);
    await expect(panel(other)).not.toContainText("updated.synthetic@example.com");
    const unauthorized = await request.get(`${support}/conversations/${guest.id}`, { headers: headers(stranger) });
    expect(unauthorized.status()).toBe(404);
  } finally { await otherContext.close(); }
  const queue = await request.get(`${adminApi}/conversations`, { headers: adminHeaders });
  expect(await queue.text()).not.toContain("updated.synthetic@example.com");
  await openAdmin(page, guest);
  const details = page.getByRole("region", { name: "Private follow-up contact" });
  await expect(details).toContainText("Updated Synthetic Guest");
  await expect(details.getByRole("link", { name: "updated.synthetic@example.com" })).toHaveAttribute("href", `mailto:${encodeURIComponent("updated.synthetic@example.com")}`);
  await expect(page.getByRole("log", { name: "Selected support messages" })).not.toContainText("updated.synthetic@example.com");
  await expect(page.getByRole("button").filter({ hasText: `Guest ${guest.id.slice(0, 8)}` })).not.toContainText("updated.synthetic@example.com");
});

test("SUP-019 CONTACT-002: contact CAS and lost acknowledgement preserve drafts and retry without adding chat messages", async ({ page, request }) => {
  const guest = await start(page);
  await escalate(page, guest, request);
  const endpoint = `${support}/conversations/${guest.id}/contact`;
  await fillContact(page, "Synthetic Local Draft", "local.synthetic@example.com");
  const competing = await request.put(endpoint, { headers: headers(guest), data: { name: "Synthetic Other Tab", email: "other.synthetic@example.com", expectedRevision: 0 } });
  expect(competing.status()).toBe(200);
  await saveContact(page);
  await expect(contactForm(page).getByRole("alert")).toContainText("Contact details have changed.");
  await expect(contactForm(page).getByRole("textbox", { name: "Your name" })).toHaveValue("Synthetic Local Draft");
  await expect(contactForm(page).getByRole("textbox", { name: "Email address" })).toHaveValue("local.synthetic@example.com");
  await saveContact(page);
  await expect(contactForm(page)).toHaveCount(0);
  expect((await thread(request, guest)).contact).toMatchObject({ name: "Synthetic Local Draft", revision: 2 });
  await panel(page).getByRole("button", { name: "Edit contact details", exact: true }).click();
  await fillContact(page, "Synthetic Retry", "retry.synthetic@example.com");
  const before = await thread(request, guest);
  await page.route(endpoint, async (route) => {
    const saved = await route.fetch();
    expect(saved.status()).toBe(200);
    await route.abort("failed");
  });
  await saveContact(page);
  await expect(contactForm(page).getByRole("alert")).toContainText("We couldn't save your contact details.");
  await expect(contactForm(page).getByRole("textbox", { name: "Your name" })).toHaveValue("Synthetic Retry");
  await page.unroute(endpoint);
  await saveContact(page);
  await expect(contactForm(page)).toHaveCount(0);
  const retried = await thread(request, guest);
  expect(retried.contact).toMatchObject({ name: "Synthetic Retry", email: "retry.synthetic@example.com", revision: 3 });
  expect(retried.messages).toEqual(before.messages);
});

test("SUP-019 CONTACT-003: pending contact save merges newer replies, disables duplicate writes and resets drafts for a new conversation", async ({ page, request }) => {
  const guest = await start(page);
  await escalate(page, guest, request);
  const endpoint = `${support}/conversations/${guest.id}/contact`;
  let release = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let committed = false;
  await page.route(endpoint, async (route) => {
    const saved = await route.fetch();
    const snapshot = await saved.json();
    committed = true;
    await gate;
    await route.fulfill({ json: snapshot });
  });
  try {
    await fillContact(page, "Synthetic Inflight", "inflight.synthetic@example.com");
    await composer(page).fill("Unsent message stays separate");
    await saveContact(page);
    await expect(contactForm(page).getByRole("button", { name: "Saving…", exact: true })).toBeDisabled();
    await expect(contactForm(page).getByRole("textbox", { name: "Your name" })).toHaveAttribute("readonly", "");
    await expect(composer(page)).toHaveAttribute("readonly", "");
    await expect.poll(() => committed).toBe(true);
    const sent = await request.post(`${support}/conversations/${guest.id}/messages`, { headers: headers(guest), data: { text: "Hello", clientMessageId: randomUUID() } });
    expect(sent.status()).toBe(200);
    await expect.poll(async () => (await thread(request, guest)).processing).toBe(false);
    await expect(messages(page).locator('[data-support-role="assistant"]')).not.toHaveCount(0);
    const latest = await thread(request, guest);
    release();
    await expect(contactForm(page)).toHaveCount(0);
    await expect(messages(page).locator("article")).toHaveCount(latest.messages.length);
    await expect(composer(page)).toHaveValue("Unsent message stays separate");
  } finally { release(); await page.unroute(endpoint); }
  await panel(page).getByRole("button", { name: "Edit contact details", exact: true }).click();
  await fillContact(page, "Unsaved old conversation", "unsaved.synthetic@example.com");
  const current = await thread(request, guest);
  const closed = await request.post(`${adminApi}/conversations/${guest.id}/action`, { headers: adminHeaders, data: { action: "close", expectedRevision: current.revision } });
  expect(closed.status()).toBe(200);
  await panel(page).getByRole("button", { name: "New conversation", exact: true }).click();
  await expect(composer(page)).toHaveValue("");
  await expect(contactForm(page)).toHaveCount(0);
  const next = await page.evaluate(() => JSON.parse(localStorage.getItem("styl-support-guest")!) as Guest);
  expect(next.id).not.toBe(guest.id);
  await escalate(page, next, request);
  await expect(contactForm(page).getByRole("textbox", { name: "Your name" })).toHaveValue("");
  await expect(contactForm(page).getByRole("textbox", { name: "Email address" })).toHaveValue("");
});

test("SUP-019 CONTACT-004: legacy missing contacts stay usable and unsafe email remains inert in the private admin panel", async ({ page, request }) => {
  const guest = await start(page);
  const existing = await thread(request, guest);
  await page.route(`${support}/conversations/${guest.id}`, (route) => {
    const { contact: omitted, ...legacy } = existing;
    void omitted;
    return route.fulfill({ json: { ...legacy, needsHuman: true, revision: existing.revision + 1 } });
  });
  await expect(contactForm(page)).toBeVisible();
  await composer(page).fill("Legacy guest can still compose");
  await expect(panel(page).getByRole("button", { name: "Send message" })).toBeEnabled();
  await composer(page).fill("");
  let email = "synthetic?subject=notice@example.com";
  let revision = 1;
  await page.route(`${adminApi}/conversations/${guest.id}`, (route) => route.fulfill({ json: {
    ...existing, revision: existing.revision + 2,
    contact: { name: "<img src=x onerror=alert(1)>", email, revision, updatedAt: new Date().toISOString() },
  } }));
  await openAdmin(page, guest);
  const details = page.getByRole("region", { name: "Private follow-up contact" });
  await expect(details).toContainText("<img src=x onerror=alert(1)>");
  await expect(details.getByRole("link", { name: email, exact: true })).toHaveAttribute("href", `mailto:${encodeURIComponent(email)}`);
  email = "victim@example.com?bcc=other@example.com"; revision++;
  await page.getByRole("button", { name: "Refresh selected conversation", exact: true }).click();
  await expect(details).toContainText("victim@example.com?bcc=other@example.com");
  await expect(details.locator("a, img")).toHaveCount(0);
  await expect(page.getByRole("log", { name: "Selected support messages" })).not.toContainText("victim@example.com");
});

test("SUP-019 CONTACT-005: compact Privacy link explains OpenAI retention, video-only Gemini, optional contact and honest follow-up", async ({ page }) => {
  await start(page);
  await panel(page).getByRole("link", { name: "Privacy", exact: true }).click();
  await expect(page).toHaveURL(/\/privacy$/);
  await expect(panel(page)).not.toBeVisible();
  const disclosure = page.getByRole("region", { name: "STYL Assistant and team follow-up" });
  await expect(disclosure).toContainText("Chat messages and selected STYL catalog context may be sent to OpenAI.");
  await expect(disclosure).toContainText("not used to train its models by default");
  await expect(disclosure).toContainText("store: false");
  await expect(disclosure).toContainText("does not guarantee zero retention");
  await expect(disclosure).toContainText("abuse-monitoring logs");
  await expect(disclosure).toContainText("images and PDFs to OpenAI, and videos only to Google Gemini");
  await expect(disclosure).toContainText("Gemini is not used for customer chat.");
  await expect(disclosure).toContainText("human review");
  await expect(disclosure).toContainText("reviews the extracted draft and approves it");
  await expect(disclosure).not.toContainText("Chat messages may be sent to Google Gemini");
  await expect(disclosure).not.toContainText("never stored");
  await expect(disclosure).toContainText("dedicated contact fields");
  await expect(disclosure).toContainText("never sent to the AI model or usage analytics");
  await expect(disclosure).toContainText("You do not need an account or contact details to chat.");
  await expect(disclosure).toContainText("does not mean a team member is online");
  await expect(disclosure).toContainText("send an email automatically");
});
