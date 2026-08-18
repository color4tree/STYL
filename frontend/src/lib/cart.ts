export type CartItem = {
  id: number;
  name: string;
  price: number;
  quantity: number;
  slug?: string;
};

export const CART_KEY = "styl-cart";

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

export function addProductToCart(product: { id: number; name: string; price: number; slug?: string }) {
  const existing = readCart();
  const index = existing.findIndex((item) => item.id === product.id);

  const next = index >= 0
    ? existing.map((item) =>
        item.id === product.id ? { ...item, quantity: item.quantity + 1 } : item,
      )
    : [...existing, { ...product, quantity: 1 }];

  writeCart(next);
  return next;
}

export function updateCartQuantity(id: number, delta: number) {
  const existing = readCart();
  const next = existing
    .map((item) =>
      item.id === id ? { ...item, quantity: Math.max(0, item.quantity + delta) } : item,
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
