"use client";

import { useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Expand, Play, X, ZoomIn, ZoomOut } from "lucide-react";
import { resolveProductImage } from "@/lib/api";
import { getVideoPoster, isVideo } from "@/lib/catalogDetails";
import CatalogVideo from "@/components/CatalogVideo";

const controlClass = "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-[var(--line)] bg-white hover:bg-neutral-100 disabled:opacity-30";

export default function PhotoGallery({ photos, name, compact = false }: { photos: string[]; name: string; compact?: boolean }) {
  const [selected, setSelected] = useState(0);
  const [zoomed, setZoomed] = useState(false);
  const [opened, setOpened] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const index = Math.min(selected, Math.max(photos.length - 1, 0));
  const active = photos[index];
  const changePhoto = (next: number) => { setSelected(next); setZoomed(false); };

  return (
    <div className="min-w-0" aria-label={`${name} photos and videos`}>
      {active && isVideo(active) ? (
        <CatalogVideo key={active} src={active} name={name} className={`w-full rounded-lg bg-neutral-100 object-contain ${compact ? "h-52" : "aspect-[4/3]"}`} />
      ) : active ? (
        <button type="button" onClick={() => { setOpened(true); dialog.current?.showModal(); }} aria-label={`Enlarge ${name} photo ${index + 1}`} title="Enlarge photo" className={`relative block w-full overflow-hidden rounded-lg bg-neutral-100 ${compact ? "h-52" : "aspect-[4/3]"}`}>
          <img src={resolveProductImage(active)} alt={`${name} - photo ${index + 1}`} className="h-full w-full object-contain" />
          <Expand size={18} aria-hidden="true" className="absolute bottom-3 right-3 rounded bg-white/90 p-1 box-content" />
        </button>
      ) : <div className={`flex items-center justify-center rounded-lg bg-neutral-100 text-sm text-[var(--muted)] ${compact ? "h-52" : "aspect-[4/3]"}`}>Photo unavailable</div>}
      {photos.length > 1 ? (
        <div className="mt-2 flex gap-2 overflow-x-auto pb-2" aria-label="Media thumbnails">
          {photos.map((photo, photoIndex) => (
            <button key={photo} type="button" aria-label={`Show ${name} ${isVideo(photo) ? "video" : "photo"} ${photoIndex + 1}`} aria-pressed={index === photoIndex} onClick={() => changePhoto(photoIndex)} className={`relative h-14 w-14 shrink-0 overflow-hidden rounded-md border-2 bg-neutral-100 ${index === photoIndex ? "border-[var(--ink)]" : "border-transparent"}`}>
              {!isVideo(photo) || getVideoPoster(photo) ? <img src={resolveProductImage(isVideo(photo) ? getVideoPoster(photo)! : photo)} alt="" className="h-full w-full object-contain" /> : null}
              {isVideo(photo) ? <Play size={20} aria-hidden="true" className="absolute inset-0 m-auto rounded bg-white/90 p-1 box-content" /> : null}
            </button>
          ))}
        </div>
      ) : null}
      <dialog ref={dialog} aria-label={`${name} enlarged media`} onClose={() => { setZoomed(false); setOpened(false); }} onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close(); }} onKeyDown={(event) => {
        if (event.target instanceof HTMLElement && event.target.closest("video")) return;
        if (event.key === "Escape") { event.preventDefault(); dialog.current?.close(); }
        if (event.key === "ArrowLeft" && index > 0) { event.preventDefault(); changePhoto(index - 1); }
        if (event.key === "ArrowRight" && index < photos.length - 1) { event.preventDefault(); changePhoto(index + 1); }
      }} className="fixed inset-0 m-auto max-h-[94dvh] w-[94vw] max-w-5xl rounded-lg bg-white p-4 text-[var(--ink)] backdrop:bg-black/70">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="min-w-0 break-words text-base font-semibold">{name}</h2>
          <button type="button" title="Close" aria-label="Close enlarged photos" onClick={() => dialog.current?.close()} className={controlClass}><X size={20} /></button>
        </div>
        <div className="max-h-[65dvh] overflow-auto bg-neutral-100">
          {opened && active ? isVideo(active) ? <CatalogVideo key={active} src={active} name={name} className="h-[60dvh] w-full object-contain" /> : <img src={resolveProductImage(active)} alt={`${name} - photo ${index + 1}, enlarged`} className={zoomed ? "w-[200%] max-w-none" : "h-[60dvh] w-full object-contain"} /> : null}
        </div>
        <div className="mt-3 flex items-center justify-center gap-3">
          <button type="button" title="Previous media" aria-label="Previous media" disabled={index === 0} onClick={() => changePhoto(index - 1)} className={controlClass}><ChevronLeft size={20} /></button>
          <span className="min-w-12 text-center text-sm" aria-live="polite">{index + 1} / {photos.length}</span>
          <button type="button" title="Next media" aria-label="Next media" disabled={index >= photos.length - 1} onClick={() => changePhoto(index + 1)} className={controlClass}><ChevronRight size={20} /></button>
          <button type="button" disabled={!active || isVideo(active)} title={zoomed ? "Zoom out" : "Zoom in"} aria-label={zoomed ? "Zoom out" : "Zoom in"} onClick={() => setZoomed(!zoomed)} className={controlClass}>{zoomed ? <ZoomOut size={20} /> : <ZoomIn size={20} />}</button>
        </div>
      </dialog>
    </div>
  );
}