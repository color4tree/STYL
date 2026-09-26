"use client";

import Link from "next/link";
import { type ChangeEvent, useEffect, useState } from "react";
import { API_BASE, resolveProductImage } from "@/lib/api";
import { defaultHero, fetchHero, formatHeroPriceLabel, type Hero } from "@/lib/hero";
import { AdminNotice, AdminSaveBar, type AdminMessage } from "./AdminFields";

const inputClass = "mt-2 w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3";

const textFields: { key: Exclude<keyof Hero, "image">; label: string; maxLength: number }[] = [
  { key: "tag", label: "Top-left tag", maxLength: 40 },
  { key: "number", label: "Top-right number", maxLength: 10 },
  { key: "eyebrow", label: "Small heading", maxLength: 60 },
  { key: "title", label: "Title", maxLength: 80 },
  { key: "priceLabel", label: "Price text", maxLength: 40 },
];

export default function HeroManager({ adminToken, onBusyChange, onDirtyChange }: { adminToken: string; onBusyChange: (busy: boolean) => void; onDirtyChange: (dirty: boolean) => void }) {
  const [form, setForm] = useState<Hero>(defaultHero);
  const [baseline, setBaseline] = useState(JSON.stringify(defaultHero));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<AdminMessage | null>(null);
  const dirty = JSON.stringify(form) !== baseline;

  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false); }, [dirty, onDirtyChange]);
  useEffect(() => { onBusyChange(loading || saving || uploading); return () => onBusyChange(false); }, [loading, saving, uploading, onBusyChange]);

  useEffect(() => {
    fetchHero()
      .then((item) => { setForm(item); setBaseline(JSON.stringify(item)); })
      .catch((error) => setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to load home banner." }))
      .finally(() => setLoading(false));
  }, []);

  const updateField = <K extends keyof Hero>(key: K, value: Hero[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setMessage((current) => current?.type === "success" ? null : current);
  };

  const uploadImage = async (event: ChangeEvent<HTMLInputElement>) => {
    const image = event.target.files?.[0];
    event.target.value = "";
    if (!image) return;

    onBusyChange(true);
    setUploading(true);
    setMessage(null);

    try {
      const body = new FormData();
      body.append("image", image);
      const res = await fetch(`${API_BASE}/api/uploads/product-image`, {
        method: "POST",
        headers: { Authorization: `Bearer ${adminToken}` },
        body,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? "Unable to upload image.");
      }

      updateField("image", data.image as string);
      setMessage({ type: "success", text: "Photo uploaded. Save changes to publish it." });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to upload image." });
    } finally {
      setUploading(false);
    }
  };

  const saveHero = async () => {
    onBusyChange(true);
    setSaving(true);
    setMessage(null);

    try {
      const res = await fetch(`${API_BASE}/api/hero`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${adminToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Unable to save home banner.");
      }

      setForm(data.item as Hero);
      setBaseline(JSON.stringify(data.item));
      setMessage({ type: "success", text: "Home banner saved successfully." });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to save home banner." });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="text-[var(--muted)]">Loading home banner...</p>;
  }

  return (
    <>
    <AdminNotice message={message} />
    <fieldset disabled={saving || uploading} className="grid min-w-0 gap-8 lg:grid-cols-[0.8fr_1.2fr]">
      <aside className="rounded-[28px] border border-[var(--line)] bg-white/80 p-4">
        <h2 className="mb-4 text-lg font-semibold">Preview</h2>
        <div className="rounded-[28px] bg-[linear-gradient(135deg,#1c1c1c,#504639)] p-6 text-white">
          <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] text-white/70">
            <span>{form.tag}</span>
            <span>{form.number}</span>
          </div>
          <div className="mt-8 rounded-[24px] bg-white/10 p-5">
            <img src={resolveProductImage(form.image)} alt="Home banner preview" className="mb-4 h-48 w-full rounded-[20px] object-cover" />
            <div className="flex items-end justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-white/60">{form.eyebrow}</div>
                <div className="mt-2 text-2xl font-semibold">{form.title}</div>
              </div>
              <div className="text-xl font-medium">{formatHeroPriceLabel(form.priceLabel)}</div>
            </div>
          </div>
        </div>
      </aside>

      <section className="rounded-[28px] border border-[var(--line)] bg-white/80 p-6">
        <div className="grid gap-5 md:grid-cols-2">
          {textFields.map((field) => (
            <label key={field.key} className="block text-sm font-medium">
              {field.label}
              <input
                value={form[field.key]}
                maxLength={field.maxLength}
                onChange={(event) => updateField(field.key, event.target.value)}
                className={inputClass}
              />
            </label>
          ))}

          <div className="md:col-span-2">
            <div className="text-sm font-medium">Banner photo</div>
            <div className="mt-2 rounded-2xl border border-[var(--line)] bg-white p-4">
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
                maxLength={500}
                onChange={(event) => updateField("image", event.target.value)}
                className="mt-3 w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm"
                aria-label="Banner image URL or path"
                placeholder="Image URL or path"
              />
            </div>
          </div>
        </div>

        <AdminSaveBar>
          <button type="button" onClick={saveHero} disabled={saving || uploading} className="rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white disabled:opacity-60">
            {saving ? "Saving..." : "Save changes"}
          </button>
          {dirty ? <span className="text-sm text-[var(--muted)]">Unsaved changes</span> : null}
        </AdminSaveBar>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Link href="/" className="rounded-full border border-[var(--line)] px-5 py-3 text-sm font-medium text-[var(--ink)]">
            View home page
          </Link>
        </div>

      </section>
    </fieldset>
    </>
  );
}
