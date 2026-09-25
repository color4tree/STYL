"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { addProductToCart, formatPrice, getCartCount, readCart } from "@/lib/cart";
import { API_BASE } from "@/lib/api";
import BrandLogo from "@/components/BrandLogo";
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
        setProduct(data.item?.publicationStatus === "draft" ? null : data.item as Product);
      } catch (error) {
        setProduct(null);
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
    return formatPrice(product.price, product.currency);
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

  const photos = getCatalogPhotos(product);
  const specifications = productSpecificationFields.filter((field) => product[field.key]?.trim());
  const features = product.features?.filter((feature) => feature.trim()) ?? [];
  const shortDescription = product.shortDescription?.trim();
  const description = product.description?.trim();

  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-12 text-[var(--ink)] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <Link href="/" aria-label="STYL home" className="mb-8 inline-flex">
          <BrandLogo markClassName="h-8 w-auto" />
        </Link>
        <div className="mb-8 flex items-center justify-between gap-4">
          <Link href="/" className="text-sm font-medium text-[var(--muted)]">
            ← Back to collection
          </Link>
          <Link href="/cart" className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium">
            Cart ({cartCount})
          </Link>
        </div>

        <section className={`grid gap-10 rounded-[32px] border border-[var(--line)] bg-white/70 p-6 md:p-8 ${photos.length ? "md:grid-cols-[1.1fr_0.9fr]" : ""}`}>
          {photos.length ? <PhotoGallery key={product.id} photos={photos} name={product.name} /> : null}

          <div className="min-w-0 break-words">
            <div className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">{product.category}</div>
            <h1 className="mt-4 text-4xl font-semibold tracking-[-0.06em] md:text-5xl">{product.name}</h1>
            <div className="mt-5 text-3xl font-semibold">{priceLabel}</div>
            {product.stockStatus?.trim() ? <p className="mt-3 text-sm font-medium">{product.stockStatus}</p> : null}
            {shortDescription ? <p className="mt-6 whitespace-pre-line text-lg leading-8 text-[var(--muted)]">{shortDescription}</p> : null}
            {specifications.length ? (
              <section className="my-5 border-t border-[var(--line)] pt-4">
                <h2 className="text-base font-semibold">Specifications</h2>
                <dl className="mt-3 space-y-3 text-sm">
                  {specifications.map((field) => (
                    <div key={field.key}>
                      <dt className="text-[var(--muted)]">{field.label}</dt>
                      <dd className="mt-1 whitespace-pre-line break-words">{product[field.key]}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : null}
            <CompatibilityDetails value={product.compatibility} />

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
    </main>
  );
}
