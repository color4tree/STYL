import { API_BASE } from "./api";
import { productSpecificationFields, type CatalogDetails, type Compatibility, type ProductSpecifications, type SellingUnit } from "./catalogDetails";
import type { AnalyticsItemType } from "./analyticsTypes";
import { isCatalogFacts, reviewedFactRows, type CatalogFacts } from "./catalogFacts";

export type CatalogView = "all" | "equipment" | "accessories";
export type PublicCatalogItem = CatalogDetails & ProductSpecifications & {
  id: number; slug?: string; name: string; category: string; price: number; currency: string;
  shortDescription?: string; description?: string; features?: string[]; notes?: string;
  sellingUnit?: SellingUnit; packageQuantity?: number | null;
  catalogFacts?: CatalogFacts | null;
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
    && (item.catalogFacts === undefined || item.catalogFacts === null || (isCatalogFacts(item.catalogFacts) && item.catalogFacts.reviewed))
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
  const legacy: (readonly [string, string | undefined])[] = itemType === "product"
    ? [...productSpecificationFields.map(field => [field.label, item[field.key]] as const), ["Availability", item.stockStatus]]
    : [["Dimensions", item.dimensions], ["Material", item.material], ["Weight", item.weight], ["Finish / colour", item.colourOptions], ["What's included", item.included]];
  const facts = item.catalogFacts;
  if (!isCatalogFacts(facts) || !facts.reviewed) return legacy;
  const replaced = new Set<string>();
  const overall = facts.measurements.filter(row => row.scope === "overall" || row.scope === "product");
  if (overall.some(row => ["length", "width", "height", "depth", "diameter"].includes(row.kind))) replaced.add("Dimensions");
  if (overall.some(row => row.kind === "weight")) replaced.add("Weight");
  if (facts.materials.some(row => !row.component || /^(overall|product)$/i.test(row.component))) replaced.add("Material");
  if (facts.options.colors.length || facts.options.sizes.length || facts.options.finish) { replaced.add("Colour / options"); replaced.add("Finish / colour"); }
  if (facts.components.length || facts.packageNote) replaced.add("What's included");
  const referenceLabels: Record<string, string> = {
    Dimensions: "Original listing dimensions",
    Material: "Original listing material",
    Weight: "Original listing weight",
    "Colour / options": "Original listing options",
    "Finish / colour": "Original listing options",
    "What's included": "Original listing contents",
  };
  const references = legacy
    .filter(([label, value]) => replaced.has(label) && value?.trim())
    .map(([label, value]) => [referenceLabels[label], value] as const);
  return [
    ...reviewedFactRows(facts),
    ...legacy.filter(([label]) => !replaced.has(label)),
    ...(references.length ? [["Original listing details", "Reviewed values above take precedence."] as const, ...references] : []),
  ];
}

export function catalogCompatibility(item: PublicCatalogItem): Compatibility | undefined {
  if (!item.compatibility) return undefined;
  const facts = item.catalogFacts;
  if (!isCatalogFacts(facts) || !facts.reviewed) return item.compatibility;
  const legacy = { ...item.compatibility };
  for (const int of facts.interfaces) {
    if (int.kind !== "rack_mount" && int.kind !== "shelf_mount") continue;
    for (const constraint of int.constraints) {
      if (constraint.attribute === "uprightSize" || constraint.attribute === "holeDiameter" || constraint.attribute === "holeSpacing") legacy[constraint.attribute] = "";
    }
  }
  return legacy;
}
