"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { API_BASE, resolveProductImage } from "@/lib/api";
import AccessoryManager from "./AccessoryManager";
import HeroManager from "./HeroManager";
import BrandLogo from "@/components/BrandLogo";
import PhotoEditor from "@/components/PhotoEditor";
import { CompatibilityEditor } from "@/components/Compatibility";
import { getCatalogPhotos, getCatalogCover, emptyCompatibility, getProductSpecifications, productSpecificationFields, stockStatuses, type CatalogDetails, type ProductSpecifications, type Provenance } from "@/lib/catalogDetails";
import { fetchCatalogCategories } from "@/lib/accessories";
import { AdminNotice, AdminSaveBar, PriceInput, ProvenanceEditor, parsePrice, priceError, type AdminMessage } from "./AdminFields";
import { useUnsavedChanges } from "./useUnsavedChanges";

type Product = CatalogDetails & ProductSpecifications & {
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
  provenance?: Provenance;
};

type AdminTab = "products" | "accessories" | "banner";

const adminTabs: { id: AdminTab; label: string; heading: string }[] = [
  { id: "products", label: "Products", heading: "Product management" },
  { id: "accessories", label: "Accessories", heading: "Accessory management" },
  { id: "banner", label: "Home banner", heading: "Home banner" },
];

const emptyProduct: Omit<Product, "id" | "slug"> = {
  ...getProductSpecifications({}),
  name: "",
  category: "",
  price: 0,
  currency: "CAD",
  shortDescription: "",
  description: "",
  featured: false,
  image: "",
  photos: [],
  compatibility: emptyCompatibility,
  features: [""],
};

async function fetchProducts(token: string): Promise<Product[]> {
  const res = await fetch(`${API_BASE}/api/admin/products`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error("Unable to fetch products");
  }

  const data = await res.json();
  return Array.isArray(data.items) ? (data.items as Product[]) : [];
}

async function verifyAdminToken(token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/verify`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(res.status === 503 ? "Admin access is not configured." : "Incorrect admin token.");
  }
}

function toFormState(product: Product): Omit<Product, "id" | "slug"> {
  return {
    ...getProductSpecifications(product),
    name: product.name,
    category: product.category,
    price: product.price,
    currency: product.currency,
    shortDescription: product.shortDescription ?? "",
    description: product.description ?? "",
    featured: product.featured,
    image: product.image,
    photos: getCatalogPhotos(product),
    compatibility: product.compatibility ?? emptyCompatibility,
    features: product.features?.length > 0 ? product.features : [""],
    provenance: product.provenance,
  };
}

export default function AdminPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [adminToken, setAdminToken] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [checkingAccess, setCheckingAccess] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<Omit<Product, "id" | "slug">>(emptyProduct);
  const [baseline, setBaseline] = useState(JSON.stringify(emptyProduct));
  const [priceText, setPriceText] = useState("0.00");
  const [categories, setCategories] = useState<string[]>([]);
  const [showEditor, setShowEditor] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [accessoryBusy, setAccessoryBusy] = useState(false);
  const [childDirty, setChildDirty] = useState(false);
  const [message, setMessage] = useState<AdminMessage | null>(null);
  const [activeTab, setActiveTab] = useState<AdminTab>("products");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const dirty = activeTab === "products" ? JSON.stringify(form) !== baseline || priceText !== form.price.toFixed(2) : childDirty;
  const busy = saving || uploading || accessoryBusy;
  const confirmLeave = useUnsavedChanges(authenticated && dirty, busy);

  const loadForm = (next: Omit<Product, "id" | "slug">) => {
    setForm(next);
    setBaseline(JSON.stringify(next));
    setPriceText(next.price.toFixed(2));
  };

  const verifyAccess = async (token = adminToken) => {
    setCheckingAccess(true);
    setMessage(null);

    try {
      await verifyAdminToken(token);
      const [items, supportedCategories] = await Promise.all([fetchProducts(token), fetchCatalogCategories(token)]);
      setCategories(supportedCategories);
      setProducts(items);
      setSelectedId(items[0]?.id ?? null);
      loadForm(items[0] ? toFormState(items[0]) : emptyProduct);
      window.sessionStorage.setItem("styl-admin-token", token);
      setAdminToken(token);
      setAuthenticated(true);
    } catch (error) {
      window.sessionStorage.removeItem("styl-admin-token");
      setAuthenticated(false);
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to verify admin access." });
    } finally {
      setCheckingAccess(false);
    }
  };

  const signOut = () => {
    if (!confirmLeave()) return;
    window.sessionStorage.removeItem("styl-admin-token");
    setAdminToken("");
    setAuthenticated(false);
    setMessage(null);
    loadForm(emptyProduct);
    setChildDirty(false);
    setActiveTab("products");
    setShowEditor(false);
  };

  useEffect(() => {
    let active = true;
    async function initialize() {
      const savedToken = window.sessionStorage.getItem("styl-admin-token");
      if (savedToken) {
        try {
          await verifyAdminToken(savedToken);
          const [items, supportedCategories] = await Promise.all([fetchProducts(savedToken), fetchCatalogCategories(savedToken)]);
          if (!active) return;
          setCategories(supportedCategories);
          setProducts(items);
          setSelectedId(items[0]?.id ?? null);
          loadForm(items[0] ? toFormState(items[0]) : emptyProduct);
          setAdminToken(savedToken);
          setAuthenticated(true);
        } catch (error) {
          if (!active) return;
          window.sessionStorage.removeItem("styl-admin-token");
          setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to verify admin access." });
        }
      }
      if (!active) return;
      setLoading(false);
      setCheckingAccess(false);
    }

    initialize();
    return () => { active = false; };
  }, []);

  const updateField = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setMessage((current) => current?.type === "success" ? null : current);
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
    if (!confirmLeave()) return;
    setSelectedId(product.id);
    loadForm(toFormState(product));
    setShowEditor(true);
    setMessage(null);
    setConfirmingDelete(false);
  };

  const resetForm = () => {
    if (!confirmLeave()) return;
    loadForm(emptyProduct);
    setShowEditor(true);
    setSelectedId(null);
    setMessage(null);
    setConfirmingDelete(false);
  };

  const saveProduct = async () => {
    const price = parsePrice(priceText);
    if (price === null) {
      setMessage({ type: "error", text: priceError });
      return;
    }
    if (!form.name.trim() || !form.category.trim()) {
      setMessage({ type: "error", text: "Name and category are required." });
      return;
    }
    if (!categories.includes(form.category)) {
      setMessage({ type: "error", text: "Select a supported category from the list." });
      return;
    }

    setPriceText(price.toFixed(2));
    setSaving(true);
    setMessage(null);

    try {
      const payload = {
        ...form,
        name: form.name.trim(),
        category: form.category.trim(),
        price,
        features: form.features.map((feature) => feature.trim()).filter(Boolean),
      };

      const method = selectedId ? "PUT" : "POST";
      const url = selectedId ? `${API_BASE}/api/products/${selectedId}` : `${API_BASE}/api/products`;

      const res = await fetch(url, {
        method,
        headers: {
          Authorization: `Bearer ${adminToken}`,
          "Content-Type": "application/json",
        },
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
      loadForm(toFormState(saved));
      setMessage({ type: "success", text: "Product saved successfully." });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to save product." });
    } finally {
      setSaving(false);
    }
  };

  const deleteProduct = async () => {
    const product = products.find((item) => item.id === selectedId);
    if (!product) return;

    setSaving(true);
    setMessage(null);
    setConfirmingDelete(false);

    try {
      const res = await fetch(`${API_BASE}/api/products/${product.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${adminToken}` },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : "Unable to delete product.");
      }

      const remaining = products.filter((item) => item.id !== product.id);
      setProducts(remaining);
      if (remaining.length > 0) {
        setSelectedId(remaining[0].id);
        loadForm(toFormState(remaining[0]));
      } else {
        setSelectedId(null);
        loadForm(emptyProduct);
      }
      setMessage({ type: "success", text: `"${product.name}" deleted.` });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to delete product." });
    } finally {
      setSaving(false);
    }
  };

  if (loading || checkingAccess) {
    return <main className="min-h-screen bg-[var(--bg)] px-4 py-16 text-[var(--ink)]">Loading admin catalog...</main>;
  }

  if (!authenticated) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] px-4 py-16 text-[var(--ink)]">
        <form
          className="w-full max-w-sm rounded-[28px] border border-[var(--line)] bg-white p-7"
          onSubmit={(event) => {
            event.preventDefault();
            verifyAccess();
          }}
        >
          <BrandLogo markClassName="h-8 w-auto" className="mb-6" />
          <div className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Admin</div>
          <h1 className="mt-3 text-3xl font-semibold">Sign in</h1>
          <label className="mt-6 block text-sm font-medium">
            Admin token
            <input
              type="password"
              value={adminToken}
              onChange={(event) => setAdminToken(event.target.value)}
              autoComplete="current-password"
              required
              className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
            />
          </label>
          <button type="submit" className="mt-5 w-full rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white">
            Sign in
          </button>
          <AdminNotice message={message} />
        </form>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-12 text-[var(--ink)] sm:px-6 lg:px-8">
      <fieldset disabled={busy} className="mx-auto min-w-0 max-w-7xl">
        <header className="mb-8 flex flex-col justify-between gap-4 border-b border-[var(--line)] pb-6 md:flex-row md:items-end">
          <div>
            <BrandLogo markClassName="h-8 w-auto" className="mb-5" />
            <div className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Admin</div>
            <h1 className="mt-3 text-4xl font-semibold tracking-[-0.06em]">
              {adminTabs.find((tab) => tab.id === activeTab)?.heading}
            </h1>
            <div className="mt-4 inline-flex flex-wrap rounded-2xl border border-[var(--line)] bg-white p-1 text-sm font-medium">
              {adminTabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => {
                    if (tab.id === activeTab || !confirmLeave()) return;
                    const selected = products.find((product) => product.id === selectedId);
                    loadForm(selected ? toFormState(selected) : emptyProduct);
                    setMessage(null);
                    setChildDirty(false);
                    setActiveTab(tab.id);
                  }}
                  aria-pressed={activeTab === tab.id}
                  className={`rounded-full px-4 py-1.5 ${activeTab === tab.id ? "bg-[var(--ink)] text-white" : "text-[var(--muted)]"}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
          {activeTab === "products" ? (
            <div className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium text-[var(--muted)]">
              {products.length} products · {products.filter((product) => product.publicationStatus === "draft").length} drafts
            </div>
          ) : null}
          <button type="button" onClick={signOut} className="text-sm font-medium text-[var(--muted)]">
            Sign out
          </button>
        </header>

        {activeTab === "banner" ? (
          <HeroManager adminToken={adminToken} onBusyChange={setAccessoryBusy} onDirtyChange={setChildDirty} />
        ) : activeTab === "accessories" ? (
          <AccessoryManager adminToken={adminToken} onBusyChange={setAccessoryBusy} onDirtyChange={setChildDirty} confirmLeave={confirmLeave} />
        ) : (
        <>
        <AdminNotice message={message} />
        <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr]">
          <aside className={`${showEditor ? "hidden lg:block" : ""} rounded-[28px] border border-[var(--line)] bg-white/80 p-4`}>
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
                      <div className="mt-1 text-xs text-[var(--muted)]">${product.price.toFixed(2)} {product.currency}</div>
                      <div className="mt-1 text-xs text-[var(--muted)]">{product.publicationStatus === "draft" ? "Draft" : "Published"}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <section className={`${showEditor ? "" : "hidden lg:block"} min-w-0 rounded-[28px] border border-[var(--line)] bg-white/80 p-4 sm:p-6`}>
            <button type="button" onClick={() => {
              if (!confirmLeave()) return;
              const selected = products.find((product) => product.id === selectedId);
              loadForm(selected ? toFormState(selected) : emptyProduct);
              setShowEditor(false);
              setMessage(null);
            }} className="mb-5 rounded-full border border-[var(--line)] px-4 py-2 text-sm lg:hidden">← Back to products</button>
            <fieldset className="grid min-w-0 gap-5 md:grid-cols-2">
              <legend className="mb-4 text-lg font-semibold">Product essentials &amp; details</legend>
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
                <select
                  value={form.category}
                  onChange={(event) => updateField("category", event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                >
                  <option value="">Select category</option>
                  {form.category && !categories.includes(form.category) ? <option value={form.category}>{form.category} (existing)</option> : null}
                  {categories.map((category) => <option key={category} value={category}>{category}</option>)}
                </select>
              </label>

              <PriceInput id="product-price" value={priceText} onChange={setPriceText} />

              <label className="block text-sm font-medium">
                Currency
                <select
                  value={form.currency}
                  onChange={(event) => updateField("currency", event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                >
                  <option value="CAD">CAD</option>
                  <option value="USD">USD</option>
                </select>
              </label>

              <label className="block text-sm font-medium">
                Publication status
                <select value={form.publicationStatus || "published"} onChange={(event) => updateField("publicationStatus", event.target.value as ProductSpecifications["publicationStatus"])} className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3">
                  <option value="published">Published</option>
                  <option value="draft">Draft</option>
                </select>
              </label>
              <label className="block text-sm font-medium">
                Stock status (optional)
                <select value={form.stockStatus ?? ""} onChange={(event) => updateField("stockStatus", event.target.value as ProductSpecifications["stockStatus"])} className="mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3">
                  <option value="">Not specified</option>
                  {stockStatuses.map((status) => <option key={status} value={status}>{status}</option>)}
                </select>
              </label>

              <fieldset className="min-w-0 border-t border-[var(--line)] pt-5 md:col-span-2">
                <legend className="text-lg font-semibold">Product details (optional)</legend>
                <div className="grid gap-4 md:grid-cols-2">
                  {productSpecificationFields.map((field) => (
                    <label key={field.key} className="block min-w-0 text-sm font-medium">
                      {field.label}
                      <textarea value={form[field.key] ?? ""} onChange={(event) => updateField(field.key, event.target.value)} maxLength={field.limit} rows={field.rows} className="mt-2 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 font-normal" />
                    </label>
                  ))}
                </div>
              </fieldset>

              <PhotoEditor key={selectedId ?? "new"} photos={getCatalogPhotos(form)} adminToken={adminToken} disabled={saving || uploading} onBusyChange={setUploading} onChange={(photos) => setForm((current) => ({ ...current, photos, image: getCatalogCover(photos) }))} />
              <CompatibilityEditor value={form.compatibility} onChange={(value) => updateField("compatibility", value)} />

              <fieldset className="grid min-w-0 gap-5 border-t border-[var(--line)] pt-5 md:col-span-2 md:grid-cols-2">
                <legend className="text-lg font-semibold">Customer-facing descriptions</legend>
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
                        aria-label={`Feature ${index + 1}`}
                        value={feature}
                        onChange={(event) => updateFeature(index, event.target.value)}
                        className="w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3"
                        placeholder="Feature description"
                      />
                      <button type="button" aria-label={`Remove feature ${index + 1}`} onClick={() => removeFeature(index)} className="rounded-full border border-[var(--line)] px-3 py-2 text-sm">
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
                Show first in the home collection
              </label>
              </fieldset>
              <ProvenanceEditor value={form.provenance} onChange={(value) => updateField("provenance", value)} />
            </fieldset>

            <AdminSaveBar>
              <button type="button" onClick={saveProduct} disabled={saving} className="rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white disabled:opacity-60">
                {saving ? "Saving..." : selectedId ? "Save changes" : "Create product"}
              </button>
              {dirty ? <span className="text-sm text-[var(--muted)]">Unsaved changes</span> : null}
            </AdminSaveBar>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              {selectedId && !confirmingDelete ? (
                <button
                  type="button"
                  onClick={() => setConfirmingDelete(true)}
                  disabled={saving}
                  className="rounded-full border border-red-300 px-5 py-3 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-60"
                >
                  Delete product
                </button>
              ) : null}
              {selectedId && confirmingDelete ? (
                <>
                  <button
                    type="button"
                    onClick={deleteProduct}
                    disabled={saving}
                    className="rounded-full bg-red-700 px-5 py-3 text-sm font-medium text-white hover:bg-red-800 disabled:opacity-60"
                  >
                    Confirm delete
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmingDelete(false)}
                    className="rounded-full border border-[var(--line)] px-5 py-3 text-sm font-medium"
                  >
                    Cancel
                  </button>
                </>
              ) : null}
              <Link href="/" className="rounded-full border border-[var(--line)] px-5 py-3 text-sm font-medium text-[var(--ink)]">
                View portal
              </Link>
            </div>

          </section>
        </div>
        </>
        )}
      </fieldset>
    </main>
  );
}
