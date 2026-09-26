"use client";

import Image from "next/image";
import { useState } from "react";
import { resolveProductImage } from "@/lib/api";

export default function CatalogImage({ src, alt, className, thumbnail = false, onOpen }: {
  src: string;
  alt: string;
  className: string;
  thumbnail?: boolean;
  onOpen?: () => void;
}) {
  const [failed, setFailed] = useState(false);
  const image = <Image unoptimized src={resolveProductImage(src)} alt={alt} width={1200} height={900} className={className} onError={() => setFailed(true)} />;
  return failed ? (
    <span className={`${className} flex flex-col items-center justify-center gap-2 bg-neutral-100 p-2 text-center text-xs`}>
      <span role={thumbnail ? undefined : "status"}>{thumbnail ? "Unavailable" : `${alt}: image unavailable.`}</span>
      {!thumbnail && <button type="button" onClick={() => setFailed(false)} className="min-h-11 rounded-md border border-[var(--line)] bg-white px-3">Retry image</button>}
    </span>
  ) : (
    onOpen ? <button type="button" onClick={onOpen} aria-label={`Enlarge ${alt}`} className="block h-full w-full">{image}</button> : image
  );
}
