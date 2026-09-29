"use client";

import { useEffect, useState } from "react";
import CatalogGrid from "@/components/CatalogGrid";
import StoreHeader from "@/components/StoreHeader";
import CartFeedback from "@/components/CartFeedback";
import { fetchPublicCatalog, type PublicCatalogItem } from "@/lib/publicCatalog";
import { getCartCount } from "@/lib/cart";
import { useCart } from "@/lib/useCart";

export default function AccessoriesPage() {
  const [items, setItems] = useState<PublicCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const { cart, add, loading: cartLoading, error: cartError, notice } = useCart();
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    fetchPublicCatalog("accessories", controller.signal).then(items => {
      if (active) { setItems(items); setError(false); }
    }).catch(failure => { if (active) { console.error(failure); setError(true); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [retry]);
  return <>
    <StoreHeader cartCount={getCartCount(cart)} />
    <main className="container py-8 text-[var(--ink)] lg:py-12">
      <h1 className="text-3xl font-semibold tracking-tight lg:text-5xl">Accessories</h1>
      <p className="mt-4 max-w-2xl leading-7 text-[var(--muted)]">Attachments and accessories for your training space. Contact us for fit confirmation and bundle pricing.</p>
      <CartFeedback error={cartError} notice={notice} />
      <div className="mt-8">
        {loading ? <p role="status">Loading accessories...</p>
          : error ? <div role="alert" data-analytics-event="site_error"><p>Accessories are unavailable right now. Please try again.</p><button type="button" onClick={() => { setLoading(true); setRetry(value => value + 1); }} className="mt-3 min-h-12 rounded-full border px-5">Retry</button></div>
            : !items.length ? <p data-analytics-event="catalog_empty" data-analytics-list="accessories">No accessories are currently available.</p>
              : <CatalogGrid entries={items.map(item => ({ item, itemType: "accessory" }))} cart={cart} add={add} disabled={cartLoading || Boolean(cartError)} headingLevel={2} />}
      </div>
      <p className="mt-6 text-sm text-[var(--muted)]">Specifications may vary slightly by production batch.</p>
    </main>
  </>;
}
