"use client";

import { useRef, useState, type MouseEvent, type TouchEvent } from "react";
import { ChevronLeft, ChevronRight, Expand, Play, X, ZoomIn, ZoomOut } from "lucide-react";
import { getVideoPoster, isVideo } from "@/lib/catalogDetails";
import CatalogImage from "@/components/CatalogImage";
import CatalogVideo from "@/components/CatalogVideo";

const controlClass = "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-[var(--line)] bg-white hover:bg-neutral-100 disabled:opacity-30";

export default function PhotoGallery({ photos, name, compact = false }: { photos: string[]; name: string; compact?: boolean }) {
  const [selected, setSelected] = useState(0);
  const [zoomed, setZoomed] = useState(false);
  const [opened, setOpened] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const enlargeButton = useRef<HTMLButtonElement>(null);
  const touch = useRef<{ x: number; y: number } | null>(null);
  const swiped = useRef(false);
  const index = Math.min(selected, Math.max(photos.length - 1, 0));
  const active = photos[index];
  const changePhoto = (next: number) => { setSelected(next); setZoomed(false); };
  const open = () => {
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    document.querySelectorAll("video").forEach((video) => video.pause());
    setOpened(true);
    dialog.current?.showModal();
  };
  const startTouch = (event: TouchEvent<HTMLDivElement>) => {
    swiped.current = false;
    touch.current = !zoomed && event.touches.length === 1 && !(event.target instanceof HTMLElement && event.target.closest("video, a"))
      ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null;
  };
  const endTouch = (event: TouchEvent<HTMLDivElement>) => {
    const start = touch.current;
    touch.current = null;
    if (!start || !event.changedTouches.length) return;
    const dx = event.changedTouches[0].clientX - start.x;
    const dy = event.changedTouches[0].clientY - start.y;
    if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
    swiped.current = true;
    changePhoto(Math.max(0, Math.min(photos.length - 1, index + (dx < 0 ? 1 : -1))));
  };
  const swipeHandlers = {
    onTouchStart: startTouch,
    onTouchMove: (event: TouchEvent<HTMLDivElement>) => {
      if (event.touches.length !== 1 || (touch.current && Math.abs(event.touches[0].clientY - touch.current.y) > 30)) touch.current = null;
    },
    onTouchEnd: endTouch,
    onTouchCancel: () => { touch.current = null; },
    onClickCapture: (event: MouseEvent<HTMLDivElement>) => {
      if (swiped.current) { event.preventDefault(); event.stopPropagation(); swiped.current = false; }
    },
  };
  const navigation = (enlarged = false) => (
    <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
      <button type="button" title="Previous media" aria-label="Previous media" disabled={index === 0} onClick={() => changePhoto(index - 1)} className={controlClass}><ChevronLeft size={20} /></button>
      <span className="min-w-12 text-center text-sm" role="status" aria-atomic="true">{photos.length ? index + 1 : 0} / {photos.length}</span>
      <button type="button" title="Next media" aria-label="Next media" disabled={index >= photos.length - 1} onClick={() => changePhoto(index + 1)} className={controlClass}><ChevronRight size={20} /></button>
      {enlarged ? <button type="button" disabled={!active || isVideo(active)} title={zoomed ? "Zoom out" : "Zoom in"} aria-label={zoomed ? "Zoom out" : "Zoom in"} aria-pressed={zoomed} onClick={() => setZoomed(!zoomed)} className={controlClass}>{zoomed ? <ZoomOut size={20} /> : <ZoomIn size={20} />}</button> :
        <button ref={enlargeButton} type="button" disabled={!active} title="Enlarge media" aria-label={`Enlarge ${name} media ${index + 1}`} onClick={open} className={controlClass}><Expand size={20} /></button>}
    </div>
  );

  return (
    <div className="min-w-0" role="group" aria-label={`${name} photos and videos`}>
      <div {...swipeHandlers} className={`overflow-hidden rounded-lg bg-neutral-100 ${compact ? "h-52" : "aspect-[4/3]"}`} style={{ touchAction: "pan-y pinch-zoom" }}>
        {opened ? <div className="flex h-full items-center justify-center text-sm">Media open in enlarged view</div> :
          active && isVideo(active) ? <CatalogVideo key={active} src={active} name={name} preload={compact ? "none" : "metadata"} className="h-full w-full object-contain" /> :
            active ? <CatalogImage key={active} src={active} alt={`${name} - photo ${index + 1}`} className="h-full w-full object-contain" onOpen={open} /> :
              <div role="status" className="flex h-full items-center justify-center text-sm text-[var(--muted)]">Photo unavailable</div>}
      </div>
      {navigation()}
      {photos.length > 1 ? (
        <div className="mt-2 flex gap-2 overflow-x-auto pb-2" aria-label="Media thumbnails">
          {photos.map((photo, photoIndex) => (
            <button key={photo} type="button" aria-label={`Show ${name} ${isVideo(photo) ? "video" : "photo"} ${photoIndex + 1}`} aria-pressed={index === photoIndex} onClick={() => changePhoto(photoIndex)} className={`relative h-14 w-14 shrink-0 overflow-hidden rounded-md border-2 bg-neutral-100 ${index === photoIndex ? "border-[var(--ink)]" : "border-transparent"}`}>
              {!isVideo(photo) || getVideoPoster(photo) ? <CatalogImage key={photo} src={isVideo(photo) ? getVideoPoster(photo)! : photo} alt="" thumbnail className="h-full w-full object-contain" /> : null}
              {isVideo(photo) ? <Play size={20} aria-hidden="true" className="absolute inset-0 m-auto rounded bg-white/90 p-1 box-content" /> : null}
            </button>
          ))}
        </div>
      ) : null}
      <dialog ref={dialog} aria-label={`${name} enlarged media`} onClose={() => {
        dialog.current?.querySelectorAll("video").forEach((video) => video.pause());
        setZoomed(false);
        setOpened(false);
        requestAnimationFrame(() => (opener.current?.isConnected ? opener.current : enlargeButton.current)?.focus());
      }} onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close(); }} onKeyDown={(event) => {
        if (event.key === "Escape") { event.preventDefault(); dialog.current?.close(); return; }
        if (event.target instanceof HTMLElement && event.target.closest("video")) return;
        if (event.key === "ArrowLeft" && index > 0) { event.preventDefault(); changePhoto(index - 1); }
        if (event.key === "ArrowRight" && index < photos.length - 1) { event.preventDefault(); changePhoto(index + 1); }
      }} className="fixed inset-0 m-auto max-h-[94dvh] w-[94vw] max-w-5xl overflow-y-auto rounded-lg bg-white p-3 text-[var(--ink)] backdrop:bg-black/70 sm:p-4">
        <div className="sticky top-0 z-10 mb-3 flex items-start justify-between gap-3 bg-white pb-2">
          <h2 className="min-w-0 break-words text-base font-semibold">{name}</h2>
          <button type="button" title="Close" aria-label="Close enlarged media" onClick={() => dialog.current?.close()} className={controlClass}><X size={20} /></button>
        </div>
        <div {...swipeHandlers} className="max-h-[60dvh] overflow-auto bg-neutral-100" style={{ touchAction: zoomed ? "auto" : "pan-y pinch-zoom" }}>
          {opened && active ? isVideo(active) ? <CatalogVideo key={active} src={active} name={name} preload="metadata" className="h-[min(55dvh,40rem)] w-full object-contain" /> :
            <CatalogImage key={active} src={active} alt={`${name} - photo ${index + 1}, enlarged`} className={zoomed ? "h-auto w-[200%] max-w-none" : "h-[min(55dvh,40rem)] w-full object-contain"} /> : null}
        </div>
        {navigation(true)}
      </dialog>
    </div>
  );
}
