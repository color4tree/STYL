import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import path from "node:path";

test("SUP-025 KNW-015: approved general Q&A is usable in the customer widget with no product assignment", async ({ page, request }) => {
  const directory = process.env.STYL_E2E_DATA_DIR;
  if (!directory || !path.isAbsolute(directory) || !path.basename(directory).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) throw new Error("General Q&A tests require isolated data.");
  const api = "http://127.0.0.1:8102";
  const headers = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };
  const settingsUrl = `${api}/api/admin/support/config`;
  const previous = await (await request.get(settingsUrl, { headers })).json();
  const configured = await request.put(settingsUrl, { headers, data: {
    enabled: true, allowedTopics: ["products", "pricing", "compatibility", "customer_service"], expectedRevision: previous.revision,
  } });
  expect(configured.status()).toBe(200);
  const endpoint = `${api}/api/admin/support/knowledge`;
  const marker = randomUUID().slice(0, 8).replace(/\d/g, (digit) => String.fromCharCode(103 + Number(digit)));
  const name = `Service FAQ ${marker}`;
  const policy = `The ${marker} delivery service takes five business days.`;
  try {
    const uploaded = await request.post(`${endpoint}/documents`, { headers, multipart: {
      title: name, scope: "general", itemRefs: "[]",
      file: { name: "service-faq.txt", mimeType: "text/plain", buffer: Buffer.from(policy) },
    } });
    expect(uploaded.status(), await uploaded.text()).toBe(201);
    const document = await uploaded.json();
    const configuration = await (await request.get(endpoint, { headers })).json();
    const queued = await request.post(`${endpoint}/sources/${document.id}/extract`, { headers, data: {
      expectedRevision: document.revision, acknowledgeExternalProcessing: true, expectedRouteFingerprint: configuration.routeFingerprint,
    } });
    expect(queued.status()).toBe(200);
    const load = async () => (await (await request.get(endpoint, { headers })).json()).sources.find((source: { id: string }) => source.id === document.id);
    await expect.poll(async () => (await load()).state).toBe("review");
    const reviewed = await load();
    const approved = await request.post(`${endpoint}/sources/${document.id}/review`, { headers, data: {
      expectedRevision: reviewed.revision, decision: "approve",
      facts: [{ text: policy, topic: "customer_service", location: "FAQ, delivery" }],
    } });
    expect(approved.status(), await approved.text()).toBe(200);
    await page.goto("/support");
    const dialog = page.getByRole("dialog", { name: "STYL Assistant", exact: true });
    await dialog.getByRole("button", { name: "Start conversation", exact: true }).click();
    const input = dialog.getByRole("textbox", { name: "Your message", exact: true });
    await input.fill(`How long does the ${marker} delivery service take?`);
    await input.press("Enter");
    const answer = dialog.getByRole("log", { name: "Conversation messages" }).locator('[data-support-role="assistant"]').last();
    await expect(answer).toContainText("five business days");
    await expect(answer).toContainText(name);
    await expect(answer.locator("summary", { hasText: /^Sources$/ })).toHaveCount(0);
    await expect(answer.getByRole("link", { includeHidden: true })).toHaveCount(0);
    await expect(answer).not.toContainText("customer_service");
  } finally {
    const current = await (await request.get(settingsUrl, { headers })).json();
    const restored = await request.put(settingsUrl, { headers, data: {
      enabled: previous.enabled, allowedTopics: previous.allowedTopics, expectedRevision: current.revision,
    } });
    expect(restored.status()).toBe(200);
  }
});
