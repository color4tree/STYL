"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { clearCart, readCart, removeProductFromCart, updateCartQuantity, type CartItem } from "@/lib/cart";

export default function CartPage() {
  const [items, setItems] = useState<CartItem[]>([]);

  useEffect(() => {
    setItems(readCart());
  }, []);

  const total = useMemo(
    () => items.reduce((sum, item) => sum + item.price * item.quantity, 0),
    [items],
  );

  const updateQuantity = (id: number, delta: number) => {
    setItems(updateCartQuantity(id, delta));
  };

  const removeItem = (id: number) => {
    setItems(removeProductFromCart(id));
  };

  const handleClearCart = () => {
    setItems(clearCart());
  };

  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-12 text-[var(--ink)] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8 flex items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Cart</div>
            <h1 className="mt-3 text-4xl font-semibold tracking-[-0.06em]">Your selected equipment</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleClearCart}
              className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium text-[var(--ink)]"
            >
              Clear cart
            </button>
            <Link href="/" className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium">
              Continue shopping
            </Link>
          </div>
        </div>

        {items.length === 0 ? (
          <section className="rounded-[28px] border border-[var(--line)] bg-white/70 p-8">
            <p className="text-lg text-[var(--muted)]">Your cart is empty.</p>
            <Link href="/" className="mt-6 inline-flex rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white">
              Explore collection
            </Link>
          </section>
        ) : (
          <div className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr]">
            <section className="space-y-4">
              {items.map((item) => (
                <div key={item.id} className="flex flex-col gap-4 rounded-[24px] border border-[var(--line)] bg-white/70 p-5 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="text-xl font-semibold">{item.name}</div>
                    <div className="mt-2 text-sm text-[var(--muted)]">Unit price: ${item.price.toLocaleString()}</div>
                  </div>

                  <div className="flex items-center justify-between gap-4 sm:justify-end">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.id, -1)}
                        className="h-9 w-9 rounded-full border border-[var(--line)] bg-white text-lg"
                        aria-label={`Decrease quantity for ${item.name}`}
                      >
                        −
                      </button>
                      <span className="min-w-8 text-center text-sm font-medium">{item.quantity}</span>
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.id, 1)}
                        className="h-9 w-9 rounded-full border border-[var(--line)] bg-white text-lg"
                        aria-label={`Increase quantity for ${item.name}`}
                      >
                        +
                      </button>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="min-w-24 text-right font-semibold">
                        ${(item.price * item.quantity).toLocaleString()}
                      </div>
                      <button
                        type="button"
                        onClick={() => removeItem(item.id)}
                        className="text-sm font-medium text-[var(--muted)] underline-offset-4 hover:underline"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </section>

            <aside className="rounded-[28px] border border-[var(--line)] bg-[var(--ink)] p-6 text-white">
              <div className="text-xs uppercase tracking-[0.24em] text-white/60">Summary</div>
              <div className="mt-6 flex items-center justify-between text-lg">
                <span>Subtotal</span>
                <span>${total.toLocaleString()}</span>
              </div>
              <div className="mt-3 flex items-center justify-between text-sm text-white/70">
                <span>Shipping</span>
                <span>Calculated later</span>
              </div>
              <div className="mt-8 border-t border-white/15 pt-5 text-xl font-semibold">
                <div className="flex items-center justify-between">
                  <span>Total</span>
                  <span>${total.toLocaleString()}</span>
                </div>
              </div>

              <Link href="/?quote=cart#contact" className="mt-8 inline-flex w-full items-center justify-center rounded-full bg-white px-4 py-3 text-sm font-medium text-[var(--ink)]">
                Request a quote
              </Link>
            </aside>
          </div>
        )}
      </div>
    </main>
  );
}
