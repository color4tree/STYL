"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { addProductToCart, formatCartSummary, formatPrice, getCartCount, getCartTotals, MAX_ITEM_QUANTITY, readCart, updateCartQuantity, type CartItem } from "@/lib/cart";
import { API_BASE, resolveProductImage } from "@/lib/api";
import BrandLogo from "@/components/BrandLogo";
import { defaultHero, fetchHero, type Hero } from "@/lib/hero";

type Product = {
  id: number;
  slug: string;
  name: string;
  category: string;
  price: number;
  currency: string;
  shortDescription: string;
  description?: string;
  featured?: boolean;
  image?: string;
  features?: string[];
};

const brandAssets = [
  {
    name: "Signature shield",
    category: "Brand mark",
    description: "Laser-etched into brushed stainless steel on every frame upright.",
    file: "/images/brand/logo-plate.jpg",
  },
  {
    name: "J-hook",
    category: "Rack hardware",
    description: "Rubber-lined steel hooks that protect the bar and carry the wordmark.",
    file: "/images/brand/j-hook.jpg",
  },
  {
    name: "Cable swivel plate",
    category: "Cable system",
    description: "Machined plate and 360° swivel for smooth, tangle-free cable work.",
    file: "/images/brand/cable-swivel.jpg",
  },
  {
    name: "Frame badge",
    category: "Crossmember",
    description: "Brushed steel badge finishing the top crossmember of the multi trainer.",
    file: "/images/brand/frame-badge.jpg",
  },
];

export default function Home() {
  const [products, setProducts] = useState<Product[]>([]);
  const [catalogError, setCatalogError] = useState(false);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [inquiry, setInquiry] = useState({
    name: "",
    email: "",
    phone: "",
    company: "",
    message: "",
  });
  const [submitStatus, setSubmitStatus] = useState<string | null>(null);
  const [hero, setHero] = useState<Hero>(defaultHero);

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/products`);
        if (!res.ok) {
          throw new Error("Failed to fetch products");
        }

        const data = await res.json();
        if (Array.isArray(data.items)) {
          setProducts(data.items as Product[]);
        }
      } catch (error) {
        console.error("Unable to load products:", error);
        setCatalogError(true);
      } finally {
        setLoading(false);
      }
    };

    const savedCart = readCart();
    setCart(savedCart);

    const params = new URLSearchParams(window.location.search);
    const intent = params.get("quote");
    const productName = params.get("product");

    if (intent === "cart" && savedCart.length > 0) {
      setInquiry((current) => ({
        ...current,
        message: `${formatCartSummary(savedCart)} Please share final pricing and delivery details.`,
      }));
    }

    if (intent === "product" && productName) {
      setInquiry((current) => ({
        ...current,
        message: `I am interested in ${productName}. Please share the available options, pricing, and lead time.`,
      }));
    }

    fetchProducts();
    fetchHero()
      .then(setHero)
      .catch((error) => console.error("Using default home banner:", error));
  }, []);

  const totals = useMemo(
    () => getCartTotals(cart),
    [cart],
  );

  const addToCart = (product: Product) => {
    const nextCart = addProductToCart(product);
    setCart(nextCart);
  };

  const updateQuantity = (id: number, delta: number) => {
    const nextCart = updateCartQuantity(id, delta);
    setCart(nextCart);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    try {
      const res = await fetch(`${API_BASE}/api/inquiries`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: inquiry.name,
          email: inquiry.email,
          phone: inquiry.phone,
          company: inquiry.company,
          message: inquiry.message,
          source: "website",
        }),
      });

      if (!res.ok) {
        throw new Error("Inquiry submission failed");
      }

      setSubmitStatus("Inquiry received. Our team will contact you shortly.");
      setInquiry({ name: "", email: "", phone: "", company: "", message: "" });
    } catch (error) {
      console.error(error);
      setSubmitStatus("Something went wrong. Please try again later.");
    }
  };

  return (
    <main className="min-h-screen bg-[var(--bg)] pt-[81px] text-[var(--ink)]">
      <header className="fixed inset-x-0 top-0 z-50 border-b border-[var(--line)] bg-white/90 shadow-[0_8px_30px_rgba(17,17,17,0.05)] backdrop-blur-xl">
        <div className="container flex items-center justify-between py-5">
          <Link href="/" aria-label="STYL home">
            <BrandLogo markClassName="h-9 w-auto" />
          </Link>

          <nav className="hidden items-center gap-8 text-sm text-[var(--muted)] md:flex">
            <a href="#about">About</a>
            <a href="#products">Products</a>
            <Link href="/accessories">Accessories</Link>
            <a href="#contact">Contact</a>
          </nav>

          <div className="flex items-center gap-3">
            <Link href="/cart" className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium text-[var(--ink)]">
              Cart ({getCartCount(cart)})
            </Link>
            <a href="/#contact" className="rounded-full bg-[var(--ink)] px-5 py-2.5 text-sm font-medium text-white">
              Request a quote
            </a>
          </div>
        </div>
      </header>

      <section className="container grid gap-10 pt-16 pb-8 lg:grid-cols-[1.25fr_0.75fr] lg:items-center lg:pt-24">
        <div>
          <div className="mb-5 inline-flex rounded-full border border-[var(--line)] bg-white/70 px-3 py-1.5 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
            Premium performance, minimal form
          </div>

          <h1 className="max-w-xl text-5xl font-semibold tracking-[-0.06em] text-[var(--ink)] md:text-6xl">
            Build strength with a cleaner standard.
          </h1>

          <p className="mt-6 max-w-lg text-lg leading-8 text-[var(--muted)]">
            STYL creates premium fitness equipment designed for modern living—quiet,
            precise, and built to fit beautifully into your routine.
          </p>

          <div className="mt-8 flex flex-wrap gap-4">
            <a href="#products" className="rounded-full bg-[var(--ink)] px-6 py-3 text-sm font-medium text-white">
              Shop collection
            </a>
            <a href="#about" className="rounded-full border border-[var(--ink)] bg-transparent px-6 py-3 text-sm font-medium text-[var(--ink)]">
              Explore products
            </a>
          </div>

          <blockquote className="mt-10 max-w-lg border-l-2 border-[var(--ink)] pl-5">
            <div className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">
              Our business principle
            </div>
            <p className="mt-3 text-xl font-medium leading-8 tracking-[-0.02em] text-[var(--ink)]">
              Maximize customer value first, then capture a fair share of the value created.
            </p>
          </blockquote>
        </div>

        <div className="soft-panel rounded-[32px] p-6 shadow-[0_20px_60px_rgba(17,17,17,0.08)]">
          <div className="rounded-[28px] bg-[linear-gradient(135deg,#1c1c1c,#504639)] p-6 text-white">
            <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] text-white/70">
              <span>{hero.tag}</span>
              <span>{hero.number}</span>
            </div>
            <div className="mt-12 rounded-[24px] bg-white/10 p-6 backdrop-blur-sm">
              <img
                src={resolveProductImage(hero.image)}
                alt={`${hero.eyebrow} ${hero.title}`.trim() || "STYL signature equipment"}
                className="mb-4 h-52 w-full rounded-[20px] object-cover"
              />
              <div className="flex items-end justify-between gap-4">
                <div>
                  <div className="text-xs uppercase tracking-[0.22em] text-white/60">
                    {hero.eyebrow}
                  </div>
                  <div className="mt-2 text-2xl font-semibold">{hero.title}</div>
                </div>
                <div className="text-xl font-medium">{hero.priceLabel}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="products" className="container scroll-mt-24 pt-8 pb-20">
        <div className="mb-10 flex items-end justify-between gap-6">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">
              Curated collection
            </div>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.05em] md:text-5xl">
              Precision-built for real routines.
            </h2>
          </div>
          <a href="#contact" className="text-sm font-medium text-[var(--ink)]">
            View all products →
          </a>
        </div>

        {loading ? (
          <div className="text-[var(--muted)]">Loading products...</div>
        ) : catalogError ? (
          <p className="text-[var(--muted)]">Products are unavailable right now. Please try again later.</p>
        ) : products.length === 0 ? (
          <p className="text-[var(--muted)]">No products are currently available.</p>
        ) : (
          <div className="grid gap-7 md:grid-cols-3">
            {products.map((product) => (
              <article key={product.id} className="soft-panel rounded-[28px] p-5 shadow-[0_16px_40px_rgba(17,17,17,0.04)]">
                <div className="overflow-hidden rounded-[22px] bg-[#efeae4]">
                  <img
                    src={resolveProductImage(product.image)}
                    alt={product.name}
                    className="h-64 w-full object-cover"
                  />
                </div>
                <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                  <span className="text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
                    {product.category}
                  </span>
                  <span className="text-lg font-semibold">{formatPrice(product.price, product.currency)}</span>
                </div>
                <h3 className="mt-4 text-2xl font-semibold tracking-[-0.04em]">
                  {product.name}
                </h3>
                {product.shortDescription?.trim() ? <p className="mt-3 text-base leading-7 text-[var(--muted)]">
                  {product.shortDescription}
                </p> : null}
                <div className="mt-6 flex gap-3">
                  <button
                    type="button"
                    onClick={() => addToCart(product)}
                    className="flex-1 rounded-full bg-[var(--ink)] px-4 py-3 text-sm font-medium text-white"
                  >
                    Add to cart
                  </button>
                  <Link
                    href={`/products/${product.slug}`}
                    className="flex items-center justify-center rounded-full border border-[var(--line)] bg-white px-4 py-3 text-sm font-medium text-[var(--ink)]"
                  >
                    Details
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section id="gallery" className="container scroll-mt-24 py-20">
        <div className="mb-10 flex items-end justify-between gap-6">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-[var(--muted)]">
              Brand details
            </div>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.05em] md:text-5xl">
              Our mark, engineered into every piece.
            </h2>
          </div>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {brandAssets.map((asset) => (
            <article key={asset.name} className="group overflow-hidden rounded-[28px] border border-[var(--line)] bg-white p-4 shadow-[0_18px_44px_rgba(17,17,17,0.04)]">
              <div className="overflow-hidden rounded-[22px] bg-[#f3efe9]">
                <img
                  src={asset.file}
                  alt={asset.name}
                  className="aspect-[4/5] w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                />
              </div>
              <div className="mt-5">
                <div className="text-xs uppercase tracking-[0.2em] text-[var(--muted)]">{asset.category}</div>
                <h3 className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{asset.name}</h3>
                <p className="mt-2 text-base leading-7 text-[var(--muted)]">{asset.description}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="about" className="scroll-mt-24 bg-[#171717] py-20 text-white">
        <div className="container grid gap-10 lg:grid-cols-[1fr_1fr] lg:items-center">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-white/60">
              Why STYL
            </div>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.05em] md:text-5xl">
              Design for performance and everyday life.
            </h2>
          </div>
          <div className="space-y-6 text-lg leading-8 text-white/75">
            <p>
              STYL exists for people who want better routines without sacrificing the
              aesthetic of their space. Our equipment is engineered to be dependable,
              calm, and beautifully integrated into real homes and workspaces.
            </p>
            <p>
              We combine premium materials, disciplined design, and a refined user
              experience so that every interaction feels as considered as the product itself.
            </p>
          </div>
        </div>
      </section>

      <section className="container grid gap-8 py-20 lg:grid-cols-[1fr_0.8fr]">
        <div className="soft-panel rounded-[28px] p-6">
          <div className="mb-6 text-xs uppercase tracking-[0.24em] text-[var(--muted)]">
            Cart overview
          </div>
          <div className="space-y-4">
            {cart.length === 0 ? (
              <div className="rounded-2xl bg-[#f8f5f2] p-4 text-[var(--muted)]">
                Your cart is empty.
              </div>
            ) : (
              cart.map((item) => (
                <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-[#f8f5f2] p-4">
                  <div className="min-w-0 break-words">
                    <div className="font-medium">{item.name}</div>
                    <div className="text-sm text-[var(--muted)]">Qty: {item.quantity}</div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="font-medium">{formatPrice(item.price * item.quantity, item.currency)}</div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.id, -1)}
                        className="h-8 w-8 rounded-full border border-[var(--line)] bg-white text-lg"
                      >
                        −
                      </button>
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.id, 1)}
                        disabled={item.quantity >= MAX_ITEM_QUANTITY}
                        className="h-8 w-8 rounded-full border border-[var(--line)] bg-white text-lg disabled:opacity-40"
                      >
                        +
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
          {totals.length ? (
            <div className="mt-6 space-y-2 border-t border-[var(--line)] pt-5 text-lg font-semibold">
              {totals.map(([currency, total]) => (
                <div key={currency} className="flex flex-wrap items-center justify-between gap-2">
                  <span>Total</span>
                  <span>{formatPrice(total, currency)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div id="contact" className="soft-panel scroll-mt-24 rounded-[28px] p-6">
          <div className="mb-6 text-xs uppercase tracking-[0.24em] text-[var(--muted)]">
            Request a quote
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <input
                value={inquiry.name}
                onChange={(event) => setInquiry((current) => ({ ...current, name: event.target.value }))}
                className="w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3 outline-none"
                placeholder="Name"
                required
              />
              <input
                type="email"
                value={inquiry.email}
                onChange={(event) => setInquiry((current) => ({ ...current, email: event.target.value }))}
                className="w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3 outline-none"
                placeholder="Email"
                required
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <input
                type="tel"
                value={inquiry.phone}
                onChange={(event) => setInquiry((current) => ({ ...current, phone: event.target.value }))}
                className="w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3 outline-none"
                placeholder="Phone"
              />
              <input
                value={inquiry.company}
                onChange={(event) => setInquiry((current) => ({ ...current, company: event.target.value }))}
                className="w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3 outline-none"
                placeholder="Company / Studio"
              />
            </div>

            <textarea
              value={inquiry.message}
              onChange={(event) => setInquiry((current) => ({ ...current, message: event.target.value }))}
              className="min-h-32 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3 outline-none"
              placeholder="Tell us about your project"
              required
            />
            <button type="submit" className="w-full rounded-full bg-[var(--ink)] px-4 py-3 text-sm font-medium text-white">
              Submit inquiry
            </button>
            {submitStatus ? <p className="text-sm text-[var(--muted)]">{submitStatus}</p> : null}
          </form>
        </div>
      </section>
    </main>
  );
}
