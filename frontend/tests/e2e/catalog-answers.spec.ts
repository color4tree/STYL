import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const support = `${api}/api/support`;
const settings = `${api}/api/admin/support/config`;
const adminHeaders = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
type Item = {
  id: number; slug: string; name: string; itemType: "product" | "accessory";
  colourOptions: string; material: string;
};
type Catalog = { bench: Item; rack: Item; bar: Item };
type Guest = { id: string; token: string };
type Message = {
  id: string; role: string; text: string; needsHuman?: boolean;
  references: { type: string; id: number; label: string; url: string }[];
};
type Thread = {
  id: string; processing: boolean; needsHuman: boolean; needsHumanQuestions?: number;
  messages: Message[];
};
type Payload = { text: string; clientMessageId: string; itemRef?: string; pageContextVersion: string };
const href = (item: Item) => item.itemType === "product" ? `/products/${item.slug}` : `/accessories/${item.id}`;
const itemRef = (item: Item) => `${item.itemType}:${item.id}`;
const panel = (page: Page) => page.getByRole("dialog", { name: "STYL Assistant", exact: true });
const history = (page: Page) => panel(page).getByRole("log", { name: "Conversation messages", exact: true });
const composer = (page: Page) => panel(page).getByRole("textbox", { name: "Your message", exact: true });
const contactForm = (page: Page) => panel(page).getByRole("form", { name: "Follow-up contact details" });
const guestHeaders = (guest: Guest) => ({ Authorization: `Bearer ${guest.token}` });
const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const compatible = {
  uprightSize: "3 × 3 in / 75 × 75 mm", holeDiameter: "1 in", holeSpacing: "", models: "", limitations: "",
};

// SUP-027/028: real isolated catalog/chat persistence with the runner's mock provider.
// These values are synthetic fixtures, not claims about any saleable STYL item.
const test = base.extend<{ catalog: Catalog }>({
  catalog: [async ({ request }, run) => {
    const directory = process.env.STYL_E2E_DATA_DIR;
    if (!directory || !path.isAbsolute(directory) || !path.basename(directory).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) {
      throw new Error("Catalog-answer tests require the isolated E2E API, never the local catalog mirror.");
    }
    const config = await request.get(`${support}/config`);
    expect(config.status()).toBe(200);
    expect(await config.json()).toMatchObject({ provider: "mock", model: "mock", environment: "test", localTestingOnly: true });
    const before = await request.get(settings, { headers: adminHeaders });
    expect(before.status()).toBe(200);
    const previous = await before.json();
    const enabled = await request.put(settings, { headers: adminHeaders, data: {
      enabled: true, allowedTopics: ["products", "pricing", "compatibility"], expectedRevision: previous.revision,
    } });
    expect(enabled.status()).toBe(200);
    const created: Item[] = [];
    try {
      const categories = await request.get(`${api}/api/admin/categories`, { headers: adminHeaders });
      expect(categories.status()).toBe(200);
      expect((await categories.json()).items).toEqual(expect.arrayContaining(["Benches", "Racks", "Handle"]));
      const suffix = randomUUID().slice(0, 8).replace(/\d/g, (digit) => String.fromCharCode(103 + Number(digit)));
      const fixtures = [
        { itemType: "product", name: `STYL Atlas Bench ${suffix}`, category: "Benches", price: 314.25,
          colourOptions: "matte teal", material: "upholstered steel", weight: "" },
        { itemType: "product", name: `STYL Meridian Rack ${suffix}`, category: "Racks", price: 628.5,
          colourOptions: "ember red", material: "structural steel", weight: "50 kg", compatibility: compatible },
        { itemType: "accessory", name: `STYL Orbit Rack Bar ${suffix}`, category: "Handle", price: 82.75,
          colourOptions: "cobalt blue", material: "stainless steel", weight: "12 kg", compatibility: compatible },
      ] as const;
      for (const { itemType, price, ...fields } of fixtures) {
        const response = await request.post(`${api}/api/${itemType === "product" ? "products" : "accessories"}`, {
          headers: adminHeaders, data: {
            ...fields, publicationStatus: "published", prices: { CAD: price, USD: price },
            shortDescription: "Synthetic catalog-answer fixture.",
            description: "Synthetic fixture for isolated customer field-answer checks.", photos: [],
          },
        });
        expect(response.status(), await response.text()).toBe(200);
        created.push({ ...(await response.json()).item, itemType });
      }
      await run({ bench: created[0], rack: created[1], bar: created[2] });
    } finally {
      for (const item of created) {
        const removed = await request.delete(`${api}/api/${item.itemType === "product" ? "products" : "accessories"}/${item.id}`, { headers: adminHeaders });
        expect(removed.ok()).toBe(true);
      }
      const current = await request.get(settings, { headers: adminHeaders });
      expect(current.status()).toBe(200);
      const reset = await request.put(settings, { headers: adminHeaders, data: {
        enabled: previous.enabled, allowedTopics: previous.allowedTopics, expectedRevision: (await current.json()).revision,
      } });
      expect(reset.status()).toBe(200);
    }
  }, { auto: true }],
});

async function start(page: Page, item: Item): Promise<Guest> {
  await page.goto(href(item));
  await expect(page.getByRole("heading", { level: 1, name: item.name, exact: true })).toBeVisible();
  await page.getByRole("button", { name: /^Ask STYL chat/ }).click();
  await expect(panel(page).getByLabel("Current page item", { exact: true })).toHaveText(`About: ${item.name}`);
  const created = page.waitForResponse((response) => response.url() === `${support}/conversations` && response.request().method() === "POST");
  await panel(page).getByRole("button", { name: "Start conversation", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const value = await response.json();
  await expect(composer(page)).toBeVisible();
  return { id: value.conversation.id, token: value.token };
}

async function thread(request: APIRequestContext, guest: Guest): Promise<Thread> {
  const response = await request.get(`${support}/conversations/${guest.id}`, { headers: guestHeaders(guest) });
  expect(response.status(), await response.text()).toBe(200);
  return response.json();
}

async function ask(page: Page, request: APIRequestContext, guest: Guest, text: string) {
  await composer(page).fill(text);
  const sent = page.waitForResponse((response) => response.url() === `${support}/conversations/${guest.id}/messages` && response.request().method() === "POST");
  await panel(page).getByRole("button", { name: "Send message", exact: true }).click();
  const response = await sent;
  expect(response.status(), await response.text()).toBe(200);
  const payload = response.request().postDataJSON() as Payload;
  expect(payload.pageContextVersion).toMatch(/^[0-9a-f-]{36}$/);
  const accepted = await response.json() as Thread;
  const question = accepted.messages.filter((message) => message.role === "customer").at(-1)!;
  expect(question.text).toBe(text);
  await expect(composer(page)).toHaveValue("");
  await expect.poll(async () => {
    const current = await thread(request, guest);
    const index = current.messages.findIndex((message) => message.id === question.id);
    return !current.processing && index >= 0 && current.messages.length > index + 1;
  }).toBe(true);
  const saved = await thread(request, guest);
  const questionIndex = saved.messages.findIndex((message) => message.id === question.id);
  const reply = saved.messages.slice(questionIndex + 1).find((message) => message.role === "assistant")
    ?? saved.messages.slice(questionIndex + 1).at(-1)!;
  const bubble = history(page).locator(`#support-message-${reply.id}`);
  await expect(bubble).toBeVisible();
  await expect(bubble).not.toContainText(/insufficient_evidence|unsupported_field|page_context_changed|answerPlan|pageContextVersion/);
  expect(saved).not.toHaveProperty("answerPlan");
  for (const message of saved.messages) expect(message).not.toHaveProperty("answerPlan");
  return { payload, question: saved.messages[questionIndex], reply, saved, bubble };
}

async function citedAnswer(page: Page, result: Awaited<ReturnType<typeof ask>>, item: Item) {
  expect(result.reply.role).toBe("assistant");
  expect(result.reply.references).toContainEqual(expect.objectContaining({ type: item.itemType, id: item.id, url: href(item) }));
  await expect(result.bubble.getByRole("link", { name: item.name, exact: true })).toHaveAttribute("href", href(item));
  await expect(panel(page).getByRole("button", { name: /Ask for human help|Refresh conversation/ })).toHaveCount(0);
}

for (const kind of ["bench", "rack", "bar"] as const) {
  test(`SUP-027 CAT-001 (${kind}): explicit color and material facts answer across catalog categories with STYL omitted`, async ({ page, request, catalog }) => {
    const item = catalog[kind];
    const guest = await start(page, item);
    const result = await ask(page, request, guest, `What are the color and material of ${item.name.replace(/^STYL /, "")}?`);
    await citedAnswer(page, result, item);
    expect(result.payload.itemRef).toBe(itemRef(item));
    expect(result.reply.text).toMatch(new RegExp(escapeRegExp(item.colourOptions), "i"));
    expect(result.reply.text).toMatch(new RegExp(escapeRegExp(item.material), "i"));
    expect(result.saved.needsHuman).toBe(false);
    expect(result.question.needsHuman).not.toBe(true);
    await expect(contactForm(page)).toHaveCount(0);
  });
}

test("SUP-027 CAT-002: known price survives unknown weight as an assistant partial answer and its team flag survives a later answer", async ({ page, request, catalog }) => {
  const guest = await start(page, catalog.bench);
  const partial = await ask(page, request, guest, "What are its price and weight?");
  await citedAnswer(page, partial, catalog.bench);
  expect(partial.reply.text).toContain("314.25");
  expect(partial.reply.text).toMatch(/weight/i);
  expect(partial.reply.text).toMatch(/team|not (?:listed|available|confirmed|provided|published)|unknown|cannot confirm|can't confirm/i);
  expect(partial.reply.text).not.toMatch(/\b(?:50|12)\s*kg/i);
  expect(partial.saved.needsHuman).toBe(true);
  expect(partial.question.needsHuman).toBe(true);
  await expect(contactForm(page)).toBeVisible();
  const later = await ask(page, request, guest, "What is its color?");
  await citedAnswer(page, later, catalog.bench);
  expect(later.reply.text).toContain(catalog.bench.colourOptions);
  expect(later.saved.messages.find((message) => message.id === partial.question.id)?.needsHuman).toBe(true);
  expect(later.saved.needsHuman).toBe(true);
  expect(later.saved.needsHumanQuestions).toBe(1);
  await expect(contactForm(page)).toBeVisible();
  await expect(panel(page)).toContainText("Your request has been sent to our team.");
});

test("SUP-027 CAT-003: known own weight never becomes an unknown safe load or weight capacity", async ({ page, request, catalog }) => {
  const guest = await start(page, catalog.rack);
  const result = await ask(page, request, guest, "What are its own weight and maximum safe load capacity?");
  await citedAnswer(page, result, catalog.rack);
  expect(result.reply.text).toMatch(/50\s*kg/i);
  expect(result.reply.text).toMatch(/weigh(?:t|s)/i);
  expect(result.reply.text).toMatch(/load|capacity/i);
  expect(result.reply.text).toMatch(/team|not (?:listed|available|confirmed|provided|published)|unknown|cannot confirm|can't confirm/i);
  expect(result.reply.text).not.toMatch(/(?:capacity|safe load|load limit|maximum load)\s*(?:is|of|:|=)?\s*50\s*kg/i);
  expect(result.saved.needsHuman).toBe(true);
  expect(result.question.needsHuman).toBe(true);
  await expect(contactForm(page)).toBeVisible();
});

test("SUP-027 CAT-004: direct upright size and hole diameter facts do not demand a customer rack model", async ({ page, request, catalog }) => {
  const guest = await start(page, catalog.rack);
  for (const question of ["What are its upright size and hole diameter?", "What is the compatible upright size?", "what the compatible upright size"]) {
    const result = await ask(page, request, guest, question);
    await citedAnswer(page, result, catalog.rack);
    expect(result.reply.text).toMatch(/3\s*[×x]\s*3\s*(?:in|inch)/i);
    expect(result.reply.text).toMatch(/75\s*[×x]\s*75\s*mm/i);
    expect(result.reply.text).toMatch(/1\s*(?:in\b|inch)/i);
    expect(result.reply.text).not.toMatch(/(?:what|which|provide|tell me|could you share).{0,60}(?:your|customer).{0,30}(?:rack|model|equipment)/i);
    expect(result.saved.needsHuman).toBe(false);
  }
  await expect(contactForm(page)).toHaveCount(0);
});

test("SUP-028 CAT-005: conditional 3x3 fit asks for the missing hole and a same-item 1 inch reply completes it", async ({ page, request, catalog }) => {
  const guest = await start(page, catalog.bar);
  const pending = await ask(page, request, guest, "Will it fit my 3x3 rack?");
  expect(pending.reply.role).toBe("assistant");
  expect(pending.reply.text).toMatch(/hole|diameter/i);
  expect(pending.reply.text).toMatch(/\?|provide|tell|need|confirm/i);
  expect(pending.saved.needsHuman).toBe(false);
  const completed = await ask(page, request, guest, "1 inch");
  await citedAnswer(page, completed, catalog.bar);
  expect(completed.payload.pageContextVersion).toBe(pending.payload.pageContextVersion);
  expect(completed.reply.text).toMatch(/fit|compatib|match/i);
  expect(completed.reply.text).toMatch(/3\s*[×x]\s*3/i);
  expect(completed.reply.text).toMatch(/1\s*(?:in\b|inch)/i);
  expect(completed.reply.text).not.toMatch(/(?:what|which).{0,35}(?:hole|diameter)|(?:need|provide).{0,25}hole/i);
  expect(completed.saved.needsHuman).toBe(false);
  await expect(contactForm(page)).toHaveCount(0);
});

for (const kind of ["rack", "bar"] as const) {
  test(`SUP-028 CAT-006 (${kind}): after navigating to Bench a tiny 1 inch reply cannot finish the old item fit clarification`, async ({ page, request, catalog }) => {
    const item = catalog[kind];
    const guest = await start(page, item);
    // Obtain a real citation for client-side navigation before opening the fit question.
    const bench = await ask(page, request, guest, `What is the color of ${catalog.bench.name}?`);
    await citedAnswer(page, bench, catalog.bench);
    const pending = await ask(page, request, guest, `Will ${item.name} fit my 3x3 rack?`);
    expect(pending.reply.role).toBe("assistant");
    expect(pending.reply.text).toMatch(/hole|diameter/i);
    await history(page).getByRole("link", { name: catalog.bench.name, exact: true }).last().click();
    await expect(page).toHaveURL(new RegExp(`${href(catalog.bench)}$`));
    await expect(panel(page).getByLabel("Current page item", { exact: true })).toHaveText(`About: ${catalog.bench.name}`);
    const afterNavigation = await ask(page, request, guest, "1 inch");
    expect(afterNavigation.payload.itemRef).toBe(itemRef(catalog.bench));
    expect(afterNavigation.payload.pageContextVersion).not.toBe(pending.payload.pageContextVersion);
    expect(afterNavigation.reply.references).not.toContainEqual(expect.objectContaining({ type: item.itemType, id: item.id }));
    expect(afterNavigation.reply.text).not.toContain(item.name);
    expect(afterNavigation.reply.text).not.toMatch(/(?:fits?|compatible|match(?:es)?)\s+(?:with\s+)?your\s+(?:3\s*[×x]\s*3\s+)?rack/i);
    expect(afterNavigation.reply.text).not.toMatch(/3\s*[×x]\s*3/);
  });
}

test("SUP-027 CAT-007: a compound two-product color question preserves each product and color association", async ({ page, request, catalog }) => {
  const guest = await start(page, catalog.bar);
  const result = await ask(page, request, guest, `What are the colors of ${catalog.bench.name} and ${catalog.rack.name}?`);
  await citedAnswer(page, result, catalog.bench);
  await citedAnswer(page, result, catalog.rack);
  const ordered = [catalog.bench, catalog.rack].map((item) => ({ item, index: result.reply.text.indexOf(item.name) }))
    .sort((left, right) => left.index - right.index);
  expect(ordered.every(({ index }) => index >= 0)).toBe(true);
  for (const [index, entry] of ordered.entries()) {
    const associated = result.reply.text.slice(entry.index, ordered[index + 1]?.index);
    const other = entry.item.id === catalog.bench.id ? catalog.rack : catalog.bench;
    expect(associated).toMatch(new RegExp(escapeRegExp(entry.item.colourOptions), "i"));
    expect(associated).not.toMatch(new RegExp(escapeRegExp(other.colourOptions), "i"));
  }
  expect(result.reply.text).not.toContain(catalog.bar.colourOptions);
  expect(result.saved.needsHuman).toBe(false);
});
