"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import type { SupportPageContext } from "./SupportWidget";

type Topic = "products" | "pricing" | "compatibility" | "customer_service";
type Reference = { type: "product" | "accessory"; id: number; url: string; label: string };
type Message = { id: string; role: "customer" | "assistant" | "human" | "system"; text: string; createdAt: string; references: Reference[]; needsHuman?: boolean; humanReason?: string | null; answeredBy?: string | null; replyTo?: { id: string; text: string } | null };
type Contact = { name: string; email: string; revision: number; updatedAt: string };
type ContactDraft = { conversationId: string; name: string; email: string; expectedRevision: number };
type Conversation = { id: string; state: "ai" | "waiting_human" | "human" | "closed"; revision: number; createdAt: string; updatedAt: string; currency: string; needsHuman: boolean; needsHumanQuestions?: number; reason: string | null; processing: boolean; messages: Message[]; contact?: Contact | null };
type Config = { enabled: boolean; aiEnabled: boolean; environment: string; provider: string; model: string; allowedTopics: Topic[]; localTestingOnly: boolean; notice: string };
type Guest = { id: string; token: string };
const storageKey = "styl-support-guest";
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string";
const identifier = (value: unknown): value is string => text(value) && /^[a-zA-Z0-9_-]{1,128}$/.test(value);
const date = (value: unknown) => text(value) && Number.isFinite(Date.parse(value));
const number = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const topics = (value: unknown): value is Topic[] => Array.isArray(value) && value.every((topic) => ["products", "pricing", "compatibility", "customer_service"].includes(topic));
const sourceUrl = (value: string) => /^\/(?:products|accessories)\/[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(value);
const validContact = (value: unknown): value is Contact => object(value) && text(value.name) && text(value.email) && number(value.revision) && date(value.updatedAt);
function validConversation(value: unknown): value is Conversation {
  return object(value) && identifier(value.id) && ["ai", "waiting_human", "human", "closed"].includes(String(value.state))
    && number(value.revision) && date(value.createdAt) && date(value.updatedAt) && text(value.currency)
    && typeof value.needsHuman === "boolean" && (value.reason === null || text(value.reason)) && typeof value.processing === "boolean"
    && (value.needsHumanQuestions === undefined || number(value.needsHumanQuestions))
    && (value.contact === undefined || value.contact === null || validContact(value.contact))
    && Array.isArray(value.messages) && value.messages.every((message) => object(message) && identifier(message.id)
      && ["customer", "assistant", "human", "system"].includes(String(message.role)) && text(message.text) && date(message.createdAt)
      && (message.needsHuman === undefined || typeof message.needsHuman === "boolean")
      && (message.humanReason === undefined || message.humanReason === null || text(message.humanReason))
      && (message.answeredBy === undefined || message.answeredBy === null || identifier(message.answeredBy))
      && (message.replyTo === undefined || message.replyTo === null || (object(message.replyTo) && identifier(message.replyTo.id) && text(message.replyTo.text)))
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
const status = (conversation: Conversation) => conversation.state === "closed" ? "Conversation closed" : conversation.processing ? "Preparing a reply…" : "STYL Assistant";
const handoffConfirmation = "Your request has been sent to our team.";
const messageText = (message: Message) => message.role === "system" && message.text === "Your message is saved. Human help has been requested; AI replies are paused."
  ? handoffConfirmation : message.text;
class SupportRequestError extends Error {
  constructor(message: string, readonly status?: number) { super(message); }
}
const errorMessage = (value: unknown) => value instanceof SupportRequestError ? value.message : "We couldn't complete your request. Please try again. Your message is still here.";

export function SupportQuestionQuote({ question }: { question: { id: string; text: string } }) {
  const characters = Array.from(question.text);
  return <blockquote aria-label="Quoted customer question" data-reply-to={question.id} className="mt-2 min-w-0 border-l-2 border-current pl-3 text-sm">
    <p className="text-xs font-medium">In reply to</p>
    {characters.length > 200 ? <details className="mt-1">
      <summary className="min-h-11 cursor-pointer whitespace-pre-wrap break-words py-2 [overflow-wrap:anywhere]">{characters.slice(0, 200).join("")}… <span className="underline">Show full question</span></summary>
      <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{question.text}</p>
    </details> : <p className="mt-1 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{question.text}</p>}
  </blockquote>;
}

export default function SupportConversation({ visible, onActivity, onMinimize, pageContext, getPageContextVersion }: {
  visible: boolean;
  onActivity: (activity: { unread: number; responding: boolean }) => void;
  onMinimize: () => void;
  pageContext: SupportPageContext | null;
  getPageContextVersion: () => string;
}) {
  const [config, setConfig] = useState<Config | null>(null);
  const [guest, setGuest] = useState<Guest | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");
  const [contactDraft, setContactDraft] = useState<ContactDraft | null>(null);
  const [contactError, setContactError] = useState("");
  const [contactSaved, setContactSaved] = useState(false);
  const [savingContact, setSavingContact] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stale, setStale] = useState("");
  const [storageWarning, setStorageWarning] = useState("");
  const [invalidGuest, setInvalidGuest] = useState(false);
  const [reload, setReload] = useState(0);
  const operation = useRef<AbortController | null>(null);
  const retry = useRef<Readonly<{ text: string; id: string; itemRef?: string; pageContextVersion: string }> | null>(null);
  const history = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const [unread, setUnread] = useState(0);
  const [foreground, setForeground] = useState(true);
  const receivedMessages = useRef<{ id: string; ids: Set<string> } | null>(null);
  const unreadMessages = useRef(new Set<string>());
  const scrollPosition = useRef(0);
  const contact = conversation?.contact ?? null;
  const currentContactDraft = contactDraft?.conversationId === conversation?.id ? contactDraft : null;
  const showContactForm = Boolean(conversation && conversation.state !== "closed" && !invalidGuest && (currentContactDraft || (conversation.needsHuman && !contact)));

  const request = useCallback(async (suffix: string, signal: AbortSignal, capability?: Guest, options: RequestInit = {}) => {
    const response = await fetch(`${API_BASE}/api/support${suffix}`, {
      ...options, headers: { ...(capability ? { Authorization: `Bearer ${capability.token}` } : {}), ...options.headers },
      cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal,
    }).catch(() => { throw new SupportRequestError("Connection lost. Check your connection and try again. Your message is still here."); });
    if (!response.ok) {
      if (response.status === 404 && capability) {
        setInvalidGuest(true);
        throw new SupportRequestError("This conversation is no longer available. Start a new conversation or contact STYL.");
      }
      if (response.status === 429) throw new SupportRequestError("Too many requests. Please wait a moment and try again. Your message is still here.");
      if (suffix.endsWith("/contact")) throw new SupportRequestError(response.status === 409
        ? "Contact details have changed. Review your details and try again."
        : response.status === 413 || response.status === 422
          ? "Please enter your name and a valid email address, then try again."
          : "We couldn't save your contact details. Please try again. Your details are still here.", response.status);
      if (response.status === 413 || response.status === 422) throw new SupportRequestError("Please check your message and keep it within 2,000 characters, then try again.");
      if (response.status === 409) throw new SupportRequestError("This conversation has changed. Please try again. Your message is still here.");
      throw new SupportRequestError("We couldn't complete your request. Please try again. Your message is still here.");
    }
    return response.json() as Promise<unknown>;
  }, []);

  const receive = useCallback((value: unknown, expectedId: string) => {
    if (!validConversation(value) || value.id !== expectedId) throw new SupportRequestError("We couldn't update this conversation. Please try again. Your message is still here.");
    setConversation((current) => {
      if (!current || current.id !== value.id) return { ...value, contact: value.contact ?? null };
      const latest = current.revision >= value.revision ? current : value;
      // Contact saves and AI replies advance independent revisions and can arrive out of order.
      const latestContact = (current.contact?.revision ?? 0) >= (value.contact?.revision ?? 0) ? current.contact ?? null : value.contact ?? null;
      return latest === current && latestContact === current.contact ? current : { ...latest, contact: latestContact };
    });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function initialize() {
      setLoading(true); setError("");
      try {
        const value = await request("/config", controller.signal);
        if (!validConfig(value)) throw new SupportRequestError("Chat is unavailable right now. Please try again or contact STYL.");
        if (controller.signal.aborted) return;
        setConfig(value);
        if (!value.enabled) return;
        let saved: Guest | null = null;
        try {
          const serialized = window.localStorage.getItem(storageKey);
          if (serialized) {
            const parsed: unknown = JSON.parse(serialized);
            if (validGuest(parsed)) saved = parsed;
            else setStorageWarning("We couldn't reopen your saved conversation. Please start a new conversation.");
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
        if (!controller.signal.aborted) setError(errorMessage(value));
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
        if (!stopped && !active.signal.aborted) setStale(errorMessage(value));
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
    if (!element || !conversation) return;
    if (receivedMessages.current?.id !== conversation.id) {
      receivedMessages.current = { id: conversation.id, ids: new Set(conversation.messages.map((message) => message.id)) };
      unreadMessages.current.clear();
      nearBottom.current = true;
    } else {
      for (const message of conversation.messages) {
        if (!receivedMessages.current.ids.has(message.id) && message.role !== "customer") unreadMessages.current.add(message.id);
        receivedMessages.current.ids.add(message.id);
      }
    }
    if (visible && foreground) {
      if (nearBottom.current) {
        element.scrollTop = element.scrollHeight;
        unreadMessages.current.clear();
      } else element.scrollTop = scrollPosition.current;
    }
    const notify = window.setTimeout(() => setUnread(unreadMessages.current.size), 0);
    return () => window.clearTimeout(notify);
  }, [conversation, visible, foreground]);
  useEffect(() => {
    const visibility = () => setForeground(document.visibilityState === "visible");
    visibility();
    document.addEventListener("visibilitychange", visibility);
    return () => document.removeEventListener("visibilitychange", visibility);
  }, []);
  useEffect(() => {
    onActivity({ unread, responding: Boolean(conversation?.processing) });
  }, [unread, conversation?.processing, onActivity]);
  useEffect(() => () => { operation.current?.abort(); }, []);
  useEffect(() => {
    if (!draft && !currentContactDraft && !busy && !(guest && storageWarning)) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [draft, currentContactDraft, busy, guest, storageWarning]);

  const perform = async (action: (signal: AbortSignal) => Promise<void>) => {
    if (operation.current) return;
    const controller = new AbortController();
    operation.current = controller; setBusy(true); setError("");
    try { await action(controller.signal); }
    catch (value) { if (!controller.signal.aborted) setError(errorMessage(value)); }
    finally { operation.current = null; if (!controller.signal.aborted) setBusy(false); }
  };

  const start = () => void perform(async (signal) => {
    const value = await request("/conversations", signal, undefined, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!object(value) || !validConversation(value.conversation) || !validGuest({ id: value.conversation.id, token: value.token })) throw new SupportRequestError("We couldn't start your conversation. Please try again or contact STYL.");
    const capability = { id: value.conversation.id, token: value.token as string };
    setGuest(capability); setConversation(value.conversation); setInvalidGuest(false); setDraft(""); retry.current = null; setStale("");
    setContactDraft(null); setContactError(""); setContactSaved(false);
    nearBottom.current = true;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(capability));
      setStorageWarning("");
    } catch {
      setStorageWarning("This conversation is open in this tab, but guest access could not be saved. Do not reload or close this tab: you may lose access. Browser storage must be enabled for reliable resume.");
    }
  });

  const send = () => {
    if (operation.current || !guest || !conversation || conversation.state === "closed" || conversation.processing || invalidGuest || !draft.trim() || draft.length > 2000) return;
    const body = draft.trim();
    if (retry.current?.text !== body) retry.current = {
      text: body, id: crypto.randomUUID(), pageContextVersion: getPageContextVersion(),
      ...(pageContext ? { itemRef: `${pageContext.itemType}:${pageContext.id}` } : {}),
    };
    const attempt = retry.current;
    void perform(async (signal) => {
      const value = await request(`/conversations/${guest.id}/messages`, signal, guest, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: attempt.text, clientMessageId: attempt.id, pageContextVersion: attempt.pageContextVersion, ...(attempt.itemRef ? { itemRef: attempt.itemRef } : {}) }) });
      receive(value, guest.id);
      setDraft((current) => current.trim() === attempt.text ? "" : current); retry.current = null;
    });
  };
  const refresh = () => {
    if (!guest) { setReload((value) => value + 1); return; }
    void perform(async (signal) => {
      receive(await request(`/conversations/${guest.id}`, signal, guest), guest.id);
      setStale(""); setInvalidGuest(false);
    });
  };
  const editContact = (changes: Partial<Pick<ContactDraft, "name" | "email">> = {}) => {
    if (!conversation) return;
    setContactSaved(false);
    setContactDraft({ ...(currentContactDraft ?? { conversationId: conversation.id, name: contact?.name ?? "", email: contact?.email ?? "", expectedRevision: contact?.revision ?? 0 }), ...changes });
  };
  const saveContact = async () => {
    if (operation.current || !guest || !conversation || conversation.state === "closed" || invalidGuest || !currentContactDraft) return;
    const submitted = currentContactDraft;
    if (!submitted.name.trim() || !submitted.email.trim()) { setContactError("Please enter your name and a valid email address, then try again."); return; }
    const controller = new AbortController();
    operation.current = controller; setBusy(true); setSavingContact(true); setContactError(""); setContactSaved(false);
    try {
      const value = await request(`/conversations/${guest.id}/contact`, controller.signal, guest, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: submitted.name.trim(), email: submitted.email.trim(), expectedRevision: submitted.expectedRevision }),
      });
      if (!validConversation(value) || !value.contact) throw new SupportRequestError("We couldn't confirm your contact details. Please try again. Your details are still here.");
      receive(value, guest.id);
      setContactDraft(null); setContactSaved(true);
    } catch (value) {
      if (!controller.signal.aborted) {
        setContactError(value instanceof SupportRequestError && value.status
          ? value.message : "We couldn't save your contact details. Please try again. Your details are still here.");
        if (value instanceof SupportRequestError && value.status === 409) {
          try {
            const latest = await request(`/conversations/${guest.id}`, controller.signal, guest);
            receive(latest, guest.id);
            if (validConversation(latest)) setContactDraft((current) => current?.conversationId === guest.id ? { ...current, expectedRevision: latest.contact?.revision ?? 0 } : current);
          } catch { /* Keep the draft and its revision until the connection recovers. */ }
        }
      }
    } finally {
      operation.current = null;
      if (!controller.signal.aborted) { setBusy(false); setSavingContact(false); }
    }
  };

  return <div className="support-content">
      <div className="support-links"><Link href="/privacy" onClick={onMinimize} className="inline-flex min-h-11 items-center underline">Privacy</Link><Link href="/#contact" onClick={onMinimize} className="inline-flex min-h-11 items-center underline">Contact STYL instead</Link><Link href="/" onClick={onMinimize} className="inline-flex min-h-11 items-center underline">Continue shopping</Link></div>
      {pageContext ? <p aria-label="Current page item" className="mt-2 max-w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-xs [overflow-wrap:anywhere]">About: {pageContext.name}</p> : null}
      {storageWarning ? <p role="alert" className="mt-4 rounded-xl border border-amber-400 bg-amber-50 p-4 text-sm">{storageWarning}</p> : null}
      {error ? <p role="alert" className="mt-4 rounded-xl border border-red-300 bg-red-50 p-4 text-sm">{error}</p> : null}
      {stale ? <p role="alert" className="mt-4 rounded-xl border border-amber-400 bg-amber-50 p-4 text-sm">Messages may not be up to date. {stale}</p> : null}
      {(error || stale) && config?.enabled && guest && !invalidGuest ? <button type="button" disabled={busy} onClick={refresh} className={`mt-2 ${button}`}>Retry support connection</button> : null}
      {loading ? <p role="status" className="mt-4">Loading support…</p> : !config?.enabled ? <div className="mt-5 rounded-2xl border border-[var(--line)] bg-white p-5"><h2 className="text-xl font-semibold">Support chat is unavailable</h2><p className="mt-2 text-sm">Shopping, your cart, and the inquiry form remain available.</p><button type="button" onClick={() => setReload((value) => value + 1)} className={`mt-4 ${button}`}>Retry support connection</button></div> : <>
        {!config.aiEnabled ? <p role="status" className="mt-4 text-sm">The STYL Assistant is unavailable right now. You can still leave a question for our team or contact STYL.</p> : null}
        {!guest || invalidGuest ? <button type="button" disabled={busy} onClick={start} className={`mt-5 ${button} !bg-[var(--ink)] text-white`}>{busy ? "Starting…" : invalidGuest ? "New conversation" : "Start conversation"}</button> : null}
        {conversation ? <section className="support-conversation" aria-labelledby="conversation-title">
          <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="conversation-title" className="text-xl font-semibold">Your conversation</h2><p role="status" className="text-sm font-medium">{status(conversation)}</p></div>
          {conversation.needsHuman && conversation.state !== "closed" ? <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm"><span>{handoffConfirmation}</span> You can keep asking questions.</p> : null}
          <div ref={history} role="log" aria-label="Conversation messages" aria-live={visible ? "polite" : "off"} aria-relevant="additions" tabIndex={0} onScroll={() => {
            const element = history.current;
            if (element && visible && foreground) {
              scrollPosition.current = element.scrollTop;
              nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 60;
              if (nearBottom.current) { unreadMessages.current.clear(); setUnread(0); }
            }
          }} className="support-history">
            {conversation.messages.length ? conversation.messages.map((message) => <article key={message.id} id={`support-message-${message.id}`} data-support-role={message.role} className={`support-message support-message-${message.role}`}>
              <p className="text-xs font-semibold">{message.role === "assistant" ? "STYL Assistant" : message.role === "human" ? "STYL team" : message.role === "customer" ? "You" : "Support status"}</p>
              {message.role === "human" && message.replyTo ? <SupportQuestionQuote question={message.replyTo} /> : null}
              <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 [overflow-wrap:anywhere]">{messageText(message)}</p>
              {message.references.some((reference) => sourceUrl(reference.url)) ? <details className="mt-2 text-xs text-[var(--muted)]">
                <summary className="min-h-11 w-fit cursor-pointer py-3">Sources</summary>
                {message.references.filter((reference) => sourceUrl(reference.url)).map((reference, index) => <Link key={`${reference.type}-${reference.id}-${index}`} href={reference.url} className="block min-h-11 break-words py-2 text-sm underline">{reference.label}</Link>)}
              </details> : null}
            </article>) : <p className="text-sm text-[var(--muted)]">How can we help you today?</p>}
          </div>
          {unread ? <button type="button" className={button} onClick={() => { if (history.current) history.current.scrollTop = history.current.scrollHeight; nearBottom.current = true; unreadMessages.current.clear(); setUnread(0); }}>Jump to latest messages</button> : null}
          {conversation.state === "closed" ? <div className="mt-4"><p className="text-sm">This conversation is closed. You can still read it here. Starting a new conversation replaces this browser&apos;s saved access.</p><button type="button" disabled={busy} onClick={start} className={`mt-3 ${button}`}>New conversation</button></div> : <form className="support-composer" onSubmit={(event) => { event.preventDefault(); send(); }}>
            <label className="block text-sm font-medium">Your message
              <textarea aria-label="Your message" value={draft} maxLength={2000} rows={2} readOnly={busy} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); }
              }} className="mt-2 block w-full min-w-0 rounded-xl border border-[var(--line)] p-3 text-base" placeholder="Ask about our products..." />
            </label>
            <p className="mt-2 text-xs text-[var(--muted)]">{draft.length}/2000 characters · Enter to send; Shift+Enter for a new line.</p>
            <button type="submit" disabled={busy || invalidGuest || conversation.processing || !draft.trim()} className={`mt-3 ${button} !bg-[var(--ink)] text-white`}>{busy && !savingContact ? "Sending…" : "Send message"}</button>
          </form>}
          {showContactForm ? <form aria-label="Follow-up contact details" className="support-contact-form mt-4 border-t border-[var(--line)] pt-3" onSubmit={(event) => { event.preventDefault(); void saveContact(); }}>
            <p className="text-sm">If you&apos;d like our team to follow up, you can share your name and email. This is optional; you can keep chatting without sharing them.</p>
            <label className="mt-3 block text-sm font-medium">Your name
              <input name="name" autoComplete="name" value={currentContactDraft?.name ?? ""} maxLength={120} required readOnly={busy} onChange={(event) => editContact({ name: event.target.value })} className="mt-1 block min-h-11 w-full min-w-0 rounded-xl border border-[var(--line)] p-2 text-base" />
            </label>
            <label className="mt-3 block text-sm font-medium">Email address
              <input name="email" type="email" autoComplete="email" value={currentContactDraft?.email ?? ""} maxLength={254} required readOnly={busy} onChange={(event) => editContact({ email: event.target.value })} className="mt-1 block min-h-11 w-full min-w-0 rounded-xl border border-[var(--line)] p-2 text-base" />
            </label>
            <p className="mt-2 text-xs text-[var(--muted)]">These details are private to our team and are not sent to the AI.</p>
            {contactError ? <p role="alert" className="mt-2 text-sm">{contactError}</p> : null}
            <button type="submit" disabled={busy} className={`mt-3 ${button}`}>{savingContact ? "Saving…" : "Share contact details"}</button>
            {contact ? <button type="button" disabled={busy} onClick={() => { setContactDraft(null); setContactError(""); }} className="ml-3 min-h-11 text-xs underline">Cancel contact edit</button> : null}
          </form> : null}
          {contactSaved ? <p role="status" className="mt-3 text-sm">Thank you. Our team can follow up using these details.</p> : null}
          {contact && !showContactForm && conversation.state !== "closed" && !invalidGuest ? <button type="button" disabled={busy} onClick={() => editContact()} className="mt-2 min-h-11 text-xs underline">Edit contact details</button> : null}
        </section> : null}
      </>}
  </div>;
}
