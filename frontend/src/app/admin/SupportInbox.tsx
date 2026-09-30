"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { AdminNotice, type AdminMessage } from "./AdminFields";

type Topic = "products" | "pricing" | "compatibility";
type State = "ai" | "waiting_human" | "human" | "closed";
type Reference = { type: "product" | "accessory"; id: number; url: string; label: string };
type Message = { id: string; role: "customer" | "assistant" | "human" | "system"; text: string; createdAt: string; references: Reference[] };
type Conversation = { id: string; state: State; revision: number; createdAt: string; updatedAt: string; currency: string; needsHuman: boolean; reason: string | null; processing: boolean; messages: Message[] };
type Summary = Omit<Conversation, "messages" | "processing"> & { lastMessage: string; messageCount: number; guestLabel: string };
type Settings = { enabled: boolean; allowedTopics: Topic[]; revision: number; provider: string; model: string; configured: boolean; environment: string; localTestingOnly: boolean };
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string";
const identifier = (value: unknown): value is string => text(value) && /^[a-zA-Z0-9_-]{1,128}$/.test(value);
const date = (value: unknown) => text(value) && Number.isFinite(Date.parse(value));
const number = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const topics = (value: unknown): value is Topic[] => Array.isArray(value) && value.every((topic) => ["products", "pricing", "compatibility"].includes(topic));
function validBase(value: unknown): boolean {
  return object(value) && identifier(value.id) && ["ai", "waiting_human", "human", "closed"].includes(String(value.state))
    && number(value.revision) && date(value.createdAt) && date(value.updatedAt) && text(value.currency)
    && typeof value.needsHuman === "boolean" && (value.reason === null || text(value.reason));
}
function validConversation(value: unknown): value is Conversation {
  return validBase(value) && object(value) && typeof value.processing === "boolean"
    && Array.isArray(value.messages) && value.messages.every((message) => object(message) && identifier(message.id)
      && ["customer", "assistant", "human", "system"].includes(String(message.role)) && text(message.text) && date(message.createdAt)
      && Array.isArray(message.references) && message.references.every((reference) => object(reference)
        && ["product", "accessory"].includes(String(reference.type)) && number(reference.id) && text(reference.url) && text(reference.label)));
}
function validSettings(value: unknown): value is Settings {
  return object(value) && typeof value.enabled === "boolean" && topics(value.allowedTopics) && number(value.revision)
    && ["provider", "model", "environment"].every((key) => text(value[key])) && typeof value.configured === "boolean" && typeof value.localTestingOnly === "boolean";
}
function validQueue(value: unknown): value is { items: Summary[]; needsHumanCount: number } {
  return object(value) && number(value.needsHumanCount) && Array.isArray(value.items)
    && value.items.every((item) => validBase(item) && object(item) && text(item.lastMessage) && number(item.messageCount) && text(item.guestLabel));
}
const label = (value: State) => ({ ai: "AI assistance", waiting_human: "Waiting for human help", human: "Human operator joined", closed: "Closed" })[value];
const button = "min-h-12 rounded-full border border-[var(--line)] bg-white px-4 py-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50";
const sourceUrl = (value: string) => /^\/(?:products|accessories)\/[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(value);

export default function SupportInbox({ adminToken, active, onBusyChange, onDirtyChange }: {
  adminToken: string; active: boolean; onBusyChange: (busy: boolean) => void; onDirtyChange: (dirty: boolean) => void;
}) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [allowedTopics, setAllowedTopics] = useState<Topic[]>([]);
  const [queue, setQueue] = useState<{ items: Summary[]; needsHumanCount: number } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [threads, setThreads] = useState<Record<string, Conversation>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<AdminMessage | null>(null);
  const [connectionError, setConnectionError] = useState("");
  const [accessError, setAccessError] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const initialized = useRef(false);
  const writeController = useRef<AbortController | null>(null);
  const retries = useRef<Record<string, { id: string; text: string }>>({});
  const history = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const selected = selectedId ? threads[selectedId] : null;
  const draft = selectedId ? drafts[selectedId] ?? "" : "";
  const settingsDirty = Boolean(settings && (enabled !== settings.enabled || [...allowedTopics].sort().join() !== [...settings.allowedTopics].sort().join()));
  const dirty = settingsDirty || Object.values(drafts).some((value) => value.length > 0);
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => () => { writeController.current?.abort(); onBusyChange(false); onDirtyChange(false); }, [onBusyChange, onDirtyChange]);
  useEffect(() => {
    if (history.current && nearBottom.current) history.current.scrollTop = history.current.scrollHeight;
  }, [selectedId, selected?.messages.length]);

  const request = useCallback(async (suffix: string, signal: AbortSignal, options: RequestInit = {}) => {
    const response = await fetch(`${API_BASE}/api/admin/support${suffix}`, {
      ...options, headers: { Authorization: `Bearer ${adminToken}`, ...options.headers },
      cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal,
    });
    if (!response.ok) {
      let detail = `Support inbox request failed (HTTP ${response.status}). Your draft is preserved.`;
      try { const value: unknown = await response.json(); if (object(value) && text(value.detail)) detail = value.detail; } catch { /* Retain the safe HTTP fallback. */ }
      if (response.status === 401) { setAccessError(true); detail = "Admin access was rejected. Private support data is hidden. Sign in again or refresh after restoring access. Drafts remain in this tab."; }
      if (response.status === 409) detail += " Refresh the selected conversation or reload saved AI settings before retrying; nothing will be automatically resubmitted.";
      throw new Error(adminToken ? detail.replaceAll(adminToken, "[redacted]") : detail);
    }
    return response.json() as Promise<unknown>;
  }, [adminToken]);
  const receive = useCallback((value: unknown, expectedId: string) => {
    if (!validConversation(value) || value.id !== expectedId) throw new Error("Support conversation response is invalid. Your draft is preserved.");
    setThreads((current) => current[value.id]?.revision >= value.revision ? current : { ...current, [value.id]: value });
  }, []);
  const loadSettings = useCallback(async (signal: AbortSignal) => {
    const value = await request("/config", signal);
    if (!validSettings(value)) throw new Error("Support settings response is invalid. Reload saved settings to retry.");
    if (signal.aborted) return;
    setSettings(value); setEnabled(value.enabled); setAllowedTopics(value.allowedTopics); initialized.current = true;
  }, [request]);
  const loadQueue = useCallback(async (signal: AbortSignal) => {
    const value = await request("/conversations", signal);
    if (!validQueue(value)) throw new Error("Support inbox response is invalid. Existing conversations may be stale.");
    if (signal.aborted) return;
    setQueue(value);
  }, [request]);
  const loadThread = useCallback(async (signal: AbortSignal, id: string) => {
    const value = await request(`/conversations/${id}`, signal);
    if (!signal.aborted) receive(value, id);
  }, [receive, request]);

  useEffect(() => {
    if (!active) return;
    let stopped = false;
    let timer: number | undefined;
    let controller: AbortController | null = null;
    const poll = async () => {
      if (stopped || controller || document.visibilityState !== "visible") return;
      controller = new AbortController();
      const current = controller;
      try {
        if (!writeController.current) {
          if (!initialized.current) { setLoading(true); await loadSettings(current.signal); }
          await loadQueue(current.signal);
          if (selectedId) await loadThread(current.signal, selectedId);
          if (!stopped) { setConnectionError(""); setAccessError(false); }
        }
      } catch (value) {
        if (!stopped && !current.signal.aborted) setConnectionError(value instanceof Error ? value.message : "Connection lost; existing support data may be stale.");
      } finally {
        controller = null;
        if (!stopped) {
          setLoading(false);
          if (document.visibilityState === "visible") timer = window.setTimeout(poll, 2000);
        }
      }
    };
    const visibility = () => { window.clearTimeout(timer); if (document.visibilityState === "visible") void poll(); else controller?.abort(); };
    void poll();
    document.addEventListener("visibilitychange", visibility);
    return () => { stopped = true; window.clearTimeout(timer); controller?.abort(); document.removeEventListener("visibilitychange", visibility); };
  }, [active, selectedId, loadSettings, loadQueue, loadThread]);

  const perform = async (action: (signal: AbortSignal) => Promise<void>) => {
    if (writeController.current) return;
    const controller = new AbortController();
    writeController.current = controller; setBusy(true); onBusyChange(true); setNotice(null);
    try { await action(controller.signal); }
    catch (value) { if (!controller.signal.aborted) setNotice({ type: "error", text: value instanceof Error ? value.message : "Unable to save support changes. Drafts are preserved." }); }
    finally { writeController.current = null; if (!controller.signal.aborted) { setBusy(false); onBusyChange(false); } }
  };
  const refresh = () => void perform(async (signal) => {
    if (!initialized.current) await loadSettings(signal);
    await loadQueue(signal);
    if (selectedId) await loadThread(signal, selectedId);
    setConflict(null); setConnectionError(""); setAccessError(false);
  });
  const action = (next: "takeover" | "resume_ai" | "close") => {
    if (!selected || accessError) return;
    if ((next === "close" || next === "resume_ai") && !window.confirm(next === "close" ? "Close this conversation? The customer will need to start a new conversation." : "Resume automatic AI replies for this conversation? Human reply drafts will be kept.")) return;
    void perform(async (signal) => {
      try {
        receive(await request(`/conversations/${selected.id}/action`, signal, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: next, expectedRevision: selected.revision }) }), selected.id);
        await loadQueue(signal);
      } catch (value) { setConflict(selected.id); throw value; }
    });
  };
  const send = () => {
    if (!selected || selected.state !== "human" || accessError || conflict === selected.id || !draft.trim() || draft.length > 2000) return;
    const body = draft.trim();
    if (retries.current[selected.id]?.text !== body) retries.current[selected.id] = { id: crypto.randomUUID(), text: body };
    const attempt = retries.current[selected.id];
    void perform(async (signal) => {
      try {
        receive(await request(`/conversations/${selected.id}/messages`, signal, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: attempt.text, clientMessageId: attempt.id, expectedRevision: selected.revision }) }), selected.id);
        setDrafts((current) => ({ ...current, [selected.id]: current[selected.id]?.trim() === attempt.text ? "" : current[selected.id] }));
        delete retries.current[selected.id];
        setNotice({ type: "success", text: "Human reply saved." });
        await loadQueue(signal);
      } catch (value) { setConflict(selected.id); throw value; }
    });
  };
  const saveSettings = () => {
    if (!settings || accessError || !allowedTopics.length) return;
    void perform(async (signal) => {
      const value = await request("/config", signal, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled, allowedTopics, expectedRevision: settings.revision }) });
      if (!validSettings(value)) throw new Error("Unable to confirm saved support settings. Your choices are retained.");
      setSettings(value); setEnabled(value.enabled); setAllowedTopics(value.allowedTopics);
      setNotice({ type: "success", text: "AI scope settings saved. Existing human conversations are not automatically resumed." });
    });
  };

  return <section aria-labelledby="support-inbox-title" className="min-w-0 space-y-5">
    <div className="rounded-2xl border border-[var(--line)] bg-white/80 p-5">
      <h2 id="support-inbox-title" className="text-xl font-semibold">Customer support inbox</h2>
      <p className="mt-2 text-sm leading-6">Local single-operator prototype using the existing shared admin sign-in. This is not multi-agent staff identity or production customer support. Use only synthetic messages; no personal or confidential information.</p>
      <p className="mt-2 text-sm leading-6">AI messages and human replies are labeled separately. Taking over pauses AI; returning to AI or closing always requires an explicit action.</p>
      <button type="button" disabled={busy} onClick={refresh} className={`mt-4 ${button}`}>Refresh support inbox</button>
      {loading ? <p role="status" className="mt-3 text-sm">Loading support inbox…</p> : null}
      {connectionError ? <p role="alert" className="mt-3 rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm">Connection problem. Existing data may be stale, not empty. {connectionError}</p> : null}
      <AdminNotice message={notice} />
    </div>
    {accessError ? <p role="alert" className="rounded-xl border border-red-400 bg-red-50 p-4 text-sm">Private support content hidden because admin access was rejected. Sign out and authenticate again, or refresh after access is restored. Unsaved replies remain in memory.</p> : <>
      {settings ? <section aria-labelledby="support-settings-title" className="min-w-0 rounded-2xl border border-[var(--line)] bg-white/80 p-5">
        <h3 id="support-settings-title" className="text-lg font-semibold">Automatic AI scope</h3>
        <p className="mt-2 break-words text-sm">Provider: {settings.provider} · Model: {settings.model} · {settings.configured ? "Provider configured" : "Provider not configured"} · Environment: {settings.environment}</p>
        <p className="mt-2 text-sm text-[var(--muted)]">Provider/model are server-configured. No API keys are shown or entered here. Disabling AI keeps human support available. Gemini free-tier messages may be reviewed or used for service improvement.</p>
        <fieldset disabled={busy} className="mt-4 min-w-0 space-y-2">
          <label className="flex min-h-12 items-center gap-3 text-sm"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} className="h-5 w-5" />Enable automatic AI replies</label>
          <legend className="sr-only">Allowed AI topics</legend>
          {(["products", "pricing", "compatibility"] as const).map((topic) => <label key={topic} className="flex min-h-12 items-center gap-3 text-sm"><input type="checkbox" checked={allowedTopics.includes(topic)} onChange={(event) => setAllowedTopics((current) => event.target.checked ? [...current, topic] : current.filter((value) => value !== topic))} className="h-5 w-5" />{({ products: "Product information", pricing: "Listed pricing", compatibility: "Documented compatibility" })[topic]}</label>)}
        </fieldset>
        {!allowedTopics.length ? <p className="mt-3 text-sm text-amber-900">Choose at least one approved topic. To stop automatic replies entirely, switch AI replies off.</p> : null}
        <div className="mt-4 flex flex-wrap gap-3"><button type="button" disabled={busy || !settingsDirty || !allowedTopics.length} onClick={saveSettings} className={button}>Save AI scope</button><button type="button" disabled={busy} onClick={() => {
          if (settingsDirty && !window.confirm("Discard unsaved AI settings and reload saved settings?")) return;
          void perform(async (signal) => { await loadSettings(signal); setConnectionError(""); });
        }} className={button}>Reload saved AI settings</button></div>
      </section> : null}
      <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <section aria-labelledby="support-queue-title" className="min-w-0 rounded-2xl border border-[var(--line)] bg-white/80 p-4">
          <h3 id="support-queue-title" className="text-lg font-semibold">Conversations</h3>
          <p className="mt-2 text-sm" role="status">{queue ? `${queue.needsHumanCount} need human attention · ${queue.items.length} conversations` : "Conversation counts are not yet available."}</p>
          {queue?.items.length === 0 ? <p className="mt-4 text-sm">No support conversations yet.</p> : null}
          <ul className="mt-4 space-y-3">{queue?.items.map((item) => <li key={item.id}><button type="button" disabled={busy} aria-pressed={selectedId === item.id} onClick={() => { setSelectedId(item.id); nearBottom.current = true; setNotice(null); }} className={`block min-h-12 w-full min-w-0 rounded-xl border p-3 text-left text-sm ${item.needsHuman ? "border-amber-400 bg-amber-50" : "border-[var(--line)] bg-white"} ${selectedId === item.id ? "ring-2 ring-[var(--ink)]" : ""}`}>
            <span className="block break-words font-semibold">{item.guestLabel}</span>
            <span className="mt-1 block">{item.needsHuman ? "Needs human attention · " : ""}{label(item.state)} · {item.currency}</span>
            <span className="mt-2 line-clamp-3 block whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{item.lastMessage || "No messages yet"}</span>
            <span className="mt-2 block text-xs">{item.messageCount} messages{drafts[item.id] ? " · Unsaved reply" : ""}</span>
          </button></li>)}</ul>
        </section>
        <section aria-labelledby="support-thread-title" className="min-w-0 rounded-2xl border border-[var(--line)] bg-white/80 p-4 sm:p-5">
          <h3 id="support-thread-title" className="text-lg font-semibold">Selected conversation</h3>
          {!selected ? <p className="mt-3 text-sm">{selectedId ? "Loading selected conversation…" : "Choose a conversation to review or take over."}</p> : <>
            <p role="status" className="mt-3 text-sm font-semibold">{label(selected.state)}{selected.processing ? " · AI is thinking…" : ""}</p>
            {selected.needsHuman ? <p className="mt-3 rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm">Needs human attention{selected.reason ? `: ${selected.reason}` : ""}</p> : null}
            <div ref={history} role="log" aria-label="Selected support messages" aria-live="polite" aria-relevant="additions" tabIndex={0} onScroll={() => { const element = history.current; if (element) nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 60; }} className="mt-4 max-h-[52vh] min-h-32 space-y-3 overflow-y-auto overscroll-contain rounded-xl border border-[var(--line)] p-3">
              {selected.messages.map((message) => <article key={message.id} className="min-w-0 rounded-xl bg-neutral-50 p-3"><p className="text-xs font-semibold">{({ customer: "Customer", assistant: "STYL AI", human: "STYL human operator", system: "Support status" })[message.role]}</p><p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 [overflow-wrap:anywhere]">{message.text}</p>{message.references.filter((reference) => sourceUrl(reference.url)).map((reference, position) => <Link key={`${reference.id}-${position}`} href={reference.url} className="mt-2 block min-h-11 break-words py-2 text-sm underline">{reference.label}</Link>)}</article>)}
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" disabled={busy || selected.state === "closed" || selected.state === "human" || conflict === selected.id} onClick={() => action("takeover")} className={button}>Take over conversation</button>
              <button type="button" disabled={busy || selected.state === "closed" || selected.state === "ai" || !settings?.enabled || conflict === selected.id} onClick={() => action("resume_ai")} className={button}>Resume AI</button>
              <button type="button" disabled={busy || selected.state === "closed" || conflict === selected.id} onClick={() => action("close")} className={button}>Close conversation</button>
              <button type="button" disabled={busy} onClick={refresh} className={button}>Refresh selected conversation</button>
            </div>
            {conflict === selected.id ? <p role="alert" className="mt-3 rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm">The last write could not be confirmed. Refresh this conversation before retrying. Your reply and its retry identity are preserved; no automatic resend will occur.</p> : null}
            <form className="mt-4" onSubmit={(event) => { event.preventDefault(); send(); }}>
              <label className="block text-sm font-medium">Human reply<textarea aria-label="Human reply" value={draft} maxLength={2000} rows={4} disabled={busy} onChange={(event) => setDrafts((current) => ({ ...current, [selected.id]: event.target.value }))} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} className="mt-2 block w-full min-w-0 rounded-xl border border-[var(--line)] p-3 text-base" /></label>
              <p className="mt-2 text-xs leading-5 text-[var(--muted)]">{draft.length}/2000 characters. {selected.state !== "human" ? "Take over before sending a human reply. Drafts are retained across admin sections." : "Enter to send; Shift+Enter for a new line."}</p>
              <button type="submit" disabled={busy || selected.state !== "human" || conflict === selected.id || !draft.trim()} className={`mt-3 ${button}`}>{busy ? "Saving…" : "Send human reply"}</button>
            </form>
          </>}
        </section>
      </div>
    </>}
  </section>;
}
