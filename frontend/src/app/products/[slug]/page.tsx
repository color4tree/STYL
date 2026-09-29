"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { formatPrice, getCartCount, MAX_ITEM_QUANTITY } from "@/lib/cart";
import { useCart } from "@/lib/useCart";
import { API_BASE } from "@/lib/api";
import StoreHeader from "@/components/StoreHeader";
import CartFeedback from "@/components/CartFeedback";
import AddToCartButton from "@/components/AddToCartButton";
import PhotoGallery from "@/components/PhotoGallery";
import { CompatibilityDetails } from "@/components/Compatibility";
import { getCatalogPhotos, productSpecificationFields, type CatalogDetails, type ProductSpecifications } from "@/lib/catalogDetails";

type Product = CatalogDetails & ProductSpecifications & {
  id: number;
  slug: string;
  name: string;
  category: string;
  price: number;
  currency: string;
  shortDescription: string;
  description?: string;
  image?: string;
  features?: string[];
};

export default function ProductDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug;
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolvedSlug, setResolvedSlug] = useState<string | null>(null);
  const { cart, add, loading: cartLoading, error, notice } = useCart();
  const action = useRef<HTMLDivElement>(null);
  const [actionVisible, setActionVisible] = useState(true);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!slug) return;
    let active = true;
    const controller = new AbortController();

    const loadProduct = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/products/${slug}`, { cache: "no-store", signal: controller.signal });
        if (!res.ok) {
          throw new Error("Equipment not found");
        }

        const data = await res.json();
        if (active) setProduct(data.item?.publicationStatus === "draft" ? null : data.item as Product);
      } catch (error) {
        if (!active) return;
        setProduct(null);
        console.error(error);
      } finally {
        if (active) { setLoading(false); setResolvedSlug(slug); }
      }
    };

    loadProduct();
    return () => { active = false; controller.abort(); };
  }, [slug, retry]);

  useEffect(() => {
    if (!action.current) return;
    const observer = new IntersectionObserver(([entry]) => setActionVisible(entry.isIntersecting));
    observer.observe(action.current);
    return () => observer.disconnect();
  }, [product]);

  if (loading || resolvedSlug !== slug) {
    return (
      <main className="min-h-screen bg-[var(--bg)] px-4 py-20 text-[var(--ink)]">
        <div className="mx-auto max-w-4xl text-lg text-[var(--muted)]">Loading equipment...</div>
      </main>
    );
  }

  if (!product) {
    return (
      <main className="min-h-screen bg-[var(--bg)] px-4 py-20 text-[var(--ink)]">
        <div className="mx-auto max-w-4xl">
          <h1 data-analytics-event="item_unavailable" className="text-3xl font-semibold">Equipment not found</h1>
          <button type="button" className="mt-4 min-h-11 rounded-full border px-5" onClick={() => { setLoading(true); setRetry(retry + 1); }}>Retry</button>
          <Link href="/" className="mt-6 inline-block rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white">
            Return home
          </Link>
        </div>
      </main>
    );
  }

  const photos = getCatalogPhotos(product);
  const specifications = productSpecificationFields.filter((field) => product[field.key]?.trim());
  const features = product.features?.filter((feature) => feature.trim()) ?? [];
  const shortDescription = product.shortDescription?.trim();
  const description = product.description?.trim();
  const priceLabel = formatPrice(product.price, product.currency);
  const atLimit = (cart.find((item) => item.id === product.id)?.quantity ?? 0) >= MAX_ITEM_QUANTITY;

  return (
    <>
    <StoreHeader cartCount={getCartCount(cart)} />
    <main className="min-h-screen bg-[var(--bg)] px-4 py-6 pb-32 text-[var(--ink)] sm:px-6 lg:px-8 lg:py-12">
      <div className="mx-auto max-w-6xl">
        <div className="mb-4">
          <Link href="/#products" data-analytics-action="back_to_collection" className="inline-flex min-h-11 items-center text-sm font-medium text-[var(--muted)]">
            ← Back to collection
          </Link>
        </div>
        <CartFeedback error={error} notice={notice} />

        <section data-analytics-event="item_detail_open" data-analytics-item-id={product.id} data-analytics-item-type="product" className={`grid gap-6 rounded-3xl border border-[var(--line)] bg-white/70 p-4 lg:gap-10 lg:p-8 ${photos.length ? "lg:grid-cols-[1.1fr_0.9fr]" : ""}`}>
          <div className={photos.length ? "lg:col-start-2 lg:row-start-1" : ""}>
            <div className="text-sm text-[var(--muted)]">{product.category}</div>
            <h1 data-analytics-identity className="mt-2 break-words text-3xl font-semibold tracking-tight lg:text-5xl">{product.name}</h1>
            <div data-analytics-price className="mt-4 text-2xl font-semibold">{priceLabel}</div>
            {product.stockStatus?.trim() ? <p className="mt-3 text-sm font-medium">{product.stockStatus}</p> : null}
          </div>
          {photos.length ? <div className="lg:col-start-1 lg:row-span-2 lg:row-start-1"><PhotoGallery key={product.id} photos={photos} name={product.name} item={{ itemType: "product", itemId: product.id }} /></div> : null}

          <div className="min-w-0 break-words">
            {shortDescription ? <p className="whitespace-pre-line text-base leading-7 text-[var(--muted)] lg:text-lg lg:leading-8">{shortDescription}</p> : null}
            <div ref={action} className="my-5 flex flex-wrap gap-3">
              <AddToCartButton key={product.id} disabled={cartLoading || Boolean(error)} atLimit={atLimit} onAdd={() => add(product)} className="min-h-12 rounded-full bg-[var(--ink)] px-6 py-3 font-medium text-white disabled:opacity-50" />
              <Link href={`/?quote=product&product=${encodeURIComponent(product.name)}&itemType=product&itemId=${product.id}#contact`} data-analytics-source="product" scroll={false} className="inline-flex min-h-12 items-center rounded-full border border-[var(--ink)] px-6 py-3 font-medium">
                Request quote
              </Link>
            </div>
            <CompatibilityDetails value={product.compatibility} />
            {specifications.length ? (
              <details className="my-5 border-t border-[var(--line)] pt-4" open>
                <summary className="min-h-11 text-base font-semibold">Specifications</summary>
                <dl className="mt-3 space-y-3 text-sm">
                  {specifications.map((field) => (
                    <div key={field.key}>
                      <dt className="text-[var(--muted)]">{field.label}</dt>
                      <dd className="mt-1 whitespace-pre-line break-words">{product[field.key]}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            ) : null}
          </div>
        </section>

        {features.length || description ? (
          <div className="mt-10 grid gap-8 md:grid-cols-2">
            {features.length ? (
              <section className="min-w-0 border-t border-[var(--line)] pt-5">
                <h2 className="text-lg font-semibold">Features</h2>
                <ul className="mt-4 list-inside list-disc space-y-3 break-words text-base leading-7 text-[var(--muted)]">
                  {features.map((feature, index) => <li key={index}>{feature}</li>)}
                </ul>
              </section>
            ) : null}
            {description ? (
              <section className="min-w-0 border-t border-[var(--line)] pt-5">
                <h2 className="text-lg font-semibold">Overview</h2>
                <p className="mt-4 whitespace-pre-line break-words text-base leading-7 text-[var(--muted)]">{description}</p>
              </section>
            ) : null}
          </div>
        ) : null}
      </div>
      {!actionVisible ? <div className="safe-action fixed inset-x-0 bottom-0 z-30 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--line)] bg-white p-3 lg:hidden"><span className="font-semibold">{priceLabel}</span><AddToCartButton key={product.id} disabled={cartLoading || Boolean(error)} atLimit={atLimit} onAdd={() => add(product)} className="min-h-12 rounded-full bg-[var(--ink)] px-5 py-3 text-white disabled:opacity-50" /></div> : null}
    </main>
    </>
  );
}
