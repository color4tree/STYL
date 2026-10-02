import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const support = `${api}/api/support`;
const adminSupport = `${api}/api/admin/support`;
const adminHeaders = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Item = { id: number; name: string; slug: string; itemType: "product" | "accessory" };
type Catalog = { a: Item; b: Item; accessory: Item };
type Guest = { id: string; token: string };
type Payload = { text: string; clientMessageId: string; itemRef?: string; pageContextVersion: string };
type Thread = {
  id: string; processing: boolean;
  messages: { id: string; role: string; text: string; references: { type: string; id: number; label: string; url: string }[] }[];
};
const endpoint = (item: Item) => `${api}/api/${item.itemType === "product" ? "products" : "accessories"}/${item.itemType === "product" ? item.slug : item.id}`;
const href = (item: Item) => item.itemType === "product" ? `/products/${item.slug}` : `/accessories/${item.id}`;
const itemRef = (item: Item) => `${item.itemType}:${item.id}`;
const panel = (page: Page) => page.getByRole("dialog", { name: "STYL Assistant", exact: true });
const launcher = (page: Page) => page.getByRole("button", { name: /^Ask STYL chat/ });
const composer = (page: Page) => panel(page).getByRole("textbox", { name: "Your message", exact: true });
const history = (page: Page) => panel(page).getByRole("log", { name: "Conversation messages", exact: true });
const chip = (page: Page) => panel(page).getByLabel("Current page item", { exact: true });
const sendButton = (page: Page) => panel(page).getByRole("button", { name: "Send message", exact: true });

// SUP-026: real isolated catalog/support API; only delivery/failure timing is intercepted.
const test = base.extend<{ catalog: Catalog }>({
  catalog: [async ({ request }, run) => {
    const directory = process.env.STYL_E2E_DATA_DIR;
    if (!directory || !path.isAbsolute(directory) || !path.basename(directory).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) {
      throw new Error("Context tests require the isolated E2E API, never the local catalog mirror.");
    }
    const config = await request.get(`${support}/config`);
    expect(config.status()).toBe(200);
    expect(await config.json()).toMatchObject({ enabled: true, provider: "mock", model: "mock", environment: "test", localTestingOnly: true });
    const before = await request.get(`${adminSupport}/config`, { headers: adminHeaders });
    expect(before.status()).toBe(200);
    const previous = await before.json();
    const enabled = await request.put(`${adminSupport}/config`, { headers: adminHeaders, data: {
      enabled: true, allowedTopics: ["products", "pricing", "compatibility"], expectedRevision: previous.revision,
    } });
    expect(enabled.status()).toBe(200);
    const created: Item[] = [];
    try {
      const suffix = randomUUID().slice(0, 8).replace(/\d/g, (digit) => String.fromCharCode(103 + Number(digit)));
      for (const [itemType, name, price] of [
        ["product", `Synthetic context atlas ${suffix}`, 125.5],
        ["product", `Synthetic context boreal ${suffix}`, 237.75],
        ["accessory", `Synthetic context cable ${suffix}`, 49.5],
      ] as const) {
        const response = await request.post(`${api}/api/${itemType === "product" ? "products" : "accessories"}`, { headers: adminHeaders, data: {
          name, category: itemType === "product" ? "Racks" : "Handle", publicationStatus: "published",
          prices: { CAD: price, USD: price }, shortDescription: "Synthetic public page-context fixture.",
          description: "Published synthetic fixture for isolated chat context checks.", photos: [],
        } });
        expect(response.status(), await response.text()).toBe(200);
        created.push({ ...(await response.json()).item, itemType });
      }
      await run({ a: created[0], b: created[1], accessory: created[2] });
    } finally {
      for (const item of created) {
        const removed = await request.delete(`${api}/api/${item.itemType === "product" ? "products" : "accessories"}/${item.id}`, { headers: adminHeaders });
        expect(removed.ok()).toBe(true);
      }
      const current = await request.get(`${adminSupport}/config`, { headers: adminHeaders });
      expect(current.status()).toBe(200);
      const reset = await request.put(`${adminSupport}/config`, { headers: adminHeaders, data: {
        enabled: previous.enabled, allowedTopics: previous.allowedTopics, expectedRevision: (await current.json()).revision,
      } });
      expect(reset.status()).toBe(200);
    }
  }, { auto: true }],
});

async function openDetail(page: Page, item: Item) {
  await page.goto(href(item));
  await expect(page.getByRole("heading", { level: 1, name: item.name, exact: true })).toBeVisible();
  await expect(panel(page)).not.toBeVisible();
  await launcher(page).click();
  await expect(chip(page)).toHaveText(`About: ${item.name}`);
}
async function start(page: Page): Promise<Guest> {
  const created = page.waitForResponse((response) => response.url() === `${support}/conversations` && response.request().method() === "POST");
  await panel(page).getByRole("button", { name: "Start conversation", exact: true }).click();
  const response = await created;
  expect(response.status(), await response.text()).toBe(201);
  const value = await response.json();
  await expect(composer(page)).toBeVisible();
  return { id: value.conversation.id, token: value.token };
}
async function thread(request: APIRequestContext, guest: Guest): Promise<Thread> {
  const response = await request.get(`${support}/conversations/${guest.id}`, { headers: { Authorization: `Bearer ${guest.token}` } });
  expect(response.status()).toBe(200);
  return response.json();
}
async function submit(page: Page, guest: Guest): Promise<Payload> {
  const sent = page.waitForResponse((response) => response.url() === `${support}/conversations/${guest.id}/messages` && response.request().method() === "POST");
  await sendButton(page).click();
  const response = await sent;
  expect(response.status(), await response.text()).toBe(200);
  await expect(composer(page)).toHaveValue("");
  return response.request().postDataJSON() as Payload;
}
async function ask(page: Page, guest: Guest, text: string) {
  await composer(page).fill(text);
  return submit(page, guest);
}
async function answer(page: Page, item: Item, price: string) {
  const latest = history(page).locator('[data-support-role="assistant"]').last();
  await expect(latest).toContainText(item.name);
  await expect(latest).toContainText(price);
  const sources = latest.locator("details").filter({ has: page.locator("summary", { hasText: /^Sources$/ }) });
  await expect(sources.locator("summary")).toBeVisible();
  await expect(sources).not.toHaveAttribute("open");
  const link = sources.getByRole("link", { name: item.name, exact: true, includeHidden: true });
  await expect(link).toHaveAttribute("href", href(item));
  await expect(link).toBeHidden();
  expect((await latest.innerText()).split(item.name)).toHaveLength(2);
}
async function seedNavigation(page: Page, request: APIRequestContext, guest: Guest, item: Item) {
  const response = await request.post(`${support}/conversations/${guest.id}/messages`, {
    headers: { Authorization: `Bearer ${guest.token}` },
    data: { text: `What is the price of ${item.name}?`, itemRef: itemRef(item), clientMessageId: randomUUID() },
  });
  expect(response.status(), await response.text()).toBe(200);
  await expect.poll(async () => (await thread(request, guest)).messages.some((message) =>
    message.role === "assistant" && message.references.some((reference) =>
      reference.type === item.itemType && reference.id === item.id && reference.label === item.name && reference.url === href(item)))).toBe(true);
  const link = history(page).getByRole("link", { name: item.name, exact: true, includeHidden: true }).last();
  await expect(link).toHaveAttribute("href", href(item));
  await expect(link).toBeHidden();
}
async function followCitation(page: Page, item: Item) {
  const sources = history(page).locator("details").filter({
    has: page.getByRole("link", { name: item.name, exact: true, includeHidden: true }),
  }).last();
  await expect(sources.locator("summary")).toHaveText("Sources");
  if (!await sources.evaluate((element) => (element as HTMLDetailsElement).open)) await sources.locator("summary").click();
  await sources.getByRole("link", { name: item.name, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`${href(item)}$`));
}
function onlyContext(payload: Payload, text: string, item?: Item) {
  expect(payload).toEqual({
    text, clientMessageId: expect.any(String), pageContextVersion: expect.any(String), ...(item ? { itemRef: itemRef(item) } : {}),
  });
  expect(payload.clientMessageId).toMatch(/^[0-9a-f-]{36}$/);
  expect(payload.pageContextVersion).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  expect(payload.pageContextVersion.length).toBeLessThanOrEqual(64);
  expect(payload.pageContextVersion).not.toBe(payload.clientMessageId);
}

test("SUP-026 CTX-001: product detail is opt-in and How much sends only the public reference and opaque context stamp with a priced citation", async ({ page, catalog }) => {
  const supportRequests: string[] = [];
  page.on("request", (request) => { if (request.url().startsWith(support)) supportRequests.push(request.url()); });
  await page.goto(href(catalog.a));
  await expect(page.getByRole("heading", { level: 1, name: catalog.a.name })).toBeVisible();
  await expect(panel(page)).not.toBeVisible();
  expect(supportRequests).toEqual([]);
  await launcher(page).click();
  await expect(chip(page)).toHaveText(`About: ${catalog.a.name}`);
  const guest = await start(page);
  onlyContext(await ask(page, guest, "How much?"), "How much?", catalog.a);
  await answer(page, catalog.a, "125.50");
});

test("SUP-026 CTX-002: accessory detail supplies accessory identity, not a product ID or page price", async ({ page, catalog }) => {
  await openDetail(page, catalog.accessory);
  const guest = await start(page);
  onlyContext(await ask(page, guest, "How much?"), "How much?", catalog.accessory);
  await answer(page, catalog.accessory, "49.50");
});

test("SUP-026 CTX-003: an explicitly named other product overrides the detail-page default without changing its chip", async ({ page, catalog }) => {
  await openDetail(page, catalog.a);
  const guest = await start(page);
  const question = `What is the price of ${catalog.b.name}?`;
  onlyContext(await ask(page, guest, question), question, catalog.a);
  await answer(page, catalog.b, "237.75");
  await expect(chip(page)).toHaveText(`About: ${catalog.a.name}`);
  await expect(history(page).locator('[data-support-role="assistant"]').last()).not.toContainText("125.50");
});

test("SUP-026 CTX-004: Next product navigation preserves the guest, draft and old history; new sends capture the new item", async ({ page, request, catalog }) => {
  let starts = 0;
  page.on("request", (request) => { if (request.url() === `${support}/conversations` && request.method() === "POST") starts++; });
  await openDetail(page, catalog.a);
  const guest = await start(page);
  await seedNavigation(page, request, guest, catalog.b);
  const previous = (await thread(request, guest)).messages;
  await composer(page).fill("How much?");
  await followCitation(page, catalog.b);
  await expect(chip(page)).toHaveText(`About: ${catalog.b.name}`);
  await expect(panel(page)).toBeVisible();
  await expect(composer(page)).toHaveValue("How much?");
  expect((await thread(request, guest)).messages).toEqual(previous);
  onlyContext(await submit(page, guest), "How much?", catalog.b);
  await answer(page, catalog.b, "237.75");
  expect((await thread(request, guest)).messages.slice(0, previous.length)).toEqual(previous);
  expect(starts).toBe(1);
});

test("SUP-026 CTX-005: exit to home or a non-detail page removes page context but keeps the draft and history follow-ups", async ({ page, catalog }) => {
  await openDetail(page, catalog.a);
  const guest = await start(page);
  const original = await ask(page, guest, "How much?");
  await answer(page, catalog.a, "125.50");
  await composer(page).fill("What is its price?");
  await panel(page).getByRole("link", { name: "Continue shopping", exact: true }).click();
  await expect(page).toHaveURL("/");
  await expect(panel(page)).not.toBeVisible();
  await launcher(page).click();
  await expect(chip(page)).toHaveCount(0);
  await expect(composer(page)).toHaveValue("What is its price?");
  const home = await submit(page, guest);
  onlyContext(home, "What is its price?");
  expect(home.pageContextVersion).not.toBe(original.pageContextVersion);
  await expect(history(page).locator('[data-support-role="assistant"]')).toHaveCount(2);
  await answer(page, catalog.a, "125.50");
  await panel(page).getByRole("link", { name: "Privacy", exact: true }).click();
  await expect(page).toHaveURL(/\/privacy$/);
  await launcher(page).click();
  await expect(chip(page)).toHaveCount(0);
  const privacy = await ask(page, guest, "Hello");
  onlyContext(privacy, "Hello");
  expect(privacy.pageContextVersion).not.toBe(home.pageContextVersion);
});

// SUP-028 also covers the captured stamp in the in-flight and idempotent retry cases.
test("SUP-026 CTX-006: an in-flight product A question remains A after navigation to B", async ({ page, request, catalog }) => {
  await openDetail(page, catalog.a);
  const guest = await start(page);
  await seedNavigation(page, request, guest, catalog.b);
  const messageEndpoint = `${support}/conversations/${guest.id}/messages`;
  let release = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let received: Payload | undefined;
  await page.route(messageEndpoint, async (route) => {
    received = route.request().postDataJSON();
    await gate;
    const response = await route.fetch();
    await route.fulfill({ response });
  });
  try {
    await composer(page).fill("How much?");
    const sent = page.waitForResponse((response) => response.url() === messageEndpoint && response.request().method() === "POST");
    await sendButton(page).click();
    await expect.poll(() => received).toBeDefined();
    onlyContext(received!, "How much?", catalog.a);
    const original = received!;
    await followCitation(page, catalog.b);
    await expect(chip(page)).toHaveText(`About: ${catalog.b.name}`);
    await expect(panel(page).getByRole("button", { name: "Sending…", exact: true })).toBeDisabled();
    release();
    expect((await sent).status()).toBe(200);
    await expect(composer(page)).toHaveValue("");
    await answer(page, catalog.a, "125.50");
    await expect(chip(page)).toHaveText(`About: ${catalog.b.name}`);
    await page.unroute(messageEndpoint);
    const next = await ask(page, guest, "What is the listed price?");
    onlyContext(next, "What is the listed price?", catalog.b);
    expect(next.pageContextVersion).not.toBe(original.pageContextVersion);
    await answer(page, catalog.b, "237.75");
  } finally {
    release();
    await page.unroute(messageEndpoint);
  }
});

for (const edited of [false, true]) {
  test(`SUP-026 CTX-00${edited ? 8 : 7}: failed A send at B ${edited ? "uses a new UUID and B when the text changes" : "retries the identical UUID, text and original A context"}`, async ({ page, request, catalog }) => {
    await openDetail(page, catalog.a);
    const guest = await start(page);
    await seedNavigation(page, request, guest, catalog.b);
    const messageEndpoint = `${support}/conversations/${guest.id}/messages`;
    let release = () => {};
    const gate = new Promise<void>((resolve) => { release = resolve; });
    let original: Payload | undefined;
    await page.route(messageEndpoint, async (route) => {
      original = route.request().postDataJSON();
      await gate;
      await route.fulfill({ status: 503, json: { detail: "Synthetic delivery failure." } });
    });
    try {
      await composer(page).fill("How much?");
      await sendButton(page).click();
      await expect.poll(() => original).toBeDefined();
      onlyContext(original!, "How much?", catalog.a);
      await followCitation(page, catalog.b);
      await expect(chip(page)).toHaveText(`About: ${catalog.b.name}`);
      release();
      await expect(panel(page).getByRole("alert")).toContainText("Your message is still here");
      await expect(composer(page)).toHaveValue("How much?");
      await page.unroute(messageEndpoint);
      const question = edited ? "What is the listed price?" : "How much?";
      if (edited) await composer(page).fill(question);
      const retried = await submit(page, guest);
      if (edited) {
        expect(retried.clientMessageId).not.toBe(original!.clientMessageId);
        expect(retried.pageContextVersion).not.toBe(original!.pageContextVersion);
      }
      else expect(retried).toEqual(original);
      onlyContext(retried, question, edited ? catalog.b : catalog.a);
      await answer(page, edited ? catalog.b : catalog.a, edited ? "237.75" : "125.50");
      const saved = await thread(request, guest);
      expect(saved.messages.filter((message) => message.role === "customer" && message.text === question)).toHaveLength(1);
    } finally {
      release();
      await page.unroute(messageEndpoint);
    }
  });
}

for (const failure of ["404", "503", "draft", "invalid-public-dto"] as const) {
  test(`SUP-026 CTX-009 (${failure}): failed or hidden detail clears the previous context and does not send an item reference`, async ({ page, request, catalog }) => {
    await openDetail(page, catalog.a);
    const guest = await start(page);
    await seedNavigation(page, request, guest, catalog.b);
    await page.route(endpoint(catalog.b), async (route) => {
      if (failure === "404" || failure === "503") return route.fulfill({ status: Number(failure), json: { detail: "Synthetic unavailable detail." } });
      const response = await route.fetch();
      const data = await response.json();
      data.item = failure === "draft" ? { ...data.item, publicationStatus: "draft" } : { ...data.item, price: null };
      return route.fulfill({ json: data });
    });
    await composer(page).fill("Hello");
    await followCitation(page, catalog.b);
    await expect(page.getByRole("heading", { level: 1, name: failure === "503" ? "Equipment is unavailable right now. Please retry." : "Equipment not found", exact: true })).toBeVisible();
    await expect(chip(page)).toHaveCount(0);
    await expect(composer(page)).toHaveValue("Hello");
    onlyContext(await submit(page, guest), "Hello");
    await page.unroute(endpoint(catalog.b));
  });
}

test("SUP-026 CTX-010: a delayed verified detail cannot register early or restore context after leaving its route", async ({ page, request, catalog }) => {
  await openDetail(page, catalog.a);
  const guest = await start(page);
  await seedNavigation(page, request, guest, catalog.b);
  let release = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let entered = false;
  let completed = false;
  await page.route(endpoint(catalog.b), async (route) => {
    const response = await route.fetch();
    entered = true;
    await gate;
    try { await route.fulfill({ response }); } finally { completed = true; }
  });
  try {
    await composer(page).fill("Hello");
    await followCitation(page, catalog.b);
    await expect.poll(() => entered).toBe(true);
    await expect(page.getByText("Loading equipment...", { exact: true })).toBeVisible();
    await expect(chip(page)).toHaveCount(0);
    await panel(page).getByRole("link", { name: "Continue shopping", exact: true }).click();
    await expect(page).toHaveURL("/");
    release();
    await expect.poll(() => completed).toBe(true);
    await launcher(page).click();
    await expect(chip(page)).toHaveCount(0);
    await expect(composer(page)).toHaveValue("Hello");
    onlyContext(await submit(page, guest), "Hello");
  } finally {
    release();
    await page.unroute(endpoint(catalog.b));
  }
});

test("SUP-026 CTX-011: long public names stay plain text and fit the chat at 390 and 320 pixels", async ({ page, catalog }) => {
  const name = `Synthetic <strong>context</strong> ${"UnbrokenName".repeat(20)}`;
  await page.route(endpoint(catalog.a), async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({ json: { ...data, item: { ...data.item, name } } });
  });
  await openDetail(page, { ...catalog.a, name });
  await expect(chip(page).locator("strong")).toHaveCount(0);
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await chip(page).scrollIntoViewIfNeeded();
    await expect.poll(async () => {
      const context = await chip(page).boundingBox();
      const dialog = await panel(page).boundingBox();
      return Boolean(context && dialog && context.x >= dialog.x && context.x + context.width <= dialog.x + dialog.width
        && dialog.x >= 8 && dialog.x + dialog.width <= width - 8);
    }).toBe(true);
    expect(await chip(page).evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    expect(await panel(page).evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  }
});

test("SUP-028 CTX-012: the opaque context stamp survives polls, hash scrolling, drafts and separate contact saves without storage or network leakage", async ({ page, request, catalog }) => {
  const traffic: { url: string; method: string; headers: Record<string, string>; body: string }[] = [];
  page.on("request", (outgoing) => traffic.push({
    url: outgoing.url(), method: outgoing.method(), headers: outgoing.headers(), body: outgoing.postData() ?? "",
  }));
  await openDetail(page, catalog.a);
  const guest = await start(page);
  const messageEndpoint = `${support}/conversations/${guest.id}/messages`;
  // The stamp lifecycle does not depend on any new answer-engine behavior.
  await page.route(messageEndpoint, async (route) => route.fulfill({ json: await thread(request, guest) }));
  try {
    const first = await ask(page, guest, "Synthetic first message");
    onlyContext(first, "Synthetic first message", catalog.a);
    const polled = page.waitForResponse((response) => response.url() === `${support}/conversations/${guest.id}` && response.request().method() === "GET");
    await composer(page).fill("Draft retained during polling");
    expect((await polled).status()).toBe(200);
    await expect(composer(page)).toHaveValue("Draft retained during polling");
    await page.evaluate(() => { window.location.hash = "synthetic-scroll-target"; window.scrollTo(0, 200); });
    const afterPoll = await submit(page, guest);
    expect(afterPoll.pageContextVersion).toBe(first.pageContextVersion);
    expect(afterPoll.clientMessageId).not.toBe(first.clientMessageId);

    const requested = await request.post(`${support}/conversations/${guest.id}/handoff`, {
      headers: { Authorization: `Bearer ${guest.token}` }, data: {},
    });
    expect(requested.status()).toBe(200);
    const contact = panel(page).getByRole("form", { name: "Follow-up contact details" });
    await expect(contact).toBeVisible();
    await contact.getByRole("textbox", { name: "Your name", exact: true }).fill("Synthetic Context Guest");
    await contact.getByRole("textbox", { name: "Email address", exact: true }).fill("context.stamp@example.com");
    const saved = page.waitForResponse((response) => response.url() === `${support}/conversations/${guest.id}/contact` && response.request().method() === "PUT");
    await contact.getByRole("button", { name: "Share contact details", exact: true }).click();
    const savedResponse = await saved;
    expect(savedResponse.status()).toBe(200);
    expect(savedResponse.request().postDataJSON()).toEqual({
      name: "Synthetic Context Guest", email: "context.stamp@example.com", expectedRevision: 0,
    });
    await expect(panel(page).getByText("Thank you. Our team can follow up using these details.", { exact: true })).toBeVisible();
    const afterContact = await ask(page, guest, "Synthetic message after contact");
    onlyContext(afterContact, "Synthetic message after contact", catalog.a);
    expect(afterContact.pageContextVersion).toBe(first.pageContextVersion);

    const stamp = first.pageContextVersion;
    expect(JSON.stringify(await page.context().cookies())).not.toContain(stamp);
    const storage = await page.evaluate(() => ({
      local: Object.entries(localStorage), session: Object.entries(sessionStorage),
    }));
    expect(JSON.stringify(storage)).not.toContain(stamp);
    for (const outgoing of traffic) {
      expect(outgoing.url).not.toContain(stamp);
      expect(JSON.stringify(outgoing.headers)).not.toContain(stamp);
      if (outgoing.url === messageEndpoint && outgoing.method === "POST") {
        expect(JSON.parse(outgoing.body).pageContextVersion).toBe(stamp);
      } else {
        expect(outgoing.body).not.toContain(stamp);
        expect(outgoing.body).not.toContain("pageContextVersion");
      }
    }
  } finally {
    await page.unroute(messageEndpoint);
  }
});

test("SUP-028 CTX-013: route and item revisions change the stamp including A to B to A without an intervening send and clearing to home", async ({ page, request, catalog }) => {
  await openDetail(page, catalog.a);
  const guest = await start(page);
  const conversationEndpoint = `${support}/conversations/${guest.id}`;
  const response = await request.get(conversationEndpoint, { headers: { Authorization: `Bearer ${guest.token}` } });
  expect(response.status()).toBe(200);
  const displayed = await response.json();
  displayed.revision++;
  displayed.messages.push({
    id: randomUUID(), role: "assistant", text: "Synthetic navigation references.", createdAt: new Date().toISOString(),
    references: [catalog.a, catalog.b, catalog.accessory].map((item) => ({ type: item.itemType, id: item.id, label: item.name, url: href(item) })),
  });
  // Keep navigation and stamping independent from catalog-answer implementation.
  await page.route(conversationEndpoint, (route) => route.fulfill({ json: displayed }));
  await page.route(`${conversationEndpoint}/messages`, (route) => route.fulfill({ json: displayed }));
  try {
    const first = await ask(page, guest, "Synthetic initial question");
    onlyContext(first, "Synthetic initial question", catalog.a);
    await followCitation(page, catalog.a);
    const same = await ask(page, guest, "Synthetic same-page question");
    expect(same.pageContextVersion).toBe(first.pageContextVersion);
    await followCitation(page, catalog.b);
    await expect(chip(page)).toHaveText(`About: ${catalog.b.name}`);
    await followCitation(page, catalog.a);
    await expect(chip(page)).toHaveText(`About: ${catalog.a.name}`);
    const returned = await ask(page, guest, "Synthetic return question");
    onlyContext(returned, "Synthetic return question", catalog.a);
    expect(returned.pageContextVersion).not.toBe(first.pageContextVersion);

    await followCitation(page, catalog.accessory);
    await expect(chip(page)).toHaveText(`About: ${catalog.accessory.name}`);
    const accessory = await ask(page, guest, "Synthetic accessory question");
    onlyContext(accessory, "Synthetic accessory question", catalog.accessory);
    expect(accessory.pageContextVersion).not.toBe(returned.pageContextVersion);
    await panel(page).getByRole("link", { name: "Continue shopping", exact: true }).click();
    await expect(page).toHaveURL("/");
    await launcher(page).click();
    await expect(chip(page)).toHaveCount(0);
    const home = await ask(page, guest, "Synthetic home question");
    onlyContext(home, "Synthetic home question");
    expect(home.pageContextVersion).not.toBe(accessory.pageContextVersion);
    expect(new Set([first, returned, accessory, home].map((payload) => payload.pageContextVersion)).size).toBe(4);
  } finally {
    await page.unroute(conversationEndpoint);
    await page.unroute(`${conversationEndpoint}/messages`);
  }
});
