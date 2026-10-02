"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { API_BASE } from "@/lib/api";
import type { AnalyticsBreakdown, AnalyticsDelivery, AnalyticsEmailPreview, AnalyticsReport } from "@/lib/analyticsTypes";
import { AdminNotice, type AdminMessage } from "./AdminFields";
import DailyEmailSettings from "./DailyEmailSettings";

const zone = "America/Los_Angeles";
const number = (value: number | null | undefined) => value == null ? "N/A" : new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const numeric = (value: unknown) => typeof value === "number" && Number.isFinite(value);
const reportTime = (value: string, timezone: string) => new Intl.DateTimeFormat("en-US", { timeZone: timezone, dateStyle: "medium", timeStyle: "medium" }).format(new Date(value));
const text = (value: unknown) => typeof value === "string";
const nullableNumber = (value: unknown) => value === null || numeric(value);
const nullableText = (value: unknown) => value === null || text(value);
function validReportTime(value: unknown, timezone: unknown) {
  if (typeof value !== "string" || typeof timezone !== "string") return false;
  try {
    reportTime(value, timezone);
    return true;
  } catch (error) {
    if (error instanceof RangeError) return false;
    throw error;
  }
}
function rows(value: unknown, fields: Record<string, (field: unknown) => boolean>) {
  return Array.isArray(value) && value.every((row) => record(row) && Object.entries(fields).every(([key, check]) => check(row[key])));
}

function businessDate(offset = 0, timezone = zone) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const part = (type: string) => parts.find((value) => value.type === type)?.value;
  const day = new Date(`${part("year")}-${part("month")}-${part("day")}T12:00:00Z`);
  day.setUTCDate(day.getUTCDate() + offset);
  return day.toISOString().slice(0, 10);
}

function isReport(value: unknown): value is AnalyticsReport {
  if (!record(value) || !record(value.summary) || !record(value.coverage) || !record(value.comparison)) return false;
  const summary = value.summary;
  const coverage = value.coverage;
  const comparison = value.comparison;
  const breakdown = { label: text, pageViews: numeric };
  return ["start", "end", "timezone", "generatedAt", "cutoffAt", "environment"].every((key) => typeof value[key] === "string")
    && validReportTime(value.generatedAt, value.timezone)
    && (coverage.lastEventAt === null || validReportTime(coverage.lastEventAt, value.timezone))
    && typeof value.collectionEnabled === "boolean"
    && ["pageViews", "activeSeconds"].every((key) => numeric(summary[key]))
    && nullableNumber(summary.savedInquiries)
    && coverage.mode === "aggregate-only"
    && nullableText(coverage.trackingSince) && nullableText(coverage.lastEventAt)
    && numeric(coverage.excluded) && numeric(coverage.rejected)
    && Array.isArray(coverage.warnings) && coverage.warnings.every(text)
    && ["days", "pageViewsDailyAverage"].every((key) => numeric(comparison[key]))
    && nullableNumber(comparison.pageViewsChangePercent)
    && ["countries", "sources", "campaigns", "devices", "browsers"].every((key) => rows(value[key], breakdown))
    && rows(value.pages, { path: text, pageViews: numeric, activeSeconds: numeric })
    && rows(value.items, {
      itemType: (item) => item === "product" || item === "accessory", itemId: numeric, name: text, category: text, currency: text,
      impressions: numeric, detailViews: numeric, expansions: numeric, cartAdds: numeric, mediaOpens: numeric, quoteOpens: numeric,
    })
    && rows(value.actions, { name: text, count: numeric })
    && rows(value.errors, { code: text, count: numeric })
    && rows(value.webVitals, { metric: text, count: numeric, average: numeric })
    && rows(value.daily, { date: text, activeSeconds: numeric, pageViews: numeric, inquiries: numeric })
    && rows(value.hourly, { hour: numeric, activeSeconds: numeric, pageViews: numeric })
    && Array.isArray(value.observations) && value.observations.every(text);
}

function isPreview(value: unknown): value is AnalyticsEmailPreview {
  return record(value) && ["reportDate", "timezone", "subject", "text", "html", "nextRunAt"].every((key) => typeof value[key] === "string")
    && typeof value.emailEnabled === "boolean" && typeof value.recipientsConfigured === "boolean";
}

function isDelivery(value: unknown): value is AnalyticsDelivery {
  return record(value) && ["reportDate", "timezone", "recipient", "status", "updatedAt"].every((key) => typeof value[key] === "string")
    && numeric(value.attempts) && (value.error === null || typeof value.error === "string");
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="min-w-0 rounded-2xl border border-[var(--line)] bg-white p-4 sm:p-5">
    <h3 className="text-lg font-semibold">{title}</h3>{children}
  </section>;
}

function Breakdown({ title, rows }: { title: string; rows: AnalyticsBreakdown[] }) {
  const max = Math.max(1, ...rows.map((row) => row.pageViews));
  return <Section title={title}>
    {rows.length ? <ul className="mt-4 space-y-3">{rows.slice(0, 10).map((row) => <li key={row.label} className="min-w-0">
      <div className="flex flex-wrap justify-between gap-2 text-sm"><span className="break-words">{row.label}</span><span>{number(row.pageViews)} views</span></div>
      <div aria-hidden="true" className="mt-1 h-1.5 rounded bg-neutral-100"><div className="h-full rounded bg-[var(--muted)]" style={{ width: `${row.pageViews / max * 100}%` }} /></div>
    </li>)}</ul> : <p className="mt-3 text-sm text-[var(--muted)]">No tracked data for this period.</p>}
  </Section>;
}

export default function AnalyticsManager({ adminToken, active }: { adminToken: string; active: boolean }) {
  const [start, setStart] = useState(() => businessDate());
  const [end, setEnd] = useState(() => businessDate());
  const [range, setRange] = useState(() => ({ start: businessDate(), end: businessDate() }));
  const [refresh, setRefresh] = useState(0);
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [deliveries, setDeliveries] = useState<AnalyticsDelivery[]>([]);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<AdminMessage | null>(null);
  const [previewDate, setPreviewDate] = useState(() => businessDate(-1));
  const [preview, setPreview] = useState<AnalyticsEmailPreview | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [itemType, setItemType] = useState("all");
  const [itemCurrency, setItemCurrency] = useState("all");
  const [itemCategory, setItemCategory] = useState("all");
  const previewController = useRef<AbortController | null>(null);
  const exportController = useRef<AbortController | null>(null);
  const downloadUrls = useRef(new Map<string, number>());

  useEffect(() => {
    const urls = downloadUrls.current;
    return () => {
      for (const [url, timer] of urls) { window.clearTimeout(timer); URL.revokeObjectURL(url); }
      urls.clear();
    };
  }, []);

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setNotice(null);
      try {
        const query = new URLSearchParams(range);
        const responses = await Promise.all([
          fetch(`${API_BASE}/api/admin/analytics/report?${query}`, { headers: { Authorization: `Bearer ${adminToken}` }, cache: "no-store", signal: controller.signal }),
          fetch(`${API_BASE}/api/admin/analytics/deliveries`, { headers: { Authorization: `Bearer ${adminToken}` }, cache: "no-store", signal: controller.signal }),
        ]);
        for (const response of responses) await checkResponse(response);
        const summary: unknown = await responses[0].json();
        const history: unknown = await responses[1].json();
        if (!isReport(summary) || !record(history) || !Array.isArray(history.items) || !history.items.every(isDelivery)) {
          throw new Error("The analytics response is invalid. No report is shown; please retry.");
        }
        if (!controller.signal.aborted) {
          setReport(summary);
          setDeliveries(history.items);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setReport(null);
          setNotice({ type: "error", text: error instanceof Error ? error.message : "Analytics are unavailable. Please retry." });
        }
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => {
      controller.abort();
      previewController.current?.abort();
      exportController.current?.abort();
    };
  }, [active, adminToken, range, refresh]);

  const chooseRange = (days: number, yesterday = false) => {
    const timezone = report?.timezone ?? zone;
    const last = businessDate(yesterday ? -1 : 0, timezone);
    const first = businessDate(yesterday ? -days : -(days - 1), timezone);
    setStart(first); setEnd(last); setRange({ start: first, end: last });
  };

  const showPreview = async () => {
    if (previewBusy) return;
    const controller = new AbortController();
    previewController.current = controller;
    setPreviewBusy(true); setNotice(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/analytics/email-preview?${new URLSearchParams({ date: previewDate })}`, {
        headers: { Authorization: `Bearer ${adminToken}` }, cache: "no-store", signal: controller.signal,
      });
      await checkResponse(response);
      const value: unknown = await response.json();
      if (!isPreview(value)) throw new Error("The email preview is invalid. No email was sent.");
      if (!controller.signal.aborted) setPreview(value);
    } catch (error) {
      if (!controller.signal.aborted) {
        setPreview(null);
        setNotice({ type: "error", text: error instanceof Error ? error.message : "Unable to preview the report. No email was sent." });
      }
    } finally { setPreviewBusy(false); }
  };

  const downloadCsv = async () => {
    if (exportBusy) return;
    const controller = new AbortController();
    exportController.current = controller;
    setExportBusy(true); setNotice(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/analytics/export?${new URLSearchParams(range)}`, {
        headers: { Authorization: `Bearer ${adminToken}` }, cache: "no-store", signal: controller.signal,
      });
      await checkResponse(response);
      const blob = await response.blob();
      if (!response.headers.get("content-type")?.includes("text/csv")) throw new Error("The server did not return an aggregate CSV report.");
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `styl-analytics-${range.start}-${range.end}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      downloadUrls.current.set(url, window.setTimeout(() => {
        URL.revokeObjectURL(url);
        downloadUrls.current.delete(url);
      }, 60_000));
      setNotice({ type: "success", text: "Aggregate CSV download started. It does not contain raw visitor identifiers or inquiry text." });
    } catch (error) {
      if (!controller.signal.aborted) setNotice({ type: "error", text: error instanceof Error ? error.message : "Unable to export analytics. Please retry." });
    } finally { setExportBusy(false); }
  };

  return <section className="min-w-0 space-y-5" aria-labelledby="analytics-title" aria-busy={loading}>
    <div>
      <h2 id="analytics-title" className="text-2xl font-semibold">Usage overview</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">Aggregate-only usage counts, without analytics browser/session identifiers or individual journeys. No raw IP addresses or form contents are stored in analytics. Admin browsing, privacy signals and opted-out browsers are excluded.</p>
    </div>
    <form onSubmit={(event) => {
      event.preventDefault();
      if (!start || !end || start > end) { setNotice({ type: "error", text: "Choose a valid start and end date." }); return; }
      setRange({ start, end });
    }} className="flex min-w-0 flex-wrap items-end gap-3 rounded-2xl border border-[var(--line)] bg-white p-4">
      <label className="min-w-0 text-sm">Start date<input aria-label="Analytics start date" type="date" required value={start} onChange={(event) => setStart(event.target.value)} className="mt-1 block min-h-11 max-w-full rounded-lg border border-[var(--line)] px-3" /></label>
      <label className="min-w-0 text-sm">End date<input aria-label="Analytics end date" type="date" required value={end} onChange={(event) => setEnd(event.target.value)} className="mt-1 block min-h-11 max-w-full rounded-lg border border-[var(--line)] px-3" /></label>
      <button type="submit" disabled={loading} className="min-h-11 rounded-full bg-[var(--ink)] px-5 text-sm text-white disabled:opacity-50">Apply dates</button>
      <button type="button" onClick={() => setRefresh((value) => value + 1)} disabled={loading} className="min-h-11 rounded-full border border-[var(--line)] px-4 text-sm disabled:opacity-50">Refresh analytics</button>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => chooseRange(1)} className="min-h-11 px-2 text-sm underline">Today</button>
        <button type="button" onClick={() => chooseRange(1, true)} className="min-h-11 px-2 text-sm underline">Yesterday</button>
        <button type="button" onClick={() => chooseRange(7)} className="min-h-11 px-2 text-sm underline">Last 7 days</button>
        <button type="button" onClick={() => chooseRange(30)} className="min-h-11 px-2 text-sm underline">Last 30 days</button>
      </div>
    </form>
    <AdminNotice message={notice} />
    {loading ? <p role="status">Loading analytics...</p> : null}
    {report ? <>
      {report.summary.pageViews === 0 ? <section data-testid="analytics-empty-guidance" aria-labelledby="analytics-empty-title" className="rounded-2xl border border-[var(--line)] bg-neutral-50 p-4 text-sm leading-6 sm:p-5">
        <h3 id="analytics-empty-title" className="text-lg font-semibold">No measured page views in this date range</h3>
        <p className="mt-2">This does not mean nobody visited. Privacy signals, opt-outs, admin exclusions and unavailable scripts can reduce coverage. There is no customer consent panel to dismiss.</p>
        {!report.collectionEnabled
          ? <p className="mt-2 font-medium">Server collection is disabled. Check this environment&apos;s configuration before testing; refreshing pages will not create analytics.</p>
          : <>
            <ol className="mt-3 list-decimal space-y-2 pl-5">
              <li>Open the storefront in a separate <strong>InPrivate / Incognito</strong> window. Type its address directly; do not duplicate an admin tab or sign in to admin in that customer window.</li>
              <li>Browse the storefront normally; measurement starts automatically when enabled. Prior opt-outs and browser privacy signals are still respected. The <strong>Privacy</strong> page contains the browser&apos;s measurement preference.</li>
              <li>The initial page count is sent promptly. For item/actions data, keep the customer window open for at least <strong>15 seconds</strong> so its automatic batch can be sent.</li>
              <li>Return here, choose <strong>Today</strong> in {report.timezone}, and click <strong>Refresh analytics</strong>. This dashboard is a snapshot, not a live counter.</li>
            </ol>
            {report.environment === "local" || report.environment === "test" ? <p className="mt-3">Local data is separate from production. <code>localhost</code> and <code>127.0.0.1</code> have separate browser privacy preferences.</p> : null}
          </>}
        <p className="mt-3 text-[var(--muted)]">Aggregate-only data begins with this collection mode. Earlier individual-session history is not included, and missed events cannot be reconstructed.</p>
      </section> : null}
      <div className="rounded-2xl border border-[var(--line)] bg-white p-4 text-sm leading-6">
        <p><strong>{report.environment}</strong> · {report.start} to {report.end} · {report.timezone}</p>
        <p>Collection: {report.collectionEnabled ? "enabled automatically; privacy exclusions apply" : "disabled"} · Data mode: aggregate-only hourly buckets</p>
        <p>Report generated: {reportTime(report.generatedAt, report.timezone)} ({report.timezone}). Use Refresh analytics to load newer activity; collection batches normally arrive within 15 seconds.</p>
        <p>Last activity hour (start): {report.coverage.lastEventAt ? reportTime(report.coverage.lastEventAt, report.timezone) : "None"} · Server-observed excluded requests: {number(report.coverage.excluded)} · Rejected events/requests: {number(report.coverage.rejected)}</p>
        <p className="text-xs text-[var(--muted)]">Visits blocked before a request is sent, including opt-outs or client-side admin exclusion, do not appear in the excluded-request count. Activity times are hourly buckets, not exact visitor timestamps.</p>
        {report.coverage.warnings.length ? <ul className="mt-2 list-disc pl-5">{report.coverage.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul> : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Page views", number(report.summary.pageViews)],
          ["Saved inquiries", number(report.summary.savedInquiries)],
          ["Total active time", `${number(report.summary.activeSeconds / 60)} minutes`],
        ].map(([label, value]) => <div key={label} className="min-w-0 rounded-2xl border border-[var(--line)] bg-white p-4"><p className="text-sm text-[var(--muted)]">{label}</p><p data-testid={label === "Page views" ? "analytics-page-view-count" : undefined} className="mt-2 break-words text-2xl font-semibold">{value}</p></div>)}
      </div>
      <p className="text-sm text-[var(--muted)]">Prior seven completed days: {number(report.comparison.pageViewsDailyAverage)} page views/day. Change: {report.comparison.pageViewsChangePercent === null ? "new / no comparable baseline" : `${number(report.comparison.pageViewsChangePercent)}%`}. Inquiries are not sales; active time is an estimate.</p>
      <p data-testid="analytics-unavailable-metrics" className="rounded-xl bg-neutral-50 p-4 text-sm leading-6">Not measured: unique or returning visitors, sessions, individual journeys, per-session funnels, conversion rates and per-visitor active-time medians. These require identifiers that aggregate-only measurement does not use. Saved inquiries are independent business totals, not attributed to browsing activity.</p>
      <div className="grid gap-4 lg:grid-cols-2">
        <Breakdown title="Countries" rows={report.countries} />
        <Breakdown title="Acquisition sources" rows={report.sources} />
        <Breakdown title="Campaigns" rows={report.campaigns} />
        <Breakdown title="Devices" rows={report.devices} />
        <Breakdown title="Browsers" rows={report.browsers} />
        <Section title="Action totals">
          <p className="mt-2 text-xs text-[var(--muted)]">Independent action occurrences, not unique customers or a linked conversion funnel.</p>
          <ul className="mt-3 space-y-2">{report.actions.map((row) => <li key={row.name} className="flex justify-between gap-3 text-sm"><span>{row.name}</span><span>{number(row.count)}</span></li>)}</ul>
        </Section>
      </div>
      <Section title="Equipment and accessory interest">
        <p className="mt-2 text-xs text-[var(--muted)]">Currencies stay separate. Counts are action occurrences, not distinct viewers. No view-to-cart or quote conversion rate is inferred from unlinked events.</p>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          <label className="min-w-0">Item type<select aria-label="Analytics item type" value={itemType} onChange={(event) => setItemType(event.target.value)} className="ml-2 min-h-11 max-w-full rounded-lg border px-2"><option value="all">All</option><option value="product">Equipment</option><option value="accessory">Accessories</option></select></label>
          <label className="min-w-0">Currency<select aria-label="Analytics currency" value={itemCurrency} onChange={(event) => setItemCurrency(event.target.value)} className="ml-2 min-h-11 max-w-full rounded-lg border px-2"><option value="all">All</option><option value="CAD">CAD</option><option value="USD">USD</option></select></label>
          <label className="min-w-0">Category<select aria-label="Analytics category" value={itemCategory} onChange={(event) => setItemCategory(event.target.value)} className="ml-2 min-h-11 max-w-full rounded-lg border px-2"><option value="all">All</option>{[...new Set(report.items.map((item) => item.category))].map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
        </div>
        <p className="mt-1 text-xs text-[var(--muted)]">These filters affect the item table only; overview and CSV include the full date range.</p>
        <div className="mt-3 max-w-full overflow-x-auto">
          <table className="w-full text-left text-sm"><thead><tr>{["Item", "Market", "Impressions", "Detail views", "Expansions", "Media opens", "Cart adds", "Quote opens"].map((label) => <th key={label} className="whitespace-nowrap border-b px-3 py-2">{label}</th>)}</tr></thead>
            <tbody>{report.items.filter((item) => (itemType === "all" || item.itemType === itemType) && (itemCurrency === "all" || item.currency === itemCurrency) && (itemCategory === "all" || item.category === itemCategory)).map((item) => <tr key={`${item.itemType}-${item.itemId}-${item.currency}`}>
              <td className="min-w-44 border-b px-3 py-3">{item.name}<span className="block text-xs text-[var(--muted)]">{item.itemType === "product" ? "equipment" : "accessory"} #{item.itemId} · {item.category}</span></td>
              {[item.currency, number(item.impressions), number(item.detailViews), number(item.expansions), number(item.mediaOpens), number(item.cartAdds), number(item.quoteOpens)].map((value, index) => <td key={index} className="border-b px-3 py-3">{value}</td>)}
            </tr>)}</tbody>
          </table>
        </div>
        {!report.items.length ? <p className="mt-3 text-sm">No tracked item activity in this period.</p> : null}
      </Section>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Page totals"><ul className="mt-3 space-y-2 text-sm">{report.pages.map((row) => <li key={row.path} className="break-words">{row.path}: {number(row.pageViews)} views · {number(row.activeSeconds)} estimated active seconds</li>)}</ul></Section>
        <Section title="Daily traffic"><ul className="mt-3 space-y-2 text-sm">{report.daily.map((row) => <li key={row.date}>{row.date}: {number(row.pageViews)} views · {number(report.summary.savedInquiries === null ? null : row.inquiries)} inquiries</li>)}</ul></Section>
        <Section title="Hourly visits"><ul className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">{report.hourly.map((row) => <li key={row.hour}>{String(row.hour).padStart(2, "0")}:00 — {number(row.pageViews)} views</li>)}</ul></Section>
        <Section title="Errors and performance">
          {report.errors.length ? <ul className="mt-3 space-y-2 text-sm">{report.errors.map((row) => <li key={row.code}>{row.code}: {number(row.count)}</li>)}</ul> : <p className="mt-3 text-sm">No recorded errors; coverage may be incomplete.</p>}
          <ul className="mt-3 space-y-2 text-sm">{report.webVitals.map((row) => <li key={row.metric}>{row.metric}: average {number(row.average)}{row.metric === "CLS" ? "" : " ms"} ({row.count} samples)</li>)}</ul>
        </Section>
        <Section title="Observations"><ul className="mt-3 list-disc space-y-2 pl-5 text-sm">{report.observations.map((observation, index) => <li key={index}>{observation}</li>)}</ul></Section>
      </div>
      <button type="button" disabled={exportBusy || loading} onClick={downloadCsv} className="min-h-12 rounded-full border border-[var(--ink)] px-5 text-sm disabled:opacity-50">{exportBusy ? "Preparing CSV..." : "Download aggregate CSV"}</button>
    </> : !loading ? <p className="text-sm">Analytics data is unavailable. Refresh after resolving the reported problem.</p> : null}
    <DailyEmailSettings adminToken={adminToken} active={active} onSaved={() => {
      previewController.current?.abort();
      setPreview(null);
    }} />
    <Section title="Daily usage email preview">
      <p className="mt-2 text-sm leading-6">A short daily business summary, scheduled for 12:15 AM Pacific (00:15 America/Los_Angeles) early the next day, covering the previous completed calendar day. Previewing does not send email.</p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="min-w-0 text-sm">Report date<input aria-label="Email report date" type="date" required value={previewDate} onChange={(event) => setPreviewDate(event.target.value)} className="mt-1 block min-h-11 max-w-full rounded-lg border border-[var(--line)] px-3" /></label>
        <button type="button" onClick={showPreview} disabled={previewBusy || !previewDate} className="min-h-11 rounded-full border border-[var(--ink)] px-4 text-sm disabled:opacity-50">{previewBusy ? "Generating preview..." : "Preview daily email"}</button>
      </div>
      {preview ? <div className="mt-4 min-w-0">
        <p className="text-sm">Real email: {preview.emailEnabled ? "enabled by production configuration" : "disabled"} · Recipients: {preview.recipientsConfigured ? "configured" : "not configured"}.</p>
        <p className="mt-1 text-xs text-[var(--muted)]">Next scheduled time: {new Date(preview.nextRunAt).toLocaleString("en-US", { timeZone: preview.timezone })} ({preview.timezone}).</p>
        <pre aria-label="Daily email preview" className="mt-3 max-h-[36rem] overflow-auto whitespace-pre-wrap break-words rounded-xl bg-neutral-50 p-4 font-sans text-sm leading-6">{preview.text}</pre>
      </div> : null}
    </Section>
    <Section title="Report delivery history">
      <p className="mt-2 text-xs text-[var(--muted)]">Accepted means SMTP accepted the email, not confirmed inbox delivery. Ambiguous or interrupted sends require an operator review; they are not automatically resent.</p>
      {deliveries.length ? <ul className="mt-3 space-y-3 text-sm">{deliveries.map((delivery) => <li key={`${delivery.reportDate}-${delivery.recipient}-${delivery.timezone}`} className="break-words">{delivery.reportDate} · {delivery.recipient} · {delivery.status} · {delivery.attempts} attempts{delivery.error ? ` · ${delivery.error}` : ""}</li>)}</ul> : <p className="mt-3 text-sm">No email delivery attempts recorded.</p>}
    </Section>
  </section>;
}

async function checkResponse(response: Response) {
  if (response.ok) return;
  if (response.status === 404) throw new Error("The analytics backend is not available in this API build yet. No analytics report can be shown.");
  let detail = `Analytics request failed (HTTP ${response.status}). Please retry.`;
  try {
    const value: unknown = await response.json();
    if (record(value) && typeof value.detail === "string") detail = value.detail;
  } catch {
    // Keep the explicit HTTP failure when the proxy returned a non-JSON response.
  }
  throw new Error(detail);
}
