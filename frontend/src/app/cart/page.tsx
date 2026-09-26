"use client";

import Link from "next/link";
import { useState } from "react";
import { formatPrice, getCartCount, getCartTotals, lineAmount, MAX_ITEM_QUANTITY } from "@/lib/cart";
import { quantityLabel } from "@/lib/catalogDetails";
import { useCart } from "@/lib/useCart";
import StoreHeader from "@/components/StoreHeader";
import CartFeedback from "@/components/CartFeedback";

export default function CartPage() {
  const { cart: items, update, remove, clear, error, notice } = useCart();
  const [confirmClear, setConfirmClear] = useState(false);
  const totals = getCartTotals(items);
  return <>
    <StoreHeader cartCount={getCartCount(items)} />
    <main className="container py-8 pb-32 text-[var(--ink)] lg:py-12">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div><h1 className="text-3xl font-semibold tracking-tight lg:text-5xl">Your selection</h1><p className="mt-3 max-w-2xl leading-7 text-[var(--muted)]">Review your equipment and request a quote. No payment is collected here.</p></div>
        <Link href="/#products" className="inline-flex min-h-11 items-center underline">Continue shopping</Link>
      </div>
      <CartFeedback error={error} notice={notice} />
      {!items.length && !error ? <section className="soft-panel rounded-3xl p-6">
        <h2 className="text-xl font-semibold">Your cart is empty.</h2>
        <div className="mt-4 flex flex-wrap gap-3"><Link href="/#products" className="inline-flex min-h-12 items-center rounded-full bg-[var(--ink)] px-5 text-white">Shop equipment</Link><Link href="/accessories" className="inline-flex min-h-12 items-center rounded-full border px-5">Browse accessories</Link></div>
      </section> : <>
        <div className="grid items-start gap-8 lg:grid-cols-[1.3fr_0.7fr]">
          <section aria-label="Selected items" className="space-y-4">
            {items.map((item) => <article key={item.id} className="soft-panel min-w-0 rounded-2xl p-4 lg:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1"><h2 className="break-words text-xl font-semibold">{item.slug ? <Link href={`/products/${item.slug}`} className="hover:underline">{item.name}</Link> : item.name}</h2>
                  <p className="mt-2 text-sm text-[var(--muted)]">Unit price: {formatPrice(item.price, item.currency)}{item.sellingUnit ? ` / ${item.sellingUnit.toLowerCase()}` : ""}</p>
                  {item.packageQuantity ? <p className="mt-1 text-sm text-[var(--muted)]">{item.packageQuantity} pieces per sale unit</p> : null}
                </div>
                <p className="font-semibold">{formatPrice(lineAmount(item.price, item.quantity), item.currency)}</p>
              </div>
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <div><span className="mb-2 block text-sm">Quantity: {quantityLabel(item.quantity, item.sellingUnit)}</span>
                  <div className="inline-flex items-center rounded-full border border-[var(--line)] bg-white">
                    <button type="button" disabled={item.quantity <= 1} onClick={() => update(item.id, -1)} aria-label={`Decrease quantity for ${item.name}`} className="h-11 w-11 rounded-full disabled:opacity-40">−</button>
                    <span className="min-w-8 text-center">{item.quantity}</span>
                    <button type="button" disabled={item.quantity >= MAX_ITEM_QUANTITY} onClick={() => update(item.id, 1)} aria-label={`Increase quantity for ${item.name}`} className="h-11 w-11 rounded-full disabled:opacity-40">+</button>
                  </div>
                </div>
                <button type="button" onClick={() => remove(item.id)} aria-label={`Remove ${item.name}`} className="min-h-11 px-3 text-sm underline">Remove</button>
              </div>
            </article>)}
          </section>
          <aside className="rounded-3xl bg-[var(--ink)] p-6 text-white lg:sticky lg:top-28">
            <h2 className="text-xl font-semibold">Summary</h2>
            <div className="mt-5 space-y-3">{totals.map(([currency, total]) => <div key={currency} className="flex flex-wrap justify-between gap-3 text-lg"><span>Total</span><span>{formatPrice(total, currency)}</span></div>)}</div>
            <p className="mt-3 text-sm text-white/80">Shipping and final pricing confirmed with your quote.</p>
            {items.length ? <Link href="/?quote=cart#contact" className="mt-6 inline-flex min-h-12 w-full items-center justify-center rounded-full bg-white px-4 text-center font-medium text-[var(--ink)]">Request a quote</Link> : null}
          </aside>
        </div>
        <div className="mt-8">
          {confirmClear ? <div className="flex flex-wrap items-center gap-3"><p>Remove all selected items?</p><button type="button" className="min-h-11 rounded-full bg-red-700 px-4 text-white" onClick={() => { if (clear()) setConfirmClear(false); }}>Confirm clear cart</button><button type="button" className="min-h-11 px-4" onClick={() => setConfirmClear(false)}>Cancel</button></div>
            : <button type="button" className="min-h-11 px-3 text-sm underline" onClick={() => setConfirmClear(true)}>Clear cart</button>}
        </div>
        {items.length ? <div className="safe-action fixed inset-x-0 bottom-0 z-30 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--line)] bg-white p-3 lg:hidden"><span className="text-sm">{getCartCount(items)} sale units selected</span><Link href="/?quote=cart#contact" className="inline-flex min-h-12 items-center justify-center rounded-full bg-[var(--ink)] px-5 font-medium text-white">Request a quote</Link></div> : null}
      </>}
    </main>
  </>;
}
