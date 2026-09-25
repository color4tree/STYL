"use client";

import { useState, type ChangeEvent } from "react";
import { ArrowLeft, ArrowRight, Plus, Star, Trash2, Upload } from "lucide-react";
import { API_BASE, resolveProductImage } from "@/lib/api";
import { MAX_PHOTOS } from "@/lib/catalogDetails";

const controlClass = "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-[var(--line)] bg-white hover:bg-neutral-100 disabled:opacity-30";

export default function PhotoEditor({ photos, onChange, adminToken, disabled, onBusyChange }: {
  photos: string[];
  onChange: (photos: string[]) => void;
  adminToken: string;
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
}) {
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    if (files.length + photos.length > MAX_PHOTOS) {
      setMessage(`A maximum of ${MAX_PHOTOS} photos is allowed.`);
      return;
    }
    if (files.some((file) => !["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type) || file.size > 8 * 1024 * 1024)) {
      setMessage("Each photo must be a JPG, PNG, WebP, or GIF of 8 MB or less.");
      return;
    }
    onBusyChange(true);
    setMessage("Uploading photos...");
    const next = [...photos];
    try {
      for (const file of files) {
        const body = new FormData();
        body.append("image", file);
        const response = await fetch(`${API_BASE}/api/uploads/product-image`, {
          method: "POST", headers: { Authorization: `Bearer ${adminToken}` }, body,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Unable to upload photo.");
        next.push(data.image as string);
        onChange([...next]);
      }
      setMessage("Photos uploaded.");
    } catch (error) {
      setMessage(`${error instanceof Error ? error.message : "Upload failed."} ${next.length - photos.length} photos uploaded.`);
    } finally {
      onBusyChange(false);
    }
  };

  const addUrl = () => {
    const value = url.trim();
    if (!/^(\/images\/|\/api\/uploads\/|https:\/\/)/.test(value)) {
      setMessage("Use an /images/ or /api/uploads/ path, or an HTTPS URL.");
      return;
    }
    if (photos.includes(value)) {
      setMessage("This photo is already in the gallery.");
      return;
    }
    onChange([...photos, value]);
    setUrl("");
    setMessage(null);
  };

  const move = (index: number, target: number) => {
    const next = [...photos];
    const [photo] = next.splice(index, 1);
    next.splice(target, 0, photo);
    onChange(next);
  };

  return (
    <fieldset disabled={disabled} className="min-w-0 border-t border-[var(--line)] pt-5 md:col-span-2">
      <legend className="text-lg font-semibold">Photos ({photos.length}/{MAX_PHOTOS})</legend>
      <div className="grid gap-4 sm:grid-cols-2">
        {photos.map((photo, index) => (
          <div key={photo} className="min-w-0">
            <img src={resolveProductImage(photo)} alt={`Photo ${index + 1}`} className="aspect-[4/3] w-full rounded-lg bg-neutral-100 object-contain" />
            <div className="mt-2 flex flex-wrap items-center gap-1">
              <button type="button" title={index === 0 ? "Main photo" : "Set as main photo"} aria-label={`Set photo ${index + 1} as main`} aria-pressed={index === 0} disabled={index === 0} onClick={() => move(index, 0)} className={controlClass}>
                <Star size={16} fill={index === 0 ? "currentColor" : "none"} />
              </button>
              <button type="button" title="Move earlier" aria-label={`Move photo ${index + 1} earlier`} disabled={index === 0} onClick={() => move(index, index - 1)} className={controlClass}><ArrowLeft size={16} /></button>
              <button type="button" title="Move later" aria-label={`Move photo ${index + 1} later`} disabled={index === photos.length - 1} onClick={() => move(index, index + 1)} className={controlClass}><ArrowRight size={16} /></button>
              <button type="button" title="Remove photo" aria-label={`Remove photo ${index + 1}`} onClick={() => onChange(photos.filter((_, photoIndex) => photoIndex !== index))} className={`${controlClass} text-red-700`}><Trash2 size={16} /></button>
              <span className="ml-1 text-xs text-[var(--muted)]">{index === 0 ? "Main photo" : index + 1}</span>
            </div>
          </div>
        ))}
      </div>
      <label className="mt-4 flex items-center gap-2 text-sm font-medium">
        <Upload size={18} aria-hidden="true" /> Upload photos
        <input type="file" multiple accept="image/jpeg,image/png,image/webp,image/gif" disabled={photos.length >= MAX_PHOTOS} onChange={upload} className="min-w-0 flex-1 text-xs file:mr-2 file:rounded-md file:border file:border-[var(--line)] file:bg-white file:px-2 file:py-2" />
      </label>
      <div className="mt-3 flex items-end gap-2">
        <label className="min-w-0 flex-1 text-sm font-medium">
          Photo URL or path
          <input value={url} onChange={(event) => setUrl(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); if (url.trim() && photos.length < MAX_PHOTOS) addUrl(); } }} className="mt-2 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2" />
        </label>
        <button type="button" title="Add photo URL" aria-label="Add photo URL" disabled={!url.trim() || photos.length >= MAX_PHOTOS} onClick={addUrl} className={controlClass}><Plus size={18} /></button>
      </div>
      {message ? <p role="status" className="mt-3 text-sm text-[var(--muted)]">{message}</p> : null}
    </fieldset>
  );
}