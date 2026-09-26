import { quantityLabel, type SellingUnit } from "./catalogDetails";

export type CartItem = {
  id: number;
  name: string;
  price: number;
  currency?: string;
  quantity: number;
  slug?: string;
  sellingUnit?: SellingUnit;
  packageQuantity?: number | null;
};

export const CART_KEY = "styl-cart";
export const MAX_ITEM_QUANTITY = 10;

function currencyCode(currency?: string) {
  return currency && /^[a-z]{3}$/i.test(currency) ? currency.toUpperCase() : "USD";
}

export function formatPrice(price: number, currency?: string) {
  return new Intl.NumberFormat("en-CA", { style: "currency", currency: currencyCode(currency), currencyDisplay: "narrowSymbol", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(price);
}

export function lineAmount(price: number, quantity: number): number {
  return Math.round(price * 100) * quantity / 100;
}

export function getCartTotals(items: CartItem[]): [string, number][] {
  const totals = new Map<string, number>();
  for (const item of items) {
    const currency = currencyCode(item.currency);
    totals.set(currency, (totals.get(currency) ?? 0) + Math.round(item.price * 100) * item.quantity);
  }
  return [...totals].map(([currency, cents]) => [currency, cents / 100]);
}

export function readCart(): CartItem[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(CART_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw) as CartItem[];
    if (!Array.isArray(parsed) || !parsed.every((item) =>
      item && Number.isInteger(item.id) && typeof item.name === "string" &&
      Number.isFinite(item.price) && item.price >= 0 &&
      Number.isInteger(item.quantity) && item.quantity >= 1 && item.quantity <= MAX_ITEM_QUANTITY
    )) throw new Error("Saved cart is invalid.");
    return parsed;
  } catch (error) {
    console.error("Unable to read cart", error);
    throw new Error("Unable to load your saved cart. Please allow browser storage or clear the cart to start again.");
  }
}

export function writeCart(items: CartItem[]) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(CART_KEY, JSON.stringify(items));
  window.dispatchEvent(new Event("styl-cart-change"));
}

export function getCartCount(items: CartItem[] = readCart()) {
  return items.reduce((sum, item) => sum + item.quantity, 0);
}

export function addProductToCart(
  product: { id: number; name: string; price: number; slug?: string; currency?: string; sellingUnit?: SellingUnit; packageQuantity?: number | null },
  quantity = 1,
) {
  if (!Number.isInteger(quantity) || quantity < 1) throw new Error("Choose a valid quantity.");
  const existing = readCart();
  const selection = {
    id: product.id, name: product.name, price: product.price, slug: product.slug,
    currency: product.currency, sellingUnit: product.sellingUnit, packageQuantity: product.packageQuantity,
  };
  const index = existing.findIndex((item) => item.id === product.id);

  const next = index >= 0
    ? existing.map((item) =>
        item.id === product.id
          ? { ...item, ...selection, quantity: Math.min(MAX_ITEM_QUANTITY, item.quantity + quantity) }
          : item,
      )
    : [...existing, { ...selection, quantity: Math.min(MAX_ITEM_QUANTITY, quantity) }];

  writeCart(next);
  return next;
}

export function updateCartQuantity(id: number, delta: number) {
  const existing = readCart();
  const next = existing
    .map((item) =>
      item.id === id
        ? { ...item, quantity: Math.min(MAX_ITEM_QUANTITY, Math.max(0, item.quantity + delta)) }
        : item,
    )
    .filter((item) => item.quantity > 0);

  writeCart(next);
  return next;
}

export function removeProductFromCart(id: number) {
  const next = readCart().filter((item) => item.id !== id);
  writeCart(next);
  return next;
}

export function clearCart() {
  writeCart([]);
  return [];
}

export function formatCartSummary(items: CartItem[] = readCart()) {
  if (items.length === 0) {
    return "No items selected yet.";
  }

  const summary = items.map((item) => `${item.name} x ${quantityLabel(item.quantity, item.sellingUnit)}${item.packageQuantity ? ` (${item.packageQuantity} pieces per sale unit)` : ""}`).join(", ");
  return `Interested in: ${summary}.`;
}
