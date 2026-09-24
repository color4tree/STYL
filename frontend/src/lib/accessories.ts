import { API_BASE } from "@/lib/api";

export type Accessory = {
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
};

export async function fetchAccessories(): Promise<Accessory[]> {
  const res = await fetch(`${API_BASE}/api/accessories`);
  if (!res.ok) {
    throw new Error("Unable to fetch accessories");
  }

  const data = await res.json();
  return Array.isArray(data.items) ? (data.items as Accessory[]) : [];
}
