export type MarketCurrency = "CAD" | "USD";
export type MarketPrices = Record<MarketCurrency, number | null>;
export type Market = {
  countryCode: string | null;
  currency: MarketCurrency;
  locationStatus: "located" | "unknown";
};

export function getMarketPrices(item: { prices?: MarketPrices; price?: number | null; currency?: string }): MarketPrices {
  if (item.prices) return { CAD: item.prices.CAD ?? null, USD: item.prices.USD ?? null };
  return {
    CAD: item.currency === "CAD" ? item.price ?? null : null,
    USD: (!item.currency || item.currency === "USD") ? item.price ?? null : null,
  };
}

export function getMarketMsrps(item: { msrps?: Partial<MarketPrices> | null }): MarketPrices {
  return { CAD: item.msrps?.CAD ?? null, USD: item.msrps?.USD ?? null };
}

export function priceInputs(prices: MarketPrices): Record<MarketCurrency, string> {
  return { CAD: prices.CAD?.toFixed(2) ?? "", USD: prices.USD?.toFixed(2) ?? "" };
}
