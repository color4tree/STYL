import { API_BASE } from "@/lib/api";
import { formatPrice } from "@/lib/cart";

export type Hero = {
  tag: string;
  number: string;
  eyebrow: string;
  title: string;
  priceLabel: string;
  image: string;
};

export const defaultHero: Hero = {
  tag: "Signature",
  number: "01",
  eyebrow: "Pro Elite",
  title: "Series X",
  priceLabel: "$2,499.00",
  image: "/images/brand/frame-badge.jpg",
};

export function formatHeroPriceLabel(label: string): string {
  if (!/^\$\s*(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(label.trim())) return label;
  return formatPrice(Number(label.replace(/[$,\s]/g, "")));
}

export async function fetchHero(): Promise<Hero> {
  const res = await fetch(`${API_BASE}/api/hero`);
  if (!res.ok) {
    throw new Error("Unable to fetch home banner");
  }

  const data = await res.json();
  return { ...defaultHero, ...(data.item as Partial<Hero>) };
}
