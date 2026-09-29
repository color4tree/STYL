"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { formatCartSummary, readCart, reconcileCart, writeCart } from "@/lib/cart";
import { fetchCatalogSelection } from "@/lib/catalogSelection";
import { analyticsPageEvent, getQuoteAnalyticsSource, trackAnalytics } from "@/lib/analytics";

const emptyInquiry = { name: "", email: "", phone: "", company: "", message: "" };
const quoteSource = () => {
  const quote = new URLSearchParams(window.location.search).get("quote");
  return getQuoteAnalyticsSource(quote === "cart" || quote === "product" ? quote : "direct");
};

export default function InquiryForm() {
  const [inquiry, setInquiry] = useState(emptyInquiry);
  const [pending, setPending] = useState(false);
  const submitting = useRef(false);
  const [status, setStatus] = useState<{ error: boolean; text: string } | null>(null);
  const messageRef = useRef<HTMLParagraphElement>(null);
  const invalidAttempt = useRef(0);
  const formStarted = () => { analyticsPageEvent("quote_form_start", { source: quoteSource() }); };
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    void Promise.resolve().then(async () => {
      const params = new URLSearchParams(window.location.search);
      try {
        let selection = "";
        if (params.get("quote") === "cart") {
          const { items } = await fetchCatalogSelection(controller.signal);
          if (!active) return;
          const previous = readCart();
          const current = reconcileCart(previous, items);
          if (JSON.stringify(previous) !== JSON.stringify(current)) writeCart(current);
          selection = formatCartSummary(current);
        }
        const message = params.get("quote") === "cart"
          ? `${selection}\n\nPlease share final pricing and delivery details.`
          : params.get("quote") === "product" && params.get("product")
            ? `Interested in:\n\n1. ${params.get("product")}\n\nPlease share options, pricing, and lead time.`
            : "";
        if (active && message) setInquiry((current) => current.message ? current : { ...current, message });
      } catch (error) {
        trackAnalytics("quote_error", { source: quoteSource(), errorCode: "catalog" });
        if (active) setStatus({ error: true, text: error instanceof Error ? error.message : "Unable to load your selection." });
      }
    });
    return () => { active = false; controller.abort(); };
  }, []);
  useEffect(() => { if (status?.error) messageRef.current?.focus(); }, [status]);
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting.current) return;
    formStarted();
    trackAnalytics("quote_submit_attempt", { source: quoteSource() });
    if (!inquiry.name.trim() || !inquiry.message.trim()) {
      trackAnalytics("quote_error", { source: quoteSource(), errorCode: "validation" });
      setStatus({ error: true, text: "Enter your name and a message before submitting." });
      return;
    }
    submitting.current = true;
    setPending(true);
    setStatus(null);
    let errorCode: "validation" | "network" | "unknown" = "network";
    try {
      const response = await fetch(`${API_BASE}/api/inquiries`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...inquiry, source: "website" }),
      });
      if (!response.ok) {
        errorCode = response.status < 500 ? "validation" : "unknown";
        const data = await response.json();
        throw new Error(typeof data.detail === "string" ? data.detail : "Please check your fields and try again.");
      }
      setStatus({ error: false, text: "Inquiry received. Your request has been saved. No payment has been collected." });
      setInquiry(emptyInquiry);
    } catch (error) {
      trackAnalytics("quote_error", { source: quoteSource(), errorCode });
      console.error("Inquiry submission failed", error);
      setStatus({ error: true, text: `Unable to confirm receipt. Your entries are retained. ${error instanceof Error ? error.message : "Please try again."}` });
    } finally { submitting.current = false; setPending(false); }
  };
  return (
    <section id="contact" className="soft-panel scroll-mt-32 rounded-3xl p-5 md:p-8 lg:scroll-mt-24">
      <h2 className="text-2xl font-semibold">Request a quote</h2>
      <p className="mt-3 text-sm leading-6 text-[var(--muted)]">Tell us about your selection and training space. No payment is collected here.</p>
      <form onSubmit={submit} onChange={formStarted} onInvalidCapture={() => {
        if (Date.now() - invalidAttempt.current < 200) return;
        invalidAttempt.current = Date.now();
        formStarted();
        trackAnalytics("quote_submit_attempt", { source: quoteSource() });
        trackAnalytics("quote_error", { source: quoteSource(), errorCode: "validation" });
      }} className="mt-5 space-y-4" aria-busy={pending}>
        <fieldset disabled={pending} className="grid min-w-0 gap-4 sm:grid-cols-2">
          {([
            ["name", "Name", "text", "name", true, 200],
            ["email", "Email", "email", "email", true, 254],
            ["phone", "Phone (optional)", "tel", "tel", false, 100],
            ["company", "Company / Studio (optional)", "text", "organization", false, 300],
          ] as const).map(([key, label, type, autoComplete, required, maxLength]) => (
            <label key={key} className="block min-w-0 text-sm font-medium">{label}
              <input name={key} type={type} autoComplete={autoComplete} required={required} maxLength={maxLength} value={inquiry[key]} onChange={(event) => { const value = event.target.value; setInquiry((current) => ({ ...current, [key]: value })); }} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-base" />
            </label>
          ))}
          <label className="block min-w-0 text-sm font-medium sm:col-span-2">Message
            <textarea name="message" required maxLength={10000} value={inquiry.message} onChange={(event) => { const message = event.target.value; setInquiry((current) => ({ ...current, message })); }} rows={Math.min(18, Math.max(8, inquiry.message.split("\n").length))} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-base leading-6" />
          </label>
        </fieldset>
        <button type="submit" disabled={pending} className="min-h-12 w-full rounded-full bg-[var(--ink)] px-5 py-3 font-medium text-white disabled:opacity-60">{pending ? "Submitting..." : "Submit inquiry"}</button>
        {status ? <p ref={messageRef} tabIndex={-1} role={status.error ? "alert" : "status"} className={`rounded-lg p-3 text-sm ${status.error ? "bg-red-50 text-red-800" : "bg-green-50 text-green-900"}`}>{status.text}</p> : null}
      </form>
    </section>
  );
}
