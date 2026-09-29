"use client";

import Link from "next/link";
import { useId, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import PhotoGallery from "@/components/PhotoGallery";
import { CompatibilityDetails } from "@/components/Compatibility";
import { compatibilityFields, getCatalogPhotos, saleUnitLabel, type CatalogDetails, type SellingUnit } from "@/lib/catalogDetails";
import CatalogPrice from "./CatalogPrice";
import { trackAnalytics } from "@/lib/analytics";
import type { AnalyticsItemType } from "@/lib/analyticsTypes";

type CardItem = CatalogDetails & {
  id: number;
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

export default function CatalogCard({ item, itemType, specifications, headingLevel, href, id, children, detailsFooter }: {
  item: CardItem;
  itemType: AnalyticsItemType;
  specifications: readonly (readonly [string, string | undefined])[];
  headingLevel: 2 | 3;
  href?: string;
  id?: string;
  children: ReactNode;
  detailsFooter?: ReactNode;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const DetailHeading = headingLevel === 2 ? "h3" : "h4";
  const specs = specifications.filter(([, value]) => value?.trim());
  const features = item.features?.filter((feature) => feature.trim()) ?? [];
  const hasCompatibility = compatibilityFields.some((field) => item.compatibility?.[field.key]?.trim());
  const hasDetails = Boolean(specs.length || features.length || hasCompatibility || item.shortDescription?.trim() || item.description?.trim() || item.notes?.trim() || item.packageQuantity || detailsFooter);
  const detailsId = useId();
  const [expanded, setExpanded] = useState(false);

  return (
    <article id={id} data-analytics-item-id={item.id} data-analytics-item-type={itemType} className="catalog-card soft-panel min-w-0 scroll-mt-32 rounded-3xl p-4 lg:scroll-mt-24 lg:p-5">
      <PhotoGallery photos={getCatalogPhotos(item)} name={item.name} item={{ itemType, itemId: item.id }} compact />
      <p className="mt-4 min-w-0 break-words text-sm text-[var(--muted)]">{item.category}</p>
      <Heading data-analytics-identity className="mt-2 min-w-0 break-words text-2xl font-semibold">
        {href ? <Link href={href} data-analytics-action="catalog" className="hover:underline">{item.name}</Link> : item.name}
      </Heading>
      <CatalogPrice price={item.price} currency={item.currency} msrp={item.msrp} sellingUnit={item.sellingUnit} className="mt-2 text-lg" />
      <div className="min-w-0">
        {hasDetails ? <section className="catalog-details mt-3 min-w-0" aria-label={`Details for ${item.name}`}>
          <button type="button" aria-expanded={expanded} aria-controls={detailsId} onClick={() => { if (!expanded) trackAnalytics("item_details_expand", { itemType, itemId: item.id }); setExpanded(!expanded); }} className="flex min-h-12 w-full items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-black/[0.02] px-4 py-3 text-left text-[var(--muted)] hover:bg-black/[0.04]">
            <span className="flex items-center gap-2">
              {!expanded ? <span aria-hidden="true" className="text-lg font-normal tracking-widest">...</span> : null}
              <span className="text-base font-normal italic underline underline-offset-4">{expanded ? "Show less" : "Show more"}</span>
            </span>
            <ChevronDown aria-hidden="true" size={20} className={`shrink-0 transition-transform ${expanded ? "rotate-180" : ""}`} />
          </button>
          <div id={detailsId} hidden={!expanded} className="catalog-details-preview" data-expanded={expanded}>
            <div className="flow-root pt-3">
              {item.packageQuantity ? <p className="mb-3 text-sm">{item.packageQuantity} {item.packageQuantity === 1 ? "piece" : "pieces"} per {saleUnitLabel(item.sellingUnit) || "sale unit"}.</p> : null}
              {item.shortDescription?.trim() ? <p className="whitespace-pre-line break-words leading-7 text-[var(--muted)]">{item.shortDescription}</p> : null}
              {item.description?.trim() ? <p className="mt-3 whitespace-pre-line break-words leading-7">{item.description}</p> : null}
              {features.length ? <div className="mt-4"><DetailHeading className="font-semibold">Features</DetailHeading><ul className="mt-2 list-inside list-disc space-y-2 break-words">{features.map((feature, index) => <li key={index}>{feature}</li>)}</ul></div> : null}
              {item.notes?.trim() ? <div className="mt-4"><DetailHeading className="font-semibold">Use</DetailHeading><p className="mt-2 whitespace-pre-line break-words leading-7">{item.notes}</p></div> : null}
              <CompatibilityDetails value={item.compatibility} headingLevel={headingLevel === 2 ? 3 : 4} />
              {specs.length ? <dl className="my-4 space-y-3">{specs.map(([label, value]) => <div key={label}><dt className="text-sm text-[var(--muted)]">{label}</dt><dd className="mt-1 whitespace-pre-line break-words">{value}</dd></div>)}</dl> : null}
              {detailsFooter}
            </div>
          </div>
        </section> : null}
      </div>
      <div className="mt-4 self-end">{children}</div>
    </article>
  );
}
