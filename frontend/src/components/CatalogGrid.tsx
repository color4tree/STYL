"use client";

import Link from "next/link";
import { useState } from "react";
import { MAX_ITEM_QUANTITY, type CartItem, type CatalogSelection } from "@/lib/cart";
import { quantityLabel } from "@/lib/catalogDetails";
import { catalogItemHref, catalogSpecifications, type CatalogEntry } from "@/lib/publicCatalog";
import AddToCartButton from "./AddToCartButton";
import CatalogCard from "./CatalogCard";

export default function CatalogGrid({ entries, cart, add, disabled, headingLevel = 3 }: {
  entries: CatalogEntry[]; cart: CartItem[]; add: (item: CatalogSelection, quantity?: number) => boolean;
  disabled: boolean; headingLevel?: 2 | 3;
}) {
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  return <div className="grid gap-x-6 gap-y-6 md:grid-cols-2 xl:grid-cols-3">
    {entries.map(({ item, itemType }) => {
      const key = `${itemType}-${item.id}`;
      const remaining = MAX_ITEM_QUANTITY - (cart.find(entry => entry.id === item.id)?.quantity ?? 0);
      const quantity = Math.min(quantities[key] ?? 1, Math.max(1, remaining));
      const href = catalogItemHref(item, itemType);
      return <CatalogCard key={key} id={key} item={item} itemType={itemType} headingLevel={headingLevel} href={href}
        specifications={catalogSpecifications(item, itemType)}
        detailsFooter={<div className="mt-4">
          <p className="mb-2 text-sm" aria-live="polite">Quantity: {quantityLabel(quantity, item.sellingUnit)}</p>
          <div className="inline-flex items-center rounded-full border border-[var(--line)] bg-white">
            <button type="button" aria-label={`Decrease quantity for ${item.name}`} disabled={quantity <= 1 || remaining <= 0} onClick={() => setQuantities(current => ({ ...current, [key]: quantity - 1 }))} className="h-12 w-12 rounded-full disabled:opacity-40">−</button>
            <span className="min-w-6 text-center">{quantity}</span>
            <button type="button" aria-label={`Increase quantity for ${item.name}`} disabled={quantity >= remaining} onClick={() => setQuantities(current => ({ ...current, [key]: quantity + 1 }))} className="h-12 w-12 rounded-full disabled:opacity-40">+</button>
          </div>
        </div>}>
        <div className="flex flex-wrap gap-3">
          <AddToCartButton disabled={disabled} atLimit={remaining <= 0} onAdd={() => {
            const saved = add(item, quantity);
            if (saved) setQuantities(current => ({ ...current, [key]: 1 }));
            return saved;
          }} className="min-h-12 flex-1 rounded-full bg-[var(--ink)] px-4 py-3 text-sm font-medium text-white disabled:opacity-50" />
          <Link href={href} data-analytics-action="details" className="hidden min-h-12 items-center rounded-full border border-[var(--line)] px-5 py-3 text-sm font-medium lg:inline-flex">Details</Link>
        </div>
      </CatalogCard>;
    })}
  </div>;
}
