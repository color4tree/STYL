"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import PhotoGallery from "@/components/PhotoGallery";
import { CompatibilityDetails } from "@/components/Compatibility";
import { compatibilityFields, getCatalogPhotos, saleUnitLabel, type CatalogDetails, type SellingUnit } from "@/lib/catalogDetails";
import { formatPrice } from "@/lib/cart";

type CardItem = CatalogDetails & {
  name: string;
  category: string;
  price: number;
  currency: string;
  shortDescription?: string;
  description?: string;
  features?: string[];
  notes?: string;
  sellingUnit?: SellingUnit;
  packageQuantity?: number | null;
};

export default function CatalogCard({ item, specifications, headingLevel, href, id, children }: {
  item: CardItem;
  specifications: readonly (readonly [string, string | undefined])[];
  headingLevel: 2 | 3;
  href?: string;
  id?: string;
  children: ReactNode;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const DetailHeading = headingLevel === 2 ? "h3" : "h4";
  const specs = specifications.filter(([, value]) => value?.trim());
  const features = item.features?.filter((feature) => feature.trim()) ?? [];
  const hasCompatibility = compatibilityFields.some((field) => item.compatibility?.[field.key]?.trim());
  const hasDetails = Boolean(specs.length || features.length || hasCompatibility || item.shortDescription?.trim() || item.description?.trim() || item.notes?.trim());
  const detailsId = useId();
  const preview = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);

  useEffect(() => {
    if (expanded || !preview.current || !content.current) return;
    const viewport = preview.current;
    const observer = new ResizeObserver(() => {
      setOverflowing(viewport.scrollHeight > viewport.clientHeight + 1);
    });
    observer.observe(viewport);
    observer.observe(content.current);
    return () => observer.disconnect();
  }, [expanded, hasDetails]);

  return (
    <article id={id} className="catalog-card soft-panel min-w-0 scroll-mt-32 rounded-3xl p-4 lg:scroll-mt-24 lg:p-5">
      <PhotoGallery photos={getCatalogPhotos(item)} name={item.name} compact />
      <p className="mt-4 min-w-0 break-words text-sm text-[var(--muted)]">{item.category}</p>
      <Heading className="mt-2 min-w-0 break-words text-2xl font-semibold">
        {href ? <Link href={href} className="hover:underline">{item.name}</Link> : item.name}
      </Heading>
      <p className="mt-2 min-w-0 break-words text-lg font-semibold">{formatPrice(item.price, item.currency)}{item.sellingUnit ? <span className="text-sm font-normal"> / {item.sellingUnit.toLowerCase()}</span> : null}</p>
      <div>
        {item.packageQuantity ? <p className="mt-2 text-sm">{item.packageQuantity} {item.packageQuantity === 1 ? "piece" : "pieces"} per {saleUnitLabel(item.sellingUnit) || "sale unit"}.</p> : null}
      </div>
      <div className="min-w-0">
        {hasDetails ? <section className="catalog-details mt-3 min-w-0" aria-label={`Details for ${item.name}`}>
          <div ref={preview} id={detailsId} className="catalog-details-preview" data-expanded={expanded} data-clipped={overflowing && !expanded}>
            <div ref={content} className="flow-root">
              {item.shortDescription?.trim() ? <p className="whitespace-pre-line break-words leading-7 text-[var(--muted)]">{item.shortDescription}</p> : null}
              {item.description?.trim() ? <p className="mt-3 whitespace-pre-line break-words leading-7">{item.description}</p> : null}
              {features.length ? <div className="mt-4"><DetailHeading className="font-semibold">Features</DetailHeading><ul className="mt-2 list-inside list-disc space-y-2 break-words">{features.map((feature, index) => <li key={index}>{feature}</li>)}</ul></div> : null}
              {item.notes?.trim() ? <div className="mt-4"><DetailHeading className="font-semibold">Use</DetailHeading><p className="mt-2 whitespace-pre-line break-words leading-7">{item.notes}</p></div> : null}
              <CompatibilityDetails value={item.compatibility} headingLevel={headingLevel === 2 ? 3 : 4} />
              {specs.length ? <dl className="my-4 space-y-3">{specs.map(([label, value]) => <div key={label}><dt className="text-sm text-[var(--muted)]">{label}</dt><dd className="mt-1 whitespace-pre-line break-words">{value}</dd></div>)}</dl> : null}
            </div>
          </div>
          {hasCompatibility ? <p className="mt-2 text-xs text-[var(--muted)]">Includes compatibility - check fit</p> : null}
          {overflowing || expanded ? <button type="button" aria-expanded={expanded} aria-controls={detailsId} onClick={() => setExpanded(!expanded)} className="mt-3 hidden min-h-12 w-full items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-black/[0.02] px-4 py-3 text-left text-[var(--muted)] hover:bg-black/[0.04] lg:flex">
            <span className="flex items-center gap-2">
              {!expanded ? <span aria-hidden="true" className="text-lg font-normal tracking-widest">...</span> : null}
              <span className="text-base font-normal italic underline underline-offset-4">{expanded ? "Show less" : "Show more"}</span>
            </span>
            <ChevronDown aria-hidden="true" size={20} className={`shrink-0 transition-transform ${expanded ? "rotate-180" : ""}`} />
          </button> : null}
        </section> : null}
      </div>
      <div className="mt-4 self-end">{children}</div>
    </article>
  );
}
