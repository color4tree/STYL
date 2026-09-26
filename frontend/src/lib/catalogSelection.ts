import { API_BASE } from "./api";
import type { CatalogSelection } from "./cart";
import type { Market } from "./pricing";

export async function fetchCatalogSelection(signal?: AbortSignal): Promise<{ items: CatalogSelection[]; market: Market }> {
  const response = await fetch(`${API_BASE}/api/catalog/selection`, { cache: "no-store", signal });
  if (!response.ok) throw new Error("Unable to check current prices for your location. Please retry.");
  const data = await response.json();
  if (!Array.isArray(data.items) || !["CAD", "USD"].includes(data.market?.currency)) throw new Error("Invalid regional catalog response.");
  return data;
}
