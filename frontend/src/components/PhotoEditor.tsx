"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { ArrowLeft, ArrowRight, Plus, Star, Trash2, Upload } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { getCatalogCover, isVideo, MAX_PHOTOS, MAX_VIDEO_SIZE } from "@/lib/catalogDetails";
import CatalogVideo from "@/components/CatalogVideo";
import CatalogImage from "@/components/CatalogImage";

const controlClass = "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-[var(--line)] bg-white hover:bg-neutral-100 disabled:opacity-30";
const fileKey = (file: File) => JSON.stringify([file.name, file.size, file.type, file.lastModified]);

export default function PhotoEditor({ photos, onChange, adminToken, disabled, onBusyChange }: {
  photos: string[];
  onChange: (photos: string[]) => void;
  adminToken: string;
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
}) {
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [failures, setFailures] = useState<{ file: File; message: string }[]>([]);
  const [progress, setProgress] = useState<{ completed: number; total: number } | null>(null);
  const uploading = useRef(false);
  const uploaded = useRef(new Map<string, string>());
  const cover = getCatalogCover(photos);

  const uploadFiles = async (files: File[]) => {
    if (!files.length || disabled || uploading.current) return;
    files = [...new Map(files.map((file) => [fileKey(file), file])).values()].filter((file) => {
      const path = uploaded.current.get(fileKey(file));
      return !path || !photos.includes(path);
    });
    if (!files.length) { setMessage("These files are already in the gallery."); return; }
    if (files.length + photos.length > MAX_PHOTOS) {
      setMessage(`A maximum of ${MAX_PHOTOS} photos and videos combined is allowed.`);
      return;
    }
    uploading.current = true;
    setProgress({ completed: 0, total: files.length });
    onBusyChange(true);
    setMessage("Uploading media...");
    const next = [...photos];
    const failed: { file: File; message: string }[] = [];
    const attempted = new Set(files.map(fileKey));
    setFailures((previous) => previous.filter(({ file }) => !attempted.has(fileKey(file))));
    try {
      for (const [index, file] of files.entries()) {
        try {
          const body = new FormData();
          const video = isVideo(file.name);
          if (video ? file.size > MAX_VIDEO_SIZE : !["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type) || file.size > 8 * 1024 * 1024) {
            throw new Error(video ? "Video exceeds 50 MiB. Trim or compress it before selecting it again." : "Use JPG, PNG, WebP or GIF, up to 8 MiB.");
          }
          setMessage(`${index + 1} of ${files.length}: ${video ? "Uploading and processing" : "Uploading"} ${file.name}...`);
          body.append(video ? "video" : "image", file);
          const response = await fetch(`${API_BASE}/api/uploads/product-${video ? "video" : "image"}`, {
            method: "POST", headers: { Authorization: `Bearer ${adminToken}` }, body,
          });
          const data = await response.json();
          if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Unable to upload media.");
          const path: unknown = video ? data.video : data.image;
          if (typeof path !== "string" || !path) throw new Error("The server did not return a media path.");
          uploaded.current.set(fileKey(file), path);
          if (!next.includes(path)) next.push(path);
          onChange([...next]);
        } catch (error) {
          failed.push({ file, message: error instanceof Error ? error.message : "Upload failed." });
        } finally {
          setProgress({ completed: index + 1, total: files.length });
        }
      }
      setFailures((previous) => [...previous, ...failed]);
      setMessage(`${files.length - failed.length} of ${files.length} files uploaded. ${failed.length ? `${failed.length} failed; successful uploads remain in the gallery. ` : ""}Save the item to keep your changes.`);
    } finally {
      uploading.current = false;
      setProgress(null);
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
    if (disabled || uploading.current || photos.length >= MAX_PHOTOS) return;
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
    <fieldset disabled={disabled || progress !== null} className="min-w-0 border-t border-[var(--line)] pt-5 md:col-span-2">
      <legend className="text-lg font-semibold">Photos &amp; videos ({photos.length}/{MAX_PHOTOS})</legend>
      <p className="mb-4 text-sm text-[var(--muted)]">The first item opens the gallery, including a video. The first photo is the catalog thumbnail. Without photos, the first video’s generated poster is used when available; otherwise there is no thumbnail. “Use as thumbnail and show first” moves a photo to the beginning.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {photos.map((photo, index) => (
          <div key={photo} className="min-w-0">
            {isVideo(photo) ? <CatalogVideo key={photo} src={photo} name={`Item ${index + 1}`} className="aspect-[4/3] w-full rounded-lg bg-neutral-100 object-contain" /> : <CatalogImage key={photo} src={photo} alt={`Photo ${index + 1}`} className="aspect-[4/3] h-auto w-full rounded-lg bg-neutral-100 object-contain" />}
            <div className="mt-2 flex flex-wrap items-center gap-1">
              <button type="button" title="Use as thumbnail and show first" aria-label={`Photo ${index + 1}: Use as thumbnail and show first`} disabled={index === 0 || isVideo(photo)} onClick={() => move(index, 0)} className={controlClass}>
                <Star size={16} fill={photo === cover ? "currentColor" : "none"} />
              </button>
              <button type="button" title="Move earlier" aria-label={`Move media ${index + 1} earlier`} disabled={index === 0} onClick={() => move(index, index - 1)} className={controlClass}><ArrowLeft size={16} /></button>
              <button type="button" title="Move later" aria-label={`Move media ${index + 1} later`} disabled={index === photos.length - 1} onClick={() => move(index, index + 1)} className={controlClass}><ArrowRight size={16} /></button>
              <button type="button" title="Remove media" aria-label={`Remove media ${index + 1}`} onClick={() => onChange(photos.filter((_, photoIndex) => photoIndex !== index))} className={`${controlClass} text-red-700`}><Trash2 size={16} /></button>
              <span className="ml-1 text-xs text-[var(--muted)]">{isVideo(photo) ? "Video" : "Photo"} {index + 1}{photo === cover ? " · Thumbnail" : ""}{index === 0 ? " · Opens gallery" : ""}</span>
            </div>
          </div>
        ))}
      </div>
      <label onDragOver={(event) => event.preventDefault()} onDrop={dropFiles} className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-dashed border-[var(--line)] bg-neutral-50 p-4 text-sm font-medium">
        <Upload size={18} aria-hidden="true" /> Upload files (photos 8 MiB / videos 50 MiB)
        <input type="file" multiple accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime,video/webm,video/x-m4v,video/x-matroska,video/x-msvideo,.mov,.mp4,.m4v,.webm,.mkv,.avi" disabled={photos.length >= MAX_PHOTOS} onChange={upload} className="min-h-11 min-w-0 flex-1 text-xs file:mr-2 file:min-h-11 file:rounded-md file:border file:border-[var(--line)] file:bg-white file:px-2 file:py-2" />
      </label>
      <p className="mt-2 text-xs text-[var(--muted)]">JPG, PNG, WebP, GIF; MP4, MOV, M4V, WebM, MKV, AVI. Uploaded videos convert to H.264/AAC MP4 (up to 1280 px), with audio retained and a poster generated. Export SDR for reliable color. Originals are discarded—keep your own copy. URL media is not converted. Keep important information available as text, not only audio.</p>
      <div className="mt-3 flex items-end gap-2">
        <label className="min-w-0 flex-1 text-sm font-medium">
          Media URL or path
          <input value={url} onChange={(event) => setUrl(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); if (url.trim() && photos.length < MAX_PHOTOS) addUrl(); } }} className="mt-2 min-h-11 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2" />
        </label>
        <button type="button" title="Add media URL" aria-label="Add media URL" disabled={!url.trim() || photos.length >= MAX_PHOTOS} onClick={addUrl} className={controlClass}><Plus size={18} /></button>
      </div>
      <p role="status" aria-atomic="true" className="mt-3 break-words text-sm text-[var(--muted)]">{message}</p>
      {progress ? <div className="mt-2 text-sm"><progress aria-label="Files processed (upload and conversion)" value={progress.completed} max={progress.total} className="w-full" /><p>{progress.completed} of {progress.total} files processed. Video conversion may take several minutes.</p></div> : null}
      {failures.length ? <div className="mt-3 text-sm">
        <ul role="alert" aria-label="Failed uploads" className="list-inside list-disc break-words text-red-700">{failures.map(({ file, message }) => <li key={fileKey(file)}>{file.name}: {message}</li>)}</ul>
        <button type="button" onClick={() => void uploadFiles(failures.map(({ file }) => file))} className="mt-2 min-h-11 rounded-md border border-[var(--line)] bg-white px-3">Retry failed files only ({failures.length})</button>
        <button type="button" onClick={() => setFailures([])} className="ml-2 mt-2 min-h-11 rounded-md px-3 underline">Dismiss failures</button>
        <p className="mt-1 text-xs text-[var(--muted)]">Retries restart failed uploads; successful files are not uploaded again. Fix unsupported or oversized files, then select them again.</p>
      </div> : null}
    </fieldset>
  );
}