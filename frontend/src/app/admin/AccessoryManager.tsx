"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { API_BASE, resolveProductImage } from "@/lib/api";
import { fetchAdminAccessories, fetchCatalogCategories, type Accessory } from "@/lib/accessories";
import PhotoEditor from "@/components/PhotoEditor";
import { CompatibilityEditor } from "@/components/Compatibility";
import { getCatalogPhotos, getCatalogCover, emptyCompatibility } from "@/lib/catalogDetails";
import { AdminNotice, AdminSaveBar, PriceInput, ProvenanceEditor, inputClass, parsePrice, priceError, type AdminMessage } from "./AdminFields";

type AccessoryForm = Omit<Accessory, "id">;

const emptyAccessory: AccessoryForm = {
  name: "",
  category: "",
  dimensions: "",
  material: "",
  weight: "",
  price: 0,
  currency: "CAD",
  notes: "",
  shortDescription: "",
  description: "",
  features: [""],
  included: "",
  sellingUnit: "",
  packageQuantity: null,
  colourOptions: "",
  image: "",
  photos: [],
  compatibility: emptyCompatibility,
};

function toFormState(item: Accessory): AccessoryForm {
  return {
    name: item.name,
    category: item.category,
    dimensions: item.dimensions,
    material: item.material,
    weight: item.weight,
    price: item.price,
    currency: item.currency,
    notes: item.notes,
    shortDescription: item.shortDescription ?? "",
    description: item.description ?? "",
    features: item.features?.length ? item.features : [""],
    included: item.included ?? "",
    sellingUnit: item.sellingUnit ?? "",
    packageQuantity: item.packageQuantity ?? null,
    colourOptions: item.colourOptions ?? "",
    provenance: item.provenance,
    image: item.image,
    photos: getCatalogPhotos(item),
    compatibility: item.compatibility ?? emptyCompatibility,
  };
}

export default function AccessoryManager({ adminToken, onBusyChange, onDirtyChange, confirmLeave }: { adminToken: string; onBusyChange: (busy: boolean) => void; onDirtyChange: (dirty: boolean) => void; confirmLeave: () => boolean }) {
  const [accessories, setAccessories] = useState<Accessory[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<AccessoryForm>(emptyAccessory);
  const [baseline, setBaseline] = useState(JSON.stringify(emptyAccessory));
  const [priceText, setPriceText] = useState("0.00");
  const [showEditor, setShowEditor] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<AdminMessage | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const dirty = JSON.stringify(form) !== baseline || priceText !== form.price.toFixed(2);
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false); }, [dirty, onDirtyChange]);

  const loadForm = (next: AccessoryForm) => {
    setForm(next);
    setBaseline(JSON.stringify(next));
    setPriceText(next.price.toFixed(2));
  };

  useEffect(() => {
    onBusyChange(loading || saving || uploading);
    return () => onBusyChange(false);
  }, [loading, saving, uploading, onBusyChange]);

  const onUploadBusyChange = useCallback((busy: boolean) => {
    setUploading(busy);
    onBusyChange(busy || saving);
  }, [onBusyChange, saving]);

  useEffect(() => {
    let active = true;
    Promise.all([fetchAdminAccessories(adminToken), fetchCatalogCategories(adminToken)])
      .then(([items, categoryOptions]) => {
        if (!active) return;
        setAccessories(items);
        setCategories(categoryOptions);
        if (items.length > 0) {
          setSelectedId(items[0].id);
          loadForm(toFormState(items[0]));
        }
      })
      .catch((error) => { if (active) setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to load accessories." }); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [adminToken]);

  const updateField = <K extends keyof AccessoryForm>(key: K, value: AccessoryForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setMessage((current) => current?.type === "success" ? null : current);
  };

  const selectAccessory = (item: Accessory) => {
    if (loading || !confirmLeave()) return;
    setSelectedId(item.id);
    loadForm(toFormState(item));
    setShowEditor(true);
    setMessage(null);
    setConfirmingDelete(false);
  };

  const resetForm = () => {
    if (loading || !confirmLeave()) return;
    setSelectedId(null);
    loadForm(emptyAccessory);
    setShowEditor(true);
    setMessage(null);
    setConfirmingDelete(false);
  };

  const backToList = () => {
    if (!confirmLeave()) return;
    const selected = accessories.find((item) => item.id === selectedId);
    loadForm(selected ? toFormState(selected) : emptyAccessory);
    setShowEditor(false);
    setMessage(null);
    setConfirmingDelete(false);
  };

  const saveAccessory = async () => {
    const price = parsePrice(priceText);
    if (price === null) {
      setMessage({ type: "error", text: priceError });
      return;
    }
    if (!form.name.trim() || !form.category.trim()) {
      setMessage({ type: "error", text: "Name and category are required." });
      return;
    }
    if (form.packageQuantity != null && (!Number.isSafeInteger(form.packageQuantity) || form.packageQuantity < 1)) {
      setMessage({ type: "error", text: "Package quantity must be a positive whole number, or leave it blank if unknown." });
      return;
    }

    setPriceText(price.toFixed(2));
    onBusyChange(true);
    setSaving(true);
    setMessage(null);

    try {
      const url = selectedId ? `${API_BASE}/api/accessories/${selectedId}` : `${API_BASE}/api/accessories`;
      const res = await fetch(url, {
        method: selectedId ? "PUT" : "POST",
        headers: {
          Authorization: `Bearer ${adminToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ...form, name: form.name.trim(), category: form.category.trim(), price, features: form.features?.map((feature) => feature.trim()).filter(Boolean), image: form.image || null }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Unable to save accessory.");
      }
      const saved = data.item as Accessory;

      setAccessories((current) =>
        selectedId ? current.map((item) => (item.id === selectedId ? saved : item)) : [...current, saved],
      );
      setSelectedId(saved.id);
      loadForm(toFormState(saved));
      setMessage({ type: "success", text: "Accessory saved successfully." });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to save accessory." });
    } finally {
      setSaving(false);
    }
  };

  const deleteAccessory = async () => {
    const accessory = accessories.find((item) => item.id === selectedId);
    if (!accessory) return;

    onBusyChange(true);
    setSaving(true);
    setMessage(null);
    setConfirmingDelete(false);

    try {
      const res = await fetch(`${API_BASE}/api/accessories/${accessory.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${adminToken}` },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : "Unable to delete accessory.");
      }

      const remaining = accessories.filter((item) => item.id !== accessory.id);
      setAccessories(remaining);
      if (remaining.length > 0) {
        setSelectedId(remaining[0].id);
        loadForm(toFormState(remaining[0]));
      } else {
        setSelectedId(null);
        loadForm(emptyAccessory);
      }
      setMessage({ type: "success", text: `"${accessory.name}" deleted.` });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to delete accessory." });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="text-[var(--muted)]">Loading accessories...</p>;
  }

  return (
    <>
    <AdminNotice message={message} />
    <fieldset disabled={saving || uploading} className="grid min-w-0 gap-8 lg:grid-cols-[0.8fr_1.2fr]">
      <aside className={`${showEditor ? "hidden lg:block" : ""} rounded-[28px] border border-[var(--line)] bg-white/80 p-4`}>
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Accessories ({accessories.length})</h2>
          <button type="button" onClick={resetForm} className="rounded-full border border-[var(--line)] px-3 py-1.5 text-sm font-medium">
            New
          </button>
        </div>

        <div className="space-y-3">
          {accessories.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => selectAccessory(item)}
              className={`w-full rounded-[22px] border p-3 text-left transition ${selectedId === item.id ? "border-[var(--ink)] bg-[#f5f1ea]" : "border-[var(--line)] bg-white"}`}
            >
              <div className="flex items-center gap-3">
                <img src={resolveProductImage(item.image)} alt={item.name} className="h-14 w-14 rounded-xl object-cover" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{item.name}</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
                    {item.category} · ${item.price.toFixed(2)} {item.currency}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </aside>

      <section className={`${showEditor ? "" : "hidden lg:block"} min-w-0 rounded-[28px] border border-[var(--line)] bg-white/80 p-4 sm:p-6`}>
        <button type="button" onClick={backToList} className="mb-5 rounded-full border border-[var(--line)] px-4 py-2 text-sm lg:hidden">← Back to accessories</button>
        <fieldset className="grid min-w-0 gap-5 md:grid-cols-2">
          <legend className="mb-4 text-lg font-semibold">Accessory essentials</legend>
          <label className="block text-sm font-medium">
            Accessory name
            <input value={form.name} onChange={(event) => updateField("name", event.target.value)} className={inputClass} placeholder="Triceps Rope" />
          </label>

          <label className="block text-sm font-medium">
            Category
            <select value={form.category} onChange={(event) => updateField("category", event.target.value)} className={inputClass}>
              <option value="">Select category</option>
              {form.category && !categories.includes(form.category) ? <option value={form.category}>{form.category} (existing)</option> : null}
              {categories.map((category) => <option key={category} value={category}>{category}</option>)}
            </select>
          </label>

          <PriceInput id="accessory-price" value={priceText} onChange={setPriceText} />

          <label className="block text-sm font-medium">
            Currency
            <select value={form.currency} onChange={(event) => updateField("currency", event.target.value)} className={inputClass}>
              <option value="CAD">CAD</option>
              <option value="USD">USD</option>
            </select>
          </label>

        </fieldset>
        <fieldset className="mt-6 grid min-w-0 gap-5 border-t border-[var(--line)] pt-5 md:grid-cols-2">
          <legend className="text-lg font-semibold">Specifications &amp; package contents</legend>
          <label className="block text-sm font-medium">
            Dimensions
            <input value={form.dimensions} onChange={(event) => updateField("dimensions", event.target.value)} className={inputClass} placeholder="70 cm length" />
          </label>

          <label className="block text-sm font-medium">
            Weight
            <input value={form.weight} onChange={(event) => updateField("weight", event.target.value)} className={inputClass} placeholder="0.8 kg" />
          </label>

          <label className="block text-sm font-medium md:col-span-2">
            Material
            <input value={form.material} onChange={(event) => updateField("material", event.target.value)} className={inputClass} placeholder="Braided nylon, steel eyelet" />
          </label>

          <label className="block text-sm font-medium">
            Selling unit
            <select value={form.sellingUnit ?? ""} onChange={(event) => updateField("sellingUnit", event.target.value as AccessoryForm["sellingUnit"])} className={inputClass}>
              <option value="">Not specified</option>
              <option value="Each">Each</option>
              <option value="Pair">Pair</option>
              <option value="Set">Set</option>
            </select>
          </label>
          <div className="text-sm font-medium">
            <label htmlFor="accessory-quantity">Package quantity (individual pieces)</label>
            <input id="accessory-quantity" aria-describedby="accessory-quantity-help" type="number" min={1} step={1} inputMode="numeric" value={form.packageQuantity ?? ""} onChange={(event) => updateField("packageQuantity", event.target.value === "" ? null : Number(event.target.value))} className={inputClass} />
            <p id="accessory-quantity-help" className="mt-2 text-xs text-[var(--muted)]">Leave blank if unknown. For a pair, enter 2; describe set contents below.</p>
          </div>
          <label className="block text-sm font-medium md:col-span-2">
            What&apos;s included / package contents
            <textarea rows={3} value={form.included ?? ""} onChange={(event) => updateField("included", event.target.value)} className={inputClass} />
          </label>
          <label className="block text-sm font-medium md:col-span-2">
            Colour / options
            <input value={form.colourOptions ?? ""} onChange={(event) => updateField("colourOptions", event.target.value)} className={inputClass} />
          </label>
        </fieldset>
        <fieldset className="mt-6 grid min-w-0 gap-5 border-t border-[var(--line)] pt-5 md:grid-cols-2">
          <legend className="text-lg font-semibold">Customer-facing descriptions</legend>
          <label className="block text-sm font-medium md:col-span-2">
            Short description
            <input value={form.shortDescription ?? ""} onChange={(event) => updateField("shortDescription", event.target.value)} className={inputClass} />
          </label>
          <label className="block text-sm font-medium md:col-span-2">
            Full description
            <textarea
              value={form.description ?? ""}
              onChange={(event) => updateField("description", event.target.value)}
              className={`${inputClass} min-h-24`}
              maxLength={10000}
              placeholder="Complete product description, benefits, and fit information."
            />
          </label>
          <label className="block text-sm font-medium md:col-span-2">
            Public use description
            <textarea aria-label="Public use description" aria-describedby="public-use-help" value={form.notes} onChange={(event) => updateField("notes", event.target.value)} className={`${inputClass} min-h-24`} placeholder="Pushdowns, face pulls, and cable crunches." />
            <span id="public-use-help" className="mt-2 block text-sm font-normal text-[var(--muted)]">Shown to customers. Use Internal notes below for private migration information.</span>
          </label>
          <fieldset className="min-w-0 md:col-span-2">
            <legend className="text-sm font-medium">Features</legend>
            <div className="mt-3 space-y-3">
              {(form.features ?? []).map((feature, index) => (
                <div key={index} className="flex items-center gap-2">
                  <input aria-label={`Feature ${index + 1}`} value={feature} onChange={(event) => updateField("features", (form.features ?? []).map((value, i) => i === index ? event.target.value : value))} className={inputClass} />
                  <button type="button" aria-label={`Remove feature ${index + 1}`} onClick={() => updateField("features", (form.features ?? []).filter((_, i) => i !== index))} className="rounded-full border border-[var(--line)] px-3 py-2 text-sm">Remove</button>
                </div>
              ))}
            </div>
            <button type="button" onClick={() => updateField("features", [...(form.features ?? []), ""])} className="mt-3 rounded-full border border-[var(--line)] px-3 py-2 text-sm">Add feature</button>
          </fieldset>
        </fieldset>

        <div className="mt-6 grid min-w-0 gap-5 md:grid-cols-2">
          <PhotoEditor key={selectedId ?? "new"} photos={getCatalogPhotos(form)} adminToken={adminToken} disabled={saving || uploading} onBusyChange={onUploadBusyChange} onChange={(photos) => { setForm((current) => ({ ...current, photos, image: getCatalogCover(photos) })); setMessage((current) => current?.type === "success" ? null : current); }} />
          <CompatibilityEditor value={form.compatibility} onChange={(value) => updateField("compatibility", value)} />
          <ProvenanceEditor value={form.provenance} onChange={(value) => updateField("provenance", value)} />
        </div>

        <AdminSaveBar>
          <button type="button" onClick={saveAccessory} disabled={saving} className="rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white disabled:opacity-60">
            {saving ? "Saving..." : selectedId ? "Save changes" : "Create accessory"}
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
              Delete accessory
            </button>
          ) : null}
          {selectedId && confirmingDelete ? (
            <>
              <button
                type="button"
                onClick={deleteAccessory}
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
          <Link href="/accessories" className="rounded-full border border-[var(--line)] px-5 py-3 text-sm font-medium text-[var(--ink)]">
            View accessories page
          </Link>
        </div>

      </section>
    </fieldset>
    </>
  );
}
