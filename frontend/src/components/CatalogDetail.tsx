"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { formatPrice, getCartCount, MAX_ITEM_QUANTITY } from "@/lib/cart";
import { useCart } from "@/lib/useCart";
import { API_BASE } from "@/lib/api";
import { getCatalogPhotos, saleUnitLabel } from "@/lib/catalogDetails";
import { catalogSpecifications, isPublicCatalogItem, type PublicCatalogItem } from "@/lib/publicCatalog";
import type { AnalyticsItemType } from "@/lib/analyticsTypes";
import StoreHeader from "./StoreHeader";
import CartFeedback from "./CartFeedback";
import AddToCartButton from "./AddToCartButton";
import PhotoGallery from "./PhotoGallery";
import CatalogPrice from "./CatalogPrice";
import CatalogCategory from "./CatalogCategory";
import { CompatibilityDetails } from "./Compatibility";

export default function CatalogDetail({ itemType, identifier }: { itemType: AnalyticsItemType; identifier?: string }) {
  const [item, setItem] = useState<PublicCatalogItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolved, setResolved] = useState("");
  const [problem, setProblem] = useState("");
  const [retry, setRetry] = useState(0);
  const [actionVisible, setActionVisible] = useState(true);
  const action = useRef<HTMLDivElement>(null);
  const { cart, add, loading: cartLoading, error, notice } = useCart();
  const label = itemType === "product" ? "Equipment" : "Accessory";
  const requestKey = `${itemType}:${identifier}`;

  useEffect(() => {
    if (!identifier) return;
    const endpoint = `${API_BASE}/api/${itemType === "product" ? "products" : "accessories"}/${encodeURIComponent(identifier)}`;
    const controller = new AbortController();
    let active = true;
    async function load() {
      try {
        const response = await fetch(endpoint, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(response.status === 404 ? `${label} not found` : `${label} is unavailable right now. Please retry.`);
        const data: unknown = await response.json();
        if (!data || typeof data !== "object" || !("item" in data) || !isPublicCatalogItem(data.item) || data.item.publicationStatus === "draft") {
          throw new Error(`${label} not found`);
        }
        if (active) { setItem(data.item); setProblem(""); }
      } catch (failure) {
        if (active) { console.error(failure); setItem(null); setProblem(failure instanceof Error ? failure.message : `${label} is unavailable right now. Please retry.`); }
      } finally { if (active) { setLoading(false); setResolved(requestKey); } }
    }
    void load();
    return () => { active = false; controller.abort(); };
  }, [identifier, itemType, label, requestKey, retry]);

  useEffect(() => {
    if (!action.current) return;
    const observer = new IntersectionObserver(([entry]) => setActionVisible(entry.isIntersecting));
    observer.observe(action.current);
    return () => observer.disconnect();
  }, [item]);

  if (loading || resolved !== requestKey) return <main className="min-h-screen bg-[var(--bg)] px-4 py-20 text-[var(--ink)]">
    <div className="mx-auto max-w-4xl text-lg text-[var(--muted)]">Loading {label.toLowerCase()}...</div>
  </main>;
  if (!item) return <main className="min-h-screen bg-[var(--bg)] px-4 py-20 text-[var(--ink)]">
    <div className="mx-auto max-w-4xl">
      <h1 data-analytics-event="item_unavailable" className="text-3xl font-semibold">{problem}</h1>
      <button type="button" className="mt-4 min-h-12 rounded-full border px-5" onClick={() => { setLoading(true); setRetry(value => value + 1); }}>Retry</button>
      <Link href="/#products" className="ml-3 mt-6 inline-flex min-h-12 items-center rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white">Return home</Link>
    </div>
  </main>;

  const photos = getCatalogPhotos(item);
  const specifications = catalogSpecifications(item, itemType).filter(([name, value]) => name !== "Availability" && value?.trim());
  const features = item.features?.filter(value => value.trim()) ?? [];
  const atLimit = (cart.find(entry => entry.id === item.id)?.quantity ?? 0) >= MAX_ITEM_QUANTITY;
  const quoteHref = `/?quote=product&product=${encodeURIComponent(item.name)}&itemType=${itemType}&itemId=${item.id}#contact`;
  return <>
    <StoreHeader cartCount={getCartCount(cart)} />
    <main className="min-h-screen bg-[var(--bg)] px-4 py-6 pb-32 text-[var(--ink)] sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-6xl">
        <Link href="/#products" data-analytics-action="back_to_collection" className="mb-4 inline-flex min-h-12 items-center text-sm font-medium text-[var(--muted)]">← Back to collection</Link>
        <CartFeedback error={error} notice={notice} />
        <section data-analytics-event="item_detail_open" data-analytics-item-id={item.id} data-analytics-item-type={itemType}
          className={`grid grid-cols-1 gap-6 rounded-3xl border border-[var(--line)] bg-white/70 p-4 lg:gap-10 lg:p-8 ${photos.length ? "lg:grid-cols-[1.1fr_0.9fr]" : ""}`}>
          <div className={`min-w-0 ${photos.length ? "lg:col-start-2 lg:row-start-1" : ""}`}>
            <p className="break-words text-sm text-[var(--muted)]"><CatalogCategory item={item} /></p>
            <h1 data-analytics-identity className="mt-2 break-words text-3xl font-semibold tracking-tight lg:text-5xl">{item.name}</h1>
            <CatalogPrice price={item.price} currency={item.currency} msrp={item.msrp} sellingUnit={item.sellingUnit} className="mt-4 text-2xl" />
            {item.packageQuantity ? <p className="mt-2 text-sm">{item.packageQuantity} {item.packageQuantity === 1 ? "piece" : "pieces"} per {saleUnitLabel(item.sellingUnit) || "sale unit"}.</p> : null}
            {item.stockStatus?.trim() ? <p className="mt-3 text-sm font-medium">{item.stockStatus}</p> : null}
          </div>
          {photos.length ? <div className="min-w-0 lg:col-start-1 lg:row-span-2 lg:row-start-1"><PhotoGallery key={`${itemType}-${item.id}`} photos={photos} name={item.name} item={{ itemType, itemId: item.id }} /></div> : null}
          <div className="min-w-0 break-words">
            {item.shortDescription?.trim() ? <p className="whitespace-pre-line text-base leading-7 text-[var(--muted)] lg:text-lg lg:leading-8">{item.shortDescription}</p> : null}
            <div ref={action} className="my-5 flex flex-wrap gap-3">
              <AddToCartButton key={`${itemType}-${item.id}`} disabled={cartLoading || Boolean(error)} atLimit={atLimit} onAdd={() => add(item)} className="min-h-12 rounded-full bg-[var(--ink)] px-6 py-3 font-medium text-white disabled:opacity-50" />
              <Link href={quoteHref} data-analytics-source="product" scroll={false} className="inline-flex min-h-12 items-center rounded-full border border-[var(--ink)] px-6 py-3 font-medium">Request quote</Link>
            </div>
            <CompatibilityDetails value={item.compatibility} />
            {specifications.length ? <details className="my-5 border-t border-[var(--line)] pt-4" open>
              <summary className="min-h-12 text-base font-semibold">Specifications</summary>
              <dl className="mt-3 space-y-3 text-sm">{specifications.map(([name, value]) => <div key={name}><dt className="text-[var(--muted)]">{name}</dt><dd className="mt-1 whitespace-pre-line break-words">{value}</dd></div>)}</dl>
            </details> : null}
          </div>
        </section>
        {features.length || item.description?.trim() || item.notes?.trim() ? <div className="mt-10 grid gap-8 md:grid-cols-2">
          {features.length ? <section className="min-w-0 border-t border-[var(--line)] pt-5"><h2 className="text-lg font-semibold">Features</h2><ul className="mt-4 list-inside list-disc space-y-3 break-words text-base leading-7 text-[var(--muted)]">{features.map((feature, index) => <li key={index}>{feature}</li>)}</ul></section> : null}
          {item.description?.trim() ? <section className="min-w-0 border-t border-[var(--line)] pt-5"><h2 className="text-lg font-semibold">Overview</h2><p className="mt-4 whitespace-pre-line break-words text-base leading-7 text-[var(--muted)]">{item.description}</p></section> : null}
          {item.notes?.trim() ? <section className="min-w-0 border-t border-[var(--line)] pt-5"><h2 className="text-lg font-semibold">Use</h2><p className="mt-4 whitespace-pre-line break-words text-base leading-7 text-[var(--muted)]">{item.notes}</p></section> : null}
        </div> : null}
      </div>
      {!actionVisible ? <div className="safe-action fixed inset-x-0 bottom-0 z-30 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--line)] bg-white p-3 lg:hidden">
        <span className="font-semibold">{formatPrice(item.price, item.currency)}</span>
        <AddToCartButton key={`sticky-${itemType}-${item.id}`} disabled={cartLoading || Boolean(error)} atLimit={atLimit} onAdd={() => add(item)} className="min-h-12 rounded-full bg-[var(--ink)] px-5 py-3 text-white disabled:opacity-50" />
      </div> : null}
    </main>
  </>;
}
