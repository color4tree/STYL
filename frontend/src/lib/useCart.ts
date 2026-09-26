"use client";

import { useEffect, useState } from "react";
import { addProductToCart, clearCart, readCart, reconcileCart, removeProductFromCart, updateCartQuantity, writeCart, type CartItem, type CatalogSelection } from "./cart";
import { fetchCatalogSelection } from "./catalogSelection";

export function useCart() {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalog, setCatalog] = useState<CatalogSelection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let currentCatalog: CatalogSelection[] | null = null;
    const refresh = () => {
      if (!currentCatalog) return;
      try {
        const previous = readCart();
        const next = reconcileCart(previous, currentCatalog);
        if (JSON.stringify(previous) !== JSON.stringify(next)) {
          writeCart(next);
          setNotice(next.length < previous.length
            ? "Some saved items are unavailable for your location and were removed from the cart."
            : "Your cart prices have been updated for your location.");
        }
        setCart(next);
        setError(null);
      } catch (error) { setError(error instanceof Error ? error.message : "Unable to load cart."); }
    };
    fetchCatalogSelection(controller.signal).then(({ items }) => {
      if (!active) return;
      currentCatalog = items;
      setCatalog(items);
      refresh();
    }).catch((error) => {
      if (active) {
        console.error("Regional cart check failed", error);
        setCart([]);
        setError(error instanceof Error ? error.message : "Unable to load current prices.");
      }
    }).finally(() => { if (active) setLoading(false); });
    window.addEventListener("storage", refresh);
    window.addEventListener("styl-cart-change", refresh);
    const refreshRegion = () => { setLoading(true); setRetry((value) => value + 1); };
    window.addEventListener("focus", refreshRegion);
    return () => {
      active = false;
      controller.abort();
      window.removeEventListener("storage", refresh);
      window.removeEventListener("styl-cart-change", refresh);
      window.removeEventListener("focus", refreshRegion);
    };
  }, [retry]);
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
    cart, loading, error, notice,
    retry: () => { setLoading(true); setRetry((value) => value + 1); },
    add: (product: CatalogSelection, quantity = 1) => {
      const current = catalog.find((item) => item.id === product.id);
      if (loading || error || !current) {
        setError("This item is not currently available for your location. Refresh the catalog and try again.");
        return false;
      }
      return run(() => addProductToCart(current, quantity), `${current.name} added to your cart.`);
    },
    update: (id: number, delta: number) => !loading && !error && run(() => updateCartQuantity(id, delta), "Quantity updated."),
    remove: (id: number) => run(() => removeProductFromCart(id), "Item removed."),
    clear: () => run(clearCart, "Cart cleared."),
  };
}
