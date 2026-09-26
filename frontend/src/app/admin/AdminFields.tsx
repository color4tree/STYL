"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { emptyProvenance, type Provenance } from "@/lib/catalogDetails";

export const inputClass = "mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3";

export function AdminSaveBar({ children }: { children: ReactNode }) {
  const [keyboardOpen, setKeyboardOpen] = useState(false);
  useEffect(() => {
    const update = () => {
      const element = document.activeElement;
      const editing = element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement;
      setKeyboardOpen(editing && window.innerWidth < 1024 && (window.visualViewport?.height ?? window.innerHeight) < window.innerHeight * 0.75);
    };
    const onBlur = () => queueMicrotask(update);
    document.addEventListener("focusin", update);
    document.addEventListener("focusout", onBlur);
    window.visualViewport?.addEventListener("resize", update);
    return () => {
      document.removeEventListener("focusin", update);
      document.removeEventListener("focusout", onBlur);
      window.visualViewport?.removeEventListener("resize", update);
    };
  }, []);
  return <div className={`sticky bottom-0 z-10 mt-8 flex flex-wrap items-center gap-3 border-t border-[var(--line)] bg-white py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:static lg:border-0 ${keyboardOpen ? "invisible lg:visible" : ""}`}>{children}</div>;
}

export type AdminMessage = { type: "error" | "success"; text: string };

export function AdminNotice({ message }: { message: AdminMessage | null }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (message?.type === "error") {
      ref.current?.scrollIntoView({ block: "center" });
      ref.current?.focus({ preventScroll: true });
    }
  }, [message]);
  if (!message) return null;
  return (
    <div ref={ref} tabIndex={-1} role={message.type === "error" ? "alert" : "status"} className={`my-4 rounded-xl border-2 p-4 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2 ${message.type === "error" ? "border-red-600 bg-red-50 text-red-900 focus:ring-red-600" : "border-green-600 bg-green-50 text-green-900 focus:ring-green-600"}`}>
      <p className="font-semibold">{message.type === "error" ? "Error" : "Success"}</p>
      <p className="mt-1 break-words">{message.text}</p>
    </div>
  );
}

export function parsePrice(value: string): number | null {
  if (!/^(?:\d+(?:\.\d{0,2})?|\.\d{1,2})$/.test(value)) return null;
  const price = Number(value);
  return Number.isFinite(price) && price >= 0 ? price : null;
}

export const priceError = "Enter a nonnegative price with no more than two decimal places (for example, 19.99).";

export function PriceInput({ value, onChange, id }: { value: string; onChange: (value: string) => void; id: string }) {
  const invalid = parsePrice(value) === null;
  return (
    <div className="text-sm font-medium">
      <label htmlFor={id}>Retail price</label>
      <input id={id} type="text" inputMode="decimal" value={value} onChange={(event) => onChange(event.target.value)} onBlur={() => {
        const price = parsePrice(value);
        if (price !== null) onChange(price.toFixed(2));
      }} aria-invalid={invalid} aria-describedby={invalid ? `${id}-error` : undefined} className={inputClass} />
      {invalid ? <span id={`${id}-error`} className="mt-2 block text-sm text-red-700">{priceError}</span> : null}
    </div>
  );
}

export function ProvenanceEditor({ value, onChange }: { value?: Provenance; onChange: (value: Provenance) => void }) {
  const provenance = { ...emptyProvenance, ...value };
  return (
    <fieldset className="min-w-0 border-t border-[var(--line)] pt-5 md:col-span-2">
      <legend className="text-lg font-semibold">Internal source / provenance</legend>
      <p className="mb-4 text-sm text-[var(--muted)]">Private admin reference only. These fields are not shown to customers.</p>
      <div className="grid gap-4 md:grid-cols-2">
        {([
          ["sourceType", "Source type", "text"],
          ["marketplaceUrl", "Marketplace / source URL", "url"],
          ["listingId", "Listing ID", "text"],
          ["capturedDate", "Captured date", "date"],
        ] as const).map(([key, label, type]) => (
          <label key={key} className="block text-sm font-medium">{label}
            <input type={type} value={provenance[key]} onChange={(event) => onChange({ ...provenance, [key]: event.target.value })} className={inputClass} />
          </label>
        ))}
        <label className="block text-sm font-medium md:col-span-2">Internal notes
          <textarea rows={3} value={provenance.notes} onChange={(event) => onChange({ ...provenance, notes: event.target.value })} className={inputClass} />
        </label>
      </div>
    </fieldset>
  );
}
