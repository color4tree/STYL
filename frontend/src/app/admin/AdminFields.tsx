"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { emptyProvenance, type Provenance } from "@/lib/catalogDetails";
import type { MarketCurrency, MarketPrices } from "@/lib/pricing";

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
      ref.current?.scrollIntoView({ block: "center", behavior: "instant" });
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
export const msrpError = "Enter a nonnegative MSRP with no more than two decimal places (for example, 19.99).";

export function PriceInput({ value, onChange, id, label = "Retail price", optional = false, error = priceError, className = "" }: { value: string; onChange: (value: string) => void; id: string; label?: string; optional?: boolean; error?: string; className?: string }) {
  const invalid = !(optional && value === "") && parsePrice(value) === null;
  return (
    <div className={`min-w-0 text-sm font-medium ${className}`}>
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" inputMode="decimal" value={value} onChange={(event) => onChange(event.target.value)} onBlur={() => {
        const price = parsePrice(value);
        if (price !== null) onChange(price.toFixed(2));
      }} aria-invalid={invalid} aria-describedby={invalid ? `${id}-error` : undefined} className={`${inputClass} min-h-11 min-w-0`} />
      {invalid ? <span id={`${id}-error`} className="mt-2 block text-sm text-red-700">{error}</span> : null}
    </div>
  );
}

export function parseMarketPrices(values: Record<MarketCurrency, string>): MarketPrices | null {
  const CAD = values.CAD === "" ? null : parsePrice(values.CAD);
  const USD = values.USD === "" ? null : parsePrice(values.USD);
  if ((values.CAD !== "" && CAD === null) || (values.USD !== "" && USD === null)) return null;
  return { CAD, USD };
}

function MarketPriceHelp({ value, kind = "price" }: { value: Record<MarketCurrency, string>; kind?: "price" | "msrp" }) {
  const isMsrp = kind === "msrp";
  return <>
    <p className="text-sm text-[var(--muted)]">{isMsrp ? "Optional; shown only when higher than Price. Does not affect checkout/quote pricing." : "CAD applies to Canada and unknown locations. USD applies to identified countries outside Canada. A blank price hides this item in that market; zero is a valid price. No currency conversion is applied."}</p>
    {!isMsrp && (!value.CAD || !value.USD) ? <p role="status" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">Needs attention: {![value.CAD, value.USD].some(Boolean) ? "Canada and US" : !value.CAD ? "Canada" : "US / other countries"} price missing. This item will not appear in that market.</p> : null}
  </>;
}

export function CountryPricingInputs({ prices, msrps, onPricesChange, onMsrpsChange, prefix }: {
  prices: Record<MarketCurrency, string>;
  msrps: Record<MarketCurrency, string>;
  onPricesChange: (value: Record<MarketCurrency, string>) => void;
  onMsrpsChange: (value: Record<MarketCurrency, string>) => void;
  prefix: string;
}) {
  return <fieldset className="grid min-w-0 gap-4 md:col-span-2">
    <legend className="mb-3 text-lg font-semibold">Country pricing</legend>
    {(["CAD", "USD"] as const).map((currency) => (
      <div key={currency} className="grid min-w-0 grid-cols-2 gap-x-3 sm:gap-x-4">
        <PriceInput id={`${prefix}-price-${currency.toLowerCase()}`} label={currency === "CAD" ? "Canada price (CAD)" : "US price (USD)"} optional value={prices[currency]} onChange={(value) => onPricesChange({ ...prices, [currency]: value })} className="row-span-3 grid grid-rows-subgrid" />
        <PriceInput id={`${prefix}-msrp-${currency.toLowerCase()}`} label={`${currency} MSRP`} error={msrpError} optional value={msrps[currency]} onChange={(value) => onMsrpsChange({ ...msrps, [currency]: value })} className="row-span-3 grid grid-rows-subgrid" />
      </div>
    ))}
    <MarketPriceHelp value={msrps} kind="msrp" />
    <MarketPriceHelp value={prices} />
  </fieldset>;
}

export function MarketPriceInputs({ value, onChange, prefix, kind = "price" }: { value: Record<MarketCurrency, string>; onChange: (value: Record<MarketCurrency, string>) => void; prefix: string; kind?: "price" | "msrp" }) {
  const isMsrp = kind === "msrp";
  return <fieldset className="grid min-w-0 gap-4 md:col-span-2 md:grid-cols-2">
    <legend className="mb-3 text-lg font-semibold">{isMsrp ? "MSRP (optional)" : "Country pricing"}</legend>
    <PriceInput id={`${prefix}-cad`} label={isMsrp ? "CAD MSRP" : "Canada price (CAD)"} error={isMsrp ? msrpError : priceError} optional value={value.CAD} onChange={(CAD) => onChange({ ...value, CAD })} />
    <PriceInput id={`${prefix}-usd`} label={isMsrp ? "USD MSRP" : "US price (USD)"} error={isMsrp ? msrpError : priceError} optional value={value.USD} onChange={(USD) => onChange({ ...value, USD })} />
    <div className="grid gap-4 md:col-span-2"><MarketPriceHelp value={value} kind={kind} /></div>
  </fieldset>;
}

export function MarketPriceSummary({ prices, msrps }: { prices: MarketPrices; msrps?: MarketPrices }) {
  return <div className="mt-1 text-sm">
    <div>CAD {prices.CAD === null ? "Not set" : `$${prices.CAD.toFixed(2)}`} · USD {prices.USD === null ? "Not set" : `$${prices.USD.toFixed(2)}`}</div>
    {msrps && (msrps.CAD !== null || msrps.USD !== null) ? <div className="mt-1 text-xs text-[var(--muted)]">MSRP · {(["CAD", "USD"] as const).filter((currency) => msrps[currency] !== null).map((currency) => `${currency} $${msrps[currency]!.toFixed(2)}`).join(" · ")}</div> : null}
    {prices.CAD === null || prices.USD === null ? <div className="mt-1 font-medium text-amber-800">Needs attention: missing {prices.CAD === null ? "Canada" : ""}{prices.CAD === null && prices.USD === null ? " and " : ""}{prices.USD === null ? "US" : ""} price</div> : null}
  </div>;
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
