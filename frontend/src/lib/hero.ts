import { API_BASE } from "@/lib/api";

export type Hero = {
  tag: string;
  number: string;
  eyebrow: string;
  title: string;
  image: string;
  engineering: EngineeringDetails;
};

export type EngineeringCard = { title: string; description: string; image: string };
export type EngineeringDetails = { heading: string; intro: string; items: EngineeringCard[] };

export const defaultEngineering: EngineeringDetails = {
  heading: "Explore our engineering details",
  intro: "Our mark, engineered into every piece.",
  items: [
    { title: "Signature shield", description: "Laser-etched into brushed stainless steel on every frame upright.", image: "/images/brand/logo-plate.jpg" },
    { title: "J-hook", description: "Rubber-lined steel hooks that protect the bar and carry the wordmark.", image: "/images/brand/j-hook.jpg" },
    { title: "Cable swivel plate", description: "Machined plate and 360° swivel for smooth, tangle-free cable work.", image: "/images/brand/cable-swivel.jpg" },
    { title: "Frame badge", description: "Brushed steel badge finishing the top crossmember of the multi trainer.", image: "/images/brand/frame-badge.jpg" },
  ],
};

export const defaultHero: Hero = {
  tag: "Signature", number: "01", eyebrow: "Pro Elite", title: "Series X",
  image: "/images/brand/frame-badge.jpg",
  engineering: defaultEngineering,
};

const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown, limit: number, required = false): value is string => typeof value === "string" && Array.from(value).length <= limit && (!required || !!value.trim());

export function isEngineeringImage(value: string): boolean {
  const source = value.trim();
  if (!source || /[\u0000-\u001f\u007f\\]/.test(source)) return false;
  try {
    if (source.startsWith("/") && !source.startsWith("//")) {
      const pathname = decodeURIComponent(source.split(/[?#]/, 1)[0]);
      if (/[\u0000-\u001f\u007f\\]/.test(pathname) || pathname.slice(1).split("/").some(part => !part || part === "." || part === "..")) return false;
      return /\.(svg|jpg|jpeg|png|gif|webp)$/i.test(pathname)
        && (pathname.startsWith("/images/") || (pathname.startsWith("/api/uploads/") && !pathname.slice("/api/uploads/".length).includes("/")));
    }
    const url = new URL(source);
    return ["http:", "https:"].includes(url.protocol) && !!url.hostname && !url.username && !url.password
      && !/\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(decodeURIComponent(url.pathname));
  } catch { return false; }
}

export function parseHero(value: unknown): Hero {
  if (!record(value) || !text(value.tag, 40) || !text(value.number, 10)
    || !text(value.eyebrow, 60) || !text(value.title, 80) || !text(value.image, 500)) {
    throw new Error("Invalid home banner response.");
  }
  const section = value.engineering === undefined ? defaultEngineering : value.engineering;
  if (!record(section) || !text(section.heading, 120, true) || !text(section.intro, 1000)
    || !Array.isArray(section.items) || section.items.length !== 4) {
    throw new Error("Invalid engineering details response.");
  }
  const items = section.items.map((item: unknown): EngineeringCard => {
    if (!record(item) || !text(item.title, 120, true) || !text(item.description, 2000) || !text(item.image, 500, true) || !isEngineeringImage(item.image)) {
      throw new Error("Invalid engineering card response.");
    }
    return { title: item.title, description: item.description, image: item.image };
  });
  return {
    tag: value.tag, number: value.number, eyebrow: value.eyebrow, title: value.title, image: value.image,
    engineering: { heading: section.heading, intro: section.intro, items },
  };
}

export function changedHeroFields(current: Hero, previous: Hero): Partial<Hero> {
  const changes: Partial<Hero> = {};
  for (const key of ["tag", "number", "eyebrow", "title", "image"] as const) {
    if (current[key] !== previous[key]) changes[key] = current[key];
  }
  if (JSON.stringify(current.engineering) !== JSON.stringify(previous.engineering)) changes.engineering = current.engineering;
  return changes;
}

export async function fetchHero(): Promise<Hero> {
  const res = await fetch(`${API_BASE}/api/hero`, { cache: "no-store" });
  if (!res.ok) throw new Error("Unable to fetch home banner.");
  const data: unknown = await res.json();
  if (!record(data)) throw new Error("Invalid home banner response.");
  return parseHero(data.item);
}
