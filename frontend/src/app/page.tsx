"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { formatPrice, getCartCount, MAX_ITEM_QUANTITY } from "@/lib/cart";
import { useCart } from "@/lib/useCart";
import { API_BASE, resolveProductImage } from "@/lib/api";
import StoreHeader from "@/components/StoreHeader";
import CartFeedback from "@/components/CartFeedback";
import InquiryForm from "@/components/InquiryForm";
import PhotoGallery from "@/components/PhotoGallery";
import { getCatalogPhotos, type CatalogDetails } from "@/lib/catalogDetails";
import { defaultHero, fetchHero, formatHeroPriceLabel, type Hero } from "@/lib/hero";

type Product = CatalogDetails & {
  id: number;
  slug: string;
  name: string;
  category: string;
  price: number;
  currency: string;
  shortDescription: string;
  featured?: boolean;
};

const brandAssets = [
  { name: "Signature shield", description: "Laser-etched into brushed stainless steel on every frame upright.", file: "/images/brand/logo-plate.jpg" },
  { name: "J-hook", description: "Rubber-lined steel hooks that protect the bar and carry the wordmark.", file: "/images/brand/j-hook.jpg" },
  { name: "Cable swivel plate", description: "Machined plate and 360° swivel for smooth, tangle-free cable work.", file: "/images/brand/cable-swivel.jpg" },
  { name: "Frame badge", description: "Brushed steel badge finishing the top crossmember of the multi trainer.", file: "/images/brand/frame-badge.jpg" },
];

export default function Home() {
  const [products, setProducts] = useState<Product[]>([]);
  const [catalogError, setCatalogError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [hero, setHero] = useState<Hero>(defaultHero);
  const { cart, add, error, notice } = useCart();
  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/api/products`).then(async (response) => {
      if (!response.ok) throw new Error("Unable to load products.");
      const data = await response.json();
      if (!Array.isArray(data.items)) throw new Error("Invalid catalog response.");
      if (active) {
        setProducts((data.items as Product[]).sort((a, b) => Number(Boolean(b.featured)) - Number(Boolean(a.featured))));
        setCatalogError(false);
      }
    }).catch((error) => { console.error(error); if (active) setCatalogError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);
  useEffect(() => {
    fetchHero().then(setHero).catch((error) => console.error("Using default home banner:", error));
  }, []);

  return (
    <>
      <StoreHeader cartCount={getCartCount(cart)} />
      <main className="min-h-screen bg-[var(--bg)] text-[var(--ink)]">
        <section className="container grid gap-5 py-8 lg:grid-cols-[1.25fr_0.75fr] lg:items-center lg:gap-12 lg:py-20">
          <div>
            <p className="text-sm font-medium text-[var(--muted)]">Premium performance, minimal form</p>
            <h1 className="mt-3 max-w-xl text-4xl font-semibold tracking-[-0.05em] lg:text-6xl">Build strength with a cleaner standard.</h1>
            <p className="mt-4 max-w-lg text-base leading-7 text-[var(--muted)] lg:mt-6 lg:text-lg lg:leading-8">
              Premium fitness equipment designed for modern living. Precise, dependable, and built for your training space.
            </p>
            <div className="mt-5 flex flex-wrap gap-3 lg:mt-8">
              <a href="#products" className="inline-flex min-h-12 items-center rounded-full bg-[var(--ink)] px-5 py-3 font-medium text-white">Shop equipment</a>
              <Link href="/accessories" className="inline-flex min-h-12 items-center rounded-full border border-[var(--ink)] px-5 py-3 font-medium">Accessories</Link>
            </div>
          </div>
          <div className="rounded-3xl bg-[linear-gradient(135deg,#1c1c1c,#504639)] p-4 text-white lg:p-7">
            <div className="flex items-center justify-between text-sm text-white/80"><span>{hero.tag}</span><span>{hero.number}</span></div>
            <img src={resolveProductImage(hero.image)} alt={`${hero.eyebrow} ${hero.title}`.trim() || "STYL equipment"} fetchPriority="high" className="mt-3 h-32 w-full rounded-xl bg-white/10 object-cover sm:h-48 lg:mt-8 lg:h-64" />
            <div className="mt-3 flex flex-wrap items-end justify-between gap-2">
              <div><p className="text-sm text-white/80">{hero.eyebrow}</p><p className="text-2xl font-semibold">{hero.title}</p></div>
              <span className="text-lg font-medium">{formatHeroPriceLabel(hero.priceLabel)}</span>
            </div>
          </div>
        </section>

        <section id="products" className="container scroll-mt-24 py-8 lg:py-12">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3 lg:mb-10">
            <div><p className="text-sm text-[var(--muted)]">Equipment collection</p><h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] lg:text-5xl">Precision-built for real routines.</h2></div>
            <Link href="/accessories" className="inline-flex min-h-11 items-center text-sm font-medium underline">Browse accessories</Link>
          </div>
          <CartFeedback error={error} notice={notice} />
          {loading ? <p role="status" className="rounded-2xl bg-white/60 p-8">Loading equipment...</p>
            : catalogError ? <div role="alert"><p>Products are unavailable right now.</p><button type="button" className="mt-3 min-h-11 rounded-full border px-5" onClick={() => { setLoading(true); setRetry(retry + 1); }}>Retry</button></div>
              : !products.length ? <p>No products are currently available.</p>
                : <div className="grid items-start gap-6 md:grid-cols-2 xl:grid-cols-3">
                  {products.map((product) => {
                    const atLimit = (cart.find((item) => item.id === product.id)?.quantity ?? 0) >= MAX_ITEM_QUANTITY;
                    return <article key={product.id} className="soft-panel min-w-0 rounded-3xl p-4 lg:p-5">
                      <PhotoGallery photos={getCatalogPhotos(product)} name={product.name} compact />
                      <div className="mt-4 flex flex-wrap items-center justify-between gap-2"><span className="text-sm text-[var(--muted)]">{product.category}</span><span className="text-lg font-semibold">{formatPrice(product.price, product.currency)}</span></div>
                      <h3 className="mt-2 break-words text-2xl font-semibold"><Link href={`/products/${product.slug}`} className="hover:underline">{product.name}</Link></h3>
                      {product.shortDescription?.trim() ? <p className="mt-3 leading-7 text-[var(--muted)]">{product.shortDescription}</p> : null}
                      <div className="mt-5 flex flex-wrap gap-3">
                        <button type="button" disabled={atLimit} onClick={() => add(product)} className="min-h-12 flex-1 rounded-full bg-[var(--ink)] px-4 py-3 text-sm font-medium text-white disabled:opacity-50">{atLimit ? "Maximum 10 in cart" : "Add to cart"}</button>
                        <Link href={`/products/${product.slug}`} className="inline-flex min-h-12 items-center rounded-full border border-[var(--line)] px-5 py-3 text-sm font-medium">Details</Link>
                      </div>
                    </article>;
                  })}
                </div>}
        </section>

        <section id="about" className="scroll-mt-24 bg-[#171717] py-10 text-white lg:my-10 lg:py-16">
          <div className="container grid gap-6 lg:grid-cols-2 lg:gap-12">
            <div><p className="text-sm text-white/75">Why STYL</p><h2 className="mt-3 text-3xl font-semibold tracking-tight lg:text-5xl">Design for performance and everyday life.</h2></div>
            <div className="space-y-5 leading-7 text-white/80">
              <p>STYL exists for people who want better routines without sacrificing the aesthetic of their space. Our equipment is engineered to be dependable, calm, and beautifully integrated into real homes and workspaces.</p>
              <p>We combine premium materials, disciplined design, and a refined user experience.</p>
              <blockquote className="border-l-2 border-white/60 pl-4"><p className="text-sm font-medium text-white">Our business principle</p><p className="mt-2">Maximize customer value first, then capture a fair share of the value created.</p></blockquote>
            </div>
          </div>
        </section>

        <section className="container grid items-start gap-6 py-10 lg:grid-cols-[0.8fr_1.2fr] lg:py-16">
          <div>
            <h2 className="text-2xl font-semibold">Build your selection</h2>
            <p className="mt-3 leading-7 text-[var(--muted)]">Explore equipment and accessories, then send your selection for pricing and delivery details.</p>
            {cart.length ? <div className="soft-panel mt-5 rounded-2xl p-5"><p className="font-semibold">{getCartCount(cart)} sale units selected</p><Link href="/cart" className="mt-3 inline-flex min-h-12 items-center rounded-full border border-[var(--ink)] px-5">Review your cart</Link></div> : null}
            <p className="mt-5 text-sm text-[var(--muted)]">Already know what you need? Use the quote form.</p>
          </div>
          <InquiryForm />
        </section>

        <section id="gallery" className="container scroll-mt-24 pb-12">
          <details className="rounded-3xl border border-[var(--line)] bg-white/60 p-5 lg:p-7">
            <summary className="min-h-11 text-xl font-semibold">Explore our engineering details</summary>
            <p className="mt-3 text-[var(--muted)]">Our mark, engineered into every piece.</p>
            <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {brandAssets.map((asset) => <article key={asset.name} className="min-w-0"><img src={asset.file} loading="lazy" alt={asset.name} className="aspect-[4/3] w-full rounded-xl object-cover" /><h3 className="mt-3 text-xl font-semibold">{asset.name}</h3><p className="mt-2 text-sm leading-6 text-[var(--muted)]">{asset.description}</p></article>)}
            </div>
          </details>
        </section>
      </main>
    </>
  );
}
