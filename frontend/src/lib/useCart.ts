"use client";

import { useEffect, useState } from "react";
import { addProductToCart, clearCart, readCart, removeProductFromCart, updateCartQuantity, type CartItem } from "./cart";

export function useCart() {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    const refresh = () => {
      try { setCart(readCart()); setError(null); }
      catch (error) { setError(error instanceof Error ? error.message : "Unable to load cart."); }
    };
    void Promise.resolve().then(refresh);
    window.addEventListener("storage", refresh);
    window.addEventListener("styl-cart-change", refresh);
    return () => {
      window.removeEventListener("storage", refresh);
      window.removeEventListener("styl-cart-change", refresh);
    };
  }, []);
  const run = (action: () => CartItem[], message: string) => {
    try { setCart(action()); setError(null); setNotice(message); return true; }
    catch (error) {
      console.error("Cart update failed", error);
      setError("Your cart was not saved. Please allow browser storage and try again.");
      setNotice(null);
      return false;
    }
  };
  return {
    cart, error, notice,
    add: (product: Parameters<typeof addProductToCart>[0], quantity = 1) =>
      run(() => addProductToCart(product, quantity), `${product.name} added to your cart.`),
    update: (id: number, delta: number) => run(() => updateCartQuantity(id, delta), "Quantity updated."),
    remove: (id: number) => run(() => removeProductFromCart(id), "Item removed."),
    clear: () => run(clearCart, "Cart cleared."),
  };
}
