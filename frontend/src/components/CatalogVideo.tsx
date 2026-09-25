"use client";

import { useState } from "react";
import { resolveProductImage } from "@/lib/api";
import { getVideoPoster } from "@/lib/catalogDetails";

export default function CatalogVideo({ src, name, className }: { src: string; name: string; className: string }) {
  const [failed, setFailed] = useState(false);
  const poster = getVideoPoster(src);

  return failed ? (
    <div className={`${className} flex flex-col items-center justify-center gap-3 bg-neutral-100 p-4 text-sm`}>
      <span>Video playback unavailable.</span>
      <a href={resolveProductImage(src)} target="_blank" rel="noopener noreferrer" className="underline">Download video</a>
    </div>
  ) : (
    <video controls playsInline preload="metadata" aria-label={`${name} video`} poster={poster ? resolveProductImage(poster) : undefined} className={className} onError={() => setFailed(true)}>
      <source src={resolveProductImage(src)} />
      <a href={resolveProductImage(src)}>Download video</a>
    </video>
  );
}