import { catalogFactsPatch, parseCatalogFacts, type CatalogFacts } from "./catalogFacts";

export type AdminCatalogMetadata = {
  schemaVersion?: 1 | 2;
  revision?: string;
  catalogFacts?: CatalogFacts | null;
  catalogFactsReviewedAt?: string | null;
};

export function isCatalogRevision(value: unknown): value is string {
  return typeof value === "string" && value.length === 64 && /^[a-f0-9]{64}$/.test(value);
}

export function catalogAdminMetadata(value: unknown): AdminCatalogMetadata {
  if (!value || typeof value !== "object") throw new Error("Invalid catalog response.");
  const item = value as Record<string, unknown>;
  if (item.schemaVersion !== undefined && item.schemaVersion !== 1 && item.schemaVersion !== 2) throw new Error("Unsupported catalog version.");
  if (item.revision !== undefined && !isCatalogRevision(item.revision)) throw new Error("Invalid catalog revision. Reload the item.");
  if (item.catalogFactsReviewedAt != null && typeof item.catalogFactsReviewedAt !== "string") throw new Error("Invalid facts review date.");
  const facts = parseCatalogFacts(item.catalogFacts);
  return {
    schemaVersion: item.schemaVersion === 2 ? 2 : 1,
    revision: isCatalogRevision(item.revision) ? item.revision : undefined,
    ...(item.catalogFacts === undefined ? {} : { catalogFacts: facts }),
    ...(typeof item.catalogFactsReviewedAt === "string" ? { catalogFactsReviewedAt: item.catalogFactsReviewedAt } : {}),
  };
}

export const revisionUnavailable = "This item has no usable revision. Reload the saved item before saving or deleting; your draft has been kept.";
export const revisionConflict = "This item changed elsewhere. Your draft has been kept. Reload the saved item to review the latest version before trying again.";

export function catalogMutationPayload<T extends AdminCatalogMetadata>(form: T, existing: boolean, factsTouched: boolean) {
  const { revision, schemaVersion: _schemaVersion, catalogFacts, catalogFactsReviewedAt: _reviewedAt, ...fields } = form;
  void _schemaVersion; void _reviewedAt;
  if (existing && !isCatalogRevision(revision)) throw new Error(revisionUnavailable);
  return { ...fields, schemaVersion: 2 as const, ...(existing ? { expectedRevision: revision } : {}), ...catalogFactsPatch(catalogFacts, factsTouched) };
}

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

export function resolveProductImage(image?: string): string {
  if (!image) {
    return "/images/pro-elite.svg";
  }

  if (image.startsWith("/api/uploads/")) {
    return `${API_BASE}${image}`;
  }

  return image;
}