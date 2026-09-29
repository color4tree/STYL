import { API_BASE } from "./api";
import { productSpecificationFields, type CatalogDetails, type ProductSpecifications, type SellingUnit } from "./catalogDetails";
import type { AnalyticsItemType } from "./analyticsTypes";

export type CatalogView = "all" | "equipment" | "accessories";
export type PublicCatalogItem = CatalogDetails & ProductSpecifications & {
  id: number; slug?: string; name: string; category: string; price: number; currency: string;
  shortDescription?: string; description?: string; features?: string[]; notes?: string;
  sellingUnit?: SellingUnit; packageQuantity?: number | null;
};
export type CatalogEntry = { item: PublicCatalogItem; itemType: AnalyticsItemType };

export const catalogViews = [
  { view: "all", label: "All products", href: "/#products" },
  { view: "equipment", label: "Equipment", href: "/?catalog=equipment#products" },
  { view: "accessories", label: "Accessories", href: "/?catalog=accessories#products" },
] as const;

export function catalogView(value: string | null): CatalogView {
  return value === "equipment" || value === "accessories" ? value : "all";
}

export function catalogItemHref(item: PublicCatalogItem, itemType: AnalyticsItemType) {
  return itemType === "product" ? `/products/${encodeURIComponent(item.slug ?? "")}` : `/accessories/${item.id}`;
}

export function isPublicCatalogItem(value: unknown): value is PublicCatalogItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return Number.isSafeInteger(item.id) && Number(item.id) > 0
    && typeof item.name === "string" && typeof item.category === "string"
    && typeof item.price === "number" && Number.isFinite(item.price) && item.price >= 0
    && (item.msrp === undefined || item.msrp === null || (typeof item.msrp === "number" && Number.isFinite(item.msrp) && item.msrp >= 0))
    && (item.currency === "CAD" || item.currency === "USD")
    && (item.slug === undefined || typeof item.slug === "string")
    && (item.photos === undefined || (Array.isArray(item.photos) && item.photos.every(photo => typeof photo === "string")));
}

export async function fetchPublicCatalog(kind: "products" | "accessories", signal: AbortSignal): Promise<PublicCatalogItem[]> {
  const response = await fetch(`${API_BASE}/api/${kind}`, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`Unable to load ${kind === "products" ? "equipment" : "accessories"}.`);
  const data: unknown = await response.json();
  if (!data || typeof data !== "object" || !("items" in data) || !Array.isArray(data.items)
    || !data.items.every(isPublicCatalogItem)
    || (kind === "products" && !data.items.every(item => Boolean(item.slug)))) {
    throw new Error("The catalog response is invalid. Please retry.");
  }
  return data.items;
}

export function catalogSpecifications(item: PublicCatalogItem, itemType: AnalyticsItemType): readonly (readonly [string, string | undefined])[] {
  return itemType === "product"
    ? [...productSpecificationFields.map(field => [field.label, item[field.key]] as const), ["Availability", item.stockStatus]]
    : [["Dimensions", item.dimensions], ["Material", item.material], ["Weight", item.weight], ["Finish / colour", item.colourOptions], ["What's included", item.included]];
}
