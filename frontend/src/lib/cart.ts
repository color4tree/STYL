export type CartItem = {
  id: number;
  name: string;
  price: number;
  currency?: string;
  quantity: number;
  slug?: string;
};

export const CART_KEY = "styl-cart";
export const MAX_ITEM_QUANTITY = 10;

function currencyCode(currency?: string) {
  return currency && /^[a-z]{3}$/i.test(currency) ? currency.toUpperCase() : "USD";
}

export function formatPrice(price: number, currency?: string) {
  return new Intl.NumberFormat("en-CA", { style: "currency", currency: currencyCode(currency), currencyDisplay: "code" }).format(price);
}

export function getCartTotals(items: CartItem[]): [string, number][] {
  const totals = new Map<string, number>();
  for (const item of items) {
    const currency = currencyCode(item.currency);
    totals.set(currency, (totals.get(currency) ?? 0) + item.price * item.quantity);
  }
  return [...totals];
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
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error("Unable to read cart", error);
    return [];
  }
}

export function writeCart(items: CartItem[]) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(CART_KEY, JSON.stringify(items));
}

export function getCartCount(items: CartItem[] = readCart()) {
  return items.reduce((sum, item) => sum + item.quantity, 0);
}

export function addProductToCart(
  product: { id: number; name: string; price: number; slug?: string; currency?: string },
  quantity = 1,
) {
  const existing = readCart();
  const index = existing.findIndex((item) => item.id === product.id);

  const next = index >= 0
    ? existing.map((item) =>
        item.id === product.id
          ? { ...item, ...product, quantity: Math.min(MAX_ITEM_QUANTITY, item.quantity + quantity) }
          : item,
      )
    : [...existing, { ...product, quantity: Math.min(MAX_ITEM_QUANTITY, quantity) }];

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

  const summary = items.map((item) => `${item.name} x${item.quantity}`).join(", ");
  return `Interested in: ${summary}.`;
}
