import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { deflateSync } from "node:zlib";
import path from "node:path";

const api = "http://127.0.0.1:8102";
const endpoint = `${api}/api/admin/support/knowledge`;
const headers: Record<string, string> = { Authorization: `Bearer ${process.env.STYL_E2E_TOKEN}` };

type Fact = { text: string; topic: "products" | "compatibility" | "customer_service"; location: string };
type Source = { id: string; name: string; state: string; revision: number; itemRefs: string[]; facts: Fact[]; kind: string; origin: string; scope?: "products" | "general"; format?: string; bytes?: number; approvedCurrent?: boolean; createdAt: string; error: string | null; retryAt: string | null };
type Index = { sources: Source[]; items: { ref: string; name: string; type: string; id: number }[]; warnings: string[]; provider: string; routes?: Record<"image" | "pdf" | "video", { provider: string; model: string }> & Partial<Record<"docx" | "text", { provider: string; model: string }>>; routeFingerprint?: string; limits: { documentBytes: number; imageBytes: number; videoBytes: number } };
type Item = { id: number; name: string; ref: string };
type Fixture = { product: Item; accessory: Item; image: string; marker: string };

function currentCatalogMedia(source: Source, fixture: Fixture) {
  // Deleted fixture IDs may be reused; historical source refs are intentionally retained.
  return source.origin === "catalog" && source.itemRefs.includes(fixture.product.ref)
    && source.name.endsWith(fixture.image.slice(fixture.image.lastIndexOf("/") + 1));
}

function crc(bytes: Buffer) {
  let value = 0xffffffff;
  for (const byte of bytes) {
    value ^= byte;
    for (let bit = 0; bit < 8; bit++) value = (value >>> 1) ^ (value & 1 ? 0xedb88320 : 0);
  }
  return (value ^ 0xffffffff) >>> 0;
}
// Complete generated fixtures, not just magic headers. No external files or provider calls.
function png(color = 125) {
  const chunk = (name: string, bytes: Buffer) => {
    const data = Buffer.concat([Buffer.from(name), bytes]);
    const length = Buffer.alloc(4); length.writeUInt32BE(bytes.length);
    const checksum = Buffer.alloc(4); checksum.writeUInt32BE(crc(data));
    return Buffer.concat([length, data, checksum]);
  };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(8, 0); ihdr.writeUInt32BE(8, 4); ihdr[8] = 8; ihdr[9] = 2;
  const rows = Buffer.concat(Array.from({ length: 8 }, () => Buffer.concat([Buffer.from([0]), Buffer.alloc(24, color)])));
  return Buffer.concat([Buffer.from("89504e470d0a1a0a", "hex"), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(rows)), chunk("IEND", Buffer.alloc(0))]);
}
function pdf(label: string) {
  const safe = label.replace(/[^a-zA-Z0-9 -]/g, "");
  const stream = `BT /F1 12 Tf 50 750 Td (${safe}: synthetic public product manual.) Tj 0 -20 Td (Steel frame. Synthetic Model Z compatibility.) Tj ET\n`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}endstream`,
  ];
  let document = "%PDF-1.4\n";
  const offsets = [0];
  for (const [position, content] of objects.entries()) { offsets.push(Buffer.byteLength(document)); document += `${position + 1} 0 obj\n${content}\nendobj\n`; }
  const xref = Buffer.byteLength(document);
  document += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(document);
}
function docx() {
  const entries: [string, string][] = [
    ["[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'],
    ["_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'],
    ["word/document.xml", '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Q: How do I prepare a synthetic order inquiry?</w:t></w:r></w:p><w:p><w:r><w:t>A: Include the synthetic product names and quantities. Café fixtures only.</w:t></w:r></w:p><w:sectPr/></w:body></w:document>'],
  ];
  const local: Buffer[] = [], central: Buffer[] = [];
  let offset = 0;
  for (const [name, content] of entries) {
    const filename = Buffer.from(name), data = Buffer.from(content);
    const header = Buffer.alloc(30);
    header.writeUInt32LE(0x04034b50); header.writeUInt16LE(20, 4);
    header.writeUInt32LE(crc(data), 14); header.writeUInt32LE(data.length, 18); header.writeUInt32LE(data.length, 22); header.writeUInt16LE(filename.length, 26);
    const directory = Buffer.alloc(46);
    directory.writeUInt32LE(0x02014b50); directory.writeUInt16LE(20, 4); directory.writeUInt16LE(20, 6);
    directory.writeUInt32LE(crc(data), 16); directory.writeUInt32LE(data.length, 20); directory.writeUInt32LE(data.length, 24); directory.writeUInt16LE(filename.length, 28); directory.writeUInt32LE(offset, 42);
    local.push(header, filename, data); central.push(directory, filename);
    offset += header.length + filename.length + data.length;
  }
  const directory = Buffer.concat(central), end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50); end.writeUInt16LE(entries.length, 8); end.writeUInt16LE(entries.length, 10); end.writeUInt32LE(directory.length, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...local, directory, end]);
}
const test = base.extend<{ fixture: Fixture }>({
  fixture: [async ({ request }, run) => {
    const directory = process.env.STYL_E2E_DATA_DIR;
    if (!directory || !path.isAbsolute(directory) || !path.basename(directory).startsWith("styl-e2e-") || !process.env.STYL_E2E_TOKEN) throw new Error("Knowledge tests require the isolated Playwright harness; never a local catalog.");
    const configuration = await request.get(endpoint, { headers });
    expect(configuration.status(), await configuration.text()).toBe(200);
    expect((await configuration.json()).provider).toBe("mock");
    const marker = randomUUID().slice(0, 8).replace(/\d/g, (digit) => String.fromCharCode(103 + Number(digit)));
    const uploaded = await request.post(`${api}/api/uploads/product-image`, { headers, multipart: { image: { name: `knowledge-${marker}.png`, mimeType: "image/png", buffer: png() } } });
    expect(uploaded.status(), await uploaded.text()).toBe(200);
    const image: string = (await uploaded.json()).image;
    const created: Item[] = [];
    try {
      for (const [catalog, type] of [["products", "product"], ["accessories", "accessory"]]) {
        const name = `Knowledge ${type} ${marker}`;
        const response = await request.post(`${api}/api/${catalog}`, { headers, data: {
          name, category: type === "product" ? "Racks" : "Handle", publicationStatus: "published",
          prices: { CAD: 75, USD: 55 }, shortDescription: "Synthetic public fixture.", description: "Synthetic steel fixture.",
          photos: [image], image,
        } });
        expect(response.status(), await response.text()).toBe(200);
        const item = (await response.json()).item;
        created.push({ id: item.id, name, ref: `${type}:${item.id}` });
      }
      await run({ product: created[0], accessory: created[1], image, marker });
    } finally {
      for (const item of created) {
        const response = await request.delete(`${api}/api/${item.ref.startsWith("product:") ? "products" : "accessories"}/${item.id}`, { headers });
        expect(response.status(), await response.text()).toBe(200);
      }
      // The harness owns uploaded files/private knowledge and removes its entire isolated directory.
    }
  }, { auto: true }],
});

async function index(request: APIRequestContext): Promise<Index> {
  const response = await request.get(endpoint, { headers });
  expect(response.status(), await response.text()).toBe(200);
  expect(response.headers()["cache-control"]).toContain("no-store");
  const value: Index = await response.json();
  expect(value.routeFingerprint).toMatch(/^[a-f0-9]{64}$/);
  return value;
}
async function source(request: APIRequestContext, id: string) {
  const result = (await index(request)).sources.find((value) => value.id === id);
  expect(result, `Source ${id} remains durable`).toBeDefined();
  return result!;
}
async function signIn(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Admin token", { exact: true }).fill(process.env.STYL_E2E_TOKEN!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Customer support", exact: true })).toBeEnabled();
}
async function openKnowledge(page: Page) {
  await page.getByRole("button", { name: "Customer support", exact: true }).click();
  await page.getByRole("button", { name: "Knowledge", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Support knowledge", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sync catalog", exact: true })).toBeEnabled();
}
async function upload(request: APIRequestContext, fixture: Fixture): Promise<Source> {
  const response = await request.post(`${endpoint}/documents`, { headers, multipart: {
    file: { name: `manual-${fixture.marker}.pdf`, mimeType: "application/pdf", buffer: pdf(fixture.marker) },
    title: `Public manual ${fixture.marker}`, itemRefs: JSON.stringify([fixture.product.ref]),
  } });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}
async function extract(request: APIRequestContext, input: Source): Promise<Source> {
  const expectedRouteFingerprint = (await index(request)).routeFingerprint;
  expect(expectedRouteFingerprint).toMatch(/^[a-f0-9]{64}$/);
  const response = await request.post(`${endpoint}/sources/${input.id}/extract`, { headers, data: { expectedRevision: input.revision, acknowledgeExternalProcessing: true, expectedRouteFingerprint } });
  expect(response.ok(), await response.text()).toBe(true);
  await expect.poll(async () => (await source(request, input.id)).state, { timeout: 20_000 }).toBe("review");
  return source(request, input.id);
}
const errorNotice = (page: Page) => page.getByRole("alert").filter({ has: page.getByText("Error", { exact: true }) });
const acknowledgement = (page: Page) => page.getByRole("checkbox", { name: /Only approved public, non-sensitive files/ });
async function selectSource(page: Page, value: Source) {
  await page.getByRole("button", { name: `Open source: ${value.name}`, exact: true }).click();
  await expect(page.getByRole("heading", { name: value.name, exact: true })).toBeVisible();
}
async function refresh(page: Page) {
  await page.getByRole("button", { name: "Refresh knowledge", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sync catalog", exact: true })).toBeEnabled();
}

test("KNW-001 KNW-002: catalog media sync and private valid PDF upload remain drafts until explicit edited approval", async ({ page, request, fixture }) => {
  await signIn(page);
  await openKnowledge(page);
  await expect(page.getByText("Catalog text is live automatically. Review media/document facts before publishing.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Extract pending", exact: true })).toBeDisabled();
  const synced = page.waitForResponse((response) => response.url() === `${endpoint}/catalog-sync`);
  await page.getByRole("button", { name: "Sync catalog", exact: true }).click();
  const response = await synced;
  expect(response.status()).toBe(200);
  expect(response.request().postDataJSON()).toEqual({});
  expect(response.request().headers()["authorization"]).toBe(headers.Authorization);
  expect(new URL(response.url()).search).toBe("");
  const syncIndex: Index = await response.json();
  expect(syncIndex.routeFingerprint).toMatch(/^[a-f0-9]{64}$/);
  const media = syncIndex.sources.filter((value) => currentCatalogMedia(value, fixture));
  expect(media.length).toBeGreaterThan(0);
  expect(media.some((value) => value.kind === "image")).toBe(true);
  for (const value of media) { expect(value.state).toBe("pending"); expect(value.facts).toEqual([]); }
  expect(JSON.stringify(syncIndex)).not.toMatch(/"(?:filePath|file_path|privatePath)"/);
  expect(syncIndex.items).toEqual(expect.arrayContaining([expect.objectContaining({ ref: fixture.product.ref, name: fixture.product.name })]));
  await expect(page.getByRole("button", { name: /^Open source:/ }).filter({ hasText: fixture.product.name }).first()).toBeVisible();

  await expect(page.getByRole("heading", { name: "Add documents", exact: true })).toBeVisible();
  await expect(page.getByText("Upload a product document or general customer-service Q&A, extract drafts, then review and approve.", { exact: true })).toBeVisible();
  const title = `UI manual ${fixture.marker}`;
  await page.getByLabel("Document title", { exact: true }).fill(title);
  await page.getByLabel("Document file", { exact: true }).setInputFiles({ name: "valid-manual.pdf", mimeType: "application/pdf", buffer: pdf(fixture.marker) });
  await expect(page.getByRole("button", { name: "Upload document", exact: true })).toBeEnabled();
  await page.getByRole("group", { name: "Assign document to published items", exact: true }).getByRole("checkbox", { name: new RegExp(fixture.product.name) }).check();
  const uploaded = page.waitForResponse((value) => value.url() === `${endpoint}/documents` && value.request().method() === "POST");
  await page.getByRole("button", { name: "Upload document", exact: true }).click();
  const saved = await uploaded;
  expect(saved.status(), await saved.text()).toBe(201);
  const document: Source = await saved.json();
  expect(document).toMatchObject({ name: title, kind: "pdf", origin: "document", state: "pending", facts: [], itemRefs: [fixture.product.ref] });
  expect(saved.headers()["cache-control"]).toContain("no-store");
  expect(saved.request().headers()["authorization"]).toBe(headers.Authorization);
  expect(new URL(saved.url()).search).toBe("");
  await expect(page.getByLabel("Document title", { exact: true })).toHaveValue("");
  await expect(page.getByRole("status").filter({ hasText: "PDF uploaded privately" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Extract source", exact: true })).toBeDisabled();
  await expect(acknowledgement(page)).toHaveAccessibleName(/selected AI provider.*Paid API usage may apply; no automatic paid upgrade/);
  await acknowledgement(page).check();
  const extraction = page.waitForResponse((value) => value.url() === `${endpoint}/sources/${document.id}/extract`);
  await page.getByRole("button", { name: "Extract source", exact: true }).click();
  const queued = await extraction;
  expect(queued.ok(), await queued.text()).toBe(true);
  expect(queued.request().postDataJSON()).toEqual({ expectedRevision: document.revision, acknowledgeExternalProcessing: true, expectedRouteFingerprint: syncIndex.routeFingerprint });
  await expect.poll(async () => (await source(request, document.id)).state, { timeout: 20_000 }).toBe("review");
  await expect(page.getByRole("button", { name: "Approve reviewed facts", exact: true })).toBeEnabled();
  const reviewed = await source(request, document.id);
  expect(reviewed.facts.length).toBeGreaterThan(0);
  expect(reviewed.facts.every((fact) => ["products", "compatibility"].includes(fact.topic) && Boolean(fact.text) && Boolean(fact.location))).toBe(true);
  const firstFact = page.getByRole("textbox", { name: "Fact 1", exact: true });
  await expect(firstFact).toHaveValue(reviewed.facts[0].text);
  await expect(page.getByRole("textbox", { name: "Source location 1", exact: true })).toHaveValue(reviewed.facts[0].location);
  await firstFact.fill("Administrator verified synthetic steel frame.");
  const approval = page.waitForResponse((value) => value.url() === `${endpoint}/sources/${document.id}/review`);
  await page.getByRole("button", { name: "Approve reviewed facts", exact: true }).click();
  const approvedResponse = await approval;
  expect(approvedResponse.status()).toBe(200);
  expect(approvedResponse.request().postDataJSON()).toMatchObject({ decision: "approve", expectedRevision: reviewed.revision, facts: [{ ...reviewed.facts[0], text: "Administrator verified synthetic steel frame." }, ...reviewed.facts.slice(1)] });
  const approved = await source(request, document.id);
  expect(approved.state).toBe("approved");
  expect(approved.facts[0].text).toBe("Administrator verified synthetic steel frame.");
  await expect(page.getByRole("button", { name: "Approve reviewed facts", exact: true })).toHaveCount(0);
  await page.reload();
  await openKnowledge(page);
  await selectSource(page, approved);
  await expect(page.getByRole("heading", { name: new RegExp(`^Approved facts \\(${approved.facts.length}\\)$`) })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Fact 1", exact: true })).toHaveValue(approved.facts[0].text);
});

test("KNW-009: mocked routing metadata UI labels and visible Add documents flow, not live provider routing", async ({ page, request, fixture }) => {
  const current = await index(request);
  const configEndpoint = `${api}/api/admin/support/config`;
  const configuration = await request.get(configEndpoint, { headers });
  expect(configuration.status()).toBe(200);
  const currentConfiguration = await configuration.json();
  let chatRoute: { provider: string; model: string } | null = { provider: "openai", model: "gpt-6-luna" };
  let routes: Index["routes"] = {
    image: { provider: "openai", model: "gpt-6-luna" },
    pdf: { provider: "openai", model: "gpt-6-luna" },
    video: { provider: "gemini", model: "gemini-3.8-flash" },
  };
  let provider = "mock";
  // Only metadata is intercepted; real routing belongs to backend contract tests.
  await page.route(endpoint, (route) => route.fulfill({ json: { ...current, sources: [], provider, routes } }));
  await page.route(configEndpoint, (route) => route.fulfill(chatRoute
    ? { json: { ...currentConfiguration, ...chatRoute } }
    : { status: 503, json: { detail: "Synthetic chat configuration unavailable." } }));
  await signIn(page); await openKnowledge(page);
  const routing = page.getByRole("region", { name: "AI routing", exact: true });
  const general = routing.getByRole("group", { name: "Chat / images / PDFs", exact: true });
  const videos = routing.getByRole("group", { name: "Videos", exact: true });
  await expect(general).toContainText("Chat / images / PDFs: GPT-6 Luna");
  await expect(general).toContainText("Provider: openai · Model: gpt-6-luna");
  await expect(videos).toContainText("Videos: Gemini 3.8 Flash");
  await expect(videos).toContainText("Provider: gemini · Model: gemini-3.8-flash");
  await expect(routing).toContainText("no API keys are shown or entered here");
  routes = { ...routes, docx: routes.pdf, text: routes.pdf };
  await refresh(page);
  await expect(routing.getByRole("group", { name: "Chat / images / documents", exact: true })).toContainText("Provider: openai · Model: gpt-6-luna");
  routes = { ...routes, text: { provider: "mock", model: "mock-text-route" } };
  await refresh(page);
  await expect(routing.getByRole("group", { name: "Chat / images / documents", exact: true })).toHaveCount(0);
  await expect(routing.getByRole("group", { name: "TXT / MD", exact: true })).toContainText("Provider: mock · Model: mock-text-route");
  routes = { image: routes.image, pdf: routes.pdf, video: routes.video };
  await refresh(page);

  const documents = page.getByRole("region", { name: "Add documents", exact: true });
  await expect(documents.getByRole("heading", { name: "Add documents", exact: true })).toBeVisible();
  await expect(documents).toContainText("Upload a product document or general customer-service Q&A, extract drafts, then review and approve.");
  await expect(documents.getByLabel("Document file", { exact: true })).toHaveAttribute("accept", ".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown");
  await expect(documents).toContainText(`PDF, DOCX, TXT or MD · up to ${(current.limits.documentBytes / 1024 ** 2).toFixed(1)} MiB`);
  await expect(documents).toContainText("Upload saves privately; extraction is a separate action.");
  const uploadButton = documents.getByRole("button", { name: "Upload document", exact: true });
  await expect(uploadButton).toBeEnabled();
  await documents.getByLabel("Document title", { exact: true }).fill("Synthetic public manual");
  await documents.getByLabel("Document file", { exact: true }).setInputFiles({ name: "public-manual.pdf", mimeType: "application/pdf", buffer: pdf("Public") });
  await expect(uploadButton).toBeEnabled();
  const assignment = documents.getByRole("group", { name: "Assign document to published items", exact: true })
    .getByRole("checkbox", { name: new RegExp(fixture.product.name) });
  await assignment.check(); await expect(uploadButton).toBeEnabled();
  await assignment.uncheck(); await expect(uploadButton).toBeEnabled();
  await uploadButton.click();
  await expect(documents.getByText("Select at least one published item, or choose General customer-service Q&A.", { exact: true })).toBeVisible();
  await expect(documents.getByRole("group", { name: "Assign document to published items", exact: true })).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByRole("button", { name: "Extract pending", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Approve reviewed facts", exact: true })).toHaveCount(0);

  chatRoute = { provider: "mock", model: "mock-visual" };
  routes = {
    image: { provider: "mock", model: "mock-visual" },
    pdf: { provider: "mock", model: "mock-visual" },
    video: { provider: "mock", model: "mock-video" },
  };
  await refresh(page);
  await expect(general).toContainText("Chat / images / PDFs: mock-visual");
  await expect(general).toContainText("Provider: mock · Model: mock-visual");
  await expect(videos).toContainText("Videos: mock-video");
  await expect(videos).toContainText("Provider: mock · Model: mock-video");
  await expect(routing).not.toContainText("GPT-6 Luna");
  await expect(routing).not.toContainText("Gemini 3.8 Flash");

  chatRoute = { provider: "mock", model: "mock-chat" };
  await refresh(page);
  await expect(general).toHaveCount(0);
  await expect(routing.getByRole("group", { name: "Chat", exact: true })).toContainText("Model: mock-chat");
  await expect(routing.getByRole("group", { name: "Images / PDFs", exact: true })).toContainText("Model: mock-visual");
  routes = { ...routes, pdf: { provider: "mock", model: "mock-pdf" } };
  await refresh(page);
  await expect(routing.getByRole("group", { name: "Images", exact: true })).toContainText("Model: mock-visual");
  await expect(routing.getByRole("group", { name: "PDFs", exact: true })).toContainText("Model: mock-pdf");
  chatRoute = null;
  await refresh(page);
  await expect(routing.getByRole("group", { name: "Chat", exact: true })).toHaveCount(0);
  await expect(routing).toContainText("Chat routing is unavailable.");
  await expect(routing).toContainText("check Conversations for the configured chat provider/model.");

  routes = undefined;
  provider = "unrecognized-legacy-provider";
  await refresh(page);
  await expect(routing).toContainText("Legacy extraction provider: unrecognized-legacy-provider");
  await expect(routing).toContainText("Per-kind provider/model details are unavailable");
  await expect(routing).toContainText("Chat routing is unavailable.");
  await expect(routing.getByRole("group")).toHaveCount(0);
  await expect(routing).not.toContainText("GPT-6 Luna");
  await expect(routing).not.toContainText("Gemini 3.8 Flash");
  await expect(documents.getByLabel("Document title", { exact: true })).toHaveValue("Synthetic public manual");
  await page.unroute(endpoint);
  await page.route(endpoint, (route) => route.fulfill({ json: {
    ...current, sources: [], routes: { image: { provider: "openai", model: null } },
  } }));
  await refresh(page);
  await expect(errorNotice(page)).toContainText("Knowledge response is invalid");
  await expect(routing).toContainText("Per-kind provider/model details are unavailable");
  await expect(documents.getByLabel("Document title", { exact: true })).toHaveValue("Synthetic public manual");
});

test("KNW-010: mocked route consent pins requests, requires refresh after 409 and resets on refresh/poll changes", async ({ page, request, fixture }) => {
  const document = await upload(request, fixture);
  const current = await index(request);
  const firstFingerprint = "a".repeat(64);
  const secondFingerprint = "b".repeat(64);
  const thirdFingerprint = "c".repeat(64);
  const fourthFingerprint = "d".repeat(64);
  let snapshot: Index = {
    ...current, sources: [document], routeFingerprint: firstFingerprint,
    routes: {
      image: { provider: "mock", model: "mock-image-a" },
      pdf: { provider: "mock", model: "mock-pdf-a" },
      video: { provider: "mock", model: "mock-video-a" },
    },
  };
  const submissions: unknown[] = [];
  await page.route(endpoint, (route) => route.fulfill({ json: snapshot }));
  await page.route(`${endpoint}/sources/${document.id}/extract`, (route) => {
    submissions.push(route.request().postDataJSON());
    return route.fulfill({ status: 409, json: { detail: "Synthetic extraction routes changed; refresh and reconfirm." } });
  });
  await page.route(`${endpoint}/extract-pending`, (route) => {
    submissions.push(route.request().postDataJSON());
    return route.fulfill({ json: snapshot });
  });
  await signIn(page); await openKnowledge(page); await selectSource(page, document);
  await page.getByLabel("Document title", { exact: true }).fill("Keep this upload draft through route changes");
  const consent = acknowledgement(page);
  const individual = page.getByRole("button", { name: "Extract source", exact: true });
  const bulk = page.getByRole("button", { name: "Extract pending", exact: true });
  await expect(individual).toBeDisabled(); await expect(bulk).toBeDisabled();
  await consent.check();
  await expect(individual).toBeEnabled();
  // The simulated server changed routes after consent but before the next index read.
  snapshot = { ...snapshot, routeFingerprint: secondFingerprint, routes: {
    ...snapshot.routes!, pdf: { provider: "mock", model: "mock-pdf-b" },
  } };
  await individual.click();
  await expect(errorNotice(page)).toContainText("Refresh knowledge, review the current routes, then confirm external processing again.");
  expect(submissions).toEqual([{ expectedRevision: document.revision, acknowledgeExternalProcessing: true, expectedRouteFingerprint: firstFingerprint }]);
  await expect(consent).not.toBeChecked(); await expect(consent).toBeDisabled();
  await expect(individual).toBeDisabled(); await expect(bulk).toBeDisabled();
  await expect(page.getByLabel("Document title", { exact: true })).toHaveValue("Keep this upload draft through route changes");
  await refresh(page);
  await expect(page.getByRole("region", { name: "AI routing" })).toContainText("mock-pdf-b");
  await expect(consent).toBeEnabled(); await expect(consent).not.toBeChecked();
  await expect(individual).toBeDisabled();
  await consent.check(); await bulk.click();
  await expect(page.getByRole("status").filter({ hasText: "Extraction request accepted" })).toBeVisible();
  expect(submissions).toEqual([
    { expectedRevision: document.revision, acknowledgeExternalProcessing: true, expectedRouteFingerprint: firstFingerprint },
    { acknowledgeExternalProcessing: true, expectedRouteFingerprint: secondFingerprint },
  ]);

  snapshot = { ...snapshot, routeFingerprint: thirdFingerprint, routes: {
    ...snapshot.routes!, image: { provider: "mock", model: "mock-image-c" },
  } };
  await refresh(page);
  await expect(consent).not.toBeChecked();
  await expect(page.getByRole("alert").filter({ hasText: "Extraction routes changed or could not be confirmed" })).toBeVisible();
  await expect(individual).toBeDisabled(); await expect(bulk).toBeDisabled();
  await consent.check();
  snapshot = { ...snapshot, sources: [document, { ...document, id: `poll-${fixture.marker}`, name: "Synthetic polling source", state: "queued" }] };
  await refresh(page);
  await expect(consent).toBeChecked();
  snapshot = { ...snapshot, routeFingerprint: fourthFingerprint, routes: {
    ...snapshot.routes!, video: { provider: "mock", model: "mock-video-d" },
  } };
  // An ordinary queued-work poll must revoke consent without an explicit refresh.
  await expect(consent).not.toBeChecked();
  await expect(page.getByRole("region", { name: "AI routing" })).toContainText("mock-video-d");
  await expect(individual).toBeDisabled(); await expect(bulk).toBeDisabled();
  expect(submissions).toHaveLength(2);

  snapshot = { ...snapshot, sources: [document], routeFingerprint: undefined };
  await refresh(page);
  await expect(consent).toBeDisabled();
  await expect(page.getByRole("alert").filter({ hasText: "current route consent metadata is missing" })).toBeVisible();
  await expect(individual).toBeDisabled(); await expect(bulk).toBeDisabled();
  snapshot = { ...snapshot, routeFingerprint: firstFingerprint };
  await refresh(page);
  await expect(consent).toBeEnabled(); await expect(consent).not.toBeChecked();
  await expect(individual).toBeDisabled();
  await expect(page.getByLabel("Document title", { exact: true })).toHaveValue("Keep this upload draft through route changes");
  expect(submissions).toHaveLength(2);
  expect((await source(request, document.id)).state).toBe("pending");
});

test("KNW-003: assignment changes revoke approval, stale revisions preserve review edits and require deliberate refresh", async ({ page, request, fixture }) => {
  const document = await upload(request, fixture);
  const reviewed = await extract(request, document);
  await signIn(page); await openKnowledge(page); await selectSource(page, reviewed);
  const text = "Keep this unsubmitted review edit.";
  await page.getByRole("textbox", { name: "Fact 1", exact: true }).fill(text);
  const conflictResponse = await request.put(`${endpoint}/sources/${document.id}/assignment`, { headers, data: { expectedRevision: reviewed.revision, itemRefs: [fixture.accessory.ref] } });
  expect(conflictResponse.status(), await conflictResponse.text()).toBe(200);
  expect((await conflictResponse.json()).state).not.toBe("approved");
  const rejected = page.waitForResponse((value) => value.url() === `${endpoint}/sources/${document.id}/review`);
  await page.getByRole("button", { name: "Approve reviewed facts", exact: true }).click();
  expect((await rejected).status()).toBe(409);
  await expect(errorNotice(page)).toContainText("Source changed (409)");
  await expect(page.getByRole("textbox", { name: "Fact 1", exact: true })).toHaveValue(text);
  await refresh(page);
  await expect(page.getByRole("textbox", { name: "Fact 1", exact: true })).toHaveValue(text);
  await expect(page.getByRole("alert").filter({ hasText: "Source revision changed or could not be confirmed" })).toBeVisible();
  expect((await source(request, document.id)).state).not.toBe("approved");
  const dialog = page.waitForEvent("dialog");
  const reload = page.getByRole("button", { name: "Reload source draft", exact: true }).click();
  await (await dialog).accept(); await reload;
  await acknowledgement(page).check();
  await page.getByRole("button", { name: "Extract source", exact: true }).click();
  await expect.poll(async () => (await source(request, document.id)).state, { timeout: 20_000 }).toBe("review");
  await expect(page.getByRole("button", { name: "Approve reviewed facts", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Approve reviewed facts", exact: true }).click();
  await expect.poll(async () => (await source(request, document.id)).state).toBe("approved");
  const choices = page.getByRole("group", { name: "Assigned published items", exact: true });
  await choices.getByRole("checkbox", { name: new RegExp(fixture.product.name) }).check();
  await choices.getByRole("checkbox", { name: new RegExp(fixture.accessory.name) }).uncheck();
  await page.getByRole("button", { name: "Save assignment", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Assignment saved" })).toBeVisible();
  const reassigned = await source(request, document.id);
  expect(reassigned.state).not.toBe("approved");
  expect(reassigned.itemRefs).toEqual([fixture.product.ref]);
  await page.reload(); await openKnowledge(page); await selectSource(page, reassigned);
  await expect(page.getByRole("group", { name: "Assigned published items", exact: true }).getByRole("checkbox", { name: new RegExp(fixture.product.name) })).toBeChecked();
});

test("KNW-004: bulk extraction acknowledgement and explicit rejection never auto-approve catalog facts", async ({ page, request, fixture }) => {
  const synced = await request.post(`${endpoint}/catalog-sync`, { headers, data: {} });
  expect(synced.status(), await synced.text()).toBe(200);
  const media: Source = (await synced.json()).sources.find((value: Source) => currentCatalogMedia(value, fixture));
  expect(media).toBeDefined();
  await signIn(page); await openKnowledge(page);
  await expect(page.getByRole("button", { name: "Extract pending", exact: true })).toBeDisabled();
  await acknowledgement(page).check();
  const pending = page.waitForResponse((value) => value.url() === `${endpoint}/extract-pending` && value.request().method() === "POST");
  await page.getByRole("button", { name: "Extract pending", exact: true }).click();
  const response = await pending;
  expect(response.ok(), await response.text()).toBe(true);
  expect(response.request().postDataJSON()).toEqual({ acknowledgeExternalProcessing: true, expectedRouteFingerprint: (await index(request)).routeFingerprint });
  const queued = (await response.json()).sources.filter((value: Source) => ["queued", "processing"].includes(value.state)).length;
  // One worker drains the entire acknowledged batch, including prior failed fixture sources.
  await expect.poll(async () => (await source(request, media.id)).state, { timeout: Math.max(20_000, 5000 + queued * 2000) }).toBe("review");
  expect((await source(request, media.id)).facts).toContainEqual({
    text: "Synthetic test-only media fact. An administrator must review this draft.",
    topic: "products", location: "Image: synthetic test fixture",
  });
  await refresh(page); await selectSource(page, media);
  await page.getByRole("button", { name: "Reject draft", exact: true }).click();
  await expect.poll(async () => (await source(request, media.id)).state).toBe("rejected");
  await expect(page.getByRole("button", { name: "Retry extraction", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Retry extraction", exact: true }).click();
  await expect.poll(async () => (await source(request, media.id)).state, { timeout: 20_000 }).toBe("review");
  expect((await source(request, media.id)).state).not.toBe("approved");
});

test("KNW-005: busy/failed upload keeps PDF inputs and catalog/support drafts across both support subtabs at 320/390", async ({ page, request, fixture }, testInfo) => {
  const document = await extract(request, await upload(request, fixture));
  await signIn(page);
  await page.getByRole("button", { name: "New", exact: true }).click();
  await page.getByRole("textbox", { name: "Equipment name", exact: true }).fill("Preserved knowledge catalog draft");
  await openKnowledge(page); await selectSource(page, document);
  await page.getByRole("textbox", { name: "Fact 1", exact: true }).fill("Preserved knowledge fact draft");
  await page.getByRole("button", { name: "Conversations", exact: true }).click();
  const enabled = page.getByRole("checkbox", { name: "Enable automatic AI replies", exact: true });
  const before = await enabled.isChecked(); await enabled.setChecked(!before);
  await page.getByRole("button", { name: "Knowledge", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Fact 1", exact: true })).toHaveValue("Preserved knowledge fact draft");
  await expect(page.getByRole("heading", { name: "Add documents", exact: true })).toBeVisible();
  await page.getByLabel("Document title", { exact: true }).fill("Preserved PDF title");
  await page.getByLabel("Document file", { exact: true }).setInputFiles({ name: "retained.pdf", mimeType: "application/pdf", buffer: pdf("Retained") });
  await page.getByRole("group", { name: "Assign document to published items", exact: true }).getByRole("checkbox", { name: new RegExp(fixture.product.name) }).check();
  let release = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let uploads = 0;
  await page.route(`${endpoint}/documents`, async (route) => { uploads++; await gate; await route.fulfill({ status: 503, json: { detail: "Synthetic document storage unavailable." } }); });
  try {
    await page.getByRole("button", { name: "Upload document", exact: true }).click();
    for (const name of ["Choose file", "Upload document", "Knowledge", "Conversations", "Customer support", "Equipment", "Backup", "Sign out"]) await expect(page.getByRole("button", { name, exact: true })).toBeDisabled();
    await expect(page.getByLabel("Document title", { exact: true })).toBeDisabled();
    expect(uploads).toBe(1);
    release();
    await expect(errorNotice(page)).toContainText("Synthetic document storage unavailable");
    await expect(page.getByLabel("Document title", { exact: true })).toHaveValue("Preserved PDF title");
    expect(await page.getByLabel("Document file", { exact: true }).evaluate((element: HTMLInputElement) => element.files?.[0]?.name)).toBe("retained.pdf");
  } finally { release(); await page.unroute(`${endpoint}/documents`); }
  for (const width of testInfo.project.name.startsWith("phone") ? [320, 390] : [1440]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => globalThis.document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    for (const name of ["Choose file", "Upload document", "Knowledge", "Conversations", "Refresh knowledge"]) {
      const bounds = await page.getByRole("button", { name, exact: true }).boundingBox();
      expect(bounds!.height).toBeGreaterThanOrEqual(["Choose file", "Upload document"].includes(name) ? 48 : 44);
      expect(bounds!.width + bounds!.x).toBeLessThanOrEqual(width);
    }
    const facts = page.getByLabel("Source facts", { exact: true });
    expect(await facts.evaluate((element) => element.clientHeight)).toBeLessThanOrEqual(450);
  }
  await page.getByRole("button", { name: "Conversations", exact: true }).click();
  await expect(enabled).toBeChecked({ checked: !before });
  await page.getByRole("button", { name: "Backup", exact: true }).click();
  await page.getByRole("button", { name: "Equipment", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Equipment name", exact: true })).toHaveValue("Preserved knowledge catalog draft");
  await openKnowledge(page);
  await expect(page.getByLabel("Document title", { exact: true })).toHaveValue("Preserved PDF title");
  await expect(page.getByRole("textbox", { name: "Fact 1", exact: true })).toHaveValue("Preserved knowledge fact draft");
  const accepted = page.waitForResponse((value) => value.url() === `${endpoint}/documents` && value.request().method() === "POST");
  await page.getByRole("button", { name: "Upload document", exact: true }).click();
  expect((await accepted).status()).toBe(201);
  await expect(page.getByLabel("Document title", { exact: true })).toHaveValue("");
});

test("KNW-006: real admin authorization and simulated read/paused states retain drafts without false success", async ({ page, request, fixture }) => {
  const document = await upload(request, fixture);
  const expectedRouteFingerprint = (await index(request)).routeFingerprint;
  for (const rejectedHeaders of [{}, { Authorization: "Bearer invalid-knowledge-token" }] as Record<string, string>[]) {
    for (const response of [
      await request.get(endpoint, { headers: rejectedHeaders }),
      await request.post(`${endpoint}/catalog-sync`, { headers: rejectedHeaders, data: {} }),
      await request.post(`${endpoint}/extract-pending`, { headers: rejectedHeaders, data: { acknowledgeExternalProcessing: true, expectedRouteFingerprint } }),
      await request.post(`${endpoint}/documents`, { headers: rejectedHeaders, multipart: {
        file: { name: "unauthorized.pdf", mimeType: "application/pdf", buffer: pdf("Unauthorized") },
        title: "Unauthorized fixture", itemRefs: JSON.stringify([fixture.product.ref]),
      } }),
      await request.post(`${endpoint}/sources/${document.id}/extract`, { headers: rejectedHeaders, data: { expectedRevision: document.revision, acknowledgeExternalProcessing: true, expectedRouteFingerprint } }),
      await request.put(`${endpoint}/sources/${document.id}/assignment`, { headers: rejectedHeaders, data: { expectedRevision: document.revision, itemRefs: [fixture.accessory.ref] } }),
      await request.post(`${endpoint}/sources/${document.id}/review`, { headers: rejectedHeaders, data: { expectedRevision: document.revision, decision: "approve" } }),
      await request.get(`${endpoint}/sources/${document.id}/file`, { headers: rejectedHeaders }),
    ]) { expect(response.status()).toBe(401); expect(await response.text()).not.toContain(document.name); }
  }
  const noConsent = await request.post(`${endpoint}/sources/${document.id}/extract`, { headers, data: { expectedRevision: document.revision, acknowledgeExternalProcessing: false, expectedRouteFingerprint } });
  expect([400, 422]).toContain(noConsent.status());
  expect((await source(request, document.id)).state).toBe("pending");
  await signIn(page); await openKnowledge(page); await selectSource(page, document);
  await expect(page.getByRole("heading", { name: "Add documents", exact: true })).toBeVisible();
  await page.getByLabel("Document title", { exact: true }).fill("Draft kept after read failures");
  await page.route(endpoint, (route) => route.fulfill({ status: 200, json: { sources: "invalid" } }));
  await refresh(page);
  await expect(errorNotice(page)).toContainText("Knowledge response is invalid");
  await expect(page.getByRole("heading", { name: document.name, exact: true })).toBeVisible();
  await page.unroute(endpoint);
  await page.route(endpoint, (route) => route.fulfill({ status: 401, json: { detail: "Unauthorized" } }));
  await page.getByRole("button", { name: "Refresh knowledge", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Private knowledge hidden because" })).toBeVisible();
  await expect(page.getByRole("heading", { name: document.name, exact: true })).toHaveCount(0);
  await page.unroute(endpoint); await refresh(page);
  await expect(page.getByLabel("Document title", { exact: true })).toHaveValue("Draft kept after read failures");
  await expect(page.locator("main")).not.toContainText(process.env.STYL_E2E_TOKEN!);
  const current = await index(request);
  const paused = { ...await source(request, document.id), state: "paused", error: "Synthetic provider quota paused; retry deliberately.", retryAt: "2000-01-01T00:00:00Z" };
  await page.route(endpoint, (route) => route.fulfill({ json: { ...current, sources: current.sources.map((value) => value.id === document.id ? paused : value) } }));
  await refresh(page);
  await expect(page.getByRole("alert").filter({ hasText: "Synthetic provider quota paused" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Needs attention \([1-9]\d*\)$/ })).toBeVisible();
  await acknowledgement(page).check();
  await expect(page.getByRole("button", { name: "Retry extraction", exact: true })).toBeEnabled();
  await page.unroute(endpoint);
  await page.getByRole("button", { name: "Retry extraction", exact: true }).click();
  await expect.poll(async () => (await source(request, document.id)).state, { timeout: 20_000 }).toBe("review");
  await expect(page.getByRole("button", { name: "Approve reviewed facts", exact: true })).toBeEnabled();
  expect((await source(request, document.id)).state).not.toBe("approved");
});

test("KNW-008: helpful empty state and long PDF drafts remain usable without mobile page overflow", async ({ page, request, fixture }, testInfo) => {
  const document = await upload(request, fixture);
  const current = await index(request);
  await page.route(endpoint, (route) => route.fulfill({ json: { ...current, sources: [] } }));
  await signIn(page); await openKnowledge(page);
  await expect(page.getByText(/No knowledge sources yet\. Sync catalog to reuse product photos\/videos/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Extract pending", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "All sources (0)", exact: true })).toBeVisible();
  await page.unroute(endpoint);
  const facts: Fact[] = Array.from({ length: 80 }, (_, position) => ({
    text: `Synthetic draft fact from page ${position + 1}. ${"Bounded public manual evidence. ".repeat(8)}`,
    location: `page ${position + 1}`, topic: position % 2 ? "compatibility" : "products",
  }));
  const reviewed = { ...document, state: "review", facts };
  await page.route(endpoint, (route) => route.fulfill({ json: { ...current, sources: [reviewed] } }));
  await refresh(page); await selectSource(page, reviewed);
  await expect(page.getByRole("button", { name: "Review (1)", exact: true })).toBeVisible();
  const factBox = page.getByLabel("Source facts", { exact: true });
  await expect(factBox.getByRole("textbox", { name: "Fact 80", exact: true })).toHaveValue(facts[79].text);
  for (const width of testInfo.project.name.startsWith("phone") ? [320, 390] : [1440]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => globalThis.document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const dimensions = await factBox.evaluate((element) => ({ height: element.clientHeight, scroll: element.scrollHeight }));
    expect(dimensions.height).toBeLessThanOrEqual(450);
    expect(dimensions.scroll).toBeGreaterThan(dimensions.height);
    await factBox.getByRole("textbox", { name: "Fact 80", exact: true }).fill(`Retained final-page edit at ${width}`);
    await expect(factBox.getByRole("textbox", { name: "Fact 80", exact: true })).toHaveValue(`Retained final-page edit at ${width}`);
    const approve = await page.getByRole("button", { name: "Approve reviewed facts", exact: true }).boundingBox();
    expect(approve!.height).toBeGreaterThanOrEqual(44);
    expect(approve!.width + approve!.x).toBeLessThanOrEqual(width);
  }
  expect((await source(request, document.id)).state).toBe("pending");
  await page.unroute(endpoint);
});

test("KNW-007: changed catalog media becomes stale and cannot reuse a previous approval", async ({ page, request, fixture }) => {
  const synced = await request.post(`${endpoint}/catalog-sync`, { headers, data: {} });
  expect(synced.status(), await synced.text()).toBe(200);
  const media: Source = (await synced.json()).sources.find((value: Source) => currentCatalogMedia(value, fixture));
  expect(media).toBeDefined();
  const reviewed = await extract(request, media);
  const approved = await request.post(`${endpoint}/sources/${media.id}/review`, { headers, data: { expectedRevision: reviewed.revision, decision: "approve" } });
  expect(approved.status(), await approved.text()).toBe(200);
  expect((await source(request, media.id)).state).toBe("approved");
  expect(fixture.image).toMatch(/^\/api\/uploads\/[^/\\]+$/);
  const imageFile = path.join(process.env.STYL_E2E_DATA_DIR!, "uploads", fixture.image.slice("/api/uploads/".length));
  const original = readFileSync(imageFile);
  try {
    writeFileSync(imageFile, png(210));
    await signIn(page); await openKnowledge(page);
    await page.getByRole("button", { name: "Sync catalog", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "Catalog media synced" })).toBeVisible();
    const stale = await source(request, media.id);
    expect(stale.state).toBe("stale");
    expect(stale.revision).toBeGreaterThan(reviewed.revision);
    await selectSource(page, stale);
    await expect(page.getByText("This source changed. Previous facts are not in use. Sync catalog if needed, then extract and review again.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve reviewed facts", exact: true })).toHaveCount(0);
    const obsoleteApproval = await request.post(`${endpoint}/sources/${media.id}/review`, { headers, data: { expectedRevision: reviewed.revision, decision: "approve" } });
    expect(obsoleteApproval.status()).toBe(409);
    expect((await source(request, media.id)).state).toBe("stale");
  } finally { writeFileSync(imageFile, original); }
});

test("KNW-011: actionable upload validation preserves inputs; select-all snapshots current items in upload and assignment", async ({ page, request, fixture }, testInfo) => {
  await signIn(page); await openKnowledge(page);
  const form = page.getByRole("region", { name: "Add documents", exact: true });
  const title = form.getByLabel("Document title", { exact: true });
  const file = form.getByLabel("Document file", { exact: true });
  const choose = form.getByRole("button", { name: "Choose file", exact: true });
  const uploadButton = form.getByRole("button", { name: "Upload document", exact: true });
  const choices = form.getByRole("group", { name: "Assign document to published items", exact: true });
  let attempts = 0;
  page.on("request", (request) => { if (request.url() === `${endpoint}/documents` && request.method() === "POST") attempts++; });
  await expect(uploadButton).toBeEnabled(); await uploadButton.click();
  await expect(title).toBeFocused(); await expect(title).toHaveAttribute("aria-invalid", "true");
  await expect(form.getByText("Enter a document title (1–200 characters).", { exact: true })).toBeVisible();
  await expect(form.getByText("Choose a PDF, DOCX, TXT or MD file.", { exact: true })).toBeVisible();
  await expect(choices).toHaveAttribute("aria-invalid", "true");
  const fileChooser = page.waitForEvent("filechooser");
  await choose.click();
  await (await fileChooser).setFiles({ name: "synthetic-manual.pdf", mimeType: "application/pdf", buffer: pdf(fixture.marker) });
  await expect(title).toHaveValue("");
  await uploadButton.click(); await expect(title).toBeFocused();
  const documentTitle = `Synthetic manual ${fixture.marker} `.padEnd(200, "x");
  await expect(title).toHaveAttribute("maxlength", "200"); await title.fill(documentTitle);
  await file.setInputFiles([]); await uploadButton.click(); await expect(choose).toBeFocused();
  await expect(file).toHaveAttribute("aria-invalid", "true");
  for (const invalid of [
    { name: "empty.txt", mimeType: "text/plain", buffer: Buffer.alloc(0) },
    { name: "not-a-document.html", mimeType: "text/html", buffer: Buffer.from("<p>Synthetic fixture only</p>") },
  ]) {
    await file.setInputFiles(invalid); await uploadButton.click();
    await expect(choose).toBeFocused();
    await expect(form.getByText(/Choose a nonempty PDF, DOCX, TXT or MD file no larger than/)).toBeVisible();
    await expect(title).toHaveValue(documentTitle);
  }
  const bytes = pdf(fixture.marker);
  const snapshot = await index(request);
  await page.route(endpoint, (route) => route.fulfill({ json: { ...snapshot, limits: { ...snapshot.limits, documentBytes: 1 } } }));
  await refresh(page);
  await file.setInputFiles({ name: "synthetic-manual.pdf", mimeType: "application/pdf", buffer: bytes });
  await uploadButton.click(); await expect(choose).toBeFocused();
  await expect(form.getByText(/Choose a nonempty PDF, DOCX, TXT or MD file no larger than 1 bytes/)).toBeVisible();
  await page.unroute(endpoint); await refresh(page);
  await file.setInputFiles({ name: "synthetic-manual.pdf", mimeType: "application/pdf", buffer: bytes });
  await uploadButton.click(); await expect(choices).toBeFocused();
  await expect(choices).toHaveAttribute("aria-invalid", "true");
  expect(attempts).toBe(0);
  const originalItems = (await index(request)).items.map((item) => item.ref);
  await choices.getByRole("button", { name: "Select all currently published items", exact: true }).click();
  expect(await choices.getByRole("checkbox").count()).toBe(originalItems.length);
  await expect(choices.getByRole("checkbox", { checked: false })).toHaveCount(0);
  await choices.getByRole("button", { name: "Clear selection", exact: true }).click();
  await expect(choices.getByRole("checkbox", { checked: true })).toHaveCount(0);
  await choices.getByRole("button", { name: "Select all currently published items", exact: true }).click();

  const laterName = `Later published item ${fixture.marker}`;
  const laterResponse = await request.post(`${api}/api/products`, { headers, data: {
    name: laterName, category: "Racks", publicationStatus: "published",
    prices: { CAD: 80, USD: 60 }, shortDescription: "Synthetic later fixture.", description: "Synthetic public product.",
    photos: [fixture.image], image: fixture.image,
  } });
  expect(laterResponse.status(), await laterResponse.text()).toBe(200);
  const laterId: number = (await laterResponse.json()).item.id;
  try {
    await refresh(page);
    await expect(choices.getByRole("checkbox", { name: new RegExp(laterName) })).not.toBeChecked();
    const savedResponse = page.waitForResponse((response) => response.url() === `${endpoint}/documents` && response.request().method() === "POST");
    await uploadButton.click();
    const saved = await savedResponse;
    expect(saved.status(), await saved.text()).toBe(201);
    const document: Source = await saved.json();
    expect(document).toMatchObject({ name: documentTitle, scope: "products", format: "pdf", bytes: bytes.length });
    expect(document.itemRefs.slice().sort()).toEqual(originalItems.slice().sort());
    expect(document.itemRefs).not.toContain(`product:${laterId}`);
    const library = page.getByRole("region", { name: "Uploaded documents", exact: true });
    const row = library.getByRole("listitem").filter({ has: page.getByRole("button", { name: `Review document: ${documentTitle}`, exact: true }) });
    await expect(row).toContainText("Not included in assistant knowledge");
    await expect(row.locator("time")).toHaveAttribute("datetime", document.createdAt);
    for (const width of testInfo.project.name.startsWith("phone") ? [320, 390] : [1440]) {
      await page.setViewportSize({ width, height: 844 });
      expect(await page.evaluate(() => globalThis.document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      for (const control of [choose, uploadButton, row.getByRole("button")]) {
        const box = await control.boundingBox();
        expect(box!.height).toBeGreaterThanOrEqual(48); expect(box!.x + box!.width).toBeLessThanOrEqual(width);
      }
    }
    await row.getByRole("button").click();
    const assigned = page.getByRole("group", { name: "Assigned published items", exact: true });
    await assigned.getByRole("button", { name: "Clear selection", exact: true }).click();
    await expect(assigned.getByRole("checkbox", { checked: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Save assignment", exact: true }).click();
    await expect(assigned).toBeFocused(); await expect(assigned).toHaveAttribute("aria-invalid", "true");
    expect((await source(request, document.id)).revision).toBe(document.revision);
    await assigned.getByRole("button", { name: "Select all currently published items", exact: true }).click();
    await page.getByRole("button", { name: "Save assignment", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "Assignment saved" })).toBeVisible();
    expect((await source(request, document.id)).itemRefs.slice().sort()).toEqual([...originalItems, `product:${laterId}`].sort());
  } finally {
    const removed = await request.delete(`${api}/api/products/${laterId}`, { headers });
    expect(removed.status(), await removed.text()).toBe(200);
  }
});

for (const extension of ["docx", "txt", "md"] as const) {
  test(`KNW-012: ${extension.toUpperCase()} general Q&A upload, metadata and approval remain visible in the document library after reload`, async ({ page, request, fixture }) => {
    const content = extension === "docx" ? docx() : Buffer.from("# Synthetic customer-service Q&A\nQ: How do I prepare a synthetic inquiry?\nA: Include synthetic product names and quantities. Café fixtures only.\n", "utf8");
    const mimeType = extension === "docx" ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document" : extension === "md" ? "text/markdown" : "text/plain";
    const name = `Synthetic general ${extension.toUpperCase()} ${fixture.marker}`;
    await signIn(page); await openKnowledge(page);
    const form = page.getByRole("region", { name: "Add documents", exact: true });
    await form.getByLabel("Document title", { exact: true }).fill(name);
    await form.getByLabel("Document file", { exact: true }).setInputFiles({ name: `synthetic-qa.${extension}`, mimeType, buffer: content });
    await form.getByRole("group", { name: "Assign document to published items", exact: true }).getByRole("button", { name: "Select all currently published items", exact: true }).click();
    await form.getByRole("radio", { name: "General customer-service Q&A", exact: true }).check();
    await expect(form.getByRole("group", { name: "Assign document to published items", exact: true })).toHaveCount(0);
    const uploaded = page.waitForResponse((response) => response.url() === `${endpoint}/documents` && response.request().method() === "POST");
    await form.getByRole("button", { name: "Upload document", exact: true }).click();
    const response = await uploaded;
    expect(response.status(), await response.text()).toBe(201);
    const document: Source = await response.json();
    expect(document).toMatchObject({ name, scope: "general", itemRefs: [], origin: "document", kind: extension === "docx" ? "docx" : "text", format: extension, bytes: content.length, state: "pending", facts: [] });
    expect(response.request().method()).toBe("POST");
    expect(response.request().headers()["content-type"]).toMatch(/^multipart\/form-data;/);
    expect(await source(request, document.id)).toMatchObject({ scope: "general", itemRefs: [] });
    const library = page.getByRole("region", { name: "Uploaded documents", exact: true });
    const row = library.getByRole("listitem").filter({ has: page.getByRole("button", { name: `Review document: ${name}`, exact: true }) });
    const stats = async () => {
      const documents = (await index(request)).sources.filter((source) => source.origin === "document");
      await expect(library.locator("dl").first().locator("div").filter({ has: page.locator("dt", { hasText: /^Uploaded$/ }) }).locator("dd")).toHaveText(String(documents.length));
      await expect(library.locator("dl").first().locator("div").filter({ has: page.locator("dt", { hasText: /^Awaiting review$/ }) }).locator("dd")).toHaveText(String(documents.filter((source) => source.state === "review").length));
      const items = (await index(request)).items;
      const configuration = await request.get(`${api}/api/admin/support/config`, { headers });
      expect(configuration.status()).toBe(200);
      const settings: { enabled: boolean; allowedTopics: string[] } = await configuration.json();
      const ready = documents.filter((source) => settings.enabled && source.state === "approved" && source.approvedCurrent !== false && source.facts.some((fact) => settings.allowedTopics.includes(fact.topic)) && source.bytes !== 0 && (source.scope === "general" || source.itemRefs.some((ref) => items.some((item) => item.ref === ref))));
      await expect(library.locator("dl").first().locator("div").filter({ has: page.locator("dt", { hasText: /^Ready for assistant$/ }) }).locator("dd")).toHaveText(String(ready.length));
    };
    await expect(row).toContainText(extension.toUpperCase());
    await expect(row).toContainText(content.length < 1024 ? `${content.length} bytes` : `${(content.length / 1024).toFixed(1)} KiB`);
    await expect(row).toContainText("General customer-service Q&A · no product assignment");
    await expect(row).toContainText("Not included in assistant knowledge");
    await expect(row.locator("time")).toHaveAttribute("datetime", document.createdAt); await stats();
    await page.reload(); await openKnowledge(page);
    await expect(row).toBeVisible(); await expect(row).toContainText("Pending extraction"); await stats();
    await row.getByRole("button").click();
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
    await expect(page.getByRole("group", { name: "Assigned published items", exact: true })).toHaveCount(0);
    const downloaded = page.waitForResponse((response) => response.url() === `${endpoint}/sources/${document.id}/file` && response.request().method() === "GET");
    const savedDownload = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download source", exact: true }).click();
    const download = await downloaded;
    expect(download.status()).toBe(200);
    expect(download.headers()["content-disposition"]).toContain("attachment");
    const savedFile = await savedDownload;
    const downloadedPath = await savedFile.path();
    expect(downloadedPath).not.toBeNull();
    expect(readFileSync(downloadedPath!)).toEqual(content);
    await savedFile.delete();
    await expect(page.getByRole("status").filter({ hasText: "Source download started" })).toBeVisible();
    await acknowledgement(page).check();
    await page.getByRole("button", { name: "Extract source", exact: true }).click();
    await expect.poll(async () => (await source(request, document.id)).state, { timeout: 20_000 }).toBe("review");
    await expect(row).toContainText("Draft · needs review"); await stats();
    const draft = await source(request, document.id);
    expect(draft.facts.length).toBeGreaterThan(0);
    expect(draft.facts.every((fact) => fact.topic === "customer_service")).toBe(true);
    await expect(page.getByRole("combobox", { name: "Topic 1", exact: true })).toHaveValue("customer_service");
    await page.getByRole("button", { name: "Approve reviewed facts", exact: true }).click();
    await expect(row).toContainText("Included in assistant knowledge"); await stats();
    await page.reload(); await openKnowledge(page);
    await expect(row).toContainText("Included in assistant knowledge"); await stats();
    await row.getByRole("button").click();
    const approvedRevision = (await source(request, document.id)).revision;
    await page.getByRole("group", { name: "Source scope", exact: true }).getByRole("radio", { name: "Product documents", exact: true }).check();
    await page.getByRole("group", { name: "Assigned published items", exact: true }).getByRole("checkbox", { name: new RegExp(fixture.product.name) }).check();
    const saved = page.waitForResponse((response) => response.url() === `${endpoint}/sources/${document.id}/assignment`);
    await page.getByRole("button", { name: "Save assignment", exact: true }).click();
    const assignment = await saved;
    expect(assignment.status(), await assignment.text()).toBe(200);
    expect(assignment.request().postDataJSON()).toEqual({ scope: "products", itemRefs: [fixture.product.ref], expectedRevision: approvedRevision });
    await expect(row).toContainText("Not included in assistant knowledge");
    expect((await source(request, document.id)).state).not.toBe("approved"); await stats();
    await acknowledgement(page).check();
    await page.getByRole("button", { name: "Extract source", exact: true }).click();
    await expect.poll(async () => (await source(request, document.id)).state, { timeout: 20_000 }).toBe("review");
    await expect(page.getByRole("button", { name: "Reject draft", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Reject draft", exact: true }).click();
    await expect(row).toContainText("Rejected"); await expect(row).toContainText("Not included in assistant knowledge"); await stats();
  });
}

test("KNW-013: existing document stays discoverable among 92 catalog sources; pending/rejected/stale metadata is never ready", async ({ page, request, fixture }) => {
  const document = await upload(request, fixture);
  const current = await index(request);
  const catalog = Array.from({ length: 92 }, (_, number) => ({ ...document, id: `catalog-${fixture.marker}-${number}`, name: `Synthetic catalog image ${number}`, kind: "image", format: "png", origin: "catalog" }));
  let state = "pending";
  await page.route(endpoint, (route) => route.fulfill({ json: { ...current, sources: [
    ...catalog, { ...document, state, facts: state === "pending" ? [] : [{ text: "Synthetic reviewed product fact.", topic: "products", location: "Page 1" }] },
  ] } }));
  await signIn(page); await openKnowledge(page);
  const library = page.getByRole("region", { name: "Uploaded documents", exact: true });
  const row = library.getByRole("listitem");
  await expect(library.getByRole("heading", { name: "Uploaded documents", exact: true })).toBeVisible();
  await expect(row).toHaveCount(1);
  await expect(row).toContainText(document.name);
  await expect(row).not.toContainText("Synthetic catalog image");
  await expect(page.getByRole("button", { name: "All sources (93)", exact: true })).toBeVisible();
  const ready = library.locator("dl").first().locator("div").filter({ has: page.locator("dt", { hasText: /^Ready for assistant$/ }) }).locator("dd");
  const uploaded = library.locator("dl").first().locator("div").filter({ has: page.locator("dt", { hasText: /^Uploaded$/ }) }).locator("dd");
  const review = library.locator("dl").first().locator("div").filter({ has: page.locator("dt", { hasText: /^Awaiting review$/ }) }).locator("dd");
  for (const next of ["pending", "review", "approved", "rejected", "stale"]) {
    state = next; await refresh(page);
    await expect(uploaded).toHaveText("1"); await expect(ready).toHaveText(state === "approved" ? "1" : "0");
    await expect(review).toHaveText(state === "review" ? "1" : "0");
    await expect(row).toContainText(state === "approved" ? "Included in assistant knowledge" : "Not included in assistant knowledge");
  }
  await row.getByRole("button", { name: `Review document: ${document.name}`, exact: true }).click();
  await expect(page.getByRole("heading", { name: document.name, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download source", exact: true })).toBeEnabled();
});

test("KNW-014: general document readiness respects customized AI topics, global disabled state and unavailable settings", async ({ page, request, fixture }) => {
  const document = await upload(request, fixture);
  const current = await index(request);
  const configEndpoint = `${api}/api/admin/support/config`;
  const configuration = await request.get(configEndpoint, { headers });
  expect(configuration.status()).toBe(200);
  const original = await configuration.json();
  let settings: { enabled: boolean; allowedTopics: string[] } | null = { enabled: true, allowedTopics: ["products", "pricing", "compatibility"] };
  let sourceBytes = document.bytes;
  let sourceNote: string | null = null;
  let approvedCurrent = true;
  await page.route(configEndpoint, (route) => route.fulfill(settings ? { json: { ...original, ...settings } } : { status: 503, json: { detail: "Synthetic configuration unavailable." } }));
  await page.route(endpoint, (route) => route.fulfill({ json: { ...current, sources: [{
    ...document, scope: "general", itemRefs: [], state: "approved", bytes: sourceBytes, error: sourceNote, approvedCurrent,
    facts: [{ text: "Synthetic approved customer-service answer.", topic: "customer_service", location: "Page 1" }],
  }] } }));
  await signIn(page); await openKnowledge(page);
  const library = page.getByRole("region", { name: "Uploaded documents", exact: true });
  const row = library.getByRole("listitem");
  const ready = library.locator("dl").first().locator("div").filter({ has: page.locator("dt", { hasText: /^Ready for assistant$/ }) }).locator("dd");
  await expect(row).toContainText("Approved"); await expect(row).toContainText("Not included in assistant knowledge");
  await expect(ready).toHaveText("0");
  await expect(library.getByRole("alert")).toContainText("General customer-service Q&A is excluded by the current AI scope.");
  await expect(library.getByRole("alert")).toContainText("Approved customer-service Q&A");
  settings = { ...settings, allowedTopics: [...settings.allowedTopics, "customer_service"] };
  await refresh(page);
  await expect(library.getByRole("alert")).toHaveCount(0);
  await expect(ready).toHaveText("1"); await expect(row).toContainText("Included in assistant knowledge");
  sourceNote = "Word text/tables processed; upload PDF/images for diagrams";
  await refresh(page);
  await expect(ready).toHaveText("1"); await expect(row).toContainText("Included in assistant knowledge");
  await expect(row).toContainText(`Source note: ${sourceNote}`);
  sourceBytes = 0; sourceNote = "Private source blob is missing or unavailable.";
  await refresh(page);
  await expect(ready).toHaveText("0"); await expect(row).toContainText("Not included in assistant knowledge");
  sourceBytes = document.bytes; sourceNote = null;
  approvedCurrent = false; await refresh(page);
  await expect(ready).toHaveText("0"); await expect(row).toContainText("Approval is no longer current.");
  approvedCurrent = true;
  settings = { ...settings, enabled: false }; await refresh(page);
  await expect(ready).toHaveText("0"); await expect(row).toContainText("Not included in assistant knowledge");
  await expect(library.getByRole("alert")).toContainText("Automatic AI replies are disabled.");
  settings = null; await refresh(page);
  await expect(ready).toHaveText("—"); await expect(row).toContainText("Assistant inclusion unconfirmed");
  await expect(library.getByRole("alert")).toContainText("AI scope settings could not be confirmed.");
  expect((await source(request, document.id)).state).toBe("pending");
});
