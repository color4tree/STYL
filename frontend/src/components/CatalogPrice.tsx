import { formatPrice } from "@/lib/cart";
import type { SellingUnit } from "@/lib/catalogDetails";

export default function CatalogPrice({ price, currency, msrp, sellingUnit, className = "" }: {
  price: number; currency: string; msrp?: number | null; sellingUnit?: SellingUnit; className?: string;
}) {
  const showMsrp = typeof msrp === "number" && Number.isFinite(msrp) && msrp > price;
  return <div className={`min-w-0 break-words ${className}`}>
    {showMsrp ? <p className="text-sm font-normal text-[var(--muted)]" data-testid="catalog-msrp">MSRP <s>{formatPrice(msrp, currency)}</s></p> : null}
    <p data-analytics-price className="font-semibold" data-testid="catalog-price">{formatPrice(price, currency)}{sellingUnit ? <span className="text-sm font-normal"> / {sellingUnit.toLowerCase()}</span> : null}</p>
  </div>;
}
