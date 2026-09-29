import { API_BASE } from "./api";
import type { AnalyticsConfig, AnalyticsContext, AnalyticsEvent, AnalyticsEventName, AnalyticsItemReference, AnalyticsProperties } from "./analyticsTypes";

export const ANALYTICS_KEYS = {
  consent: "styl-analytics-consent",
  visitor: "styl-analytics-visitor",
  session: "styl-analytics-session",
  lease: "styl-analytics-lease",
  exclude: "styl-analytics-exclude",
} as const;
const CHANGE = "styl-analytics-change";
const MAX_AGE = 5 * 60_000;
type Queued = { event: AnalyticsEvent; at: number };
type Status = { ready: boolean; enabled: boolean; active: boolean; optedOut: boolean; excluded: boolean; diagnostic: string };
const initialStatus: Status = { ready: false, enabled: false, active: false, optedOut: false, excluded: false, diagnostic: "" };
let status = initialStatus;
let config: AnalyticsConfig | null = null;
let route = "";
let queue: Queued[] = [];
let generation = 0;
let flushing = false;
let pageSeen = new Set<string>();
let legacyCleared = false;
let temporaryOptOut = false;
let context: AnalyticsContext = {};
let documentPath = "";
let lastActivity = 0;
let activeMs = 0;
let lastTick = 0;
let ownsActiveInterval = false;
let intervalPending = false;
let releaseActiveInterval: (() => void) | undefined;
let quoteNavigation = false;
let quoteSource: AnalyticsProperties["source"];
let stopWatching: (() => void) | undefined;
const requests = new Set<AbortController>();
const subscribers = new Set<() => void>();
const diagnosticMessages = {
  "storage-read": "Optional analytics could not read browser storage; shopping is unaffected.",
  "storage-write": "The usage measurement preference could not be saved; shopping is unaffected.",
  "storage-remove": "Analytics identifiers could not be cleared from browser storage. You can clear this site's browser data if needed.",
  "exclusion-check": "Analytics is off because browser privacy controls could not be checked; shopping is unaffected.",
  event: "An optional analytics event could not be recorded; shopping is unaffected.",
  delivery: "Optional analytics delivery is temporarily unavailable; shopping is unaffected.",
  "batch-rejected": "An analytics batch was rejected and was not recorded; shopping is unaffected.",
  config: "Optional analytics is unavailable; shopping is unaffected.",
  unsupported: "Optional analytics is unavailable in this browser; shopping is unaffected.",
  notification: "Analytics preferences could not refresh their status; shopping is unaffected.",
} as const;
type DiagnosticCode = keyof typeof diagnosticMessages;
const activeDiagnostics = new Set<DiagnosticCode>();
const failedReads = new Set<string>();
const failedWrites = new Set<string>();
const failedRemovals = new Set<string>();
let notifyingStatus = false;

// Diagnostics never include exception messages, identifiers or request data.
function diagnose(code: DiagnosticCode) {
  if (activeDiagnostics.has(code)) return;
  activeDiagnostics.add(code);
  updateStatus({ diagnostic: diagnosticMessages[code] });
  try { console.warn(`STYL analytics: ${code}. ${diagnosticMessages[code]}`); }
  catch { /* The status remains available even if console logging is unavailable. */ }
}
function clearDiagnostics(...codes: DiagnosticCode[]) {
  let changed = false;
  for (const code of codes) changed = activeDiagnostics.delete(code) || changed;
  if (!changed) return;
  const remaining = [...activeDiagnostics].at(-1);
  updateStatus({ diagnostic: remaining ? diagnosticMessages[remaining] : "" });
}

export function canonicalAnalyticsPath(path: string): string {
  const pathname = path.split(/[?#]/, 1)[0].replace(/\/+$/, "") || "/";
  if (["/", "/accessories", "/cart"].includes(pathname)) return pathname;
  return /^\/products\/[^/]+$/.test(pathname) ? "/products/[slug]" : "other";
}

export function safeReferrerHost(referrer: string): string | undefined {
  try {
    const url = new URL(referrer);
    const host = url.hostname.toLowerCase().replace(/\.$/, "");
    if (!["http:", "https:"].includes(url.protocol) || host.length > 253 ||
      !/^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}$/.test(host)) return;
    return host;
  } catch { return; }
}

const eventKeys: Record<AnalyticsEventName, readonly (keyof AnalyticsProperties)[]> = {
  page_view: [], navigation_click: ["action", "toPath"],
  item_impression: ["itemType", "itemId", "list"], item_detail_open: ["itemType", "itemId"],
  item_details_expand: ["itemType", "itemId"], media_open: ["itemType", "itemId", "mediaType", "mediaIndex"],
  cart_add: ["itemType", "itemId", "quantity", "lineCount", "saleUnits"],
  cart_quantity_change: ["itemType", "itemId", "quantity", "lineCount", "saleUnits"],
  cart_remove: ["itemType", "itemId", "quantity", "lineCount", "saleUnits"],
  cart_clear: ["lineCount", "saleUnits"], cart_view: ["lineCount", "saleUnits"],
  quote_open: ["source", "itemType", "itemId"], quote_form_start: ["source"],
  quote_submit_attempt: ["source"], quote_error: ["source", "errorCode"],
  catalog_empty: ["list"], item_unavailable: ["itemType", "itemId"],
  engagement: ["activeMs"],
  site_error: ["errorCode"], web_vital: ["metric", "value"],
};
const enums: Partial<Record<keyof AnalyticsProperties, readonly string[]>> = {
  itemType: ["product", "accessory"], action: ["header", "menu", "catalog", "details", "continue_shopping", "back_to_collection", "section", "quote", "other"],
  source: ["header", "cart", "product", "direct", "unknown"], list: ["products", "accessories"],
  mediaType: ["image", "video"], errorCode: ["validation", "network", "storage", "catalog", "media", "unknown"],
  metric: ["LCP", "INP", "CLS"],
};

// This boundary deliberately copies only known scalar fields, never spread caller data.
export function sanitizeAnalyticsProperties(name: AnalyticsEventName, input: AnalyticsProperties = {}): AnalyticsProperties {
  const output: Record<string, string | number> = {};
  for (const key of eventKeys[name] ?? []) {
    const value = input[key];
    if (value === undefined) continue;
    if (enums[key]) {
      if (typeof value === "string" && enums[key]!.includes(value)) output[key] = value;
    } else if (key === "toPath") {
      if (typeof value === "string") output[key] = ["#products", "#about", "#contact", "#gallery"].includes(value) ? value : canonicalAnalyticsPath(value);
    } else if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
      const max = key === "quantity" ? 10 : key === "activeMs" ? 15_000 : key === "mediaIndex" ? 11 : key === "value" ? 3_600_000 : key === "itemId" ? Number.MAX_SAFE_INTEGER : 10000;
      if (value <= max && (key === "value" || Number.isSafeInteger(value)) && (key !== "itemId" || value > 0)) output[key] = value;
    }
  }
  return output as AnalyticsProperties;
}

function read<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const value = JSON.parse(window.localStorage.getItem(key) ?? "null") as T | null;
    failedReads.delete(key);
    if (!failedReads.size) clearDiagnostics("storage-read");
    return value;
  } catch { failedReads.add(key); diagnose("storage-read"); return null; }
}
function save(key: string, value: unknown): boolean {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    failedWrites.delete(key);
    if (!failedWrites.size) clearDiagnostics("storage-write");
    return true;
  } catch { failedWrites.add(key); diagnose("storage-write"); return false; }
}
function remove(key: string): boolean {
  try {
    window.localStorage.removeItem(key);
    failedRemovals.delete(key);
    if (!failedRemovals.size) clearDiagnostics("storage-remove");
    return true;
  } catch { failedRemovals.add(key); diagnose("storage-remove"); return false; }
}
function excluded(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const isExcluded = temporaryOptOut || /^\/(?:admin|privacy)(?:\/|$)/.test(window.location.pathname) ||
      window.sessionStorage.getItem("styl-admin-token") !== null ||
      window.localStorage.getItem(ANALYTICS_KEYS.exclude) !== null ||
      navigator.doNotTrack === "1" || navigator.doNotTrack === "yes" ||
      (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl === true;
    clearDiagnostics("exclusion-check");
    return isExcluded;
  } catch { diagnose("exclusion-check"); return true; }
}
function allowed(): boolean {
  return Boolean(legacyCleared && config?.enabled && config.mode === "aggregate-only" && !excluded());
}
function current(): boolean {
  return allowed() && route === window.location.pathname;
}
function updateStatus(next: Partial<Status>) {
  if ((Object.keys(next) as (keyof Status)[]).every((key) => status[key] === next[key])) return;
  status = { ...status, ...next };
  if (notifyingStatus) return;
  notifyingStatus = true;
  try {
    subscribers.forEach((notify) => {
      try { notify(); } catch { diagnose("notification"); }
    });
  } finally { notifyingStatus = false; }
}
export const subscribeAnalytics = (notify: () => void) => { subscribers.add(notify); return () => { subscribers.delete(notify); }; };
export const getAnalyticsStatus = () => status;
export const getServerAnalyticsStatus = () => initialStatus;

function reset() {
  generation++;
  requests.forEach((request) => request.abort());
  requests.clear();
  stopWatching?.();
  stopWatching = undefined;
  queue = [];
  route = "";
  pageSeen = new Set();
  flushing = false;
  activeMs = lastTick = 0;
  lastActivity = 0;
  quoteNavigation = false;
  quoteSource = undefined;
  releaseInterval();
  updateStatus({ active: false });
}
function clearLegacyIdentifiers(): boolean {
  const previous = read<{ choice?: string }>(ANALYTICS_KEYS.consent);
  if (failedReads.size) return false;
  if (previous?.choice === "declined" && !save(ANALYTICS_KEYS.exclude, true)) return false;
  const removed = [ANALYTICS_KEYS.session, ANALYTICS_KEYS.visitor, ANALYTICS_KEYS.lease, ANALYTICS_KEYS.consent].map(remove);
  return removed.every(Boolean);
}
export function setAnalyticsOptOut(optedOut: boolean): boolean {
  if (optedOut) {
    temporaryOptOut = true;
    reset();
    updateStatus({ optedOut: true, excluded: true });
  }
  if (!legacyCleared) legacyCleared = clearLegacyIdentifiers();
  if (!legacyCleared) return false;
  const saved = optedOut ? save(ANALYTICS_KEYS.exclude, true) : remove(ANALYTICS_KEYS.exclude);
  if (!saved) return false;
  temporaryOptOut = false;
  updateStatus({ optedOut });
  window.dispatchEvent(new Event(CHANGE));
  return true;
}

export function trackAnalytics(name: AnalyticsEventName, properties?: AnalyticsProperties): boolean {
  try {
    const recorded = enqueue(name, properties);
    if (recorded) clearDiagnostics("event");
    return recorded;
  } catch { diagnose("event"); return false; }
}
function enqueue(name: AnalyticsEventName, properties?: AnalyticsProperties): boolean {
  if (!Object.hasOwn(eventKeys, name) || !current()) return false;
  if (route !== window.location.pathname) return false;
  const event: AnalyticsEvent = {
    name,
    path: canonicalAnalyticsPath(route), properties: sanitizeAnalyticsProperties(name, properties),
  };
  queue = queue.filter((entry) => Date.now() - entry.at <= MAX_AGE).slice(-99);
  queue.push({ event, at: Date.now() });
  return true;
}

export function analyticsItem(item: { id: number; slug?: string; quantity?: number }): AnalyticsItemReference {
  return { itemType: item.slug ? "product" : "accessory", itemId: item.id, ...(item.quantity !== undefined ? { quantity: item.quantity } : {}) };
}

export function getQuoteAnalyticsSource(fallback: NonNullable<AnalyticsProperties["source"]> = "direct"): NonNullable<AnalyticsProperties["source"]> {
  return current() && quoteSource ? quoteSource : fallback;
}

function acquisitionContext(): AnalyticsContext {
  const params = new URLSearchParams(window.location.search);
  const source = params.get("utm_source")?.toLowerCase();
  const medium = params.get("utm_medium")?.toLowerCase();
  const campaign = params.get("utm_campaign");
  const host = safeReferrerHost(document.referrer);
  const known = ["google", "bing", "facebook", "instagram", "youtube", "linkedin"].find((name) => host === `${name}.com` || host?.endsWith(`.${name}.com`));
  const referrerSource = known ?? (host && host !== window.location.hostname ? "other" : "direct");
  return {
    source: source && ["google", "bing", "facebook", "instagram", "youtube", "linkedin", "newsletter", "direct", "other"].includes(source) ? source : referrerSource,
    ...(medium && ["organic", "cpc", "paid", "social", "email", "referral", "direct", "other"].includes(medium) ? { medium } : {}),
    ...(campaign && config?.allowedCampaigns.includes(campaign) ? { campaign } : {}),
    viewport: window.innerWidth < 768 ? "phone" : window.innerWidth < 1024 ? "tablet" : "desktop",
  };
}

function beginPage() {
  stopWatching?.();
  route = window.location.pathname;
  pageSeen = new Set();
  activeMs = lastTick = 0;
  trackAnalytics("page_view");
  if (!quoteNavigation) quoteSource = undefined;
  if (window.location.hash === "#contact" && !quoteNavigation) {
    const source = new URLSearchParams(window.location.search).get("quote");
    quoteSource = source === "cart" || source === "product" ? source : "direct";
    trackAnalytics("quote_open", { source: quoteSource });
  }
  quoteNavigation = false;
  stopWatching = observeContent();
  void flushAnalytics();
}
export function analyticsRouteChanged(pathname: string) {
  if (excluded()) { reset(); updateStatus({ excluded: true }); return; }
  if (!allowed() || document.visibilityState !== "visible") return;
  if (route !== pathname) { emitEngagement(); beginPage(); }
  updateStatus({ active: true, excluded: false });
}

export function analyticsPageEvent(name: AnalyticsEventName, properties: AnalyticsProperties = {}, key: string = name): boolean {
  if (pageSeen.has(key)) return false;
  if (!trackAnalytics(name, properties)) return false;
  pageSeen.add(key);
  return true;
}

function elementItem(element: Element): AnalyticsItemReference | undefined {
  const root = element.closest<HTMLElement>("[data-analytics-item-id]");
  const itemId = Number(root?.dataset.analyticsItemId);
  const itemType = root?.dataset.analyticsItemType;
  return Number.isSafeInteger(itemId) && itemId > 0 && (itemType === "product" || itemType === "accessory") ? { itemId, itemType } : undefined;
}
function observeContent(): () => void {
  const ratios = new Map<Element, number>();
  const timers = new Map<Element, ReturnType<typeof setTimeout>>();
  const observed = new Set<Element>();
  function check(root: Element) {
    const item = elementItem(root);
    if (!item || !current() || route !== window.location.pathname) return;
    const key = `impression:${item.itemType}:${item.itemId}`;
    const targets = root.querySelectorAll("[data-analytics-identity], [data-analytics-price]");
    const visible = document.visibilityState === "visible" && targets.length >= 2 && [...targets].every((element) => (ratios.get(element) ?? 0) >= 0.5);
    if (!visible || pageSeen.has(key)) { clearTimeout(timers.get(root)); timers.delete(root); return; }
    if (!timers.has(root)) timers.set(root, setTimeout(() => {
      timers.delete(root);
      if (!root.isConnected || route !== window.location.pathname || document.visibilityState !== "visible" || ![...targets].every((element) => (ratios.get(element) ?? 0) >= 0.5)) return;
      analyticsPageEvent("item_impression", { ...item, list: item.itemType === "product" ? "products" : "accessories" }, key);
    }, 1000));
  }
  const observer = typeof IntersectionObserver === "undefined" ? null : new IntersectionObserver((entries) => {
    for (const entry of entries) {
      ratios.set(entry.target, entry.intersectionRatio);
      const root = entry.target.closest("[data-analytics-item-id]");
      if (root) check(root);
    }
  }, { threshold: [0, 0.5, 1] });
  const scan = () => {
    if (!current() || route !== window.location.pathname) return;
    document.querySelectorAll("[data-analytics-identity], [data-analytics-price]").forEach((element) => {
      if (!observed.has(element)) { observed.add(element); observer?.observe(element); }
    });
    document.querySelectorAll<HTMLElement>("[data-analytics-event]").forEach((element) => {
      const name = element.dataset.analyticsEvent as AnalyticsEventName;
      if (!["item_detail_open", "cart_view", "catalog_empty", "item_unavailable", "site_error"].includes(name)) return;
      const item = elementItem(element);
      const properties: AnalyticsProperties = { ...item };
      if (element.dataset.analyticsList === "products" || element.dataset.analyticsList === "accessories") properties.list = element.dataset.analyticsList;
      if (name === "cart_view") {
        properties.lineCount = Number(element.dataset.analyticsLines);
        properties.saleUnits = Number(element.dataset.analyticsUnits);
      }
      if (name === "site_error") properties.errorCode = "catalog";
      analyticsPageEvent(name, properties, `${name}:${item?.itemType ?? ""}:${item?.itemId ?? properties.list ?? ""}`);
    });
  };
  const mutation = new MutationObserver(scan);
  mutation.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-analytics-event", "data-analytics-lines", "data-analytics-units"] });
  const visibility = () => { document.querySelectorAll("[data-analytics-item-id]").forEach(check); };
  document.addEventListener("visibilitychange", visibility);
  scan();
  return () => { observer?.disconnect(); mutation.disconnect(); timers.forEach(clearTimeout); document.removeEventListener("visibilitychange", visibility); };
}

export function makeAnalyticsBatch(entries: AnalyticsEvent[], context: AnalyticsContext, maxEvents = 20, maxBytes = 16_000) {
  const events: AnalyticsEvent[] = [];
  for (const event of entries.slice(0, Math.max(0, Math.min(20, Math.floor(maxEvents))))) {
    if (new TextEncoder().encode(JSON.stringify({ context, events: [...events, event] })).byteLength > Math.min(16_000, maxBytes)) break;
    events.push(event);
  }
  return { context, events };
}
export async function flushAnalytics() {
  try { await deliverAnalyticsBatch(); }
  catch { diagnose("delivery"); }
}
async function deliverAnalyticsBatch() {
  if (!allowed() || flushing) return;
  queue = queue.filter((entry) => Date.now() - entry.at <= MAX_AGE);
  const body = makeAnalyticsBatch(queue.map((entry) => entry.event), context, config?.maxEvents, config?.maxBatchBytes);
  if (!body.events.length) return;
  // Without event IDs, an ambiguous delivery must not be retried and counted twice.
  queue.splice(0, body.events.length);
  const epoch = generation;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  requests.add(controller);
  flushing = true;
  try {
    const response = await fetch(`${API_BASE}/api/analytics/events`, {
      method: "POST", credentials: "omit", referrerPolicy: "no-referrer", keepalive: true, signal: controller.signal,
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (epoch !== generation || !allowed()) return;
    if (!response.ok) {
      if ([401, 403, 410].includes(response.status)) {
        reset();
        if (config) {
          config = { ...config, enabled: false };
          updateStatus({ enabled: false });
        }
        diagnose("batch-rejected");
        return;
      } else if (response.status >= 400 && response.status < 500) {
        diagnose("batch-rejected");
        return;
      }
      throw new Error();
    }
    clearDiagnostics("delivery", "batch-rejected");
  } catch {
    if (epoch === generation) diagnose("delivery");
  } finally {
    clearTimeout(timeout);
    requests.delete(controller);
    if (epoch === generation) flushing = false;
  }
}

function visiblePlayingVideo() {
  return [...document.querySelectorAll("video")].some((video) => {
    if (video.paused || video.ended || video.readyState < 2) return false;
    const rect = video.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth;
  });
}
function acquireInterval() {
  if (intervalPending) return;
  if (!navigator.locks) { diagnose("unsupported"); return; }
  intervalPending = true;
  void navigator.locks.request("styl-aggregate-active", { ifAvailable: true }, async (lock) => {
    if (!lock || !current() || document.visibilityState !== "visible") return;
    ownsActiveInterval = true;
    await new Promise<void>((resolve) => { releaseActiveInterval = resolve; });
    ownsActiveInterval = false;
    releaseActiveInterval = undefined;
  }).catch(() => diagnose("unsupported")).finally(() => { intervalPending = false; });
}
function releaseInterval() {
  ownsActiveInterval = false;
  releaseActiveInterval?.();
}
function emitEngagement() {
  if (activeMs > 0) trackAnalytics("engagement", { activeMs: Math.min(15000, Math.round(activeMs)) });
  activeMs = lastTick = 0;
}
function tick() {
  if (!allowed()) {
    if (status.active) { reset(); updateStatus({ excluded: excluded() }); }
    return;
  }
  if (!current()) return;
  const now = Date.now();
  const engaged = document.visibilityState === "visible" && ((document.hasFocus() && now - lastActivity <= 60_000) || visiblePlayingVideo());
  if (!engaged) {
    emitEngagement();
    releaseInterval();
    return;
  }
  acquireInterval();
  if (!ownsActiveInterval) { lastTick = 0; return; }
  if (lastTick && now - lastTick > 2000) emitEngagement();
  if (lastTick) activeMs += Math.min(1000, now - lastTick);
  lastTick = now;
  if (activeMs >= 14_000) emitEngagement();
}

function navigation(event: MouseEvent) {
  if (!current() || !event.isTrusted || (event.type === "auxclick" ? event.button !== 1 : event.button !== 0)) return;
  const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null;
  if (!link || link.hasAttribute("download")) return;
  let url: URL;
  try { url = new URL(link.href, window.location.origin); } catch { return; }
  if (url.origin !== window.location.origin || /^\/(?:admin|privacy)(?:\/|$)/.test(url.pathname)) return;
  const toPath = ["#products", "#about", "#contact", "#gallery"].includes(url.hash) ? url.hash : canonicalAnalyticsPath(url.pathname);
  const action = link.dataset.analyticsAction as AnalyticsProperties["action"] ?? (link.closest("header") ? "header" : "other");
  trackAnalytics("navigation_click", { action, toPath });
  if (toPath === "#contact") {
    const source = link.dataset.analyticsSource as AnalyticsProperties["source"] ?? (link.closest("header") ? "header" : "direct");
    quoteSource = sanitizeAnalyticsProperties("quote_open", { source }).source ?? "unknown";
    trackAnalytics("quote_open", { source, ...elementItem(link) });
    quoteNavigation = url.pathname !== window.location.pathname && !event.metaKey && !event.ctrlKey && !event.shiftKey && event.button === 0 && link.target !== "_blank";
  }
}

export function reportAnalyticsVital(metric: { name: string; value: number; entries?: readonly { startTime: number }[] }) {
  if (!current() || !["LCP", "CLS", "INP"].includes(metric.name)) return;
  if (!metric.entries?.length) return;
  if (route !== documentPath) return;
  analyticsPageEvent("web_vital", { metric: metric.name as "LCP" | "CLS" | "INP", value: metric.value }, `vital:${metric.name}:${metric.value}:${Math.max(...metric.entries.map((entry) => entry.startTime))}`);
  if (document.visibilityState === "hidden") void flushAnalytics();
}

export function initializeAnalytics(): () => void {
  documentPath = window.location.pathname;
  let disposed = false;
  let fetchingConfig = false;
  let configController: AbortController | null = null;
  const loadConfig = async () => {
    if (disposed || fetchingConfig) return;
    fetchingConfig = true;
    configController = new AbortController();
    const timeout = setTimeout(() => configController?.abort(), 10_000);
    try {
      const response = await fetch(`${API_BASE}/api/analytics/config`, { credentials: "omit", referrerPolicy: "no-referrer", cache: "no-store", signal: configController.signal });
      if (!response.ok) throw new Error();
      const value: AnalyticsConfig = await response.json();
      if (disposed) return;
      if (typeof value.enabled !== "boolean" || value.mode !== "aggregate-only" || !Array.isArray(value.allowedCampaigns) || !value.allowedCampaigns.every((entry) => typeof entry === "string") ||
          !Number.isInteger(value.maxEvents) || value.maxEvents < 1 || !Number.isInteger(value.maxBatchBytes) || value.maxBatchBytes < 512) throw new Error();
      config = value;
      context = acquisitionContext();
      clearDiagnostics("config");
      updateStatus({ ready: true, enabled: value.enabled });
      synchronize();
    } catch {
      if (!disposed) { updateStatus({ ready: true }); diagnose("config"); }
    } finally { clearTimeout(timeout); fetchingConfig = false; }
  };
  const synchronize = () => {
    if (!legacyCleared) legacyCleared = clearLegacyIdentifiers();
    const isExcluded = excluded();
    try {
      updateStatus({ optedOut: temporaryOptOut || window.localStorage.getItem(ANALYTICS_KEYS.exclude) !== null, excluded: isExcluded });
    } catch { diagnose("exclusion-check"); return; }
    if (!config) return;
    if (!allowed()) {
      reset();
    } else if (document.visibilityState === "visible") {
      if (!current()) {
        lastActivity = Date.now();
        beginPage();
      }
      updateStatus({ active: true });
    }
  };
  const storage = (event: StorageEvent) => { if (!event.key || event.key === ANALYTICS_KEYS.exclude) synchronize(); };
  const activity = () => { if (allowed()) lastActivity = Date.now(); };
  const hide = () => {
    if (document.visibilityState === "hidden") { emitEngagement(); releaseInterval(); void flushAnalytics(); }
    else { synchronize(); activity(); }
  };
  const pagehide = () => { emitEngagement(); releaseInterval(); void flushAnalytics(); };
  const coarseError = () => { trackAnalytics("site_error", { errorCode: "unknown" }); };
  const online = () => { if (!config || !config.enabled) void loadConfig(); else synchronize(); void flushAnalytics(); };
  const focus = () => { synchronize(); activity(); };
  const pageshow = (event: PageTransitionEvent) => { synchronize(); if (event.persisted && current()) beginPage(); activity(); };
  const blur = () => { emitEngagement(); releaseInterval(); };
  window.addEventListener("storage", storage);
  window.addEventListener(CHANGE, synchronize);
  window.addEventListener("online", online);
  window.addEventListener("focus", focus);
  window.addEventListener("blur", blur);
  window.addEventListener("pagehide", pagehide);
  window.addEventListener("pageshow", pageshow);
  window.addEventListener("error", coarseError);
  window.addEventListener("unhandledrejection", coarseError);
  document.addEventListener("visibilitychange", hide);
  document.addEventListener("click", navigation, true);
  document.addEventListener("auxclick", navigation, true);
  const activityEvents = ["pointerdown", "pointermove", "keydown", "scroll", "touchstart"] as const;
  activityEvents.forEach((name) => document.addEventListener(name, activity, { passive: true }));
  const heartbeat = setInterval(() => { tick(); }, 1000);
  const batches = setInterval(() => { void flushAnalytics(); }, 15_000);
  synchronize();
  void loadConfig();
  return () => {
    disposed = true;
    configController?.abort();
    clearInterval(heartbeat); clearInterval(batches);
    window.removeEventListener("storage", storage);
    window.removeEventListener(CHANGE, synchronize);
    window.removeEventListener("online", online);
    window.removeEventListener("focus", focus);
    window.removeEventListener("blur", blur);
    window.removeEventListener("pagehide", pagehide);
    window.removeEventListener("pageshow", pageshow);
    window.removeEventListener("error", coarseError);
    window.removeEventListener("unhandledrejection", coarseError);
    document.removeEventListener("visibilitychange", hide);
    document.removeEventListener("click", navigation, true);
    document.removeEventListener("auxclick", navigation, true);
    activityEvents.forEach((name) => document.removeEventListener(name, activity));
    releaseInterval();
    reset();
  };
}
