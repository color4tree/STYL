"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import StoreHeader from "@/components/StoreHeader";
import { API_BASE } from "@/lib/api";
import { useCart } from "@/lib/useCart";
import { getCartCount } from "@/lib/cart";

type Topic = "products" | "pricing" | "compatibility";
type Reference = { type: "product" | "accessory"; id: number; url: string; label: string };
type Message = { id: string; role: "customer" | "assistant" | "human" | "system"; text: string; createdAt: string; references: Reference[] };
type Conversation = { id: string; state: "ai" | "waiting_human" | "human" | "closed"; revision: number; createdAt: string; updatedAt: string; currency: string; needsHuman: boolean; reason: string | null; processing: boolean; messages: Message[] };
type Config = { enabled: boolean; aiEnabled: boolean; environment: string; provider: string; model: string; allowedTopics: Topic[]; localTestingOnly: boolean; notice: string };
type Guest = { id: string; token: string };
const storageKey = "styl-support-guest";
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string";
const identifier = (value: unknown): value is string => text(value) && /^[a-zA-Z0-9_-]{1,128}$/.test(value);
const date = (value: unknown) => text(value) && Number.isFinite(Date.parse(value));
const number = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const topics = (value: unknown): value is Topic[] => Array.isArray(value) && value.every((topic) => ["products", "pricing", "compatibility"].includes(topic));
const sourceUrl = (value: string) => /^\/(?:products|accessories)\/[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(value);
function validConversation(value: unknown): value is Conversation {
  return object(value) && identifier(value.id) && ["ai", "waiting_human", "human", "closed"].includes(String(value.state))
    && number(value.revision) && date(value.createdAt) && date(value.updatedAt) && text(value.currency)
    && typeof value.needsHuman === "boolean" && (value.reason === null || text(value.reason)) && typeof value.processing === "boolean"
    && Array.isArray(value.messages) && value.messages.every((message) => object(message) && identifier(message.id)
      && ["customer", "assistant", "human", "system"].includes(String(message.role)) && text(message.text) && date(message.createdAt)
      && Array.isArray(message.references) && message.references.every((reference) => object(reference)
        && ["product", "accessory"].includes(String(reference.type)) && number(reference.id) && text(reference.url) && text(reference.label)));
}
function validConfig(value: unknown): value is Config {
  return object(value) && typeof value.enabled === "boolean" && typeof value.aiEnabled === "boolean"
    && ["environment", "provider", "model", "notice"].every((key) => text(value[key])) && topics(value.allowedTopics) && typeof value.localTestingOnly === "boolean";
}
function validGuest(value: unknown): value is Guest {
  return object(value) && identifier(value.id) && text(value.token) && /^[a-zA-Z0-9_.~-]{20,512}$/.test(value.token);
}
const button = "inline-flex min-h-12 items-center justify-center rounded-full border border-[var(--line)] bg-white px-5 py-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50";
const status = (conversation: Conversation) => conversation.state === "closed" ? "Conversation closed" : conversation.state === "human" ? "Human operator joined" : conversation.state === "waiting_human" ? "Waiting for human help" : conversation.processing ? "AI is thinking…" : "AI assistance";

export default function SupportPage() {
  const { cart } = useCart();
  const [config, setConfig] = useState<Config | null>(null);
  const [guest, setGuest] = useState<Guest | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stale, setStale] = useState("");
  const [storageWarning, setStorageWarning] = useState("");
  const [invalidGuest, setInvalidGuest] = useState(false);
  const [reload, setReload] = useState(0);
  const operation = useRef<AbortController | null>(null);
  const retry = useRef<{ text: string; id: string } | null>(null);
  const history = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const [newMessages, setNewMessages] = useState(false);

  const request = useCallback(async (suffix: string, signal: AbortSignal, capability?: Guest, options: RequestInit = {}) => {
    const response = await fetch(`${API_BASE}/api/support${suffix}`, {
      ...options, headers: { ...(capability ? { Authorization: `Bearer ${capability.token}` } : {}), ...options.headers },
      cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal,
    });
    if (!response.ok) {
      let detail = `Support request failed (HTTP ${response.status}). Your message has not been cleared. Please retry.`;
      try { const value: unknown = await response.json(); if (object(value) && text(value.detail)) detail = value.detail; } catch { /* Retain the safe HTTP fallback. */ }
      if (response.status === 404 && capability) {
        setInvalidGuest(true);
        throw new Error("This private conversation cannot be accessed. It may no longer be available. Start a new guest conversation or use the contact link.");
      }
      throw new Error(capability ? detail.replaceAll(capability.token, "[redacted]") : detail);
    }
    return response.json() as Promise<unknown>;
  }, []);

  const receive = useCallback((value: unknown, expectedId: string) => {
    if (!validConversation(value) || value.id !== expectedId) throw new Error("The support response is invalid. Your draft is preserved; refresh the conversation.");
    setConversation((current) => current?.id === value.id && current.revision >= value.revision ? current : value);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function initialize() {
      setLoading(true); setError("");
      try {
        const value = await request("/config", controller.signal);
        if (!validConfig(value)) throw new Error("Support configuration is invalid. Please retry or use the contact link.");
        if (controller.signal.aborted) return;
        setConfig(value);
        if (!value.enabled) return;
        let saved: Guest | null = null;
        try {
          const serialized = window.localStorage.getItem(storageKey);
          if (serialized) {
            const parsed: unknown = JSON.parse(serialized);
            if (validGuest(parsed)) saved = parsed;
            else setStorageWarning("Saved guest access is invalid. Start a new conversation; do not paste access credentials into messages.");
          }
        } catch {
          setStorageWarning("Browser storage is unavailable. A new conversation can work in this tab, but cannot reliably resume after reload or closing the tab.");
        }
        if (saved) {
          setGuest(saved);
          const thread = await request(`/conversations/${saved.id}`, controller.signal, saved);
          if (!controller.signal.aborted) { receive(thread, saved.id); setInvalidGuest(false); }
        }
      } catch (value) {
        if (!controller.signal.aborted) setError(value instanceof Error ? value.message : "Support is unavailable. Please retry.");
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void initialize();
    return () => controller.abort();
  }, [reload, receive, request]);

  useEffect(() => {
    if (!config?.enabled || !guest || invalidGuest || conversation?.state === "closed") return;
    let stopped = false;
    let timer: number | undefined;
    let controller: AbortController | null = null;
    const poll = async () => {
      if (stopped || document.visibilityState !== "visible" || controller) return;
      controller = new AbortController();
      const active = controller;
      try {
        const value = await request(`/conversations/${guest.id}`, active.signal, guest);
        if (!stopped) {
          receive(value, guest.id);
          setStale("");
          if (validConversation(value) && value.state === "closed") {
            stopped = true;
            window.clearTimeout(timer);
          }
        }
      } catch (value) {
        if (!stopped && !active.signal.aborted) setStale(value instanceof Error ? value.message : "Connection lost. Displayed conversation may be stale.");
      } finally {
        controller = null;
        if (!stopped && document.visibilityState === "visible") timer = window.setTimeout(poll, 2000);
      }
    };
    const visibility = () => {
      window.clearTimeout(timer);
      if (document.visibilityState === "visible") void poll();
      else controller?.abort();
    };
    if (document.visibilityState === "visible") timer = window.setTimeout(poll, 2000);
    document.addEventListener("visibilitychange", visibility);
    return () => { stopped = true; window.clearTimeout(timer); controller?.abort(); document.removeEventListener("visibilitychange", visibility); };
  }, [config?.enabled, guest, invalidGuest, conversation?.state, receive, request]);

  useEffect(() => {
    const element = history.current;
    if (!element) return;
    if (nearBottom.current) element.scrollTop = element.scrollHeight;
    else {
      const notify = window.setTimeout(() => setNewMessages(true), 0);
      return () => window.clearTimeout(notify);
    }
  }, [conversation?.messages.length]);
  useEffect(() => () => { operation.current?.abort(); }, []);
  useEffect(() => {
    if (!draft && !busy && !(guest && storageWarning)) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [draft, busy, guest, storageWarning]);

  const perform = async (action: (signal: AbortSignal) => Promise<void>) => {
    if (operation.current) return;
    const controller = new AbortController();
    operation.current = controller; setBusy(true); setError("");
    try { await action(controller.signal); }
    catch (value) { if (!controller.signal.aborted) setError(value instanceof Error ? value.message : "Unable to complete support request. Your draft is preserved."); }
    finally { operation.current = null; if (!controller.signal.aborted) setBusy(false); }
  };

  const start = () => void perform(async (signal) => {
    const value = await request("/conversations", signal, undefined, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!object(value) || !validConversation(value.conversation) || !validGuest({ id: value.conversation.id, token: value.token })) throw new Error("Unable to confirm guest access. Please retry or use the contact link.");
    const capability = { id: value.conversation.id, token: value.token as string };
    setGuest(capability); setConversation(value.conversation); setInvalidGuest(false); setDraft(""); retry.current = null; setStale("");
    nearBottom.current = true;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(capability));
      setStorageWarning("");
    } catch {
      setStorageWarning("This conversation is open in this tab, but guest access could not be saved. Do not reload or close this tab: you may lose access. Browser storage must be enabled for reliable resume.");
    }
  });

  const send = () => {
    if (!guest || !conversation || conversation.state === "closed" || conversation.processing || invalidGuest || !draft.trim() || draft.length > 2000) return;
    const body = draft.trim();
    if (retry.current?.text !== body) retry.current = { text: body, id: crypto.randomUUID() };
    const attempt = retry.current;
    void perform(async (signal) => {
      const value = await request(`/conversations/${guest.id}/messages`, signal, guest, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: attempt.text, clientMessageId: attempt.id }) });
      receive(value, guest.id);
      setDraft((current) => current.trim() === attempt.text ? "" : current); retry.current = null;
    });
  };
  const handoff = () => {
    if (!guest || conversation?.state === "closed" || invalidGuest) return;
    void perform(async (signal) => receive(await request(`/conversations/${guest.id}/handoff`, signal, guest, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }), guest.id));
  };
  const refresh = () => {
    if (!guest) { setReload((value) => value + 1); return; }
    void perform(async (signal) => {
      receive(await request(`/conversations/${guest.id}`, signal, guest), guest.id);
      setStale(""); setInvalidGuest(false);
    });
  };

  return <>
    <StoreHeader cartCount={getCartCount(cart)} />
    <main className="container max-w-4xl py-8 sm:py-12">
      <h1 className="text-3xl font-semibold">Ask STYL</h1>
      <p className="mt-3 text-sm leading-6 text-[var(--muted)]">Guest support — no account required. AI answers are labeled; a human operator joins only after taking over the conversation.</p>
      <aside className="mt-5 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950" aria-label="Local testing notice">
        <p className="font-semibold">Local prototype · synthetic testing only</p>
        <p>Do not enter personal, confidential, payment, health, or customer information. Messages may be sent to an AI provider. Gemini free-tier input/output may be used to improve its services or reviewed by people. This is not a production customer-service channel.</p>
        {config?.notice ? <p className="mt-2">{config.notice}</p> : null}
      </aside>
      <p className="mt-4 text-sm">Approved AI scope: {config?.allowedTopics.length ? config.allowedTopics.join(", ") : "Not available"}. Missing evidence, topics outside this scope, and requests for a person are routed to human help. No response time is promised.</p>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-sm"><Link href="/#contact" className="inline-flex min-h-12 items-center underline">Contact STYL instead</Link><Link href="/" className="inline-flex min-h-12 items-center underline">Continue shopping</Link></div>
      {storageWarning ? <p role="alert" className="mt-4 rounded-xl border border-amber-400 bg-amber-50 p-4 text-sm">{storageWarning}</p> : null}
      {error ? <p role="alert" className="mt-4 rounded-xl border border-red-300 bg-red-50 p-4 text-sm">{error}</p> : null}
      {stale ? <p role="alert" className="mt-4 rounded-xl border border-amber-400 bg-amber-50 p-4 text-sm">Connection problem; displayed messages may be stale. {stale}</p> : null}
      {loading ? <p role="status" className="mt-4">Loading support…</p> : !config?.enabled ? <div className="mt-5 rounded-2xl border border-[var(--line)] bg-white p-5"><h2 className="text-xl font-semibold">Support chat is unavailable</h2><p className="mt-2 text-sm">Shopping, your cart, and the inquiry form remain available.</p><button type="button" onClick={() => setReload((value) => value + 1)} className={`mt-4 ${button}`}>Retry support connection</button></div> : <>
        {!config.aiEnabled ? <p role="status" className="mt-4 text-sm">Automatic AI replies are off. You can still request human help or use Contact STYL instead.</p> : null}
        {!guest || invalidGuest ? <button type="button" disabled={busy} onClick={start} className={`mt-5 ${button} !bg-[var(--ink)] text-white`}>{busy ? "Starting…" : invalidGuest ? "Start a new guest conversation" : "Start guest conversation"}</button> : null}
        {conversation && !invalidGuest ? <section className="mt-5 min-w-0 rounded-2xl border border-[var(--line)] bg-white p-4 sm:p-6" aria-labelledby="conversation-title">
          <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="conversation-title" className="text-xl font-semibold">Your conversation</h2><p role="status" className="text-sm font-medium">{status(conversation)}</p></div>
          <p className="mt-2 text-xs leading-5 text-[var(--muted)]">Your browser stores private guest access for resume. Anyone using this browser profile could reopen this conversation. Clearing browser storage loses guest access. Market: {conversation.currency}.</p>
          {conversation.needsHuman ? <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm">Human help has been requested. {conversation.reason ? `Reason: ${conversation.reason}. ` : ""}You can leave a synthetic follow-up; no wait-time estimate is available.</p> : null}
          <div ref={history} role="log" aria-label="Conversation messages" aria-live="polite" aria-relevant="additions" tabIndex={0} onScroll={() => {
            const element = history.current;
            if (element) { nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 60; if (nearBottom.current) setNewMessages(false); }
          }} className="mt-4 max-h-[52vh] min-h-32 space-y-3 overflow-y-auto overscroll-contain rounded-xl border border-[var(--line)] p-3">
            {conversation.messages.length ? conversation.messages.map((message) => <article key={message.id} className={`min-w-0 rounded-xl p-3 ${message.role === "customer" ? "bg-neutral-100" : "border border-[var(--line)]"}`}>
              <p className="text-xs font-semibold">{message.role === "assistant" ? "STYL AI" : message.role === "human" ? "STYL human operator" : message.role === "customer" ? "You" : "Support status"}</p>
              <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 [overflow-wrap:anywhere]">{message.text}</p>
              {message.references.filter((reference) => sourceUrl(reference.url)).map((reference, index) => <Link key={`${reference.type}-${reference.id}-${index}`} href={reference.url} className="mt-2 block min-h-11 break-words py-2 text-sm underline">{reference.label}</Link>)}
            </article>) : <p className="text-sm text-[var(--muted)]">Ask about a named catalog item, its listed price, or documented compatibility.</p>}
          </div>
          {newMessages ? <button type="button" className={`mt-2 ${button}`} onClick={() => { if (history.current) history.current.scrollTop = history.current.scrollHeight; nearBottom.current = true; setNewMessages(false); }}>Jump to latest messages</button> : null}
          <div className="mt-4 flex flex-wrap gap-3"><button type="button" disabled={busy || conversation.state === "closed"} onClick={handoff} className={button}>Ask for human help</button><button type="button" disabled={busy} onClick={refresh} className={button}>Refresh conversation</button></div>
          {conversation.state === "closed" ? <div className="mt-4"><p className="text-sm">This conversation is closed and remains read-only. Starting a new conversation replaces this browser&apos;s saved guest access.</p><button type="button" disabled={busy} onClick={start} className={`mt-3 ${button}`}>Start a new guest conversation</button></div> : <form className="mt-5" onSubmit={(event) => { event.preventDefault(); send(); }}>
            <label className="block text-sm font-medium">Your message
              <textarea aria-label="Your message" value={draft} maxLength={2000} rows={4} disabled={busy} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); }
              }} className="mt-2 block w-full min-w-0 rounded-xl border border-[var(--line)] p-3 text-base" placeholder="Synthetic questions only; no personal information." />
            </label>
            <p className="mt-2 text-xs text-[var(--muted)]">{draft.length}/2000 characters · Enter to send; Shift+Enter for a new line.</p>
            <button type="submit" disabled={busy || conversation.processing || !draft.trim()} className={`mt-3 ${button} !bg-[var(--ink)] text-white`}>{busy ? "Sending…" : "Send message"}</button>
          </form>}
        </section> : guest && !invalidGuest ? <button type="button" disabled={busy} onClick={refresh} className={`mt-4 ${button}`}>Refresh conversation</button> : null}
      </>}
    </main>
  </>;
}
