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