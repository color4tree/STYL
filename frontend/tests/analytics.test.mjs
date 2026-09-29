import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = ts.transpileModule(fs.readFileSync(new URL("../src/lib/analytics.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const config = {
  enabled: true, mode: "aggregate-only", environment: "test", timezone: "America/Los_Angeles",
  heartbeatSeconds: 15, idleSeconds: 60, maxEvents: 20, maxBatchBytes: 16384, allowedCampaigns: ["approved"],
};
const plain = value => JSON.parse(JSON.stringify(value));
const settle = async () => { for (let i = 0; i < 8; i++) await new Promise(resolve => setImmediate(resolve)); };
const legacyKeys = ["styl-analytics-consent", "styl-analytics-session", "styl-analytics-visitor", "styl-analytics-lease"];
const excludeKey = "styl-analytics-exclude";

function harness(options = {}) {
  let now = Date.UTC(2026, 8, 28, 12);
  const requests = [], observers = [], mutations = [], warnings = [], writes = [];
  const storage = options.storage ?? new Map();
  const timers = new Map(), intervals = new Map();
  let timerId = 0;
  class Target {
    listeners = new Map();
    addEventListener(name, callback) {
      if (!this.listeners.has(name)) this.listeners.set(name, new Set());
      this.listeners.get(name).add(callback);
    }
    removeEventListener(name, callback) { this.listeners.get(name)?.delete(callback); }
    dispatchEvent(event) { for (const callback of this.listeners.get(event.type) ?? []) callback(event); return true; }
  }
  class Element {
    dataset = {};
    isConnected = true;
    constructor(root) { this.root = root ?? this; }
    closest() { return this.root; }
    querySelectorAll() { return this.targets ?? []; }
  }
  const window = new Target();
  window.localStorage = {
    getItem: key => { if (options.blockRead) throw new Error("PRIVATE_STORAGE_MARKER"); return storage.get(key) ?? null; },
    setItem: (key, value) => { if (options.blockWrite) throw new Error("PRIVATE_STORAGE_MARKER"); writes.push(key); storage.set(key, value); },
    removeItem: key => { if (options.blockRemove) throw new Error("PRIVATE_STORAGE_MARKER"); storage.delete(key); },
  };
  window.sessionStorage = { getItem: key => options.admin && key === "styl-admin-token" ? "PRIVATE_ADMIN_MARKER" : null };
  window.location = { pathname: "/", hostname: "localhost", search: "", hash: "", origin: "http://localhost:3102", ...options.location };
  window.innerWidth = 390;
  window.innerHeight = 844;
  const document = new Target();
  document.visibilityState = options.hidden ? "hidden" : "visible";
  document.focused = options.focused ?? false;
  document.hasFocus = () => document.focused;
  document.referrer = options.referrer ?? "";
  document.body = {};
  document.roots = [];
  document.markers = [];
  document.videos = [];
  document.querySelectorAll = selector => {
    if (selector === "video") return document.videos;
    if (selector === "[data-analytics-item-id]") return document.roots;
    if (selector === "[data-analytics-event]") return document.markers;
    return document.roots.flatMap(root => root.targets);
  };
  const navigator = {
    doNotTrack: options.dnt ?? "0", globalPrivacyControl: options.gpc ?? false,
    locks: options.locks === false ? undefined : options.locks ?? { request: async (_name, _options, callback) => callback({}) },
  };
  const compiled = { exports: {} };
  const context = vm.createContext({
    module: compiled, exports: compiled.exports, require: () => ({ API_BASE: "http://localhost:8102" }),
    window, document, navigator, Element, HTMLElement: Element, URL, URLSearchParams, TextEncoder, AbortController, Event,
    crypto: { randomUUID: () => { throw new Error("Aggregate analytics must not generate identifiers."); } },
    Date: class extends Date { constructor(value = now) { super(value); } static now() { return now; } },
    performance: { timeOrigin: now },
    setTimeout: (callback, delay) => { const id = ++timerId; timers.set(id, { callback, at: now + delay }); return id; },
    clearTimeout: id => timers.delete(id),
    setInterval: (callback, delay) => { const id = ++timerId; intervals.set(id, { callback, delay }); return id; },
    clearInterval: id => intervals.delete(id),
    IntersectionObserver: class {
      constructor(callback) { this.callback = callback; this.observed = []; observers.push(this); }
      observe(element) { this.observed.push(element); }
      disconnect() { this.observed = []; }
    },
    MutationObserver: class { constructor(callback) { mutations.push(callback); } observe() {} disconnect() {} },
    console: { warn: message => warnings.push(message) },
    fetch: async (url, init = {}) => {
      const request = { url, method: init.method ?? "GET", body: init.body ? JSON.parse(init.body) : undefined, init };
      requests.push(request);
      const overridden = await options.fetch?.(request);
      if (overridden) return overridden;
      const data = url.endsWith("/config") ? { ...config, ...options.config } : { accepted: request.body.events.length };
      return { ok: true, status: 200, json: async () => data };
    },
  });
  vm.runInContext(source, context);
  const api = compiled.exports;
  let cleanup;
  const advance = ms => {
    now += ms;
    for (const [id, timer] of [...timers]) if (timer.at <= now) { timers.delete(id); timer.callback(); }
  };
  return {
    api, window, document, storage, requests, warnings, writes, observers, mutations, advance,
    events: () => requests.filter(request => request.url.endsWith("/events")).flatMap(request => request.body.events),
    interval: delay => { for (const interval of intervals.values()) if (interval.delay === delay) interval.callback(); },
    async start() { cleanup = api.initializeAnalytics(); await settle(); },
    stop() { cleanup?.(); },
    item(id = 1, type = "product", detail = false) {
      const root = new Element();
      root.dataset = { analyticsItemId: String(id), analyticsItemType: type, ...(detail ? { analyticsEvent: "item_detail_open" } : {}) };
      root.targets = [new Element(root), new Element(root)];
      document.roots.push(root);
      if (detail) document.markers.push(root);
      return root;
    },
    intersect(root, ratio) { for (const observer of observers) observer.callback(root.targets.map(target => ({ target, intersectionRatio: ratio }))); },
    navigate(href, overrides = {}) {
      const link = new Element();
      link.href = new URL(href, window.location.origin).href;
      link.target = "";
      link.hasAttribute = () => false;
      link.closest = selector => selector === "a[href]" ? link : selector === "header" && overrides.header ? {} : null;
      document.dispatchEvent({ type: "click", target: link, isTrusted: true, button: 0, ...overrides });
    },
  };
}

test("AN-001 AN-007: automatic page count has no identifiers, timestamps, cookies or persisted analytics state", async () => {
  const h = harness();
  await h.start();
  assert.deepEqual(h.events(), [{ name: "page_view", path: "/", properties: {} }]);
  assert.equal(h.storage.size, 0);
  assert.deepEqual(h.writes, []);
  assert.equal(h.requests.some(request => request.url.endsWith("/session")), false);
  for (const request of h.requests) {
    assert.equal(request.init.credentials, "omit");
    assert.equal(request.init.referrerPolicy, "no-referrer");
  }
  h.stop();
});

test("AN-007 AN-008: old consent is not a license to collect identified sessions; legacy keys are removed", async () => {
  const storage = new Map(legacyKeys.map(key => [key, JSON.stringify(key.endsWith("consent") ? { choice: "accepted", remember: true } : { id: "PRIVATE_LEGACY_ID" })]));
  const h = harness({ storage });
  await h.start();
  assert.equal(storage.size, 0);
  assert.equal(h.events().length, 1);
  assert.equal(JSON.stringify(h.requests).includes("PRIVATE_LEGACY_ID"), false);
  assert.deepEqual(h.writes, []);
  h.stop();
});

test("AN-007: prior decline becomes a boolean opt-out, not an implicit opt-in", async () => {
  const h = harness({ storage: new Map([["styl-analytics-consent", '{"choice":"declined"}']]) });
  await h.start();
  assert.deepEqual([...h.storage.entries()], [[excludeKey, "true"]]);
  assert.equal(h.events().length, 0);
  assert.equal(h.api.getAnalyticsStatus().optedOut, true);
  h.stop();
});

test("AN-008: admin/privacy pages, saved admin token, DNT/GPC, internal exclusion and disabled config do not collect", async () => {
  for (const options of [
    { admin: true }, { location: { pathname: "/admin" } }, { location: { pathname: "/privacy" } },
    { dnt: "1" }, { dnt: "yes" }, { gpc: true }, { storage: new Map([[excludeKey, "1"]]) }, { config: { enabled: false } },
  ]) {
    const h = harness(options);
    await h.start();
    h.api.trackAnalytics("cart_add", { itemType: "product", itemId: 1 });
    h.interval(15000);
    await settle();
    assert.equal(h.events().length, 0);
    h.stop();
  }
});

test("AN-007 AN-009: unavailable storage and invalid legacy JSON fail closed with sanitized diagnostics", async () => {
  for (const options of [{ blockRead: true }, { blockRemove: true }, { storage: new Map([["styl-analytics-consent", "{invalid"]]) }]) {
    const h = harness(options);
    await h.start();
    assert.equal(h.events().length, 0);
    assert.ok(h.warnings.length);
    assert.equal(h.warnings.join().includes("PRIVATE_STORAGE_MARKER"), false);
    h.stop();
  }
});

test("AN-007: opt-out clears pending events and cross-tab preference changes take effect", async () => {
  const storage = new Map();
  const a = harness({ storage }), b = harness({ storage });
  await a.start(); await b.start();
  a.api.trackAnalytics("cart_clear", { lineCount: 2 });
  b.api.trackAnalytics("cart_clear", { lineCount: 2 });
  assert.equal(a.api.setAnalyticsOptOut(true), true);
  b.window.dispatchEvent({ type: "storage", key: excludeKey });
  await a.api.flushAnalytics(); await b.api.flushAnalytics();
  assert.equal(a.events().length, 1);
  assert.equal(b.events().length, 1);
  assert.deepEqual([...storage.keys()], [excludeKey]);
  assert.equal(a.api.setAnalyticsOptOut(false), true);
  await settle();
  assert.equal(a.events().length, 2);
  a.stop(); b.stop();
});

test("AN-007: opting back in never overrides a browser privacy signal", async () => {
  const h = harness({ gpc: true, storage: new Map([[excludeKey, "true"]]) });
  await h.start();
  assert.equal(h.api.setAnalyticsOptOut(false), true);
  await settle();
  assert.equal(h.events().length, 0);
  h.stop();
});

test("AN-009: preference write failures stay explicit without exposing storage error contents", async () => {
  const h = harness({ blockWrite: true });
  await h.start();
  assert.equal(h.api.setAnalyticsOptOut(true), false);
  assert.match(h.api.getAnalyticsStatus().diagnostic, /could not be saved/);
  assert.equal(h.warnings.join().includes("PRIVATE_STORAGE_MARKER"), false);
  h.api.trackAnalytics("cart_clear");
  await h.api.flushAnalytics();
  assert.equal(h.events().length, 1);
  h.stop();
});

test("AN-001: route rerenders/focus do not duplicate page views; actual routes and BFCache restores do", async () => {
  const h = harness();
  await h.start();
  h.api.analyticsRouteChanged("/");
  h.window.dispatchEvent(new Event("focus"));
  await settle();
  assert.equal(h.events().length, 1);
  h.window.location.pathname = "/products/one";
  h.api.analyticsRouteChanged("/products/one");
  await settle();
  h.window.location.pathname = "/products/two";
  h.api.analyticsRouteChanged("/products/two");
  await settle();
  h.window.location.pathname = "/accessories/1001";
  h.api.analyticsRouteChanged("/accessories/1001");
  await settle();
  assert.deepEqual(h.events().map(event => event.path), ["/", "/products/[slug]", "/products/[slug]", "/accessories/[id]"]);
  h.window.dispatchEvent({ type: "pageshow", persisted: true });
  await settle();
  assert.equal(h.events().length, 5);
  h.stop();
});

test("AN-002: identity AND price need 50% visibility for one continuous second; per-view dedup is memory-only", async () => {
  const h = harness(), item = h.item();
  await h.start();
  h.intersect(item, 0.49); h.advance(1000);
  await h.api.flushAnalytics();
  assert.equal(h.events().filter(event => event.name === "item_impression").length, 0);
  h.intersect(item, 0.5); h.advance(999);
  h.intersect(item, 0); h.advance(1);
  h.intersect(item, 0.5); h.advance(1000);
  await h.api.flushAnalytics();
  h.intersect(item, 1); h.advance(2000);
  await h.api.flushAnalytics();
  assert.equal(h.events().filter(event => event.name === "item_impression").length, 1);
  assert.equal(h.storage.size, 0);
  h.stop();
});

test("AN-003: rendered detail/cart markers are discovered without extra catalog requests", async () => {
  const h = harness();
  h.item(3, "accessory", true);
  await h.start();
  assert.equal(h.events().filter(event => event.name === "item_detail_open").length, 1);
  assert.equal(h.requests.every(request => request.url.includes("/api/analytics/")), true);
  h.mutations.forEach(callback => callback());
  await h.api.flushAnalytics();
  assert.equal(h.events().filter(event => event.name === "item_detail_open").length, 1);
  h.stop();
});

test("AN-008: only coarse sources/campaigns leave the browser; full referrers/queries and unknown properties never do", async () => {
  const h = harness({ referrer: "https://www.google.com/search?q=PRIVATE_QUERY_MARKER", location: { search: "?utm_source=google&utm_medium=cpc&utm_campaign=approved&email=PRIVATE_EMAIL" } });
  await h.start();
  h.api.trackAnalytics("cart_add", { itemType: "product", itemId: 1, quantity: 2, email: "PRIVATE_EMAIL", ip: "PRIVATE_IP" });
  await h.api.flushAnalytics();
  const body = h.requests.find(request => request.method === "POST").body;
  assert.deepEqual(body.context, { source: "google", medium: "cpc", campaign: "approved", viewport: "phone" });
  assert.equal(JSON.stringify(h.requests).includes("PRIVATE_"), false);
  assert.deepEqual(plain(h.api.sanitizeAnalyticsProperties("engagement", { activeMs: 15, intervalStart: "PRIVATE_TIME", intervalEnd: "PRIVATE_TIME" })), { activeMs: 15 });
  assert.equal(h.api.canonicalAnalyticsPath("/products/equipment?email=PRIVATE"), "/products/[slug]");
  assert.equal(h.api.canonicalAnalyticsPath("/accessories/1001?email=PRIVATE"), "/accessories/[id]");
  h.stop();
});

test("AN-009: queue is bounded at 100, batches at 20/16KiB; events contain no stable dedup identifiers", async () => {
  const h = harness();
  await h.start();
  for (let i = 0; i < 140; i++) h.api.trackAnalytics("cart_add", { itemType: "product", itemId: i + 1 });
  for (let i = 0; i < 7; i++) await h.api.flushAnalytics();
  assert.equal(h.events().length, 101);
  for (const request of h.requests.filter(request => request.body)) {
    assert.ok(request.body.events.length <= 20);
    assert.ok(Buffer.byteLength(JSON.stringify(request.body)) < 16384);
    for (const event of request.body.events) assert.deepEqual(Object.keys(event).sort(), ["name", "path", "properties"]);
  }
  h.stop();
});

test("AN-009: ambiguous network delivery is not retried; later independent actions can be measured", async () => {
  let fail = false;
  const h = harness({ fetch: request => {
    if (fail && request.url.endsWith("/events")) throw new Error("PRIVATE_NETWORK_ERROR");
  } });
  await h.start();
  fail = true;
  h.api.trackAnalytics("cart_clear");
  await h.api.flushAnalytics();
  await h.api.flushAnalytics();
  assert.equal(h.events().filter(event => event.name === "cart_clear").length, 1);
  fail = false;
  h.api.trackAnalytics("cart_view");
  await h.api.flushAnalytics();
  assert.equal(h.events().filter(event => event.name === "cart_view").length, 1);
  assert.equal(h.warnings.join().includes("PRIVATE_NETWORK_ERROR"), false);
  h.stop();
});

test("AN-009: rejected events are dropped without reading private response bodies; stale queued events expire", async () => {
  let reject = false;
  const h = harness({ fetch: request => reject && request.url.endsWith("/events") ? { ok: false, status: 422, json: () => { throw new Error("Private response must not be read"); } } : undefined });
  await h.start();
  reject = true;
  h.api.trackAnalytics("cart_clear");
  await h.api.flushAnalytics();
  assert.match(h.api.getAnalyticsStatus().diagnostic, /rejected/);
  h.api.trackAnalytics("cart_view");
  h.advance(300001);
  await h.api.flushAnalytics();
  assert.equal(h.events().filter(event => event.name === "cart_view").length, 0);
  h.stop();
});

test("AN-004: visible focused active time is bounded and transmitted without interval timestamps", async () => {
  const h = harness({ focused: true });
  await h.start();
  for (let i = 0; i < 18; i++) { h.advance(1000); h.interval(1000); await settle(); }
  h.document.visibilityState = "hidden";
  h.document.dispatchEvent(new Event("visibilitychange"));
  await settle();
  const intervals = h.events().filter(event => event.name === "engagement");
  assert.ok(intervals.length);
  assert.ok(intervals.every(event => Object.keys(event.properties).join() === "activeMs" && event.properties.activeMs <= 15000));
  const measured = intervals.reduce((sum, event) => sum + event.properties.activeMs, 0);
  h.advance(100000); h.interval(1000); await h.api.flushAnalytics();
  assert.equal(h.events().filter(event => event.name === "engagement").reduce((sum, event) => sum + event.properties.activeMs, 0), measured);
  assert.equal(h.storage.size, 0);
  h.stop();
});

test("AN-004: cross-tab active measurement uses an exclusive lock without persisted lease IDs", async () => {
  let held = false;
  const locks = { request: async (_name, _options, callback) => {
    if (held) return callback(null);
    held = true;
    try { return await callback({}); } finally { held = false; }
  } };
  const a = harness({ focused: true, locks }), b = harness({ focused: true, locks });
  await a.start(); await b.start();
  for (let i = 0; i < 18; i++) {
    for (const h of [a, b]) { h.advance(1000); h.interval(1000); await settle(); }
  }
  for (const h of [a, b]) { h.window.dispatchEvent(new Event("blur")); await h.api.flushAnalytics(); }
  assert.ok(a.events().some(event => event.name === "engagement"));
  assert.equal(b.events().some(event => event.name === "engagement"), false);
  assert.equal(a.storage.size + b.storage.size, 0);
  a.stop(); b.stop();
});

test("AN-004: browsers without Web Locks omit active-time estimates but still count pages", async () => {
  const h = harness({ focused: true, locks: false });
  await h.start();
  h.advance(1000); h.interval(1000);
  await h.api.flushAnalytics();
  assert.deepEqual(h.events().map(event => event.name), ["page_view"]);
  assert.ok(h.warnings.length);
  h.stop();
});

test("AN-004: focused but idle browsers stop accumulating after the 60-second activity boundary", async () => {
  const h = harness({ focused: true });
  await h.start();
  for (let i = 0; i < 65; i++) { h.advance(1000); h.interval(1000); await settle(); }
  await h.api.flushAnalytics();
  const total = h.events().filter(event => event.name === "engagement").reduce((sum, event) => sum + event.properties.activeMs, 0);
  assert.ok(total > 0 && total <= 60000);
  for (let i = 0; i < 20; i++) { h.advance(1000); h.interval(1000); await settle(); }
  await h.api.flushAnalytics();
  assert.equal(h.events().filter(event => event.name === "engagement").reduce((sum, event) => sum + event.properties.activeMs, 0), total);
  h.stop();
});

test("AN-001 AN-008: only intentional internal navigation counts; admin/privacy and external links do not", async () => {
  const h = harness();
  await h.start();
  h.navigate("/accessories?email=PRIVATE");
  h.navigate("/admin");
  h.navigate("/privacy");
  h.navigate("https://example.com/");
  h.navigate("/cart", { isTrusted: false });
  await h.api.flushAnalytics();
  assert.deepEqual(h.events().filter(event => event.name === "navigation_click").map(event => event.properties.toPath), ["/accessories"]);
  h.stop();
});

test("AN-009 AN-014: vitals and errors contain only reviewed measurements, never stacks or messages", async () => {
  const h = harness();
  await h.start();
  h.api.reportAnalyticsVital({ name: "LCP", value: 12.3, entries: [{ startTime: 10 }], id: "PRIVATE_VITAL_ID" });
  h.window.dispatchEvent({ type: "error", message: "PRIVATE_ERROR", filename: "PRIVATE_URL" });
  await h.api.flushAnalytics();
  assert.equal(JSON.stringify(h.requests).includes("PRIVATE_"), false);
  assert.deepEqual(h.events().find(event => event.name === "web_vital").properties, { metric: "LCP", value: 12.3 });
  h.stop();
});

test("AN-009: config outage/old identified mode fail closed and reconnect can recover", async () => {
  let broken = true;
  const h = harness({ fetch: request => {
    if (broken && request.url.endsWith("/config")) throw new Error("PRIVATE_CONFIG");
  } });
  await h.start();
  assert.equal(h.events().length, 0);
  broken = false;
  h.window.dispatchEvent(new Event("online"));
  await settle();
  assert.equal(h.events().length, 1);
  h.stop();
  const old = harness({ config: { mode: undefined } });
  await old.start();
  assert.equal(old.events().length, 0);
  old.stop();
});

test("AN-007 AN-009: failed diagnostic subscribers cannot recurse or break commerce", async () => {
  const h = harness({ blockRead: true });
  h.api.subscribeAnalytics(() => { throw new Error("PRIVATE_SUBSCRIBER"); });
  await h.start();
  assert.doesNotThrow(() => h.api.trackAnalytics("cart_clear"));
  assert.equal(h.events().length, 0);
  assert.equal(h.warnings.join().includes("PRIVATE_"), false);
  assert.ok(h.warnings.length <= 4);
  h.stop();
});
