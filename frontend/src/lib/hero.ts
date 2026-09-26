import { API_BASE } from "@/lib/api";

export type Hero = {
  tag: string;
  number: string;
  eyebrow: string;
  title: string;
  image: string;
};

export const defaultHero: Hero = {
  tag: "Signature", number: "01", eyebrow: "Pro Elite", title: "Series X",
  image: "/images/brand/frame-badge.jpg",
};

export async function fetchHero(): Promise<Hero> {
  const res = await fetch(`${API_BASE}/api/hero`, { cache: "no-store" });
  if (!res.ok) throw new Error("Unable to fetch home banner.");
  const data = await res.json();
  const item = data.item;
  if (!item || !["tag", "number", "eyebrow", "title", "image"].every((key) => typeof item[key] === "string")) {
    throw new Error("Invalid home banner response.");
  }
  return { tag: item.tag, number: item.number, eyebrow: item.eyebrow, title: item.title, image: item.image };
}
