import { test as base, expect, type Page, type Locator } from "@playwright/test";
import { randomUUID } from "node:crypto";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const publicApi = `${api}/api/support`;
type Message = { id: string; role: "customer" | "assistant" | "human" | "system"; text: string; createdAt: string; replyTo?: { id: string; text: string } | null; needsHuman?: boolean; humanReason?: string | null; answeredBy?: string | null; references: { type: string; id: number; label: string; url: string }[] };
type Thread = { id: string; state: string; revision: number; createdAt: string; updatedAt: string; currency: string; needsHuman: boolean; reason: string | null; processing: boolean; messages: Message[] };
type Chat = { thread: Thread; requests: string[]; starts: number; append: (role: Message["role"], text: string) => void };
type Product = { id: number; name: string; slug: string };

const test = base.extend<{ chat: Chat; product: Product }>({
  chat: [async ({ page, request }, run) => {
    const directory = process.env.STYL_E2E_DATA_DIR;
    if (!directory || !path.isAbsolute(directory) || !path.basename(directory).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) throw new Error("Widget tests require the isolated E2E API, never the local catalog mirror.");
    const response = await request.get(`${publicApi}/config`);
    expect(response.status()).toBe(200);
    const config = await response.json();
    expect(config).toMatchObject({ provider: "mock", model: "mock", environment: "test", localTestingOnly: true });
    const now = new Date().toISOString();
    const token = `synthetic-widget-${randomUUID()}`;
    const chat: Chat = {
      thread: { id: randomUUID(), revision: 0, state: "ai", createdAt: now, updatedAt: now, currency: "CAD", needsHuman: false, reason: null, processing: false, messages: [] },
      requests: [], starts: 0,
      append(role, text) {
        chat.thread.messages.push({ id: randomUUID(), role, text, createdAt: new Date().toISOString(), references: [] });
        chat.thread.revision++;
      },
    };
    await page.route(`${publicApi}/**`, async (route) => {
      const method = route.request().method();
      const suffix = new URL(route.request().url()).pathname.slice("/api/support".length);
      chat.requests.push(`${method} ${suffix}`);
      if (suffix === "/config") return route.fulfill({ json: { ...config, enabled: true, aiEnabled: true, notice: "INTERNAL_NOTICE: STYL_SUPPORT_MODEL=private-model; environment=test; provider=mock; allowed scope products." } });
      if (suffix === "/conversations" && method === "POST") {
        chat.starts++;
        return route.fulfill({ status: 201, json: { conversation: chat.thread, token } });
      }
      expect(route.request().headers().authorization).toBe(`Bearer ${token}`);
      if (suffix.endsWith("/messages") && method === "POST") {
        chat.append("customer", route.request().postDataJSON().text);
        return route.fulfill({ json: chat.thread });
      }
      if (suffix.endsWith("/handoff")) {
        chat.thread.state = "waiting_human"; chat.thread.needsHuman = true; chat.thread.reason = "customer_request"; chat.thread.revision++;
      }
      return route.fulfill({ json: chat.thread });
    });
    await run(chat);
  }, { auto: true }],
  product: async ({ request }, run) => {
    const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
    const response = await request.post(`${api}/api/products`, { headers, data: {
      name: `Synthetic widget rack ${randomUUID().slice(0, 8)}`, category: "Racks", publicationStatus: "published",
      prices: { CAD: 125.5, USD: 100.25 }, shortDescription: "Synthetic chat layout fixture.",
      description: "Synthetic equipment for isolated navigation, gallery and sticky cart checks.", photos: ["/images/pro-elite.svg"],
    } });
    expect(response.status(), await response.text()).toBe(200);
    const product = (await response.json()).item as Product;
    try { await run(product); } finally {
      const removed = await request.delete(`${api}/api/products/${product.id}`, { headers });
      expect(removed.ok()).toBe(true);
    }
  },
});

const dialog = (page: Page) => page.getByRole("dialog", { name: "STYL Assistant", exact: true });
const launcher = (page: Page) => page.getByRole("button", { name: /^Ask STYL chat/ });
const history = (page: Page) => page.getByRole("log", { name: "Conversation messages", exact: true });
const input = (page: Page) => page.getByRole("textbox", { name: "Your message", exact: true });
async function start(page: Page) {
  await launcher(page).click();
  await page.getByRole("button", { name: "Start conversation", exact: true }).click();
  await expect(input(page)).toBeVisible();
}
async function refresh(page: Page) {
  await expect(page.getByRole("button", { name: "Refresh conversation", exact: true })).toHaveCount(0);
  await page.waitForResponse((value) => /\/api\/support\/conversations\/[^/]+$/.test(value.url()) && value.request().method() === "GET");
}
async function nonOverlapping(first: Locator, second: Locator) {
  await expect.poll(async () => {
    const a = await first.boundingBox(), b = await second.boundingBox();
    return Boolean(a && b && (a.y + a.height <= b.y || b.y + b.height <= a.y || a.x + a.width <= b.x || b.x + b.width <= a.x));
  }).toBe(true);
}

test("SUP-011 WIDGET-001: global avatar is opt-in, keyboard operable, nonmodal, and support links do not navigate away", async ({ page, chat, product, browserName }) => {
  await page.goto(`/products/${product.slug}`);
  await expect(page.getByRole("heading", { level: 1, name: product.name })).toBeVisible();
  await expect(launcher(page)).toBeVisible();
  await expect(dialog(page)).not.toBeVisible();
  expect(chat.requests).toEqual([]);
  await launcher(page).focus();
  await page.keyboard.press("Enter");
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page)).toHaveAttribute("aria-modal", "false");
  await expect(page.getByRole("button", { name: "Minimize chat" })).toBeFocused();
  await page.keyboard.press("Tab");
  // WebKit's default Tab traversal skips links; its next control is the start button.
  await expect(browserName === "webkit"
    ? dialog(page).getByRole("button", { name: "Start conversation", exact: true })
    : dialog(page).getByRole("link", { name: "Privacy", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog(page)).not.toBeVisible();
  await expect(launcher(page)).toBeFocused();
  const url = page.url();
  await page.getByRole("contentinfo").getByRole("link", { name: "Ask STYL", exact: true }).click();
  await expect(dialog(page)).toBeVisible();
  expect(page.url()).toBe(url);
  expect(chat.starts).toBe(0);
  await expect(dialog(page).getByRole("complementary", { name: "Local testing notice" })).toHaveCount(0);
  await expect(dialog(page)).not.toContainText(/Local preview|do not share personal information/i);
  await expect(dialog(page).getByRole("button", { name: /Ask for human help|Refresh conversation/ })).toHaveCount(0);
  await expect(dialog(page)).not.toContainText("INTERNAL_NOTICE");
  await expect(dialog(page)).not.toContainText("Approved AI scope");
  await expect(dialog(page).getByRole("link", { name: "Privacy", exact: true })).toHaveAttribute("href", "/privacy");
  await expect(dialog(page).locator('input[type="file"]')).toHaveCount(0);
});

test("SUP-011 WIDGET-002: conversation, open/minimized state and draft survive Next navigation without creating another guest", async ({ page, chat, product }) => {
  await page.goto("/");
  await start(page);
  await input(page).fill("Synthetic question");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(input(page)).toHaveValue("");
  chat.append("assistant", "Synthetic catalog answer.");
  chat.thread.messages.at(-1)!.references = [{ type: "product", id: product.id, label: product.name, url: `/products/${product.slug}` }];
  await refresh(page);
  await input(page).fill("Unsent synthetic navigation draft");
  const bubble = history(page).locator('[data-support-role="assistant"]').last();
  const sources = bubble.locator("details").filter({ has: page.locator("summary", { hasText: /^Sources$/ }) });
  await expect(sources.locator("summary")).toBeVisible();
  await expect(sources).not.toHaveAttribute("open");
  await expect(sources.getByRole("link", { name: product.name, exact: true, includeHidden: true })).toBeHidden();
  expect(await bubble.innerText()).not.toContain(product.name);
  await sources.locator("summary").click();
  await sources.getByRole("link", { name: product.name, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/products/${product.slug}$`));
  await expect(dialog(page)).toBeVisible();
  await expect(input(page)).toHaveValue("Unsent synthetic navigation draft");
  await expect(history(page)).toContainText("Synthetic catalog answer.");
  await page.getByRole("button", { name: "Minimize chat" }).click();
  await page.getByRole("link", { name: "Cart (0)", exact: true }).click();
  await expect(page).toHaveURL(/\/cart$/);
  await expect(dialog(page)).not.toBeVisible();
  await launcher(page).click();
  await expect(input(page)).toHaveValue("Unsent synthetic navigation draft");
  await expect(history(page)).toContainText("Synthetic question");
  expect(chat.starts).toBe(1);
  expect(chat.requests.filter((request) => request === "GET /config")).toHaveLength(1);
});

test("SUP-011 WIDGET-003: customer bubbles are measurably left and labeled AI/human bubbles right at desktop, 390 and 320", async ({ page, chat }, testInfo) => {
  await page.goto("/");
  await start(page);
  chat.append("customer", "Synthetic customer message of equal length.");
  chat.append("assistant", "Synthetic AI response of comparable length.");
  chat.append("human", "Synthetic human reply of comparable length.");
  await refresh(page);
  for (const width of testInfo.project.name.startsWith("phone") ? [390, 320] : [1440]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(dialog(page)).toBeVisible();
    await expect.poll(async () => {
      const box = await dialog(page).boundingBox();
      return Boolean(box && box.x >= 8 && box.x + box.width <= width - 8 && (width > 390 || box.width > width * 0.85));
    }).toBe(true);
    const panel = (await dialog(page).boundingBox())!;
    expect(panel.x).toBeGreaterThanOrEqual(8);
    expect(panel.x + panel.width).toBeLessThanOrEqual(width - 8);
    expect(panel.y).toBeGreaterThan(100);
    expect(panel.y + panel.height).toBeLessThanOrEqual(844 - 8);
    expect(panel.height).toBeLessThan(844 * 0.8);
    if (width <= 390) expect(panel.width).toBeGreaterThan(width * 0.85);
    await history(page).scrollIntoViewIfNeeded();
    const customer = history(page).locator('[data-support-role="customer"]');
    const ai = history(page).locator('[data-support-role="assistant"]');
    const human = history(page).locator('[data-support-role="human"]');
    await expect(customer.getByText("You", { exact: true })).toBeVisible();
    await expect(ai).toContainText("STYL Assistant");
    await expect(human).toContainText("STYL team");
    const c = (await customer.boundingBox())!, a = (await ai.boundingBox())!, h = (await human.boundingBox())!;
    expect(c.x).toBeLessThan(a.x);
    expect(c.x).toBeLessThan(h.x);
    expect(c.x + c.width).toBeLessThan(a.x + a.width);
    expect(c.x + c.width).toBeLessThan(h.x + h.width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(await dialog(page).evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await input(page).fill("x".repeat(2000));
    await expect(page.getByRole("button", { name: "Send message", exact: true })).toBeEnabled();
    expect(await input(page).evaluate((element) => getComputedStyle(element).fontSize)).toBe("16px");
    expect(await dialog(page).evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  }
});

test("SUP-011 WIDGET-004: minimized incoming badges never open chat, and old-history reading preserves position until explicit jump", async ({ page, chat }) => {
  await page.goto("/");
  await start(page);
  await page.getByRole("button", { name: "Minimize chat" }).click();
  chat.append("assistant", "Incoming while minimized.");
  await expect(launcher(page)).toHaveAccessibleName("Ask STYL chat, 1 unread message");
  await expect(dialog(page)).not.toBeVisible();
  await launcher(page).click();
  await expect(history(page)).toContainText("Incoming while minimized.");
  await expect(page.getByRole("button", { name: "Jump to latest messages" })).toHaveCount(0);
  for (let i = 0; i < 25; i++) chat.append("assistant", `Synthetic historical message ${i}.`);
  await refresh(page);
  await expect(history(page)).toContainText("Synthetic historical message 24.");
  await history(page).evaluate((element) => { element.scrollTop = 0; element.dispatchEvent(new Event("scroll")); });
  chat.append("human", "A new human reply while reading old history.");
  await refresh(page);
  await expect(page.getByRole("button", { name: "Jump to latest messages" })).toBeVisible();
  expect(await history(page).evaluate((element) => element.scrollTop)).toBe(0);
  await page.getByRole("button", { name: "Minimize chat" }).click();
  await expect(launcher(page)).toHaveAccessibleName("Ask STYL chat, 1 unread message");
  await launcher(page).click();
  expect(await history(page).evaluate((element) => element.scrollTop)).toBe(0);
  await page.getByRole("button", { name: "Jump to latest messages" }).click();
  await expect.poll(() => history(page).evaluate((element) => element.scrollHeight - element.scrollTop - element.clientHeight)).toBeLessThan(2);
  await page.getByRole("button", { name: "Minimize chat" }).click();
  await expect(launcher(page)).toHaveAccessibleName("Ask STYL chat");
});

test("SUP-011 WIDGET-005: only pending responses animate; reduced motion disables animation without hiding status", async ({ page, chat }) => {
  await page.goto("/");
  await start(page);
  chat.thread.processing = true; chat.thread.revision++;
  await refresh(page);
  await expect(dialog(page).getByRole("status")).toHaveText("Preparing a reply…");
  await page.getByRole("button", { name: "Minimize chat" }).click();
  await expect(launcher(page)).toHaveAccessibleName("Ask STYL chat, responding");
  await expect(launcher(page).locator("svg")).toHaveCSS("animation-name", "support-responding");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(launcher(page).locator("svg")).toHaveCSS("animation-name", "none");
  await expect(launcher(page)).toHaveAccessibleName("Ask STYL chat, responding");
  chat.thread.processing = false; chat.thread.revision++;
  await expect(launcher(page)).toHaveAccessibleName("Ask STYL chat");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(launcher(page).locator("svg")).toHaveCSS("animation-name", "none");
});

test("SUP-011 WIDGET-006: widget is entirely absent from admin and guest polling aborts when leaving the storefront", async ({ page, chat }) => {
  await page.goto("/admin");
  await expect(page.getByLabel("Admin token", { exact: true })).toBeVisible();
  await expect(page.locator("[data-support-widget]")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Ask STYL", exact: true })).toHaveCount(0);
  expect(chat.requests).toEqual([]);
  await page.goto("/");
  await start(page);
  await page.getByRole("button", { name: "Minimize chat" }).click();
  await page.goto("/admin");
  await expect(page.locator("[data-support-widget]")).toHaveCount(0);
  const reads = chat.requests.length;
  await page.clock.install();
  await page.clock.fastForward(8000);
  expect(chat.requests).toHaveLength(reads);
});

test("SUP-011 WIDGET-007: chat clears sticky cart/quote bars and yields to gallery/menu modals without losing draft", async ({ page, request, product }, testInfo) => {
  const extended = await request.put(`${api}/api/products/${product.id}`, {
    headers: { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` },
    data: { name: product.name, category: "Racks", description: Array.from({ length: 24 }, () => "Synthetic long product details provide enough scrolling space to exercise the sticky purchase controls.").join("\n\n") },
  });
  expect(extended.status(), await extended.text()).toBe(200);
  await page.goto(`/products/${product.slug}`);
  await expect(page.getByRole("heading", { level: 1, name: product.name })).toBeVisible();
  await start(page);
  await input(page).fill("Synthetic draft retained around modals");
  if (testInfo.project.name.startsWith("phone")) {
    await page.getByRole("button", { name: "Menu", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Site navigation", exact: true })).toBeVisible();
    await expect(page.locator("[data-support-widget]")).toBeHidden();
    await page.getByRole("navigation", { name: "Mobile navigation", exact: true }).getByRole("link", { name: "Ask STYL", exact: true }).click();
    await expect(dialog(page)).toBeVisible();
    await expect(input(page)).toHaveValue("Synthetic draft retained around modals");
  }
  await page.getByRole("button", { name: "Minimize chat" }).click();
  await page.getByRole("button", { name: `Enlarge ${product.name} media 1`, exact: true }).click();
  await expect(page.getByRole("dialog", { name: `${product.name} enlarged media`, exact: true })).toBeVisible();
  await expect(page.locator("[data-support-widget]")).toBeHidden();
  await page.getByRole("button", { name: "Close enlarged media", exact: true }).click();
  await expect(launcher(page)).toBeVisible();
  if (testInfo.project.name.startsWith("phone")) {
    await page.getByRole("contentinfo").scrollIntoViewIfNeeded();
    await expect(page.locator("main").getByRole("button", { name: "Add to cart", exact: true }).first()).not.toBeInViewport();
    const bar = page.locator(".safe-action");
    await expect(bar).toBeVisible();
    await nonOverlapping(launcher(page), bar);
    await launcher(page).click();
    await nonOverlapping(dialog(page), bar);
    await page.getByRole("button", { name: "Minimize chat" }).click();
    await bar.getByRole("button", { name: "Add to cart", exact: true }).click();
    await page.getByRole("link", { name: "Cart (1)", exact: true }).click();
    await expect(page).toHaveURL(/\/cart$/);
    const quoteBar = page.locator(".safe-action");
    await expect(quoteBar.getByRole("link", { name: "Request a quote", exact: true })).toBeVisible();
    await nonOverlapping(launcher(page), quoteBar);
    await launcher(page).click();
    await nonOverlapping(dialog(page), quoteBar);
  } else await launcher(page).click();
  await expect(input(page)).toHaveValue("Synthetic draft retained around modals");
});

test("SUP-011 WIDGET-008: visual viewport keyboard resize keeps the panel anchored with visible webpage and reachable composer", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await start(page);
  await input(page).focus();
  await page.evaluate(() => {
    const viewport = window.visualViewport!;
    Object.defineProperty(viewport, "height", { configurable: true, value: 420 });
    Object.defineProperty(viewport, "offsetTop", { configurable: true, value: 40 });
    viewport.dispatchEvent(new Event("resize"));
    viewport.dispatchEvent(new Event("scroll"));
  });
  await expect.poll(async () => {
    const box = await dialog(page).boundingBox();
    return Boolean(box && box.y >= 40 && box.y + box.height <= 460 && box.height < 420);
  }).toBe(true);
  await input(page).fill("Synthetic keyboard draft");
  await input(page).scrollIntoViewIfNeeded();
  const composer = (await input(page).boundingBox())!;
  expect(composer.y).toBeGreaterThanOrEqual(40);
  expect(composer.y + composer.height).toBeLessThanOrEqual(460);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(input(page)).toHaveValue("");
  await page.evaluate(() => {
    const viewport = window.visualViewport!;
    Reflect.deleteProperty(viewport, "height");
    Reflect.deleteProperty(viewport, "offsetTop");
    viewport.dispatchEvent(new Event("resize"));
  });
  await expect.poll(async () => {
    const box = await dialog(page).boundingBox();
    return Boolean(box && box.y + box.height > 800 && box.y > 100);
  }).toBe(true);
});

test("SUP-002 SUP-011 WIDGET-009: pending requests use neutral copy, legacy history stays stored and team messages do not replace the assistant", async ({ page, chat }) => {
  await page.goto("/");
  await start(page);
  await expect(input(page)).toHaveAttribute("placeholder", "Ask about our products...");
  chat.thread.state = "waiting_human";
  chat.thread.needsHuman = true;
  chat.thread.reason = "provider_unavailable: STYL_SUPPORT_MODEL=private-model";
  const legacy = "Your message is saved. Human help has been requested; AI replies are paused.";
  chat.append("system", legacy);
  await refresh(page);
  await expect(dialog(page).getByRole("status")).toHaveText("STYL Assistant");
  await expect(history(page)).toContainText("Your request has been sent to our team.");
  await expect(dialog(page)).toContainText("You can keep asking questions.");
  await expect(dialog(page)).not.toContainText(legacy);
  expect(chat.thread.messages[0].text).toBe(legacy);
  const ordinaryText = await dialog(page).evaluate((element) => {
    const copy = element.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("details").forEach((details) => details.remove());
    return copy.textContent;
  });
  expect(ordinaryText).not.toMatch(/provider|Gemini|model|environment|scope|Reason:|AI paused|AI replies are paused|real agent contacted|STYL team/i);
  await input(page).fill("What products do you offer?");
  await expect(page.getByRole("button", { name: "Send message", exact: true })).toBeEnabled();
  chat.thread.processing = true; chat.thread.revision++;
  await refresh(page);
  await expect(dialog(page).getByRole("status")).toHaveText("Preparing a reply…");
  chat.thread.processing = false;
  chat.thread.state = "human";
  chat.append("human", "Hello, how can we help?");
  await refresh(page);
  await expect(dialog(page).getByRole("status")).toHaveText("STYL Assistant");
  await expect(history(page).locator('[data-support-role="human"]')).toContainText("STYL team");
  await expect(dialog(page)).toContainText("You can keep asking questions.");
  await expect(input(page)).toHaveValue("What products do you offer?");
});

test("SUP-017 WIDGET-012: quoted team replies preserve exact escaped questions, expand long quotes and never infer quotes for legacy history", async ({ page, chat }, testInfo) => {
  await page.goto("/");
  await start(page);
  const question = '<img src=x onerror="alert(1)"> Is this fictional item compatible?\n' + "Synthetic full question context. ".repeat(10) + "The final clause must stay available.";
  chat.append("customer", question);
  const original = chat.thread.messages.at(-1)!;
  chat.append("human", "Legacy team response with no recorded question.");
  chat.append("human", "This reply addresses the full original question.");
  const response = chat.thread.messages.at(-1)!;
  response.replyTo = { id: original.id, text: original.text };
  await refresh(page);
  const replies = history(page).locator('[data-support-role="human"]');
  await expect(replies.first().getByRole("blockquote")).toHaveCount(0);
  const quote = replies.last().getByRole("blockquote", { name: "Quoted customer question" });
  await expect(quote).toHaveAttribute("data-reply-to", original.id);
  await expect(quote.locator("details")).not.toHaveAttribute("open");
  await expect(quote.locator("summary")).toContainText(question.slice(0, 200));
  await expect(quote.locator("summary")).not.toContainText("The final clause");
  await expect(quote.locator("img")).toHaveCount(0);
  await quote.getByText("Show full question", { exact: true }).click();
  await expect(quote.locator("details > p")).toHaveText(question);
  await expect(replies.last()).toContainText("STYL team");
  const children = await replies.last().evaluate((element) => Array.from(element.children).map((child) => child.tagName));
  expect(children.indexOf("BLOCKQUOTE")).toBeLessThan(children.lastIndexOf("P"));
  expect(chat.thread.messages.find((message) => message.id === original.id)?.text).toBe(question);
  await expect(history(page).locator(`#support-message-${original.id}`)).toHaveCount(1);
  for (const width of testInfo.project.name.startsWith("phone") ? [390, 320] : [1440]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await dialog(page).evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("SUP-004 SUP-006 WIDGET-010: customer request failures show safe actionable copy and preserve drafts and retry IDs", async ({ page, chat }) => {
  await page.goto("/");
  await start(page);
  const endpoint = `${publicApi}/conversations/${chat.thread.id}/messages`;
  const attempts: { text: string; clientMessageId: string }[] = [];
  const draft = "What products do you offer?";
  const savedAccess = await page.evaluate(() => localStorage.getItem("styl-support-guest"));
  const failures = [
    { status: 429, copy: "Too many requests. Please wait a moment and try again." },
    { status: 413, copy: "Please check your message and keep it within 2,000 characters" },
    { status: 422, copy: "Please check your message and keep it within 2,000 characters" },
    { status: 503, copy: "We couldn't complete your request. Please try again." },
    { status: 200, copy: "We couldn't update this conversation." },
    { status: 0, copy: "Connection lost. Check your connection and try again." },
  ];
  await input(page).fill(draft);
  for (const failure of failures) {
    await page.route(endpoint, async (route) => {
      attempts.push(route.request().postDataJSON());
      if (!failure.status) return route.abort("failed");
      return route.fulfill({ status: failure.status, json: { detail: "INTERNAL_FAILURE: provider mock model unavailable, scope_disabled, STYL_SUPPORT_KEY, HTTP 503" } });
    });
    await page.getByRole("button", { name: "Send message", exact: true }).click();
    await expect(dialog(page).getByRole("alert")).toContainText(failure.copy);
    await expect(dialog(page)).not.toContainText("INTERNAL_FAILURE");
    await expect(dialog(page)).not.toContainText("HTTP 503");
    await expect(input(page)).toHaveValue(draft);
    expect(chat.thread.messages).toHaveLength(0);
    expect(await page.evaluate(() => localStorage.getItem("styl-support-guest"))).toBe(savedAccess);
    await page.unroute(endpoint);
  }
  expect(attempts).toHaveLength(failures.length);
  expect(new Set(attempts.map((attempt) => attempt.clientMessageId)).size).toBe(1);
  const sent = page.waitForResponse((response) => response.url() === endpoint && response.request().method() === "POST");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  expect((await sent).request().postDataJSON()).toEqual(attempts[0]);
  await expect(input(page)).toHaveValue("");
  await expect(history(page)).toContainText(draft);
  expect(chat.thread.messages).toHaveLength(1);
});

test("SUP-004 SUP-006 WIDGET-011: connection retry and automatic polling recover without refresh controls; lost access offers a new conversation", async ({ page, chat }) => {
  await page.goto("/");
  await start(page);
  const endpoint = `${publicApi}/conversations/${chat.thread.id}`;
  await input(page).fill("A question I have not sent yet");
  await page.route(endpoint, (route) => route.fulfill({ status: 503, json: { detail: "INTERNAL_FAILURE: provider_unavailable HTTP 503" } }));
  await expect(dialog(page).getByRole("button", { name: /Ask for human help|Refresh conversation/ })).toHaveCount(0);
  await expect(dialog(page).getByRole("alert")).toContainText("Messages may not be up to date.");
  await expect(dialog(page)).not.toContainText("Your request has been sent to our team.");
  await expect(dialog(page)).not.toContainText("INTERNAL_FAILURE");
  await expect(input(page)).toHaveValue("A question I have not sent yet");
  expect(chat.thread.needsHuman).toBe(false);
  await page.unroute(endpoint);
  chat.thread.needsHuman = true; chat.thread.revision++;
  await page.getByRole("button", { name: "Retry support connection", exact: true }).click();
  await expect(dialog(page)).toContainText("Your request has been sent to our team.");
  await expect(dialog(page).getByRole("status")).toHaveText("STYL Assistant");
  await expect(input(page)).toHaveValue("A question I have not sent yet");
  await page.route(endpoint, (route) => route.abort("failed"));
  await expect(dialog(page).getByRole("alert")).toContainText("Messages may not be up to date.");
  await page.unroute(endpoint);
  await expect(dialog(page).getByRole("alert")).toHaveCount(0);
  await expect(dialog(page).getByRole("button", { name: "Retry support connection" })).toHaveCount(0);
  await page.route(endpoint, (route) => route.fulfill({ status: 404, json: {} }));
  await expect(dialog(page).getByRole("button", { name: "New conversation", exact: true })).toBeVisible();
  await expect(input(page)).toHaveValue("A question I have not sent yet");
  await expect(dialog(page).getByRole("button", { name: "Send message", exact: true })).toBeDisabled();
  await page.unroute(endpoint);
  await page.getByRole("button", { name: "New conversation", exact: true }).click();
  await expect(input(page)).toHaveValue("");
  expect(chat.starts).toBe(2);
});

test("SUP-020 WIDGET-013: Enter retains composer focus and caret across success and failure; the next question needs no click", async ({ page, chat }) => {
  await page.goto("/");
  await start(page);
  const endpoint = `${publicApi}/conversations/${chat.thread.id}/messages`;
  let release = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(endpoint, async (route) => { await gate; await route.fallback(); });
  try {
    await input(page).fill("First synthetic question");
    await page.keyboard.press("Enter");
    await expect(input(page)).toHaveAttribute("readonly", "");
    await expect(input(page)).toBeFocused();
    await expect(input(page)).toBeEnabled();
    await page.keyboard.press("Enter");
    release();
    await expect(input(page)).toHaveValue("");
    await expect(input(page)).toBeFocused();
    await page.keyboard.type("Second synthetic question");
    await page.keyboard.press("Enter");
    await expect(input(page)).toHaveValue("");
    await expect(input(page)).toBeFocused();
    expect(chat.thread.messages.map((message) => message.text)).toEqual(["First synthetic question", "Second synthetic question"]);
  } finally { release(); await page.unroute(endpoint); }
  await page.route(endpoint, (route) => route.fulfill({ status: 503, json: {} }));
  await page.keyboard.type("Failed synthetic question");
  await page.keyboard.press("ArrowLeft");
  const selection = await input(page).evaluate((element: HTMLTextAreaElement) => [element.selectionStart, element.selectionEnd]);
  await page.keyboard.press("Enter");
  await expect(dialog(page).getByRole("alert")).toContainText("We couldn't complete your request.");
  await expect(input(page)).toBeFocused();
  await expect(input(page)).toHaveValue("Failed synthetic question");
  expect(await input(page).evaluate((element: HTMLTextAreaElement) => [element.selectionStart, element.selectionEnd])).toEqual(selection);
});

test("SUP-020 WIDGET-014: pending and incoming replies never steal focus after pointer movement, minimize or navigation", async ({ page, chat }) => {
  await page.goto("/");
  await start(page);
  const endpoint = `${publicApi}/conversations/${chat.thread.id}/messages`;
  for (const target of ["pointer", "minimize", "navigation"] as const) {
    let release = () => {};
    const gate = new Promise<void>((resolve) => { release = resolve; });
    await page.route(endpoint, async (route) => { await gate; await route.fallback(); });
    try {
      await input(page).fill(`Synthetic ${target} focus question`);
      await page.keyboard.press("Enter");
      await expect(input(page)).toHaveAttribute("readonly", "");
      if (target === "pointer") {
        await history(page).click();
        await history(page).focus();
      } else if (target === "minimize") {
        await page.getByRole("button", { name: "Minimize chat" }).click();
        await expect(launcher(page)).toBeFocused();
      } else {
        await page.getByRole("link", { name: "Cart (0)", exact: true }).click();
        await expect(page).toHaveURL(/\/cart$/);
      }
      release();
      const retainedComposer = page.getByRole("textbox", { name: "Your message", exact: true, includeHidden: true });
      await expect(retainedComposer).toHaveValue("");
      await expect(retainedComposer).not.toBeFocused();
      if (target === "pointer") await expect(history(page)).toBeFocused();
      if (target === "minimize") {
        await expect(launcher(page)).toBeFocused();
        await expect(dialog(page)).not.toBeVisible();
        await launcher(page).click();
      }
    } finally { release(); await page.unroute(endpoint); }
  }
  await input(page).fill("Composing while the assistant prepares a reply");
  chat.thread.processing = true; chat.thread.revision++;
  await expect(dialog(page).getByRole("status")).toHaveText("Preparing a reply…");
  await expect(input(page)).toBeEditable();
  await page.keyboard.type(" continues");
  await expect(page.getByRole("button", { name: "Send message", exact: true })).toBeDisabled();
  chat.thread.processing = false;
  chat.append("assistant", "Incoming reply while composing.");
  await expect(history(page)).toContainText("Incoming reply while composing.");
  await expect(input(page)).toHaveValue("Composing while the assistant prepares a reply continues");
  await expect(input(page)).toBeFocused();
  await expect(page.getByRole("button", { name: "Send message", exact: true })).toBeEnabled();
});
