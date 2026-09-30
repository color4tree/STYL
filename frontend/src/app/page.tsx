"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { getCartCount } from "@/lib/cart";
import { useCart } from "@/lib/useCart";
import { resolveProductImage } from "@/lib/api";
import StoreHeader from "@/components/StoreHeader";
import CartFeedback from "@/components/CartFeedback";
import InquiryForm from "@/components/InquiryForm";
import CatalogGrid from "@/components/CatalogGrid";
import CatalogViewSync from "@/components/CatalogViewSync";
import { catalogViews, fetchPublicCatalog, type CatalogEntry, type CatalogView, type PublicCatalogItem } from "@/lib/publicCatalog";
import { defaultHero, fetchHero, type Hero } from "@/lib/hero";
import { useQuoteNavigation } from "@/lib/useQuoteNavigation";
import { trackAnalytics } from "@/lib/analytics";

const brandAssets = [
  { name: "Signature shield", description: "Laser-etched into brushed stainless steel on every frame upright.", file: "/images/brand/logo-plate.jpg" },
  { name: "J-hook", description: "Rubber-lined steel hooks that protect the bar and carry the wordmark.", file: "/images/brand/j-hook.jpg" },
  { name: "Cable swivel plate", description: "Machined plate and 360° swivel for smooth, tangle-free cable work.", file: "/images/brand/cable-swivel.jpg" },
  { name: "Frame badge", description: "Brushed steel badge finishing the top crossmember of the multi trainer.", file: "/images/brand/frame-badge.jpg" },
];

export default function Home() {
  const [products, setProducts] = useState<PublicCatalogItem[]>([]);
  const [accessories, setAccessories] = useState<PublicCatalogItem[]>([]);
  const [view, setView] = useState<CatalogView>("all");
  const [catalogError, setCatalogError] = useState(false);
  const [accessoryError, setAccessoryError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [accessoryLoading, setAccessoryLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [hero, setHero] = useState<Hero>(defaultHero);
  const [heroLoading, setHeroLoading] = useState(true);
  const { cart, add, loading: cartLoading, error, notice } = useCart();
  useQuoteNavigation(!loading && !accessoryLoading && !heroLoading && !cartLoading);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    fetchPublicCatalog("products", controller.signal).then((items) => {
      if (active) {
        setProducts(items);
        setCatalogError(false);
      }
    }).catch((error) => { if (active) { console.error(error); setCatalogError(true); } })
      .finally(() => { if (active) setLoading(false); });
    fetchPublicCatalog("accessories", controller.signal).then((items) => {
      if (active) { setAccessories(items); setAccessoryError(false); }
    }).catch((error) => { if (active) { console.error(error); setAccessoryError(true); } })
      .finally(() => { if (active) setAccessoryLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [retry]);
  useEffect(() => {
    let active = true;
    fetchHero().then((item) => { if (active) setHero(item); })
      .catch((error) => console.error("Unable to load home banner; using defaults:", error))
      .finally(() => { if (active) setHeroLoading(false); });
    return () => { active = false; };
  }, []);

  const entries: CatalogEntry[] = [
    ...(view !== "accessories" ? products.map(item => ({ item, itemType: "product" as const })) : []),
    ...(view !== "equipment" ? accessories.map(item => ({ item, itemType: "accessory" as const })) : []),
  ];
  const selectedLoading = (view !== "accessories" && loading) || (view !== "equipment" && accessoryLoading);
  const selectedError = (view !== "accessories" && catalogError) || (view !== "equipment" && accessoryError);
  const label = catalogViews.find(entry => entry.view === view)!.label;

  return (
    <>
      <Suspense fallback={null}><CatalogViewSync onChange={setView} /></Suspense>
      <StoreHeader cartCount={getCartCount(cart)} />
      <main className="min-h-screen bg-[var(--bg)] text-[var(--ink)]">
        <section className="container grid gap-5 py-8 lg:grid-cols-[1.25fr_0.75fr] lg:items-center lg:gap-12 lg:py-20">
          <div>
            <p className="text-sm font-medium text-[var(--muted)]">Premium performance, minimal form</p>
            <h1 className="mt-3 max-w-xl text-4xl font-semibold tracking-[-0.05em] lg:text-6xl">Build strength with a cleaner standard.</h1>
            <p className="mt-4 max-w-lg text-base leading-7 text-[var(--muted)] lg:mt-6 lg:text-lg lg:leading-8">
              Premium fitness equipment designed for modern living. Precise, dependable, and built for your training space.
            </p>
            <blockquote className="mt-5 max-w-xl border-l-2 border-[var(--accent-strong)] pl-4">
              <p className="text-sm font-medium text-[var(--muted)]">Our business principle</p>
              <p className="mt-2 text-base font-medium leading-6 lg:text-lg lg:leading-7">
                Maximize customer value first, then capture a fair share of the value created.
              </p>
            </blockquote>
            <div className="mt-5 flex flex-wrap gap-3 lg:mt-8">
              {catalogViews.map(entry => <Link key={entry.view} href={entry.href} aria-current={view === entry.view ? "page" : undefined}
                className={`inline-flex min-h-12 items-center rounded-full border border-[var(--ink)] px-3 py-3 font-medium sm:px-5 ${view === entry.view ? "bg-[var(--ink)] text-white" : ""}`}>
                {entry.label}
              </Link>)}
            </div>
          </div>
          <aside aria-label="Home banner" className="hidden rounded-3xl bg-[linear-gradient(135deg,#1c1c1c,#504639)] p-4 text-white md:block lg:p-7">
            <div className="flex items-center justify-between text-sm text-white/80"><span>{hero.tag}</span><span>{hero.number}</span></div>
            <img src={resolveProductImage(hero.image)} alt={`${hero.eyebrow} ${hero.title}`.trim() || "STYL equipment"} fetchPriority="high" className="mt-3 h-32 w-full rounded-xl bg-white/10 object-cover sm:h-48 lg:mt-8 lg:h-64" />
            <div className="mt-3">
              <p className="text-sm text-white/80">{hero.eyebrow}</p>
              <p className="text-2xl font-semibold">{hero.title}</p>
            </div>
          </aside>
        </section>

        <section id="products" data-catalog-view={view} aria-busy={selectedLoading} className="container scroll-mt-32 py-8 lg:scroll-mt-24 lg:py-12">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3 lg:mb-10">
            <div><p className="text-sm text-[var(--muted)]">{label}</p><h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] lg:text-5xl">Precision-built for real routines.</h2></div>
          </div>
          <CartFeedback error={error} notice={notice} />
          {selectedLoading ? <p role="status" className="rounded-2xl bg-white/60 p-8">Loading {label.toLowerCase()}...</p>
            : selectedError ? <div role="alert" data-analytics-event="site_error"><p>{view === "all" ? "The complete catalog is unavailable right now. Please retry or choose a specific catalog." : `${label} ${view === "equipment" ? "is" : "are"} unavailable right now.`}</p><button type="button" className="mt-3 min-h-11 rounded-full border px-5" onClick={() => { setLoading(true); setAccessoryLoading(true); setRetry(retry + 1); }}>Retry</button></div>
              : !entries.length ? <p data-analytics-event="catalog_empty" data-analytics-list={view === "accessories" ? "accessories" : "products"}>No {view === "all" ? "products" : view} {view === "equipment" ? "is" : "are"} currently available.</p>
                : <CatalogGrid entries={entries} cart={cart} add={add} disabled={cartLoading || Boolean(error)} />}
        </section>

        <section id="about" className="scroll-mt-32 bg-[#171717] py-10 text-white lg:my-10 lg:scroll-mt-24 lg:py-16">
          <div className="container grid gap-6 lg:grid-cols-2 lg:gap-12">
            <div><p className="text-sm text-white/75">Why STYL</p><h2 className="mt-3 text-3xl font-semibold tracking-tight lg:text-5xl">Design for performance and everyday life.</h2></div>
            <div className="space-y-5 leading-7 text-white/80">
              <p>STYL exists for people who want better routines without sacrificing the aesthetic of their space. Our equipment is engineered to be dependable, calm, and beautifully integrated into real homes and workspaces.</p>
              <p>We combine premium materials, disciplined design, and a refined user experience.</p>
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

        <section id="gallery" className="container scroll-mt-32 pb-12 lg:scroll-mt-24">
          <details onToggle={(event) => { if (event.currentTarget.open) trackAnalytics("media_open", { mediaType: "image" }); }} className="rounded-3xl border border-[var(--line)] bg-white/60 p-5 lg:p-7">
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
