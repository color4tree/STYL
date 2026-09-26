import { API_BASE } from "@/lib/api";
import type { CatalogDetails, Provenance, SellingUnit } from "@/lib/catalogDetails";

export type Accessory = CatalogDetails & {
  id: number;
  name: string;
  category: string;
  dimensions: string;
  material: string;
  weight: string;
  price: number;
  currency: string;
  notes: string;
  image: string;
  shortDescription?: string;
  description?: string;
  features?: string[];
  included?: string;
  sellingUnit?: SellingUnit;
  packageQuantity?: number | null;
  colourOptions?: string;
  provenance?: Provenance;
};

export async function fetchAdminAccessories(token: string): Promise<Accessory[]> {
  const res = await fetch(`${API_BASE}/api/admin/accessories`, {
    headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
  });
  if (!res.ok) throw new Error("Unable to load accessories. Check your admin access and retry.");
  const data = await res.json();
  if (!Array.isArray(data.items)) throw new Error("Invalid accessory response.");
  return data.items;
}

export async function fetchCatalogCategories(token: string): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/admin/categories`, {
    headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
  });
  if (!res.ok) throw new Error("Unable to load catalog categories. Please retry.");
  const data = await res.json();
  if (!Array.isArray(data.items) || !data.items.every((item: unknown) => typeof item === "string")) {
    throw new Error("Invalid category response.");
  }
  return data.items;
}

export async function fetchAccessories(): Promise<Accessory[]> {
  const res = await fetch(`${API_BASE}/api/accessories`);
  if (!res.ok) {
    throw new Error("Unable to fetch accessories");
  }

  const data = await res.json();
  if (!Array.isArray(data.items)) throw new Error("Invalid accessory response.");
  return data.items as Accessory[];
}
