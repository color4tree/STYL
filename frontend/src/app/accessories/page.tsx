"use client";

import { useEffect, useState } from "react";
import CatalogCard from "@/components/CatalogCard";
import StoreHeader from "@/components/StoreHeader";
import CartFeedback from "@/components/CartFeedback";
import { quantityLabel } from "@/lib/catalogDetails";
import { fetchAccessories, type Accessory } from "@/lib/accessories";
import { getCartCount, MAX_ITEM_QUANTITY } from "@/lib/cart";
import { useCart } from "@/lib/useCart";

export default function AccessoriesPage() {
  const [accessories, setAccessories] = useState<Accessory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const { cart, add, loading: cartLoading, error: cartError, notice } = useCart();
  useEffect(() => {
    let active = true;
    fetchAccessories().then((items) => { if (active) { setAccessories(items); setError(null); } })
      .catch(() => { if (active) setError("Accessories are unavailable right now. Please try again."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);
  return <>
    <StoreHeader cartCount={getCartCount(cart)} />
    <main className="container py-8 text-[var(--ink)] lg:py-12">
      <h1 className="text-3xl font-semibold tracking-tight lg:text-5xl">Accessories</h1>
      <p className="mt-4 max-w-2xl leading-7 text-[var(--muted)]">Attachments and accessories for your training space. Contact us for fit confirmation and bundle pricing.</p>
      <CartFeedback error={cartError} notice={notice} />
      {loading ? <p role="status" className="mt-8">Loading accessories...</p>
        : error ? <div role="alert" className="mt-8"><p>{error}</p><button type="button" onClick={() => { setLoading(true); setRetry(retry + 1); }} className="mt-3 min-h-11 rounded-full border px-5">Retry</button></div>
          : !accessories.length ? <p className="mt-8">No accessories are currently available.</p>
            : <div className="mt-8 grid gap-x-6 gap-y-6 md:grid-cols-2 xl:grid-cols-3">
              {accessories.map((item) => {
                const remaining = MAX_ITEM_QUANTITY - (cart.find((entry) => entry.id === item.id)?.quantity ?? 0);
                const quantity = Math.min(quantities[item.id] ?? 1, Math.max(1, remaining));
                const specs = [
                  ["Dimensions", item.dimensions], ["Material", item.material], ["Weight", item.weight],
                  ["Finish / colour", item.colourOptions], ["What's included", item.included],
                ] as const;
                return <CatalogCard id={`accessory-${item.id}`} key={item.id} item={item} specifications={specs} headingLevel={2}>
                  <div>
                    <p className="mb-2 text-sm" aria-live="polite">Quantity: {quantityLabel(quantity, item.sellingUnit)}</p>
                    <div className="flex flex-wrap gap-3">
                      <div className="flex items-center rounded-full border border-[var(--line)] bg-white">
                        <button type="button" aria-label={`Decrease quantity for ${item.name}`} disabled={quantity <= 1 || remaining <= 0} onClick={() => setQuantities({ ...quantities, [item.id]: quantity - 1 })} className="h-11 w-11 rounded-full disabled:opacity-40">−</button>
                        <span className="min-w-6 text-center">{quantity}</span>
                        <button type="button" aria-label={`Increase quantity for ${item.name}`} disabled={quantity >= remaining} onClick={() => setQuantities({ ...quantities, [item.id]: quantity + 1 })} className="h-11 w-11 rounded-full disabled:opacity-40">+</button>
                      </div>
                      <button type="button" disabled={remaining <= 0 || cartLoading || Boolean(cartError)} onClick={() => { if (add(item, quantity)) setQuantities({ ...quantities, [item.id]: 1 }); }} className="min-h-12 flex-1 rounded-full bg-[var(--ink)] px-4 py-3 text-sm font-medium text-white disabled:opacity-50">{remaining <= 0 ? "Maximum 10 in cart" : "Add to cart"}</button>
                    </div>
                  </div>
                </CatalogCard>;
              })}
            </div>}
      <p className="mt-6 text-sm text-[var(--muted)]">Specifications may vary slightly by production batch.</p>
    </main>
  </>;
}
