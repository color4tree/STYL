"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { SupportQuestionQuote } from "@/components/SupportConversation";
import { AdminNotice, type AdminMessage } from "./AdminFields";

type Topic = "products" | "pricing" | "compatibility" | "customer_service";
type State = "ai" | "waiting_human" | "human" | "closed";
type Reference = { type: "product" | "accessory"; id: number; url: string; label: string };
type Message = { id: string; role: "customer" | "assistant" | "human" | "system"; text: string; createdAt: string; references: Reference[]; needsHuman?: boolean; humanReason?: string | null; answeredBy?: string | null; replyTo?: { id: string; text: string } | null };
type Contact = { name: string; email: string; revision: number; updatedAt: string };
type Conversation = { id: string; state: State; revision: number; createdAt: string; updatedAt: string; currency: string; needsHuman: boolean; needsHumanQuestions?: number; reason: string | null; processing: boolean; messages: Message[]; contact?: Contact | null };
type Summary = Omit<Conversation, "messages" | "processing"> & { lastMessage: string; messageCount: number; guestLabel: string };
type Settings = { enabled: boolean; allowedTopics: Topic[]; revision: number; provider: string; model: string; configured: boolean; environment: string; localTestingOnly: boolean };
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string";
const identifier = (value: unknown): value is string => text(value) && /^[a-zA-Z0-9_-]{1,128}$/.test(value);
const date = (value: unknown) => text(value) && Number.isFinite(Date.parse(value));
const number = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const topics = (value: unknown): value is Topic[] => Array.isArray(value) && value.every((topic) => ["products", "pricing", "compatibility", "customer_service"].includes(topic));
function validBase(value: unknown): boolean {
  return object(value) && identifier(value.id) && ["ai", "waiting_human", "human", "closed"].includes(String(value.state))
    && number(value.revision) && date(value.createdAt) && date(value.updatedAt) && text(value.currency)
    && typeof value.needsHuman === "boolean" && (value.reason === null || text(value.reason))
    && (value.needsHumanQuestions === undefined || number(value.needsHumanQuestions));
}
function validConversation(value: unknown): value is Conversation {
  return validBase(value) && object(value) && typeof value.processing === "boolean"
    && (value.contact === undefined || value.contact === null || (object(value.contact) && text(value.contact.name) && text(value.contact.email) && number(value.contact.revision) && date(value.contact.updatedAt)))
    && Array.isArray(value.messages) && value.messages.every((message) => object(message) && identifier(message.id)
      && ["customer", "assistant", "human", "system"].includes(String(message.role)) && text(message.text) && date(message.createdAt)
      && (message.needsHuman === undefined || typeof message.needsHuman === "boolean")
      && (message.humanReason === undefined || message.humanReason === null || text(message.humanReason))
      && (message.answeredBy === undefined || message.answeredBy === null || identifier(message.answeredBy))
      && (message.replyTo === undefined || message.replyTo === null || (object(message.replyTo) && identifier(message.replyTo.id) && text(message.replyTo.text)))
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
const label = (value: State) => value === "closed" ? "Closed" : "Open · Assistant available";
const button = "min-h-12 rounded-full border border-[var(--line)] bg-white px-4 py-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50";
const sourceUrl = (value: string) => /^\/(?:products|accessories)\/[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(value);
const contactEmail = (value: string) => value.length <= 254 && /^[A-Za-z0-9.!#$%&'*+/=?_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/.test(value);
const needsReply = (message: Message) => message.role === "customer" && Boolean(message.needsHuman) && !message.answeredBy;
const actionableQuestion = (conversation: Conversation, message: Message) => conversation.state !== "closed" && needsReply(message);
const answerLabel = (conversation: Conversation, question: Message) => {
  const role = conversation.messages.find((message) => message.id === question.answeredBy)?.role;
  return role === "human" ? "Answered by STYL team" : role === "assistant" ? "Answered by STYL Assistant" : "Answered";
};
const replyKey = (conversationId: string, questionId: string | null) => `${conversationId}:${questionId ?? "general"}`;
const questionCount = (count: number) => `${count} ${count === 1 ? "question needs" : "questions need"} a team reply`;

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
  const [targets, setTargets] = useState<Record<string, string | null>>({});
  const [answeredSnapshots, setAnsweredSnapshots] = useState<Record<string, string | null>>({});
  const [notice, setNotice] = useState<AdminMessage | null>(null);
  const [connectionError, setConnectionError] = useState("");
  const [accessError, setAccessError] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const initialized = useRef(false);
  const initializedTargets = useRef(new Set<string>());
  const writeController = useRef<AbortController | null>(null);
  const retries = useRef<Record<string, { id: string; text: string; replyToMessageId: string | null }>>({});
  const history = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const selected = selectedId ? threads[selectedId] : null;
  const targetId = selectedId ? targets[selectedId] ?? null : null;
  const selectedQuestion = selected?.messages.find((message) => message.id === targetId && message.role === "customer");
  const draftId = selectedId ? replyKey(selectedId, targetId) : "";
  const draft = drafts[draftId] ?? "";
  const latestAnswer = selected?.messages.find((message) => message.id === selectedQuestion?.answeredBy);
  const answerChanged = Boolean(selectedQuestion && (selectedQuestion.answeredBy ?? null) !== (answeredSnapshots[draftId] ?? null));
  const canReply = Boolean(selected && selected.state !== "closed" && (selectedQuestion || !selected.messages.some((message) => message.role === "customer")));
  const remaining = selected && selected.state !== "closed" ? selected.needsHumanQuestions ?? selected.messages.filter(needsReply).length : 0;
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
    setThreads((current) => {
      const previous = current[value.id];
      if (!previous) return { ...current, [value.id]: value };
      const latest = previous.revision >= value.revision ? previous : value;
      const contact = (previous.contact?.revision ?? 0) >= (value.contact?.revision ?? 0) ? previous.contact ?? null : value.contact ?? null;
      return latest === previous && contact === previous.contact ? current : { ...current, [value.id]: { ...latest, contact } };
    });
    if (!initializedTargets.current.has(value.id)) {
      const question = value.messages.find(needsReply) ?? value.messages.findLast((message) => message.role === "customer");
      const questionId = question?.id ?? null;
      initializedTargets.current.add(value.id);
      setAnsweredSnapshots((current) => ({ ...current, [replyKey(value.id, questionId)]: question?.answeredBy ?? null }));
      setTargets((current) => ({ ...current, [value.id]: questionId }));
    }
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
  const close = () => {
    if (!selected || accessError) return;
    if (!window.confirm("Close this conversation? The customer will need to start a new conversation.")) return;
    void perform(async (signal) => {
      try {
        receive(await request(`/conversations/${selected.id}/action`, signal, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "close", expectedRevision: selected.revision }) }), selected.id);
        await loadQueue(signal);
      } catch (value) { setConflict(selected.id); throw value; }
    });
  };
  const chooseQuestion = (question: Message) => {
    if (!selected) return;
    const key = replyKey(selected.id, question.id);
    if (!drafts[key] && !retries.current[key]) setAnsweredSnapshots((current) => ({ ...current, [key]: question.answeredBy ?? null }));
    setTargets((current) => ({ ...current, [selected.id]: question.id }));
  };
  const reviewAnswer = () => {
    if (!selectedQuestion || !answerChanged || busy || conflict === selected?.id) return;
    if (!window.confirm("Have you reviewed the latest answer? Continue with the same question and draft. If your previous reply was already saved, retrying will not send it twice.")) return;
    setAnsweredSnapshots((current) => ({ ...current, [draftId]: selectedQuestion.answeredBy ?? null }));
  };
  const send = () => {
    if (!selected || !canReply || answerChanged || accessError || conflict === selected.id || !draft.trim() || draft.length > 2000) return;
    const body = draft.trim();
    if (retries.current[draftId]?.text !== body || retries.current[draftId]?.replyToMessageId !== targetId) retries.current[draftId] = { id: crypto.randomUUID(), text: body, replyToMessageId: targetId };
    const attempt = retries.current[draftId];
    const expectedAnsweredBy = answeredSnapshots[draftId] ?? null;
    void perform(async (signal) => {
      try {
        const value = await request(`/conversations/${selected.id}/messages`, signal, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: attempt.text, clientMessageId: attempt.id, expectedRevision: selected.revision, replyToMessageId: attempt.replyToMessageId, expectedAnsweredBy }) });
        receive(value, selected.id);
        if (validConversation(value)) {
          const answeredBy = value.messages.find((message) => message.id === attempt.replyToMessageId)?.answeredBy ?? null;
          setAnsweredSnapshots((current) => ({ ...current, [draftId]: answeredBy }));
        }
        setDrafts((current) => ({ ...current, [draftId]: current[draftId]?.trim() === attempt.text ? "" : current[draftId] }));
        delete retries.current[draftId];
        setNotice({ type: "success", text: "Your reply was sent." });
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
      setNotice({ type: "success", text: "AI scope settings saved. Team replies remain available." });
    });
  };

  return <section aria-labelledby="support-inbox-title" className="min-w-0 space-y-5">
    <div className="rounded-2xl border border-[var(--line)] bg-white/80 p-5">
      <h2 id="support-inbox-title" className="text-xl font-semibold">Customer support inbox</h2>
      <p className="mt-2 text-sm leading-6">Local testing only — use synthetic messages, never personal or confidential information.</p>
      <details className="mt-2 text-sm leading-6">
        <summary className="min-h-11 cursor-pointer py-2 font-medium">Details: operator access and AI replies</summary>
        <p>Local single-operator prototype using the existing shared admin sign-in, not multi-agent staff identity or production customer support. Reply to individual customer questions while the assistant continues helping with new ones. Only closing ends the conversation.</p>
      </details>
      <button type="button" disabled={busy} onClick={refresh} className={`mt-4 ${button}`}>Refresh support inbox</button>
      {loading ? <p role="status" className="mt-3 text-sm">Loading support inbox…</p> : null}
      {connectionError ? <p role="alert" className="mt-3 rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm">Connection problem. Existing data may be stale, not empty. {connectionError}</p> : null}
      <AdminNotice message={notice} />
    </div>
    {accessError ? <p role="alert" className="rounded-xl border border-red-400 bg-red-50 p-4 text-sm">Private support content hidden because admin access was rejected. Sign out and authenticate again, or refresh after access is restored. Unsaved replies remain in memory.</p> : <>
      {settings ? <section aria-labelledby="support-settings-title" className="min-w-0 rounded-2xl border border-[var(--line)] bg-white/80 p-5">
        <h3 id="support-settings-title" className="text-lg font-semibold">Automatic AI scope</h3>
        <p className="mt-2 break-words text-sm">Provider: {settings.provider} · Model: {settings.model} · {settings.configured ? "Provider configured" : "Provider not configured"} · Environment: {settings.environment}</p>
        <p className="mt-2 text-sm text-[var(--muted)]">Provider/model are server-configured. No API keys are shown or entered here. Disabling AI keeps human support available. Chat follows the provider/model shown above; approved video processing has a separate route in Knowledge. Provider retention policies still apply. Paid API usage may apply; no automatic paid upgrade.</p>
        <fieldset disabled={busy} className="mt-4 min-w-0 space-y-2">
          <label className="flex min-h-12 items-center gap-3 text-sm"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} className="h-5 w-5" />Enable automatic AI replies</label>
          <legend className="sr-only">Allowed AI topics</legend>
          {(["products", "pricing", "compatibility", "customer_service"] as const).map((topic) => <label key={topic} className="flex min-h-12 items-center gap-3 text-sm"><input type="checkbox" checked={allowedTopics.includes(topic)} onChange={(event) => setAllowedTopics((current) => event.target.checked ? [...current, topic] : current.filter((value) => value !== topic))} className="h-5 w-5" />{({ products: "Product information", pricing: "Listed pricing", compatibility: "Documented compatibility", customer_service: "Approved customer-service Q&A" })[topic]}</label>)}
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
          <p className="mt-2 text-sm" role="status">{queue ? `${queue.needsHumanCount} conversations need team attention · ${queue.items.length} conversations` : "Conversation counts are not yet available."}</p>
          {queue?.items.length === 0 ? <p className="mt-4 text-sm">No support conversations yet.</p> : null}
          <ul className="mt-4 space-y-3">{queue?.items.map((item) => <li key={item.id}><button type="button" disabled={busy} aria-pressed={selectedId === item.id} onClick={() => { setSelectedId(item.id); nearBottom.current = true; setNotice(null); }} className={`block min-h-12 w-full min-w-0 rounded-xl border p-3 text-left text-sm ${item.needsHuman ? "border-amber-400 bg-amber-50" : "border-[var(--line)] bg-white"} ${selectedId === item.id ? "ring-2 ring-[var(--ink)]" : ""}`}>
            <span className="block break-words font-semibold">{item.guestLabel}</span>
            <span className="mt-1 block">{item.needsHuman ? `${item.needsHumanQuestions ? questionCount(item.needsHumanQuestions) : "Team help requested"} · ` : ""}{label(item.state)} · {item.currency}</span>
            <span className="mt-2 line-clamp-3 block whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{item.lastMessage || "No messages yet"}</span>
            <span className="mt-2 block text-xs">{item.messageCount} messages{Object.entries(drafts).some(([key, value]) => key.startsWith(`${item.id}:`) && value) ? " · Unsaved reply" : ""}</span>
          </button></li>)}</ul>
        </section>
        <section aria-labelledby="support-thread-title" className="min-w-0 rounded-2xl border border-[var(--line)] bg-white/80 p-4 sm:p-5">
          <h3 id="support-thread-title" className="text-lg font-semibold">Selected conversation</h3>
          {!selected ? <p className="mt-3 text-sm">{selectedId ? "Loading selected conversation…" : "Choose a conversation to review and reply."}</p> : <>
            <p role="status" className="mt-3 text-sm font-semibold">{label(selected.state)}{selected.processing ? " · AI is thinking…" : ""}</p>
            {selected.contact ? <section aria-label="Private follow-up contact" className="mt-3 rounded-xl border border-[var(--line)] p-3 text-sm">
              <h4 className="font-semibold">Follow-up contact</h4>
              <dl className="mt-2 space-y-2 break-words [overflow-wrap:anywhere]">
                <div><dt className="font-medium">Name</dt><dd>{selected.contact.name}</dd></div>
                <div><dt className="font-medium">Email address</dt><dd>{contactEmail(selected.contact.email) ? <a href={`mailto:${encodeURIComponent(selected.contact.email)}`} className="inline-flex min-h-11 items-center underline">{selected.contact.email}</a> : selected.contact.email}</dd></div>
              </dl>
              <p className="mt-2 text-xs text-[var(--muted)]">Private contact details; not included in AI context.</p>
            </section> : null}
            <p role="status" className={`mt-3 rounded-xl border p-3 text-sm ${remaining || selected.needsHuman ? "border-amber-400 bg-amber-50" : "border-[var(--line)]"}`}>{questionCount(remaining)}{!remaining && selected.needsHuman ? " · Team help requested" : ""}</p>
            <div ref={history} role="log" aria-label="Selected support messages" aria-live="polite" aria-relevant="additions" tabIndex={0} onScroll={() => { const element = history.current; if (element) nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 60; }} className="mt-4 max-h-[52vh] min-h-32 space-y-3 overflow-y-auto overscroll-contain rounded-xl border border-[var(--line)] p-3">
              {selected.messages.map((message) => <article key={message.id} id={`admin-support-message-${message.id}`} data-support-role={message.role} data-needs-team-reply={actionableQuestion(selected, message)} className={`min-w-0 rounded-xl border p-3 ${actionableQuestion(selected, message) ? "border-amber-400 bg-amber-50" : "border-transparent bg-neutral-50"} ${targetId === message.id ? "ring-2 ring-[var(--ink)]" : ""}`}>
                <p className="text-xs font-semibold">{({ customer: "Customer", assistant: "STYL Assistant", human: "STYL team", system: "Support status" })[message.role]}</p>
                {message.role === "human" && message.replyTo ? <SupportQuestionQuote question={message.replyTo} /> : null}
                <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 [overflow-wrap:anywhere]">{message.text}</p>
                {message.role === "customer" ? <div className="mt-2 flex flex-wrap items-center gap-3">
                  {actionableQuestion(selected, message) ? <span className="rounded-full border border-amber-600 px-3 py-1 text-xs font-semibold">Needs a team reply</span> : message.answeredBy ? <span className="text-xs font-semibold">{answerLabel(selected, message)}</span> : null}
                  <button type="button" disabled={busy || selected.state === "closed"} aria-pressed={targetId === message.id} onClick={() => chooseQuestion(message)} className={button}>Reply</button>
                </div> : null}
                {actionableQuestion(selected, message) && message.humanReason ? <details className="mt-2 text-xs"><summary className="min-h-11 cursor-pointer py-3">Request details</summary><p className="break-words">Reason: {message.humanReason}</p></details> : null}
                {message.references.some((reference) => sourceUrl(reference.url)) ? <details className="mt-2 text-xs text-[var(--muted)]">
                  <summary className="min-h-11 w-fit cursor-pointer py-3">Sources</summary>
                  {message.references.filter((reference) => sourceUrl(reference.url)).map((reference, position) => <Link key={`${reference.id}-${position}`} href={reference.url} className="block min-h-11 break-words py-2 text-sm underline">{reference.label}</Link>)}
                </details> : null}
              </article>)}
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" disabled={busy || selected.state === "closed" || conflict === selected.id} onClick={close} className={button}>Close conversation</button>
              <button type="button" disabled={busy} onClick={refresh} className={button}>Refresh selected conversation</button>
            </div>
            {conflict === selected.id ? <p role="alert" className="mt-3 rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm">The last write could not be confirmed. Refresh this conversation before retrying. Your reply and its retry identity are preserved; no automatic resend will occur.</p> : null}
            <form className="mt-4" onSubmit={(event) => { event.preventDefault(); send(); }}>
              {selectedQuestion ? <div role="region" aria-label="Replying to customer question" className="mb-3 rounded-xl bg-neutral-50 p-3"><SupportQuestionQuote question={selectedQuestion} /></div> : selected.messages.some((message) => message.role === "customer") ? <p className="mb-3 text-sm">Choose Reply on a customer question before sending.</p> : <p className="mb-3 text-sm">No customer question yet. You can send a welcome message.</p>}
              {answerChanged && selected.state !== "closed" ? <section aria-label="Review updated answer" className="mb-3 rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm">
                <p role="alert">This question has a newer answer. Your draft and quoted question are unchanged. Review the latest answer before continuing; refreshing alone will not send or replace a reply.</p>
                {latestAnswer ? <div className="mt-3 rounded-xl bg-white p-3"><p className="text-xs font-semibold">{latestAnswer.role === "human" ? "STYL team" : "STYL Assistant"} · Latest answer</p><p className="mt-2 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{latestAnswer.text}</p></div> : <p className="mt-2">Read the updated question and answer in the conversation above.</p>}
                <button type="button" disabled={busy || conflict === selected.id} onClick={reviewAnswer} className={`mt-3 ${button}`}>Review latest answer and continue</button>
              </section> : null}
              <label className="block text-sm font-medium">Your reply<textarea aria-label="Your reply" placeholder="Write a helpful message…" value={draft} maxLength={2000} rows={4} disabled={busy || selected.state === "closed"} onChange={(event) => setDrafts((current) => ({ ...current, [draftId]: event.target.value }))} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} className="mt-2 block w-full min-w-0 rounded-xl border border-[var(--line)] p-3 text-base" /></label>
              <p className="mt-2 text-xs leading-5 text-[var(--muted)]">{draft.length}/2000 characters. Enter to send; Shift+Enter for a new line. Drafts are kept separately for each question across admin sections.</p>
              <button type="submit" disabled={busy || !canReply || answerChanged || conflict === selected.id || !draft.trim()} className={`mt-3 ${button}`}>{busy ? "Sending…" : "Send reply"}</button>
            </form>
          </>}
        </section>
      </div>
    </>}
  </section>;
}
