"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, type ChangeEvent } from "react";
import { Upload } from "lucide-react";
import { API_BASE, resolveProductImage } from "@/lib/api";
import { changedHeroFields, defaultHero, fetchHero, isEngineeringImage, parseHero, type EngineeringCard, type Hero } from "@/lib/hero";
import { AdminNotice, AdminSaveBar, inputClass, type AdminMessage } from "./AdminFields";
import CatalogImage from "@/components/CatalogImage";

const textFields: { key: "tag" | "number" | "eyebrow" | "title"; label: string; maxLength: number }[] = [
  { key: "tag", label: "Top-left tag", maxLength: 40 },
  { key: "number", label: "Top-right number", maxLength: 10 },
  { key: "eyebrow", label: "Small heading", maxLength: 60 },
  { key: "title", label: "Title", maxLength: 80 },
];

function PhotoPicker({ label, buttonLabel, onChange }: {
  label: string; buttonLabel: string; onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const hint = useId();
  return <div className="min-w-0 rounded-2xl border border-dashed border-[var(--line)] bg-neutral-50 p-4">
    <p className="text-sm font-medium">{label}</p>
    <input ref={input} type="file" aria-label={label} accept="image/jpeg,image/png,image/webp,image/gif" onChange={onChange} hidden />
    <button type="button" aria-label={buttonLabel} aria-describedby={hint} onClick={() => input.current?.click()}
      className="mt-3 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-full border border-[var(--ink)] bg-white px-5 py-3 text-sm font-semibold text-[var(--ink)] hover:bg-neutral-100 disabled:opacity-50 sm:w-auto">
      <Upload size={18} aria-hidden="true" />
      Choose photo
    </button>
    <p id={hint} className="mt-2 text-xs leading-5 text-[var(--muted)]">Click to choose or replace a photo. JPG, PNG, WebP or GIF up to 8 MiB. Choose Save changes to publish.</p>
  </div>;
}

export default function HeroManager({ adminToken, onBusyChange, onDirtyChange }: { adminToken: string; onBusyChange: (busy: boolean) => void; onDirtyChange: (dirty: boolean) => void }) {
  const [form, setForm] = useState<Hero>(defaultHero);
  const [baseline, setBaseline] = useState(JSON.stringify(defaultHero));
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [retry, setRetry] = useState(0);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<AdminMessage | null>(null);
  const pending = useRef(false);
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
  const updateCard = (index: number, key: keyof EngineeringCard, value: string) => {
    setForm(current => ({ ...current, engineering: { ...current.engineering,
      items: current.engineering.items.map((item, slot) => slot === index ? { ...item, [key]: value } : item),
    } }));
    setMessage(current => current?.type === "success" ? null : current);
  };
  const uploadImage = async (event: ChangeEvent<HTMLInputElement>, cardIndex?: number) => {
    const image = event.target.files?.[0];
    event.target.value = "";
    if (!image || pending.current) return;
    if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(image.type) || image.size > 8 * 1024 * 1024) {
      setMessage({ type: "error", text: "Use a JPG, PNG, WebP, or GIF image up to 8 MiB." });
      return;
    }
    pending.current = true;
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
      if (cardIndex === undefined) updateField("image", data.image);
      else updateCard(cardIndex, "image", data.image);
      setMessage({ type: "success", text: `Photo uploaded. Save changes to update ${cardIndex === undefined ? "the banner" : `engineering card ${cardIndex + 1}`}.` });
    } catch (error) { setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to upload banner image." }); }
    finally { pending.current = false; setUploading(false); }
  };
  const save = async () => {
    if (pending.current) return;
    if (!form.engineering.heading.trim() || form.engineering.items.some(item => !item.title.trim() || !item.image.trim())) {
      setMessage({ type: "error", text: "Enter an engineering section heading and a title and image for each of the four cards." });
      return;
    }
    if (form.engineering.items.some(item => !isEngineeringImage(item.image))) {
      setMessage({ type: "error", text: "Use an uploaded image path or an HTTP/HTTPS image URL for each engineering card. Videos are not supported here." });
      return;
    }
    pending.current = true;
    setSaving(true);
    onBusyChange(true);
    setMessage(null);
    try {
      const changes = changedHeroFields(form, parseHero(JSON.parse(baseline)));
      const response = await fetch(`${API_BASE}/api/hero`, { method: "PUT", headers: { Authorization: `Bearer ${adminToken}`, "Content-Type": "application/json" }, body: JSON.stringify(changes) });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Unable to save home banner.");
      const saved = parseHero(data.item);
      setForm(saved);
      setBaseline(JSON.stringify(saved));
      setMessage({ type: "success", text: "Home banner and engineering details saved successfully." });
    } catch (error) { setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to save home banner." }); }
    finally { pending.current = false; setSaving(false); }
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
            <PhotoPicker label="Banner photo" buttonLabel="Choose banner photo" onChange={event => void uploadImage(event)} />
            <label className="mt-4 block text-sm font-medium">Banner image URL or path
              <input value={form.image} maxLength={500} onChange={(event) => updateField("image", event.target.value)} className={inputClass} />
            </label>
          </div>
        </div>
      </section>
      <section aria-labelledby="engineering-editor-title" className="min-w-0 rounded-3xl border border-[var(--line)] bg-white/80 p-5 sm:p-6 lg:col-span-2">
        <h2 id="engineering-editor-title" className="text-xl font-semibold">Engineering details</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--muted)]">Replace the pictures and text in the four-card section near the bottom of the home page. These cards are separate from the equipment catalog. Upload images for a self-contained recovery backup.</p>
        <div className="mt-5 grid min-w-0 gap-5">
          <label className="block min-w-0 text-sm font-medium">Engineering section heading
            <input value={form.engineering.heading} maxLength={120} onChange={event => updateField("engineering", { ...form.engineering, heading: event.target.value })} className={inputClass} />
          </label>
          <label className="block min-w-0 text-sm font-medium">Engineering introduction
            <textarea aria-label="Engineering introduction" value={form.engineering.intro} maxLength={1000} rows={2} onChange={event => updateField("engineering", { ...form.engineering, intro: event.target.value })} className={`${inputClass} text-base`} />
          </label>
        </div>
        <div className="mt-6 grid min-w-0 gap-5 lg:grid-cols-2">
          {form.engineering.items.map((item, index) => <fieldset key={index} className="min-w-0 rounded-2xl border border-[var(--line)] p-4">
            <legend className="px-2 font-semibold">Engineering card {index + 1}</legend>
            {isEngineeringImage(item.image) ? <CatalogImage key={item.image} src={item.image.trim()} alt={`Engineering card ${index + 1} preview`} className="aspect-[4/3] h-auto w-full rounded-xl object-cover" />
              : <div className="flex aspect-[4/3] items-center justify-center rounded-xl bg-neutral-100 p-4 text-center text-sm text-[var(--muted)]">Enter an image path or upload a photo to preview this card.</div>}
            <label className="mt-4 block text-sm font-medium">Card {index + 1} title
              <input value={item.title} maxLength={120} onChange={event => updateCard(index, "title", event.target.value)} className={inputClass} />
            </label>
            <label className="mt-4 block text-sm font-medium">Card {index + 1} description
              <textarea aria-label={`Card ${index + 1} description`} value={item.description} maxLength={2000} rows={3} onChange={event => updateCard(index, "description", event.target.value)} className={`${inputClass} text-base`} />
            </label>
            <div className="mt-4"><PhotoPicker label={`Card ${index + 1} photo`} buttonLabel={`Choose photo for engineering card ${index + 1}`} onChange={event => void uploadImage(event, index)} /></div>
            <label className="mt-4 block text-sm font-medium">Card {index + 1} image URL or path
              <input value={item.image} maxLength={500} onChange={event => updateCard(index, "image", event.target.value)} className={inputClass} />
            </label>
          </fieldset>)}
        </div>
      </section>
      <div className="min-w-0 lg:col-span-2">
        <AdminSaveBar><button type="button" onClick={save} className="min-h-12 rounded-full bg-[var(--ink)] px-5 py-3 font-medium text-white">{saving ? "Saving..." : "Save changes"}</button>{dirty ? <span className="text-sm">Unsaved changes</span> : null}</AdminSaveBar>
        <Link href="/" className="mt-3 inline-flex min-h-12 items-center text-sm underline">View portal</Link>
      </div>
    </fieldset>
  </>;
}
