import { API_BASE } from "@/lib/api";

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
  priceLabel: "$2,499",
  image: "/images/brand/frame-badge.jpg",
};

export async function fetchHero(): Promise<Hero> {
  const res = await fetch(`${API_BASE}/api/hero`);
  if (!res.ok) {
    throw new Error("Unable to fetch home banner");
  }

  const data = await res.json();
  return { ...defaultHero, ...(data.item as Partial<Hero>) };
}
