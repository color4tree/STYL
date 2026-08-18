"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { addProductToCart, getCartCount, readCart } from "@/lib/cart";

type Product = {
  id: number;
  slug: string;
  name: string;
  category: string;
  price: number;
  currency: string;
  shortDescription: string;
  description?: string;
  features?: string[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CART_KEY = "styl-cart";

export default function ProductDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug;
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [cartCount, setCartCount] = useState(0);

  useEffect(() => {
    if (!slug) return;

    const loadProduct = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/products/${slug}`);
        if (!res.ok) {
          throw new Error("Product not found");
        }

        const data = await res.json();
        setProduct(data.item as Product);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };

    loadProduct();
  }, [slug]);

  useEffect(() => {
    setCartCount(getCartCount(readCart()));
  }, []);

  const addToCart = () => {
    if (!product) return;

    const next = addProductToCart(product);
    setCartCount(getCartCount(next));
  };

  const priceLabel = useMemo(() => {
    if (!product) return "";
    return `$${product.price.toLocaleString()}`;
  }, [product]);

  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--bg)] px-4 py-20 text-[var(--ink)]">
        <div className="mx-auto max-w-4xl text-lg text-[var(--muted)]">Loading product...</div>
      </main>
    );
  }

  if (!product) {
    return (
      <main className="min-h-screen bg-[var(--bg)] px-4 py-20 text-[var(--ink)]">
        <div className="mx-auto max-w-4xl">
          <h1 className="text-3xl font-semibold">Product not found</h1>
          <Link href="/" className="mt-6 inline-block rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white">
            Return home
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-12 text-[var(--ink)] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex items-center justify-between gap-4">
          <Link href="/" className="text-sm font-medium text-[var(--muted)]">
            ← Back to collection
          </Link>
          <Link href="/cart" className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium">
            Cart ({cartCount})
          </Link>
        </div>

        <section className="grid gap-10 rounded-[32px] border border-[var(--line)] bg-white/70 p-6 md:grid-cols-[1.1fr_0.9fr] md:p-8">
          <div className="rounded-[28px] bg-[linear-gradient(180deg,#efeae4,#d9d0c6)] p-6">
            <div className="h-[440px] rounded-[24px] bg-[radial-gradient(circle_at_30%_30%,rgba(201,176,142,0.8),rgba(24,24,24,0.65)_58%)]" />
          </div>

          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">{product.category}</div>
            <h1 className="mt-4 text-4xl font-semibold tracking-[-0.06em] md:text-5xl">{product.name}</h1>
            <div className="mt-5 text-3xl font-semibold">{priceLabel}</div>
            <p className="mt-6 text-lg leading-8 text-[var(--muted)]">{product.description ?? product.shortDescription}</p>

            <div className="mt-8 flex flex-wrap gap-4">
              <button type="button" onClick={addToCart} className="rounded-full bg-[var(--ink)] px-6 py-3 text-sm font-medium text-white">
                Add to cart
              </button>
              <Link href={`/?quote=product&product=${encodeURIComponent(product.name)}#contact`} className="rounded-full border border-[var(--ink)] bg-transparent px-6 py-3 text-sm font-medium text-[var(--ink)]">
                Request quote
              </Link>
            </div>
          </div>
        </section>

        <section className="mt-10 grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[28px] border border-[var(--line)] bg-white/70 p-6">
            <div className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Why it stands out</div>
            <ul className="mt-6 space-y-4 text-lg leading-8 text-[var(--muted)]">
              {(product.features ?? [
                "Built for durable daily use",
                "Premium design language for modern spaces",
                "Comfort-focused and high-performance",
              ]).map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-2 h-2.5 w-2.5 rounded-full bg-[var(--ink)]" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-[28px] border border-[var(--line)] bg-[var(--ink)] p-6 text-white">
            <div className="text-xs uppercase tracking-[0.24em] text-white/60">Overview</div>
            <div className="mt-6 space-y-5 text-base leading-7 text-white/80">
              <p>{product.shortDescription}</p>
              <p>Designed for users who want premium performance without compromising the design of home or studio spaces.</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
