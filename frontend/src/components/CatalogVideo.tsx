"use client";

import { useEffect, useRef, useState } from "react";
import { resolveProductImage } from "@/lib/api";
import { getVideoPoster } from "@/lib/catalogDetails";

export default function CatalogVideo({ src, name, className, preload = "none" }: { src: string; name: string; className: string; preload?: "none" | "metadata" }) {
  const [failed, setFailed] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const poster = getVideoPoster(src);

  useEffect(() => {
    const player = video.current;
    if (!player) return;
    const pauseWhenHidden = () => { if (document.hidden) player.pause(); };
    const observer = new IntersectionObserver(([entry]) => { if (!entry.isIntersecting) player.pause(); });
    observer.observe(player);
    document.addEventListener("visibilitychange", pauseWhenHidden);
    return () => {
      player.pause();
      observer.disconnect();
      document.removeEventListener("visibilitychange", pauseWhenHidden);
    };
  }, [src, failed]);

  return failed ? (
    <div className={`${className} flex flex-col items-center justify-center gap-3 bg-neutral-100 p-4 text-sm`}>
      <span role="status">{name}: video playback unavailable.</span>
      <button type="button" onClick={() => setFailed(false)} className="min-h-11 rounded-md border border-[var(--line)] bg-white px-3">Retry video</button>
      <a href={resolveProductImage(src)} target="_blank" rel="noopener noreferrer" download className="inline-flex min-h-11 items-center underline">Download video</a>
    </div>
  ) : (
    <video ref={video} src={resolveProductImage(src)} controls playsInline preload={preload} aria-label={`${name} video — press play to start`} poster={poster ? resolveProductImage(poster) : undefined} className={className} onError={() => setFailed(true)} onPlay={(event) => {
      const player = event.currentTarget;
      const modal = document.querySelector("dialog[open]");
      if (modal && !modal.contains(player)) { player.pause(); return; }
      document.querySelectorAll("video").forEach((other) => { if (other !== player) other.pause(); });
    }}>
      <a href={resolveProductImage(src)}>Download video</a>
    </video>
  );
}