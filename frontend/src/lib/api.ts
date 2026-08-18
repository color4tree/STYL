export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function resolveProductImage(image?: string): string {
  if (!image) {
    return "/images/pro-elite.svg";
  }

  if (image.startsWith("/api/uploads/")) {
    return `${API_BASE}${image}`;
  }

  return image;
}