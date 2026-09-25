"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import PhotoGallery from "@/components/PhotoGallery";
import { CompatibilityDetails } from "@/components/Compatibility";
import { getCatalogPhotos } from "@/lib/catalogDetails";
import BrandLogo from "@/components/BrandLogo";
import { fetchAccessories, type Accessory } from "@/lib/accessories";
import { addProductToCart, formatPrice, getCartCount, MAX_ITEM_QUANTITY, readCart, type CartItem } from "@/lib/cart";

export default function AccessoriesPage() {
  const [accessories, setAccessories] = useState<Accessory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [lastAddedId, setLastAddedId] = useState<number | null>(null);
  const [quantities, setQuantities] = useState<Record<number, number>>({});

  useEffect(() => {
    fetchAccessories()
      .then(setAccessories)
      .catch(() => setError("Accessories are unavailable right now. Please try again later."))
      .finally(() => {
        setCart(readCart());
        setLoading(false);
      });
  }, []);

  const addToCart = (item: Accessory, quantity: number) => {
    setCart(addProductToCart({ id: item.id, name: item.name, price: item.price, currency: item.currency }, quantity));
    setLastAddedId(item.id);
    setQuantities((current) => ({ ...current, [item.id]: 1 }));
  };

  const changeQuantity = (id: number, value: number, max: number) => {
    setQuantities((current) => ({ ...current, [id]: Math.min(max, Math.max(1, value)) }));
  };

  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-12 text-[var(--ink)] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <Link href="/" aria-label="STYL home" className="mb-8 inline-flex">
          <BrandLogo markClassName="h-8 w-auto" />
        </Link>
        <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Accessories</div>
            <h1 className="mt-3 text-4xl font-semibold tracking-[-0.06em]">Multi trainer accessories</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--muted)]">
              Attachments for your training setup. Contact us for fit confirmation and bundle pricing.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/" className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium">
              Back to home
            </Link>
            <Link href="/cart" className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium">
              Cart ({getCartCount(cart)})
            </Link>
            <Link href="/#contact" className="rounded-full bg-[var(--ink)] px-5 py-2.5 text-sm font-medium text-white">
              Request a quote
            </Link>
          </div>
        </div>

        {loading ? (
          <p className="text-[var(--muted)]">Loading accessories...</p>
        ) : error ? (
          <p className="text-[var(--muted)]">{error}</p>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {accessories.map((item) => {
              const inCart = cart.find((cartItem) => cartItem.id === item.id)?.quantity ?? 0;
              const remaining = MAX_ITEM_QUANTITY - inCart;
              const quantity = Math.min(quantities[item.id] ?? 1, Math.max(remaining, 1));

              return (
              <article
                key={item.id}
                className="flex flex-col rounded-[28px] border border-[var(--line)] bg-white/70 p-4 shadow-[0_16px_40px_rgba(17,17,17,0.04)]"
              >
                <PhotoGallery photos={getCatalogPhotos(item)} name={item.name} compact />
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <span className="text-xs uppercase tracking-[0.2em] text-[var(--muted)]">{item.category}</span>
                  <span className="text-lg font-semibold">{formatPrice(item.price, item.currency)}</span>
                </div>
                <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em]">{item.name}</h2>
                <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{item.notes}</p>
                <dl className="mb-5 mt-4 space-y-2 border-t border-[var(--line)] pt-4 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--muted)]">Dimensions</dt>
                    <dd className="text-right">{item.dimensions}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--muted)]">Material</dt>
                    <dd className="text-right">{item.material}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--muted)]">Weight</dt>
                    <dd className="text-right">{item.weight}</dd>
                  </div>
                </dl>
                <CompatibilityDetails value={item.compatibility} />
                <div className="mt-auto flex gap-3">
                  <div
                    className={`flex items-stretch overflow-hidden rounded-full border border-[var(--line)] bg-white ${remaining <= 0 ? "opacity-50" : ""}`}
                  >
                    <span className="flex min-w-12 items-center justify-center pl-4 pr-2 text-sm font-semibold" aria-live="polite">
                      {quantity}
                    </span>
                    <div className="flex flex-col border-l border-[var(--line)]">
                      <button
                        type="button"
                        onClick={() => changeQuantity(item.id, quantity + 1, remaining)}
                        disabled={quantity >= remaining}
                        className="flex flex-1 items-center justify-center px-3 text-[10px] leading-none hover:bg-[#f5f1ea] disabled:opacity-30"
                        aria-label={`Increase quantity for ${item.name}`}
                      >
                        ▲
                      </button>
                      <button
                        type="button"
                        onClick={() => changeQuantity(item.id, quantity - 1, remaining)}
                        disabled={quantity <= 1 || remaining <= 0}
                        className="flex flex-1 items-center justify-center border-t border-[var(--line)] px-3 text-[10px] leading-none hover:bg-[#f5f1ea] disabled:opacity-30"
                        aria-label={`Decrease quantity for ${item.name}`}
                      >
                        ▼
                      </button>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => addToCart(item, quantity)}
                    disabled={remaining <= 0}
                    className="flex-1 rounded-full bg-[var(--ink)] px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                  >
                    {remaining <= 0
                      ? `Max ${MAX_ITEM_QUANTITY} in cart`
                      : lastAddedId === item.id
                        ? `Added (${inCart} in cart)`
                        : "Add to cart"}
                  </button>
                </div>
              </article>
              );
            })}
          </div>
        )}

        <p className="mt-6 text-xs text-[var(--muted)]">
          Specifications may vary slightly by production batch.
        </p>
      </div>
    </main>
  );
}
