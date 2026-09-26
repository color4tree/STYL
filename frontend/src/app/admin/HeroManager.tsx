"use client";

import Link from "next/link";
import { useEffect, useState, type ChangeEvent } from "react";
import { API_BASE, resolveProductImage } from "@/lib/api";
import { defaultHero, fetchHero, type Hero } from "@/lib/hero";
import { AdminNotice, AdminSaveBar, inputClass, type AdminMessage } from "./AdminFields";

const textFields: { key: Exclude<keyof Hero, "image">; label: string; maxLength: number }[] = [
  { key: "tag", label: "Top-left tag", maxLength: 40 },
  { key: "number", label: "Top-right number", maxLength: 10 },
  { key: "eyebrow", label: "Small heading", maxLength: 60 },
  { key: "title", label: "Title", maxLength: 80 },
];

export default function HeroManager({ adminToken, onBusyChange, onDirtyChange }: { adminToken: string; onBusyChange: (busy: boolean) => void; onDirtyChange: (dirty: boolean) => void }) {
  const [form, setForm] = useState<Hero>(defaultHero);
  const [baseline, setBaseline] = useState(JSON.stringify(defaultHero));
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [retry, setRetry] = useState(0);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<AdminMessage | null>(null);
  const dirty = JSON.stringify(form) !== baseline;
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false); }, [dirty, onDirtyChange]);
  useEffect(() => { onBusyChange(loading || saving || uploading); return () => onBusyChange(false); }, [loading, saving, uploading, onBusyChange]);
  useEffect(() => {
    let active = true;
    fetchHero().then((item) => {
      if (!active) return;
      setForm(item);
      setBaseline(JSON.stringify(item));
      setLoaded(true);
      setMessage(null);
    }).catch((error) => {
      if (active) setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to load home banner." });
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);

  const updateField = <K extends keyof Hero>(key: K, value: Hero[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setMessage((current) => current?.type === "success" ? null : current);
  };
  const uploadImage = async (event: ChangeEvent<HTMLInputElement>) => {
    const image = event.target.files?.[0];
    event.target.value = "";
    if (!image) return;
    if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(image.type) || image.size > 8 * 1024 * 1024) {
      setMessage({ type: "error", text: "Use a JPG, PNG, WebP, or GIF image up to 8 MiB." });
      return;
    }
    setUploading(true);
    onBusyChange(true);
    setMessage(null);
    try {
      const body = new FormData();
      body.append("image", image);
      const response = await fetch(`${API_BASE}/api/uploads/product-image`, { method: "POST", headers: { Authorization: `Bearer ${adminToken}` }, body });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Unable to upload banner image.");
      if (typeof data.image !== "string") throw new Error("The server did not return an image path.");
      updateField("image", data.image);
      setMessage({ type: "success", text: "Photo uploaded. Save changes to update the banner." });
    } catch (error) { setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to upload banner image." }); }
    finally { setUploading(false); }
  };
  const save = async () => {
    setSaving(true);
    onBusyChange(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_BASE}/api/hero`, { method: "PUT", headers: { Authorization: `Bearer ${adminToken}`, "Content-Type": "application/json" }, body: JSON.stringify(form) });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Unable to save home banner.");
      setForm(data.item as Hero);
      setBaseline(JSON.stringify(data.item));
      setMessage({ type: "success", text: "Home banner saved successfully." });
    } catch (error) { setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to save home banner." }); }
    finally { setSaving(false); }
  };
  if (loading) return <p role="status">Loading home banner...</p>;
  return <>
    <AdminNotice message={message} />
    {!loaded ? <button type="button" className="min-h-11 rounded-full border px-5" onClick={() => { setLoading(true); setRetry((value) => value + 1); }}>Retry loading banner</button> : null}
    <fieldset disabled={!loaded || saving || uploading} className="grid min-w-0 items-start gap-8 lg:grid-cols-[0.8fr_1.2fr]">
      <aside className="min-w-0 rounded-3xl border border-[var(--line)] bg-white/80 p-4">
        <h2 className="mb-4 text-lg font-semibold">Preview</h2>
        <div className="rounded-3xl bg-[linear-gradient(135deg,#1c1c1c,#504639)] p-5 text-white">
          <div className="flex items-center justify-between gap-3 text-sm text-white/80"><span>{form.tag}</span><span>{form.number}</span></div>
          <img src={resolveProductImage(form.image)} alt="Home banner preview" className="my-4 h-48 w-full rounded-2xl object-cover" />
          <p className="text-sm text-white/80">{form.eyebrow}</p>
          <p className="mt-2 break-words text-2xl font-semibold">{form.title}</p>
        </div>
      </aside>
      <section className="min-w-0 rounded-3xl border border-[var(--line)] bg-white/80 p-5 sm:p-6">
        <h2 className="text-xl font-semibold">Home banner</h2>
        <p className="mt-3 text-sm text-[var(--muted)]">Edit the banner text and picture independently of the catalog. No price is shown. The public banner remains hidden on phone-sized screens.</p>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          {textFields.map((field) => <label key={field.key} className="block text-sm font-medium">{field.label}
            <input value={form[field.key]} maxLength={field.maxLength} onChange={(event) => updateField(field.key, event.target.value)} className={inputClass} />
          </label>)}
          <div className="md:col-span-2">
            <label className="block text-sm font-medium">Banner photo
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={uploadImage} className="mt-3 block w-full text-sm" />
            </label>
            <p className="mt-2 text-sm text-[var(--muted)]">JPG, PNG, WebP, or GIF up to 8 MiB.</p>
            <label className="mt-4 block text-sm font-medium">Banner image URL or path
              <input value={form.image} maxLength={500} onChange={(event) => updateField("image", event.target.value)} className={inputClass} />
            </label>
          </div>
        </div>
        <AdminSaveBar><button type="button" onClick={save} className="min-h-12 rounded-full bg-[var(--ink)] px-5 py-3 font-medium text-white">{saving ? "Saving..." : "Save changes"}</button>{dirty ? <span className="text-sm">Unsaved changes</span> : null}</AdminSaveBar>
        <Link href="/" className="mt-3 inline-flex min-h-11 items-center text-sm underline">View portal</Link>
      </section>
    </fieldset>
  </>;
}
