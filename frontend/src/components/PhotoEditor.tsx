"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { ArrowLeft, ArrowRight, Plus, Star, Trash2, Upload } from "lucide-react";
import { API_BASE, resolveProductImage } from "@/lib/api";
import { getCatalogCover, isVideo, MAX_PHOTOS, MAX_VIDEO_SIZE } from "@/lib/catalogDetails";
import CatalogVideo from "@/components/CatalogVideo";

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
  const uploading = useRef(false);
  const cover = getCatalogCover(photos);

  const uploadFiles = async (files: File[]) => {
    if (!files.length || disabled || uploading.current) return;
    if (files.length + photos.length > MAX_PHOTOS) {
      setMessage(`A maximum of ${MAX_PHOTOS} photos and videos combined is allowed.`);
      return;
    }
    if (files.some((file) => isVideo(file.name) ? file.size > MAX_VIDEO_SIZE : !["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type) || file.size > 8 * 1024 * 1024)) {
      setMessage("Photos: JPG, PNG, WebP, GIF up to 8 MB. Videos: MP4, MOV, M4V, WebM, MKV, AVI up to 50 MB.");
      return;
    }
    uploading.current = true;
    onBusyChange(true);
    setMessage("Uploading media...");
    const next = [...photos];
    const failures: string[] = [];
    try {
      for (const [index, file] of files.entries()) {
        try {
          const body = new FormData();
          const video = isVideo(file.name);
          setMessage(`${index + 1} of ${files.length}: ${video ? "Uploading and processing" : "Uploading"} ${file.name}...`);
          body.append(video ? "video" : "image", file);
          const response = await fetch(`${API_BASE}/api/uploads/product-${video ? "video" : "image"}`, {
            method: "POST", headers: { Authorization: `Bearer ${adminToken}` }, body,
          });
          const data = await response.json();
          if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Unable to upload media.");
          next.push((video ? data.video : data.image) as string);
          onChange([...next]);
        } catch (error) {
          failures.push(`${file.name}: ${error instanceof Error ? error.message : "Upload failed."}`);
        }
      }
      setMessage(`${next.length - photos.length} of ${files.length} files uploaded.${failures.length ? ` ${failures.join(" ")}` : ""}`);
    } finally {
      uploading.current = false;
      onBusyChange(false);
    }
  };

  const upload = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    void uploadFiles(files);
  };

  const dropFiles = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    void uploadFiles(Array.from(event.dataTransfer.files));
  };

  const addUrl = () => {
    const value = url.trim();
    if (!/^(\/images\/|\/api\/uploads\/|https:\/\/)/.test(value)) {
      setMessage("Use an /images/ or /api/uploads/ path, or an HTTPS URL.");
      return;
    }
    if (photos.includes(value)) {
      setMessage("This file is already in the gallery.");
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
      <legend className="text-lg font-semibold">Photos &amp; videos ({photos.length}/{MAX_PHOTOS})</legend>
      <div className="grid gap-4 sm:grid-cols-2">
        {photos.map((photo, index) => (
          <div key={photo} className="min-w-0">
            {isVideo(photo) ? <CatalogVideo key={photo} src={photo} name={`Item ${index + 1}`} className="aspect-[4/3] w-full rounded-lg bg-neutral-100 object-contain" /> : <img src={resolveProductImage(photo)} alt={`Photo ${index + 1}`} className="aspect-[4/3] w-full rounded-lg bg-neutral-100 object-contain" />}
            <div className="mt-2 flex flex-wrap items-center gap-1">
              <button type="button" title={photo === cover ? "Main photo" : "Set as main photo"} aria-label={`Set photo ${index + 1} as main`} aria-pressed={photo === cover} disabled={photo === cover || isVideo(photo)} onClick={() => move(index, 0)} className={controlClass}>
                <Star size={16} fill={photo === cover ? "currentColor" : "none"} />
              </button>
              <button type="button" title="Move earlier" aria-label={`Move media ${index + 1} earlier`} disabled={index === 0} onClick={() => move(index, index - 1)} className={controlClass}><ArrowLeft size={16} /></button>
              <button type="button" title="Move later" aria-label={`Move media ${index + 1} later`} disabled={index === photos.length - 1} onClick={() => move(index, index + 1)} className={controlClass}><ArrowRight size={16} /></button>
              <button type="button" title="Remove media" aria-label={`Remove media ${index + 1}`} onClick={() => onChange(photos.filter((_, photoIndex) => photoIndex !== index))} className={`${controlClass} text-red-700`}><Trash2 size={16} /></button>
              <span className="ml-1 text-xs text-[var(--muted)]">{photo === cover ? "Main photo" : isVideo(photo) ? "Video" : index + 1}</span>
            </div>
          </div>
        ))}
      </div>
      <label onDragOver={(event) => event.preventDefault()} onDrop={dropFiles} className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-dashed border-[var(--line)] bg-neutral-50 p-4 text-sm font-medium">
        <Upload size={18} aria-hidden="true" /> Upload files (photos 8 MB / videos 50 MB)
        <input type="file" multiple accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime,video/webm,video/x-m4v,video/x-matroska,video/x-msvideo,.mov,.mp4,.m4v,.webm,.mkv,.avi" disabled={photos.length >= MAX_PHOTOS} onChange={upload} className="min-w-0 flex-1 text-xs file:mr-2 file:rounded-md file:border file:border-[var(--line)] file:bg-white file:px-2 file:py-2" />
      </label>
      <div className="mt-3 flex items-end gap-2">
        <label className="min-w-0 flex-1 text-sm font-medium">
          Media URL or path
          <input value={url} onChange={(event) => setUrl(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); if (url.trim() && photos.length < MAX_PHOTOS) addUrl(); } }} className="mt-2 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2" />
        </label>
        <button type="button" title="Add media URL" aria-label="Add media URL" disabled={!url.trim() || photos.length >= MAX_PHOTOS} onClick={addUrl} className={controlClass}><Plus size={18} /></button>
      </div>
      {message ? <p role="status" className="mt-3 break-words text-sm text-[var(--muted)]">{message}</p> : null}
    </fieldset>
  );
}