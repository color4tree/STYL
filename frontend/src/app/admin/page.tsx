"use client";

import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { API_BASE, resolveProductImage } from "@/lib/api";

type Product = {
  id: number;
  slug: string;
  name: string;
  category: string;
  price: number;
  currency: string;
  shortDescription: string;
  description: string;
  featured: boolean;
  image: string;
  features: string[];
};

const emptyProduct: Omit<Product, "id" | "slug"> = {
  name: "",
  category: "",
  price: 0,
  currency: "USD",
  shortDescription: "",
  description: "",
  featured: false,
  image: "/images/pro-elite.svg",
  features: [""],
};

export default function AdminPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<Omit<Product, "id" | "slug">>(emptyProduct);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    loadProducts();
  }, []);

  const loadProducts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/products`);
      if (!res.ok) {
        throw new Error("Unable to fetch products");
      }

      const data = await res.json();
      const items = Array.isArray(data.items) ? (data.items as Product[]) : [];
      setProducts(items);

      if (items.length > 0) {
        setSelectedId(items[0].id);
        setForm(toFormState(items[0]));
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load products.");
    } finally {
      setLoading(false);
    }
  };

  const toFormState = (product: Product): Omit<Product, "id" | "slug"> => ({
    name: product.name,
    category: product.category,
    price: product.price,
    currency: product.currency,
    shortDescription: product.shortDescription,
    description: product.description,
    featured: product.featured,
    image: product.image,
    features: product.features.length > 0 ? product.features : [""],
  });

  const updateField = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const updateFeature = (index: number, value: string) => {
    setForm((current) => ({
      ...current,
      features: current.features.map((feature, featureIndex) =>
        featureIndex === index ? value : feature,
      ),
    }));
  };

  const addFeature = () => {
    setForm((current) => ({
      ...current,
      features: [...current.features, ""],
    }));
  };

  const removeFeature = (index: number) => {
    setForm((current) => ({
      ...current,
      features: current.features.filter((_, featureIndex) => featureIndex !== index),
    }));
  };

  const selectProduct = (product: Product) => {
    setSelectedId(product.id);
    setForm(toFormState(product));
  };

  const resetForm = () => {
    setForm(emptyProduct);
    setSelectedId(null);
    setMessage(null);
  };

  const uploadImage = async (event: ChangeEvent<HTMLInputElement>) => {
    const image = event.target.files?.[0];
    event.target.value = "";
    if (!image) return;

    setUploading(true);
    setMessage(null);

    try {
      const body = new FormData();
      body.append("image", image);
      const res = await fetch(`${API_BASE}/api/uploads/product-image`, {
        method: "POST",
        body,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? "Unable to upload image.");
      }

      updateField("image", data.image as string);
      setMessage("Photo uploaded. Save changes to publish it.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to upload image.");
    } finally {
      setUploading(false);
    }
  };

  const saveProduct = async () => {
    if (!form.name.trim() || !form.category.trim()) {
      setMessage("Name and category are required.");
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const payload = {
        ...form,
        name: form.name.trim(),
        category: form.category.trim(),
        price: Number(form.price || 0),
        features: form.features.map((feature) => feature.trim()).filter(Boolean),
      };

      const method = selectedId ? "PUT" : "POST";
      const url = selectedId ? `${API_BASE}/api/products/${selectedId}` : `${API_BASE}/api/products`;

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "Unable to save product.";
        throw new Error(detail);
      }
      const saved = data.item as Product;

      setProducts((current) => {
        if (selectedId) {
          return current.map((product) => (product.id === selectedId ? saved : product));
        }
        return [...current, saved];
      });

      setSelectedId(saved.id);
      setForm(toFormState(saved));
      setMessage("Product saved successfully.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save product.");
    } finally {
      setSaving(false);
    }
  };

  const totalValue = useMemo(
    () => products.reduce((sum, product) => sum + product.price, 0),
    [products],
  );

  if (loading) {
    return <main className="min-h-screen bg-[var(--bg)] px-4 py-16 text-[var(--ink)]">Loading admin catalog...</main>;
  }

  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-12 text-[var(--ink)] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 flex flex-col justify-between gap-4 border-b border-[var(--line)] pb-6 md:flex-row md:items-end">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Admin</div>
            <h1 className="mt-3 text-4xl font-semibold tracking-[-0.06em]">Product management</h1>
          </div>
          <div className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium text-[var(--muted)]">
            {products.length} products · ${totalValue.toLocaleString()} total value
          </div>
        </header>

        <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr]">
          <aside className="rounded-[28px] border border-[var(--line)] bg-white/80 p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Catalog</h2>
              <button type="button" onClick={resetForm} className="rounded-full border border-[var(--line)] px-3 py-1.5 text-sm font-medium">
                New
              </button>
            </div>

            <div className="space-y-3">
              {products.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => selectProduct(product)}
                  className={`w-full rounded-[22px] border p-3 text-left transition ${selectedId === product.id ? "border-[var(--ink)] bg-[#f5f1ea]" : "border-[var(--line)] bg-white"}`}
                >
                  <div className="flex items-center gap-3">
                    <img src={resolveProductImage(product.image)} alt={product.name} className="h-14 w-14 rounded-xl object-cover" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold">{product.name}</div>
                      <div className="mt-1 text-xs uppercase tracking-[0.16em] text-[var(--muted)]">{product.category}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <section className="rounded-[28px] border border-[var(--line)] bg-white/80 p-6">
            <div className="grid gap-5 md:grid-cols-2">
              <label className="block text-sm font-medium">
                Product name
                <input
                  value={form.name}
                  onChange={(event) => updateField("name", event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                  placeholder="Pro Elite Series"
                />
              </label>

              <label className="block text-sm font-medium">
                Category
                <input
                  value={form.category}
                  onChange={(event) => updateField("category", event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                  placeholder="Strength"
                />
              </label>

              <label className="block text-sm font-medium">
                Price
                <input
                  type="number"
                  value={form.price}
                  onChange={(event) => updateField("price", Number(event.target.value))}
                  className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                />
              </label>

              <label className="block text-sm font-medium">
                Currency
                <select
                  value={form.currency}
                  onChange={(event) => updateField("currency", event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                >
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="AUD">AUD</option>
                </select>
              </label>

              <div className="md:col-span-2">
                <div className="text-sm font-medium">Product photo</div>
                <div className="mt-2 grid gap-4 rounded-2xl border border-[var(--line)] bg-white p-4 sm:grid-cols-[160px_1fr] sm:items-center">
                  <div className="overflow-hidden rounded-xl bg-[#efeae4]">
                    <img
                      src={resolveProductImage(form.image)}
                      alt="Product photo preview"
                      className="h-36 w-full object-cover"
                    />
                  </div>
                  <div>
                    <label className="inline-flex cursor-pointer rounded-full bg-[var(--ink)] px-4 py-2.5 text-sm font-medium text-white">
                      {uploading ? "Uploading..." : "Upload or change photo"}
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp,image/gif"
                        onChange={uploadImage}
                        disabled={uploading}
                        className="sr-only"
                      />
                    </label>
                    <p className="mt-2 text-xs leading-5 text-[var(--muted)]">JPG, PNG, WebP, or GIF up to 8 MB.</p>
                    <input
                      value={form.image}
                      onChange={(event) => updateField("image", event.target.value)}
                      className="mt-3 w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm"
                      aria-label="Product image URL or path"
                      placeholder="Image URL or path"
                    />
                  </div>
                </div>
              </div>

              <label className="block text-sm font-medium md:col-span-2">
                Short description
                <input
                  value={form.shortDescription}
                  onChange={(event) => updateField("shortDescription", event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                  placeholder="Premium commercial-grade strength training setup."
                />
              </label>

              <label className="block text-sm font-medium md:col-span-2">
                Full description
                <textarea
                  value={form.description}
                  onChange={(event) => updateField("description", event.target.value)}
                  className="mt-2 min-h-28 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                  placeholder="Describe the product value and use case."
                />
              </label>

              <div className="md:col-span-2">
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-sm font-medium">Features</div>
                  <button type="button" onClick={addFeature} className="rounded-full border border-[var(--line)] px-3 py-1.5 text-sm font-medium">
                    Add feature
                  </button>
                </div>

                <div className="space-y-3">
                  {form.features.map((feature, index) => (
                    <div key={index} className="flex gap-3">
                      <input
                        value={feature}
                        onChange={(event) => updateFeature(index, event.target.value)}
                        className="w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                        placeholder="Feature description"
                      />
                      <button type="button" onClick={() => removeFeature(index)} className="rounded-full border border-[var(--line)] px-3 py-2 text-sm">
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <label className="flex items-center gap-3 text-sm font-medium md:col-span-2">
                <input
                  type="checkbox"
                  checked={form.featured}
                  onChange={(event) => updateField("featured", event.target.checked)}
                  className="h-4 w-4"
                />
                Feature this product on the home page
              </label>
            </div>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <button type="button" onClick={saveProduct} disabled={saving} className="rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white disabled:opacity-60">
                {saving ? "Saving..." : selectedId ? "Save changes" : "Create product"}
              </button>
              <a href="/" className="rounded-full border border-[var(--line)] px-5 py-3 text-sm font-medium text-[var(--ink)]">
                View portal
              </a>
            </div>

            {message ? <p className="mt-4 text-sm text-[var(--muted)]">{message}</p> : null}
          </section>
        </div>
      </div>
    </main>
  );
}
