"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { AdminNotice, type AdminMessage } from "./AdminFields";

type Fact = { text: string; topic: "products" | "compatibility" | "customer_service"; location: string };
type Scope = "products" | "general";
type SourceState = "pending" | "queued" | "processing" | "review" | "approved" | "rejected" | "failed" | "stale" | "paused";
type Source = {
  id: string; name: string; kind: "image" | "video" | "pdf" | "docx" | "text"; origin: "catalog" | "document";
  scope?: Scope; format?: string; bytes?: number; approvedCurrent?: boolean;
  itemRefs: string[]; state: SourceState; revision: number; facts: Fact[];
  error: string | null; retryAt: string | null; updatedAt: string; createdAt: string;
};
type Item = { ref: string; name: string; type: string; id: number };
type AIRoute = { provider: string; model: string };
type AssistantScope = { enabled: boolean; allowedTopics: string[] };
type KnowledgeIndex = {
  sources: Source[]; items: Item[]; warnings: string[];
  limits: { documentBytes: number; imageBytes: number; videoBytes: number }; provider: string;
  routes?: Record<"image" | "pdf" | "video", AIRoute> & Partial<Record<"docx" | "text", AIRoute>>;
  routeFingerprint?: string;
};
type AssignmentDraft = { revision: number; refs: string[]; scope: Scope };
type ReviewDraft = { revision: number; facts: Fact[] };
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string";
const integer = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const date = (value: unknown): value is string => text(value) && Number.isFinite(Date.parse(value));
const refs = (value: unknown): value is string[] => Array.isArray(value) && value.every((ref) => text(ref) && /^(?:product|accessory):[1-9]\d*$/.test(ref));
const states: SourceState[] = ["pending", "queued", "processing", "review", "approved", "rejected", "failed", "stale", "paused"];
const stateLabel: Record<SourceState, string> = {
  pending: "Pending extraction", queued: "Queued", processing: "Processing", review: "Draft · needs review",
  approved: "Approved", rejected: "Rejected", failed: "Failed", stale: "Stale · not in use", paused: "Paused",
};
const attention = (source: Source) => ["failed", "paused", "stale", "rejected"].includes(source.state);
const working = (source: Source) => source.state === "queued" || source.state === "processing";
const extractable = (source: Source) => ["pending", "failed", "paused", "stale", "rejected"].includes(source.state);
const button = "min-h-12 rounded-full border border-[var(--line)] bg-white px-4 py-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50";
const field = "mt-2 min-h-12 w-full min-w-0 rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm aria-[invalid=true]:border-red-600";
const when = (value: string) => new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
const size = (bytes: number) => bytes < 1024 ? `${bytes} bytes` : bytes < 1024 ** 2 ? `${(bytes / 1024).toFixed(1)} KiB` : `${(bytes / 1024 ** 2).toFixed(1)} MiB`;
const format = (source: Source) => (source.format || source.kind).toUpperCase();
const sourceScope = (source: Source): Scope => source.scope ?? "products";
const included = (source: Source, items: Item[], settings: AssistantScope | null) => Boolean(settings?.enabled)
  && source.state === "approved" && source.approvedCurrent !== false && source.facts.some((fact) => settings?.allowedTopics.includes(fact.topic)) && source.bytes !== 0
  && (sourceScope(source) === "general" || source.itemRefs.some((ref) => items.some((item) => item.ref === ref)));
const assignmentLabel = (source: Source, items: Item[]) => sourceScope(source) === "general" ? "General customer-service Q&A · no product assignment"
  : source.itemRefs.map((ref) => items.find((item) => item.ref === ref)?.name ?? `${ref} (unavailable)`).join(", ") || "No assigned products";
const validRoute = (value: unknown): value is AIRoute => object(value) && text(value.provider) && Boolean(value.provider.trim()) && text(value.model) && Boolean(value.model.trim());
const validAssistantScope = (value: unknown): value is AssistantScope => object(value) && typeof value.enabled === "boolean"
  && Array.isArray(value.allowedTopics) && value.allowedTopics.every((topic) => text(topic) && ["products", "pricing", "compatibility", "customer_service"].includes(topic));
const validFingerprint = (value: unknown): value is string => text(value) && /^[a-f0-9]{64}$/.test(value);
const routeLabel = (route: AIRoute) => route.provider === "openai" && route.model === "gpt-6-luna" ? "GPT-6 Luna"
  : route.provider === "gemini" && route.model === "gemini-3.8-flash" ? "Gemini 3.8 Flash" : route.model;

function validSource(value: unknown): value is Source {
  return object(value) && text(value.id) && /^[a-zA-Z0-9_-]{1,128}$/.test(value.id)
    && text(value.name) && ["image", "video", "pdf", "docx", "text"].includes(String(value.kind))
    && (value.scope === undefined || value.scope === "products" || value.scope === "general")
    && (value.format === undefined || text(value.format) && Boolean(value.format.trim()))
    && (value.bytes === undefined || integer(value.bytes))
    && (value.approvedCurrent === undefined || typeof value.approvedCurrent === "boolean")
    && ["catalog", "document"].includes(String(value.origin)) && refs(value.itemRefs)
    && states.includes(value.state as SourceState) && integer(value.revision)
    && Array.isArray(value.facts) && value.facts.every((fact) => object(fact) && text(fact.text) && text(fact.location)
      && ["products", "compatibility", "customer_service"].includes(String(fact.topic)))
    && (value.error === null || text(value.error)) && (value.retryAt === null || date(value.retryAt))
    && date(value.updatedAt) && date(value.createdAt);
}
function validIndex(value: unknown): value is KnowledgeIndex {
  return object(value) && Array.isArray(value.sources) && value.sources.every(validSource)
    && new Set(value.sources.map((source) => source.id)).size === value.sources.length
    && Array.isArray(value.items) && value.items.every((item) => object(item) && refs([item.ref])
      && text(item.name) && ["product", "accessory"].includes(String(item.type)) && integer(item.id) && item.ref === `${item.type}:${item.id}`)
    && Array.isArray(value.warnings) && value.warnings.every(text) && text(value.provider)
    && (value.routes === undefined || object(value.routes) && ["image", "pdf", "video"].every((kind) => validRoute((value.routes as Record<string, unknown>)[kind])))
    && (value.routes === undefined || ["docx", "text"].every((kind) => (value.routes as Record<string, unknown>)[kind] === undefined || validRoute((value.routes as Record<string, unknown>)[kind])))
    && (value.routeFingerprint === undefined || validFingerprint(value.routeFingerprint))
    && object(value.limits) && ["documentBytes", "imageBytes", "videoBytes"].every((key) => integer(value.limits && (value.limits as Record<string, unknown>)[key]));
}

function RoutingPanel({ index, chatRoute }: { index: KnowledgeIndex; chatRoute: AIRoute | null }) {
  const routes = index.routes;
  const documentsShared = routes?.docx && routes.text && [routes.docx, routes.text].every((route) => route.provider === routes.pdf.provider && route.model === routes.pdf.model);
  const documentLabel = documentsShared ? "Documents (PDF / DOCX / TXT / MD)" : "PDFs";
  const mediaShared = routes && routes.image.provider === routes.pdf.provider && routes.image.model === routes.pdf.model;
  const shared = mediaShared && chatRoute && chatRoute.provider === routes.image.provider && chatRoute.model === routes.image.model;
  const rows: { label: string; route: AIRoute }[] = routes ? [
    ...(shared ? [{ label: documentsShared ? "Chat / images / documents" : "Chat / images / PDFs", route: routes.image }]
      : [
        ...(chatRoute ? [{ label: "Chat", route: chatRoute }] : []),
        ...(mediaShared ? [{ label: documentsShared ? "Images / documents" : "Images / PDFs", route: routes.image }]
          : [{ label: "Images", route: routes.image }, { label: documentLabel, route: routes.pdf }]),
      ]),
    ...(!documentsShared && routes.docx ? [{ label: "DOCX", route: routes.docx }] : []),
    ...(!documentsShared && routes.text ? [{ label: "TXT / MD", route: routes.text }] : []),
    { label: "Videos", route: routes.video },
  ] : chatRoute ? [{ label: "Chat", route: chatRoute }] : [];
  return <section aria-label="AI routing" className="min-w-0 text-sm">
    <h3 className="font-semibold">AI routing</h3>
    {rows.length ? <dl className="mt-2 space-y-3">
      {rows.map(({ label, route }) => <div key={label} role="group" aria-label={label} className="min-w-0 break-words">
        <dt className="inline">{label}: </dt><dd className="inline"><strong>{routeLabel(route)}</strong>
          <span className="mt-1 block text-[var(--muted)]">Provider: {route.provider} · Model: {route.model}</span>
        </dd>
      </div>)}
    </dl> : null}
    {!routes ? <p className="mt-2 break-words">Legacy extraction provider: <strong>{index.provider || "Not reported"}</strong>. Per-kind provider/model details are unavailable; refresh after the server is updated.</p> : null}
    {!chatRoute ? <p className="mt-2 text-[var(--muted)]">Chat routing is unavailable. Refresh or check Conversations for the configured chat provider/model.</p> : null}
    <p className="mt-3 text-[var(--muted)]">Server-configured routes; no API keys are shown or entered here.</p>
  </section>;
}

function ItemChoices({ items, selected, onChange, label, disabled, error, id }: {
  items: Item[]; selected: string[]; onChange: (refs: string[]) => void; label: string; disabled: boolean; error?: string; id?: string;
}) {
  return <fieldset id={id} tabIndex={-1} aria-invalid={Boolean(error)} aria-describedby={error && id ? `${id}-error` : undefined} disabled={disabled} className="mt-4 min-w-0">
    <legend className="text-sm font-medium">{label}</legend>
    <div className="mt-2 flex flex-wrap gap-2">
      <button type="button" disabled={disabled || !items.length} onClick={() => onChange(items.map((item) => item.ref))} className={`${button} max-w-full`}>Select all currently published items</button>
      <button type="button" disabled={disabled || !selected.length} onClick={() => onChange([])} className={button}>Clear selection</button>
    </div>
    <p className="mt-2 text-sm text-[var(--muted)]">{selected.length} selected. Future published items are not selected automatically.</p>
    {error ? <p id={id ? `${id}-error` : undefined} className="mt-2 text-sm text-red-800">{error}</p> : null}
    <div className="mt-2 max-h-52 space-y-1 overflow-y-auto rounded-xl border border-[var(--line)] p-2">
      {items.length ? items.map((item) => <label key={item.ref} className="flex min-h-12 items-center gap-3 px-2 py-2 text-sm">
        <input type="checkbox" checked={selected.includes(item.ref)} onChange={(event) => onChange(event.target.checked ? [...selected, item.ref] : selected.filter((ref) => ref !== item.ref))} className="h-5 w-5 shrink-0" />
        <span className="min-w-0 break-words">{item.name} <span className="text-[var(--muted)]">({item.type} #{item.id})</span></span>
      </label>) : <p className="p-2 text-sm">No published catalog items. Publish an item before assigning knowledge.</p>}
      {selected.filter((ref) => !items.some((item) => item.ref === ref)).map((ref) => <label key={ref} className="flex min-h-12 items-center gap-3 px-2 py-2 text-sm">
        <input type="checkbox" checked onChange={() => onChange(selected.filter((value) => value !== ref))} className="h-5 w-5 shrink-0" />
        <span className="break-words">{ref} — no longer published</span>
      </label>)}
    </div>
  </fieldset>;
}

function ScopeChoices({ value, onChange, disabled, name }: { value: Scope; onChange: (scope: Scope) => void; disabled: boolean; name: string }) {
  return <fieldset disabled={disabled} className="mt-4 min-w-0">
    <legend className="text-sm font-medium">{name === "upload-scope" ? "Document scope" : "Source scope"}</legend>
    {([["products", "Product documents"], ["general", "General customer-service Q&A"]] as const).map(([scope, label]) => <label key={scope} className="flex min-h-12 items-center gap-3 text-sm">
      <input type="radio" name={name} checked={value === scope} onChange={() => onChange(scope)} className="h-5 w-5 shrink-0" />
      <span>{label}</span>
    </label>)}
  </fieldset>;
}

export default function KnowledgeManager({ adminToken, active, onBusyChange, onDirtyChange }: {
  adminToken: string; active: boolean; onBusyChange: (busy: boolean) => void; onDirtyChange: (dirty: boolean) => void;
}) {
  const [index, setIndex] = useState<KnowledgeIndex | null>(null);
  const [chatRoute, setChatRoute] = useState<AIRoute | null>(null);
  const [assistantScope, setAssistantScope] = useState<AssistantScope | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "review" | "approved" | "attention">("all");
  const [assignments, setAssignments] = useState<Record<string, AssignmentDraft>>({});
  const [reviews, setReviews] = useState<Record<string, ReviewDraft>>({});
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadScope, setUploadScope] = useState<Scope>("products");
  const [uploadRefs, setUploadRefs] = useState<string[]>([]);
  const [uploadErrors, setUploadErrors] = useState<{ title?: string; file?: string; refs?: string }>({});
  const [assignmentErrors, setAssignmentErrors] = useState<Record<string, string>>({});
  const [consent, setConsent] = useState<{ fingerprint: string | null; refreshRequired: boolean; reconfirm: boolean }>({
    fingerprint: null, refreshRequired: false, reconfirm: false,
  });
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(false);
  const [accessError, setAccessError] = useState(false);
  const [readError, setReadError] = useState("");
  const [notice, setNotice] = useState<AdminMessage | null>(null);
  const [conflicts, setConflicts] = useState<string[]>([]);
  const operation = useRef<AbortController | null>(null);
  const read = useRef<AbortController | null>(null);
  const hasWork = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const chooseFile = useRef<HTMLButtonElement>(null);
  const titleInput = useRef<HTMLInputElement>(null);
  const noticeFocusTarget = useRef<HTMLElement | null>(null);
  const library = useRef<HTMLElement>(null);
  const sourceReview = useRef<HTMLElement>(null);
  const urls = useRef(new Map<string, number>());
  const selected = index?.sources.find((source) => source.id === selectedId);
  const assignment = selected ? assignments[selected.id] : undefined;
  const review = selected ? reviews[selected.id] : undefined;
  const dirty = Boolean(file || title || uploadRefs.length || uploadScope !== "products" || Object.keys(assignments).length || Object.keys(reviews).length);
  const disabled = Boolean(busy) || loading || accessError;
  const canAcknowledge = Boolean(index?.routes && validFingerprint(index.routeFingerprint)) && !consent.refreshRequired;
  const acknowledged = canAcknowledge && consent.fingerprint !== null && consent.fingerprint === index?.routeFingerprint;
  const staleDraft = Boolean(selected && (assignment && assignment.revision !== selected.revision || review && review.revision !== selected.revision));
  const conflict = Boolean(selected && (conflicts.includes(selected.id) || staleDraft));
  const redact = useCallback((value: string) => adminToken ? value.replaceAll(adminToken, "[redacted]") : value, [adminToken]);

  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    const downloads = urls.current;
    return () => {
      operation.current?.abort(); read.current?.abort();
      for (const [url, timer] of downloads) { window.clearTimeout(timer); URL.revokeObjectURL(url); }
      downloads.clear(); onBusyChange(false); onDirtyChange(false);
    };
  }, [onBusyChange, onDirtyChange]);

  const request = useCallback(async (suffix: string, signal: AbortSignal, options: RequestInit = {}) => {
    const response = await fetch(`${API_BASE}/api/admin/support/knowledge${suffix}`, {
      ...options, headers: { ...options.headers, Authorization: `Bearer ${adminToken}` },
      cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal,
    });
    if (!response.ok) {
      let detail = `Knowledge request failed (HTTP ${response.status}). Inputs are preserved.`;
      try { const value: unknown = await response.json(); if (object(value) && text(value.detail)) detail = value.detail; } catch { /* Keep the HTTP fallback. */ }
      if (response.status === 401) { setAccessError(true); detail = "Admin access was rejected. Private knowledge is hidden; sign in again or refresh after restoring access. Drafts remain in this tab."; }
      if (response.status === 409) {
        if (suffix === "/extract-pending" || /^\/sources\/[^/]+\/extract$/.test(suffix)) {
          setConsent({ fingerprint: null, refreshRequired: true, reconfirm: true });
          detail += " Extraction settings or source changed (409). Refresh knowledge, review the current routes, then confirm external processing again. Your drafts are preserved; nothing is automatically resubmitted.";
        } else {
          const id = suffix.match(/^\/sources\/([^/]+)/)?.[1];
          if (id) setConflicts((current) => [...new Set([...current, id])]);
          detail += " Source changed (409). Refresh knowledge to compare with the latest revision. Your draft is preserved; nothing is automatically resubmitted.";
        }
      }
      throw new Error(redact(detail));
    }
    return response;
  }, [adminToken, redact]);
  const receiveIndex = useCallback((value: unknown) => {
    if (!validIndex(value)) {
      setConsent({ fingerprint: null, refreshRequired: true, reconfirm: true });
      throw new Error("Knowledge response is invalid. Existing sources may be stale; refresh to retry.");
    }
    hasWork.current = value.sources.some(working);
    setConsent((current) => ({
      fingerprint: value.routes && current.fingerprint === value.routeFingerprint ? current.fingerprint : null,
      refreshRequired: false,
      reconfirm: current.reconfirm || Boolean(current.fingerprint && (!value.routes || current.fingerprint !== value.routeFingerprint)),
    }));
    setIndex(value);
  }, []);
  const receiveSource = (value: unknown, expectedId?: string) => {
    if (!validSource(value) || expectedId && value.id !== expectedId) throw new Error("Unable to confirm the knowledge change. Inputs are preserved; refresh before retrying.");
    if (working(value)) hasWork.current = true;
    setIndex((current) => current ? { ...current, sources: [value, ...current.sources.filter((source) => source.id !== value.id)] } : current);
    return value;
  };
  const refreshIndex = useCallback(async (signal: AbortSignal) => {
    const [value, configuration]: [unknown, unknown] = await Promise.all([
      request("", signal).then((response) => response.json()),
      fetch(`${API_BASE}/api/admin/support/config`, {
        headers: { Authorization: `Bearer ${adminToken}` },
        cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal,
      }).then((response) => response.ok ? response.json() : null)
        .catch(() => null),
    ]);
    if (signal.aborted) return;
    receiveIndex(value);
    setChatRoute(validRoute(configuration) ? { provider: configuration.provider, model: configuration.model } : null);
    setAssistantScope(validAssistantScope(configuration) ? { enabled: configuration.enabled, allowedTopics: configuration.allowedTopics } : null);
    setReadError(""); setAccessError(false);
  }, [adminToken, request, receiveIndex]);

  useEffect(() => {
    if (!active) return;
    let stopped = false;
    let timer: number | undefined;
    let first = true;
    const poll = async () => {
      if (stopped || read.current) return;
      if (!operation.current && document.visibilityState === "visible" && (first || hasWork.current)) {
        const controller = new AbortController();
        read.current = controller;
        setLoading(first);
        try { await refreshIndex(controller.signal); first = false; }
        catch (error) {
          if (!controller.signal.aborted) { setReadError(redact(error instanceof Error ? error.message : "Unable to read knowledge. Refresh to retry.")); first = false; }
        } finally { if (read.current === controller) read.current = null; if (!stopped) setLoading(false); }
      }
      if (!stopped) timer = window.setTimeout(poll, 2000);
    };
    const visibility = () => { if (document.visibilityState === "visible") { first = true; window.clearTimeout(timer); void poll(); } };
    void poll();
    document.addEventListener("visibilitychange", visibility);
    return () => { stopped = true; window.clearTimeout(timer); read.current?.abort(); read.current = null; document.removeEventListener("visibilitychange", visibility); };
  }, [active, refreshIndex, redact]);

  const perform = async (label: string, action: (signal: AbortSignal) => Promise<void>) => {
    noticeFocusTarget.current = null;
    if (operation.current) return;
    const controller = new AbortController();
    operation.current = controller; read.current?.abort(); read.current = null;
    setLoading(false); setBusy(label); onBusyChange(true); setNotice(null);
    try { await action(controller.signal); }
    catch (error) { if (!controller.signal.aborted) setNotice({ type: "error", text: redact(error instanceof Error ? error.message : "Knowledge request failed. Inputs are preserved.") }); }
    finally { if (!controller.signal.aborted) { operation.current = null; setBusy(""); onBusyChange(false); } }
  };
  const json = (method: string, data: unknown): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  const refresh = () => void perform("Refreshing knowledge…", refreshIndex);
  const sync = () => void perform("Syncing catalog media…", async (signal) => {
    receiveIndex(await (await request("/catalog-sync", signal, json("POST", {}))).json());
    setNotice({ type: "success", text: "Catalog media synced without reuploading. Changed sources are stale and not used until extracted and approved again." });
  });
  const upload = () => {
    if (!index || disabled) return;
    const errors: typeof uploadErrors = {};
    if (!title.trim() || title.trim().length > 200) errors.title = "Enter a document title (1–200 characters).";
    if (!file) errors.file = "Choose a PDF, DOCX, TXT or MD file.";
    else if (!/\.(pdf|docx|txt|md)$/i.test(file.name) || !file.size || file.size > index.limits.documentBytes) {
      errors.file = `Choose a nonempty PDF, DOCX, TXT or MD file no larger than ${size(index.limits.documentBytes)}. Your selection is preserved.`;
    }
    if (uploadScope === "products" && !uploadRefs.length) errors.refs = "Select at least one published item, or choose General customer-service Q&A.";
    setUploadErrors(errors);
    if (Object.keys(errors).length) {
      noticeFocusTarget.current = errors.title ? titleInput.current
        : errors.file ? chooseFile.current : document.getElementById("upload-assignments");
      setNotice({ type: "error", text: "Document not uploaded. Check the highlighted fields below; your inputs are preserved." });
      return;
    }
    void perform("Uploading document…", async (signal) => {
      const data = new FormData(); data.append("file", file!); data.append("title", title.trim()); data.append("scope", uploadScope);
      data.append("itemRefs", JSON.stringify(uploadScope === "general" ? [] : uploadRefs));
      const source = receiveSource(await (await request("/documents", signal, { method: "POST", body: data })).json());
      setSelectedId(source.id); setFilter("all"); setFile(null); setTitle(""); setUploadRefs([]); setUploadScope("products");
      if (fileInput.current) fileInput.current.value = "";
      setNotice({ type: "success", text: `${format(source)} uploaded privately: ${source.name}. Listed in Uploaded documents; not included in assistant knowledge until extracted, reviewed and approved.` });
      window.requestAnimationFrame(() => library.current?.scrollIntoView({ block: "start", behavior: "instant" }));
    });
  };
  const extract = (source?: Source) => {
    if (!acknowledged || !consent.fingerprint) return;
    const expectedRouteFingerprint = consent.fingerprint;
    void perform(source ? "Queueing source extraction…" : "Queueing pending extractions…", async (signal) => {
      const response = await request(source ? `/sources/${source.id}/extract` : "/extract-pending", signal,
        json("POST", { acknowledgeExternalProcessing: true, expectedRouteFingerprint, ...(source ? { expectedRevision: source.revision } : {}) }));
      const value: unknown = await response.json();
      if (source) receiveSource(value, source.id); else receiveIndex(value);
      setNotice({ type: "success", text: "Extraction request accepted. Check each source for queued, processing, review or retry status; no facts were approved." });
    });
  };
  const saveAssignment = () => {
    if (!selected || !assignment || conflict) return;
    if (assignment.scope === "products" && !assignment.refs.length) {
      setAssignmentErrors((current) => ({ ...current, [selected.id]: "Select at least one published item for product documents." }));
      document.getElementById("source-assignments")?.focus(); return;
    }
    void perform("Saving document scope and assignment…", async (signal) => {
      receiveSource(await (await request(`/sources/${selected.id}/assignment`, signal, json("PUT", {
        scope: assignment.scope, itemRefs: assignment.scope === "general" ? [] : assignment.refs, expectedRevision: assignment.revision,
      }))).json(), selected.id);
      setAssignments((current) => { const next = { ...current }; delete next[selected.id]; return next; });
      setNotice({ type: "success", text: "Assignment saved. Any previous approval is invalidated; extract and review the current source before use." });
    });
  };
  const decide = (decision: "approve" | "reject") => {
    if (!selected || selected.state !== "review" || conflict || assignment) return;
    void perform(decision === "approve" ? "Approving reviewed facts…" : "Rejecting extraction draft…", async (signal) => {
      receiveSource(await (await request(`/sources/${selected.id}/review`, signal, json("POST", {
        expectedRevision: review?.revision ?? selected.revision, decision, ...(review && decision === "approve" ? { facts: review.facts } : {}),
      }))).json(), selected.id);
      setReviews((current) => { const next = { ...current }; delete next[selected.id]; return next; });
      setNotice({ type: "success", text: decision === "approve" ? "Reviewed facts approved for this source revision." : "Extraction draft rejected; these facts will not be used." });
    });
  };
  const reloadDraft = () => {
    if (!selected || !window.confirm("Replace this source's unsaved assignment and fact edits with the latest loaded source? Other drafts are kept.")) return;
    setAssignments((current) => { const next = { ...current }; delete next[selected.id]; return next; });
    setReviews((current) => { const next = { ...current }; delete next[selected.id]; return next; });
    setConflicts((current) => current.filter((id) => id !== selected.id));
    setAssignmentErrors((current) => { const next = { ...current }; delete next[selected.id]; return next; });
  };
  const download = () => {
    if (!selected) return;
    void perform("Downloading private source…", async (signal) => {
      const response = await request(`/sources/${selected.id}/file`, signal);
      const blob = await response.blob();
      const length = Number(response.headers.get("content-length"));
      if (!blob.size || length > 0 && blob.size !== length) throw new Error("Source download was incomplete. No file was saved.");
      const url = URL.createObjectURL(blob);
      urls.current.set(url, window.setTimeout(() => { URL.revokeObjectURL(url); urls.current.delete(url); }, 60_000));
      const link = document.createElement("a"); link.href = url;
      const filename = response.headers.get("content-disposition")?.match(/filename="([^"]+)"/)?.[1];
      const extension = selected.format && /^(pdf|docx|txt|md)$/i.test(selected.format) ? selected.format.toLowerCase()
        : ({ pdf: "pdf", docx: "docx", text: "txt", video: "mp4", image: "jpg" })[selected.kind];
      link.download = filename && /^[a-zA-Z0-9_. -]{1,180}$/.test(filename) ? filename : `knowledge-${selected.id}.${extension}`;
      document.body.appendChild(link); try { link.click(); } finally { link.remove(); }
      setNotice({ type: "success", text: "Source download started. Check your browser downloads." });
    });
  };
  const editFacts = (facts: Fact[]) => {
    if (selected) setReviews((current) => ({ ...current, [selected.id]: { revision: current[selected.id]?.revision ?? selected.revision, facts } }));
  };
  const currentFacts = review?.facts ?? selected?.facts ?? [];
  const invalidFacts = !currentFacts.length || currentFacts.some((fact) => !fact.text.trim() || !fact.location.trim());
  const sources = index?.sources.filter((source) => filter === "all" || (filter === "attention" ? attention(source) : source.state === filter)) ?? [];
  const documents = index?.sources.filter((source) => source.origin === "document").sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt)) ?? [];
  const editAssignment = (scope: Scope, itemRefs: string[]) => {
    if (!selected) return;
    setAssignments((current) => ({ ...current, [selected.id]: { revision: current[selected.id]?.revision ?? selected.revision, refs: itemRefs, scope } }));
    setAssignmentErrors((current) => { const next = { ...current }; delete next[selected.id]; return next; });
  };
  const openDocument = (source: Source) => {
    setSelectedId(source.id);
    window.requestAnimationFrame(() => sourceReview.current?.scrollIntoView({ block: "start", behavior: "instant" }));
  };

  return <section aria-labelledby="knowledge-title" className="min-w-0 space-y-5">
    <div className="min-w-0 rounded-2xl border border-[var(--line)] bg-white/80 p-5">
      <h2 id="knowledge-title" className="text-xl font-semibold">Support knowledge</h2>
      <p className="mt-2 text-sm leading-6">Catalog text is live automatically. Review media/document facts before publishing.</p>
      <p className="mt-2 text-sm leading-6">Sync catalog photos/videos or upload product documents and general customer-service Q&A. Extract → review drafts → approve. Changed sources are stale and out of use.</p>
      <details className="mt-2 text-sm leading-6">
        <summary className="min-h-11 cursor-pointer py-2 font-medium">Details: privacy and approval</summary>
        <p>Uploads are stored privately on this server. Extraction sends the selected file to the selected AI provider shown below. Extract only approved public, non-sensitive documents or media you are authorized to send externally. Paid API usage may apply; STYL does not automatically upgrade a plan or enable billing. Never submit customer records, personal data or confidential material. No extraction automatically approves facts.</p>
        <p className="mt-2">Catalog media is reused without reuploading. Assign product documents to published equipment or accessories, or choose general customer-service Q&A without product assignments. STYL retrieves approved facts for the assistant; a newly added document becomes available only after extraction, review and approval. Approval covers only the reviewed source revision, scope and assignment; changes require a new review.</p>
      </details>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" disabled={Boolean(busy)} onClick={refresh} className={button}>Refresh knowledge</button>
        <button type="button" disabled={disabled || !index} onClick={sync} className={button}>Sync catalog</button>
      </div>
      {loading ? <p role="status" className="mt-3 text-sm">Loading knowledge…</p> : null}
      {busy ? <p role="status" className="mt-3 text-sm">{busy} Keep this page open.</p> : null}
      {readError ? <p role="alert" className="mt-3 break-words rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm">{readError} Existing data may be stale, not empty.</p> : null}
      <AdminNotice message={notice} focusTarget={noticeFocusTarget} />
    </div>
    {accessError ? <p role="alert" className="rounded-xl border border-red-400 bg-red-50 p-4 text-sm">Private knowledge hidden because admin access was rejected. Draft inputs remain in memory.</p> : index ? <>
      {index.warnings.length ? <ul aria-label="Knowledge warnings" className="list-disc space-y-2 break-words pl-5 text-sm text-amber-950">{index.warnings.map((warning, position) => <li key={position}>{redact(warning)}</li>)}</ul> : null}
      <div className="rounded-2xl border border-[var(--line)] bg-white/80 p-5">
        <RoutingPanel index={index} chatRoute={chatRoute} />
        {!index.routes || !validFingerprint(index.routeFingerprint) ? <p role="alert" className="mt-3 text-sm text-amber-950">Extraction is unavailable because current route consent metadata is missing. Refresh knowledge after the server is updated; uploads and drafts are preserved.</p>
          : consent.refreshRequired ? <p role="alert" className="mt-3 text-sm text-amber-950">Refresh knowledge before confirming external processing again. No extraction will be retried automatically.</p>
            : consent.reconfirm ? <p role="alert" className="mt-3 text-sm text-amber-950">Extraction routes changed or could not be confirmed. Review the current routes and confirm external processing again; your drafts are preserved.</p> : null}
        <label className="mt-3 flex min-h-12 items-start gap-3 text-sm leading-6">
          <input type="checkbox" checked={acknowledged} disabled={disabled || !canAcknowledge} onChange={(event) => setConsent({
            fingerprint: event.target.checked && canAcknowledge ? index.routeFingerprint! : null,
            refreshRequired: false, reconfirm: false,
          })} className="mt-1 h-5 w-5 shrink-0" />
          <span>Only approved public, non-sensitive files — I allow sending them to the selected AI provider for extraction. Paid API usage may apply; no automatic paid upgrade.</span>
        </label>
        <button type="button" disabled={disabled || !acknowledged || !index.sources.some((source) => ["pending", "stale", "failed"].includes(source.state))} onClick={() => extract()} className={`mt-3 ${button}`}>Extract pending</button>
      </div>
      <section aria-labelledby="add-documents-title" className="min-w-0 rounded-2xl border border-[var(--line)] bg-white/80 p-5">
        <h3 id="add-documents-title" className="text-lg font-semibold">Add documents</h3>
        <p className="mt-2 text-sm leading-6">Upload a product document or general customer-service Q&A, extract drafts, then review and approve.</p>
        <fieldset disabled={disabled} className="min-w-0">
          <label className="mt-3 block text-sm font-medium">Document title<input ref={titleInput} value={title} maxLength={200} aria-required="true" aria-invalid={Boolean(uploadErrors.title)} aria-describedby={uploadErrors.title ? "document-title-error" : undefined}
            onChange={(event) => { setTitle(event.target.value); setUploadErrors((current) => ({ ...current, title: undefined })); }} className={field} /></label>
          {uploadErrors.title ? <p id="document-title-error" className="mt-2 text-sm text-red-800">{uploadErrors.title}</p> : null}
          <div className="mt-4 min-w-0">
            <input ref={fileInput} type="file" aria-label="Document file" aria-required="true" aria-invalid={Boolean(uploadErrors.file)}
              accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
              onChange={(event) => { setFile(event.target.files?.[0] ?? null); setUploadErrors((current) => ({ ...current, file: undefined })); }} className="hidden" />
            <button ref={chooseFile} type="button" disabled={disabled} aria-describedby={`document-file-name${uploadErrors.file ? " document-file-error" : ""}`}
              onClick={() => fileInput.current?.click()} className={`${button} ${uploadErrors.file ? "!border-red-600" : ""}`}>Choose file</button>
            <p id="document-file-name" className="mt-2 break-words text-sm">{file ? `${file.name} · ${size(file.size)}` : "No file chosen"}</p>
            {uploadErrors.file ? <p id="document-file-error" className="mt-2 text-sm text-red-800">{uploadErrors.file}</p> : null}
          </div>
          <p className="mt-2 text-sm text-[var(--muted)]">PDF, DOCX, TXT or MD · up to {size(index.limits.documentBytes)}. Upload saves privately; extraction is a separate action.</p>
          <ScopeChoices name="upload-scope" value={uploadScope} onChange={(scope) => { setUploadScope(scope); setUploadErrors((current) => ({ ...current, refs: undefined })); }} disabled={disabled} />
          {uploadScope === "products" ? <ItemChoices id="upload-assignments" label="Assign document to published items" items={index.items} selected={uploadRefs}
            onChange={(itemRefs) => { setUploadRefs(itemRefs); setUploadErrors((current) => ({ ...current, refs: undefined })); }} disabled={disabled} error={uploadErrors.refs} />
            : <p className="mt-2 text-sm text-[var(--muted)]">General Q&A is not tied to products. No product assignments will be sent.</p>}
          <button type="button" disabled={disabled || !index} onClick={upload} className={`mt-4 ${button} !bg-[var(--ink)] text-white`}>Upload document</button>
        </fieldset>
      </section>
      <section ref={library} aria-labelledby="document-library-title" className="min-w-0 scroll-mt-4 rounded-2xl border border-[var(--line)] bg-white/80 p-5">
        <h3 id="document-library-title" className="text-lg font-semibold">Uploaded documents</h3>
        <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
          {[["Uploaded", documents.length], ["Ready for assistant", assistantScope ? documents.filter((source) => included(source, index.items, assistantScope)).length : "—"], ["Awaiting review", documents.filter((source) => source.state === "review").length]].map(([label, count]) => <div key={label} className="min-w-0 rounded-xl bg-[var(--paper)] p-3"><dt>{label}</dt><dd className="mt-1 text-xl font-semibold">{count}</dd></div>)}
        </dl>
        <p className="mt-3 text-sm text-[var(--muted)]">Uploaded does not mean approved. Only current approved facts are included; the assistant must also be enabled for their topic. Catalog photos and videos are listed separately below.</p>
        {!assistantScope ? <p role="alert" className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-950">AI scope settings could not be confirmed. Readiness is unconfirmed; refresh knowledge or check Conversations. Uploads and approvals are preserved.</p> : <>
          {!assistantScope.enabled ? <p role="alert" className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-950">Automatic AI replies are disabled. Approved documents remain stored but are not currently used. Enable automatic AI replies in Conversations when ready.</p> : null}
          {!assistantScope.allowedTopics.includes("customer_service") ? <p role="alert" className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-950">General customer-service Q&amp;A is excluded by the current AI scope. In Conversations, select “Approved customer-service Q&amp;A” to use approved general documents. Upload and review remain available.</p> : null}
        </>}
        {documents.length ? <ul className="mt-4 max-h-[32rem] space-y-3 overflow-y-auto p-1">
          {documents.map((source) => <li key={source.id} className={`min-w-0 rounded-xl border p-4 text-sm ${selectedId === source.id ? "border-[var(--ink)]" : "border-[var(--line)]"}`}>
            <p className="break-words font-semibold">{source.name}</p>
            <dl className="mt-2 space-y-1">
              <div><dt className="inline text-[var(--muted)]">Type: </dt><dd className="inline">{format(source)}{source.bytes === undefined ? " · size unavailable" : ` · ${size(source.bytes)}`}</dd></div>
              <div><dt className="inline text-[var(--muted)]">Uploaded: </dt><dd className="inline"><time dateTime={source.createdAt}>{when(source.createdAt)}</time></dd></div>
              <div><dt className="inline text-[var(--muted)]">State: </dt><dd className="inline">{stateLabel[source.state]}</dd></div>
              <div className="break-words"><dt className="inline text-[var(--muted)]">Assignment: </dt><dd className="inline">{assignmentLabel(source, index.items)}</dd></div>
            </dl>
            <p className={`mt-2 font-medium ${included(source, index.items, assistantScope) ? "text-green-800" : "text-[var(--muted)]"}`}>{included(source, index.items, assistantScope) ? "Included in assistant knowledge" : !assistantScope && source.state === "approved" ? "Assistant inclusion unconfirmed" : "Not included in assistant knowledge"}</p>
            {source.error ? <p className="mt-2 break-words text-amber-950">Source note: {redact(source.error)}</p> : null}
            {source.state === "approved" && source.approvedCurrent === false ? <p className="mt-2 text-amber-950">Approval is no longer current. Review the source and its assignments; changed files need to be uploaded and reviewed again.</p> : null}
            <button type="button" disabled={Boolean(busy)} aria-pressed={selectedId === source.id} aria-label={`Review document: ${source.name}`} onClick={() => openDocument(source)} className={`mt-3 ${button}`}>Review / download</button>
          </li>)}
        </ul> : <p className="mt-4 text-sm">No uploaded documents yet. Upload one above; existing catalog media does not count as a document.</p>}
      </section>
      <div className="flex flex-wrap gap-2" aria-label="Knowledge source filters">
        {([["all", "All sources", index.sources.length], ["review", "Review", index.sources.filter((source) => source.state === "review").length],
          ["approved", "Approved", index.sources.filter((source) => source.state === "approved").length], ["attention", "Needs attention", index.sources.filter(attention).length]] as const)
          .map(([value, label, count]) => <button key={value} type="button" disabled={Boolean(busy)} aria-pressed={filter === value} onClick={() => setFilter(value)} className={`${button} ${filter === value ? "!bg-[var(--ink)] text-white" : ""}`}>{label} ({count})</button>)}
      </div>
      {!index.sources.length ? <p className="rounded-2xl border border-dashed border-[var(--line)] p-5 text-sm">No knowledge sources yet. Sync catalog to reuse product photos/videos, or upload a document above. Then extract and review before approving.</p> : <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <section aria-label="Knowledge sources" className="min-w-0">
          <div className="max-h-[32rem] space-y-2 overflow-y-auto p-1">
            {sources.length ? sources.map((source) => <button key={source.id} type="button" disabled={Boolean(busy)} aria-pressed={selectedId === source.id} aria-label={`Open source: ${source.name}`} onClick={() => setSelectedId(source.id)} className={`min-h-12 w-full min-w-0 rounded-2xl border p-4 text-left text-sm ${selectedId === source.id ? "border-[var(--ink)] bg-white" : "border-[var(--line)] bg-white/70"}`}>
              <span className="block break-words font-semibold">{source.name}</span>
              <span className="mt-1 block">{source.kind.toUpperCase()} · {source.origin} · {stateLabel[source.state]}</span>
              <span className="mt-2 block break-words text-[var(--muted)]">{assignmentLabel(source, index.items)}</span>
              {source.error ? <span className="mt-2 block break-words text-red-800">{redact(source.error)}</span> : null}
            </button>) : <p className="p-4 text-sm">No sources in this filter.</p>}
          </div>
        </section>
        {selected ? <section ref={sourceReview} aria-labelledby="knowledge-source-title" className="min-w-0 scroll-mt-4 rounded-2xl border border-[var(--line)] bg-white/80 p-5">
          <h3 id="knowledge-source-title" className="break-words text-lg font-semibold">{selected.name}</h3>
          <p className="mt-2 text-sm">{stateLabel[selected.state]} · Revision {selected.revision} · {when(selected.updatedAt)}</p>
          {selected.error ? <p role="alert" className="mt-3 break-words rounded-xl bg-red-50 p-3 text-sm text-red-900">{redact(selected.error)}</p> : null}
          {selected.retryAt ? <p className="mt-2 text-sm">Retry available after {when(selected.retryAt)}. Quota or provider errors require a deliberate retry.</p> : null}
          {working(selected) ? <p role="status" className="mt-3 text-sm">Extraction {selected.state}. Facts are not approved; this view checks for the result while open.</p> : null}
          {selected.state === "stale" ? <p className="mt-3 text-sm">This source changed. Previous facts are not in use. Sync catalog if needed, then extract and review again.</p> : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" disabled={disabled} onClick={download} className={button}>Download source</button>
            <button type="button" disabled={disabled || !acknowledged || !extractable(selected) || conflict || Boolean(assignment) || Boolean(review)} onClick={() => extract(selected)} className={button}>{["failed", "paused", "rejected"].includes(selected.state) ? "Retry extraction" : "Extract source"}</button>
          </div>
          {conflict ? <p role="alert" className="mt-4 rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm">Source revision changed or could not be confirmed. Refresh knowledge to compare; your unsaved inputs below are preserved. Reload source draft only when ready to replace them.</p> : null}
          {selected.origin === "document" ? <ScopeChoices name="source-scope" value={assignment?.scope ?? sourceScope(selected)} disabled={disabled || working(selected)}
            onChange={(scope) => editAssignment(scope, assignment?.refs ?? selected.itemRefs)} /> : null}
          {(assignment?.scope ?? sourceScope(selected)) === "products" ? <ItemChoices id="source-assignments" label="Assigned published items" items={index.items} selected={assignment?.refs ?? selected.itemRefs} disabled={disabled || working(selected)}
            error={assignmentErrors[selected.id]} onChange={(itemRefs) => editAssignment(assignment?.scope ?? sourceScope(selected), itemRefs)} />
            : <p className="mt-3 text-sm">General customer-service Q&A · no product assignment.</p>}
          <button type="button" disabled={disabled || !assignment || conflict || working(selected)} onClick={saveAssignment} className={`mt-3 ${button}`}>Save assignment</button>
          {assignment ? <p className="mt-2 text-sm">Saving changes invalidates approval. Save or reload this assignment before reviewing facts.</p> : null}
          <h4 className="mt-5 font-semibold">{selected.state === "approved" ? "Approved facts" : "Extracted draft facts"} ({currentFacts.length})</h4>
          <p className="mt-2 text-sm text-[var(--muted)]">Check every fact against its source location. {sourceScope(selected) === "general" ? "Only approved customer-service Q&A is allowed." : "Only product and compatibility facts are allowed; do not infer prices or unsupported claims."}</p>
          <div aria-label="Source facts" className="mt-3 max-h-[28rem] space-y-4 overflow-y-auto rounded-xl border border-[var(--line)] p-3">
            {currentFacts.length ? currentFacts.map((fact, position) => <div key={position} className="min-w-0 border-b border-[var(--line)] pb-3 last:border-b-0">
              <label className="block text-sm font-medium">Fact {position + 1}
                <textarea rows={3} value={fact.text} disabled={disabled || selected.state !== "review"} onChange={(event) => editFacts(currentFacts.map((item, i) => i === position ? { ...item, text: event.target.value } : item))} className={`${field} resize-y`} />
              </label>
              <label className="mt-2 block text-sm">Topic {position + 1}
                <select value={fact.topic} disabled={disabled || selected.state !== "review"} onChange={(event) => editFacts(currentFacts.map((item, i) => i === position ? { ...item, topic: event.target.value as Fact["topic"] } : item))} className={field}>
                  {sourceScope(selected) === "general" ? <option value="customer_service">Customer service</option> : <><option value="products">Products</option><option value="compatibility">Compatibility</option></>}
                </select>
              </label>
              <label className="mt-2 block text-sm">Source location {position + 1}
                <input value={fact.location} disabled={disabled || selected.state !== "review"} onChange={(event) => editFacts(currentFacts.map((item, i) => i === position ? { ...item, location: event.target.value } : item))} className={field} />
              </label>
              {selected.state === "review" ? <button type="button" disabled={disabled} onClick={() => editFacts(currentFacts.filter((_, i) => i !== position))} className={`mt-2 ${button}`}>Remove fact {position + 1}</button> : null}
            </div>) : <p className="text-sm">No extracted facts yet. Extract this source, then review the draft here.</p>}
          </div>
          {selected.state === "review" ? <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" disabled={disabled || conflict || Boolean(assignment) || invalidFacts} onClick={() => decide("approve")} className={`${button} !bg-[var(--ink)] text-white`}>Approve reviewed facts</button>
            <button type="button" disabled={disabled || conflict || Boolean(assignment)} onClick={() => decide("reject")} className={button}>Reject draft</button>
          </div> : null}
          {assignment || review || conflict ? <button type="button" disabled={disabled} onClick={reloadDraft} className={`mt-4 ${button}`}>Reload source draft</button> : null}
        </section> : <p className="p-5 text-sm">Choose a source to review facts, retry extraction or change its assigned products.</p>}
      </div>}
    </> : !loading ? <p className="text-sm">Knowledge is unavailable. Refresh knowledge to retry.</p> : null}
  </section>;
}
