export type Compatibility = {
  uprightSize: string;
  holeDiameter: string;
  holeSpacing: string;
  models: string;
  limitations: string;
};

export type CatalogDetails = {
  image?: string;
  photos?: string[];
  compatibility?: Compatibility;
};

export const MAX_PHOTOS = 12;

export const productSpecificationFields = [
  { key: "modelSku", label: "Model / SKU", limit: 200, rows: 1 },
  { key: "dimensions", label: "Dimensions", limit: 500, rows: 2 },
  { key: "material", label: "Material", limit: 500, rows: 2 },
  { key: "colourOptions", label: "Colour / options", limit: 1000, rows: 2 },
  { key: "included", label: "What's included", limit: 4000, rows: 3 },
  { key: "warranty", label: "Warranty", limit: 4000, rows: 3 },
] as const;

export const stockStatuses = ["In stock", "Out of stock", "Preorder", "Made to order"] as const;

export type ProductSpecifications = Partial<Record<(typeof productSpecificationFields)[number]["key"], string>> & {
  stockStatus?: "" | (typeof stockStatuses)[number];
  publicationStatus?: "" | "draft" | "published";
};

export function getProductSpecifications(product: ProductSpecifications): ProductSpecifications {
  return {
    ...Object.fromEntries(productSpecificationFields.map(({ key }) => [key, product[key] ?? ""])),
    stockStatus: product.stockStatus ?? "",
    publicationStatus: product.publicationStatus || "published",
  };
}

export const emptyCompatibility: Compatibility = {
  uprightSize: "",
  holeDiameter: "",
  holeSpacing: "",
  models: "",
  limitations: "",
};

export const compatibilityFields: { key: keyof Compatibility; label: string; limit: number; placeholder: string }[] = [
  { key: "uprightSize", label: "Upright size", limit: 300, placeholder: "75 x 75 mm; 3 x 3 inch only if separately confirmed" },
  { key: "holeDiameter", label: "Hole diameter", limit: 300, placeholder: "1 inch (25.4 mm)" },
  { key: "holeSpacing", label: "Hole spacing", limit: 300, placeholder: "50 mm center-to-center" },
  { key: "models", label: "Confirmed compatible models", limit: 1000, placeholder: "Manufacturer and model" },
  { key: "limitations", label: "Compatibility limitations", limit: 2000, placeholder: "Exclusions, clearances, or unverified combinations" },
];

export function getCatalogPhotos(item: CatalogDetails): string[] {
  return [...new Set((item.photos ?? (item.image ? [item.image] : [])).filter(Boolean))];
}