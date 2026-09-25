"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { CircleAlert, CircleCheck } from "lucide-react";
import { API_BASE, resolveProductImage } from "@/lib/api";
import { fetchAccessories, type Accessory } from "@/lib/accessories";
import PhotoEditor from "@/components/PhotoEditor";
import { CompatibilityEditor } from "@/components/Compatibility";
import { getCatalogPhotos, getCatalogCover, emptyCompatibility } from "@/lib/catalogDetails";

type AccessoryForm = Omit<Accessory, "id">;

const emptyAccessory: AccessoryForm = {
  name: "",
  category: "",
  dimensions: "",
  material: "",
  weight: "",
  price: 0,
  currency: "USD",
  notes: "",
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
    image: item.image,
    photos: getCatalogPhotos(item),
    compatibility: item.compatibility ?? emptyCompatibility,
  };
}

const inputClass = "mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3";

export default function AccessoryManager({ adminToken, onBusyChange }: { adminToken: string; onBusyChange: (busy: boolean) => void }) {
  const [accessories, setAccessories] = useState<Accessory[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<AccessoryForm>(emptyAccessory);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: "error" | "success"; title: string; text: string } | null>(null);
  const messageRef = useRef<HTMLDivElement>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    if (message?.type === "error") {
      messageRef.current?.scrollIntoView({ block: "center" });
      messageRef.current?.focus({ preventScroll: true });
    }
  }, [message]);

  useEffect(() => {
    onBusyChange(saving || uploading);
    return () => onBusyChange(false);
  }, [saving, uploading, onBusyChange]);

  useEffect(() => {
    fetchAccessories()
      .then((items) => {
        setAccessories(items);
        if (items.length > 0) {
          setSelectedId(items[0].id);
          setForm(toFormState(items[0]));
        }
      })
      .catch((error) => setMessage({ type: "error", title: "Load failed", text: error instanceof Error ? error.message : "Unable to load accessories." }))
      .finally(() => setLoading(false));
  }, []);

  const updateField = <K extends keyof AccessoryForm>(key: K, value: AccessoryForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setMessage((current) => current?.type === "success" ? null : current);
  };

  const selectAccessory = (item: Accessory) => {
    setSelectedId(item.id);
    setForm(toFormState(item));
    setMessage(null);
    setConfirmingDelete(false);
  };

  const resetForm = () => {
    setSelectedId(null);
    setForm(emptyAccessory);
    setMessage(null);
    setConfirmingDelete(false);
  };

  const saveAccessory = async () => {
    if (!form.name.trim() || !form.category.trim()) {
      setMessage({ type: "error", title: "Save failed", text: "Changes were not saved. Name and category are required." });
      return;
    }

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
        body: JSON.stringify({ ...form, price: Number(form.price || 0), image: form.image || null }),
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
      setForm(toFormState(saved));
      setMessage({ type: "success", title: "Saved", text: "Accessory saved successfully." });
    } catch (error) {
      setMessage({ type: "error", title: "Save failed", text: error instanceof Error ? error.message : "Unable to save accessory." });
    } finally {
      setSaving(false);
    }
  };

  const deleteAccessory = async () => {
    const accessory = accessories.find((item) => item.id === selectedId);
    if (!accessory) return;

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
        setForm(toFormState(remaining[0]));
      } else {
        setSelectedId(null);
        setForm(emptyAccessory);
      }
      setMessage({ type: "success", title: "Deleted", text: `"${accessory.name}" deleted.` });
    } catch (error) {
      setMessage({ type: "error", title: "Delete failed", text: error instanceof Error ? error.message : "Unable to delete accessory." });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="text-[var(--muted)]">Loading accessories...</p>;
  }

  return (
    <fieldset disabled={saving || uploading} className="grid min-w-0 gap-8 lg:grid-cols-[0.8fr_1.2fr]">
      <aside className="rounded-[28px] border border-[var(--line)] bg-white/80 p-4">
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
                    {item.category} · ${item.price.toLocaleString()}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </aside>

      <section className="rounded-[28px] border border-[var(--line)] bg-white/80 p-6">
        <div className="grid gap-5 md:grid-cols-2">
          <label className="block text-sm font-medium">
            Accessory name
            <input value={form.name} onChange={(event) => updateField("name", event.target.value)} className={inputClass} placeholder="Triceps Rope" />
          </label>

          <label className="block text-sm font-medium">
            Category
            <input value={form.category} onChange={(event) => updateField("category", event.target.value)} className={inputClass} placeholder="Handle" />
          </label>

          <label className="block text-sm font-medium">
            Retail price
            <input
              type="number"
              min={0}
              value={form.price}
              onChange={(event) => updateField("price", Number(event.target.value))}
              className={inputClass}
            />
          </label>

          <label className="block text-sm font-medium">
            Currency
            <select value={form.currency} onChange={(event) => updateField("currency", event.target.value)} className={inputClass}>
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="AUD">AUD</option>
            </select>
          </label>

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

          <label className="block text-sm font-medium md:col-span-2">
            Notes / use
            <textarea
              value={form.notes}
              onChange={(event) => updateField("notes", event.target.value)}
              className={`${inputClass} min-h-24`}
              placeholder="Pushdowns, face pulls, and cable crunches."
            />
          </label>

          <PhotoEditor key={selectedId ?? "new"} photos={getCatalogPhotos(form)} adminToken={adminToken} disabled={saving || uploading} onBusyChange={setUploading} onChange={(photos) => { setForm((current) => ({ ...current, photos, image: getCatalogCover(photos) })); setMessage((current) => current?.type === "success" ? null : current); }} />
          <CompatibilityEditor value={form.compatibility} onChange={(value) => updateField("compatibility", value)} />
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <button type="button" onClick={saveAccessory} disabled={saving} className="rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white disabled:opacity-60">
            {saving ? "Saving..." : selectedId ? "Save changes" : "Create accessory"}
          </button>
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

        {message ? (
          <div ref={messageRef} tabIndex={-1} role={message.type === "error" ? "alert" : "status"} className={`mt-4 flex items-start gap-3 rounded-lg border-2 p-4 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2 ${message.type === "error" ? "border-red-600 bg-red-50 text-red-900 focus:ring-red-600" : "border-green-600 bg-green-50 text-green-900 focus:ring-green-600"}`}>
            {message.type === "error" ? <CircleAlert size={24} aria-hidden="true" className="shrink-0" /> : <CircleCheck size={24} aria-hidden="true" className="shrink-0" />}
            <div className="min-w-0 break-words">
              <p className="text-base font-semibold">{message.title}</p>
              <p className="mt-1">{message.text}</p>
            </div>
          </div>
        ) : null}
      </section>
    </fieldset>
  );
}
