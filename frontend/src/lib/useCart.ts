"use client";

import { useEffect, useState } from "react";
import { addProductToCart, clearCart, readCart, reconcileCart, removeProductFromCart, updateCartQuantity, writeCart, type CartItem, type CatalogSelection } from "./cart";
import { fetchCatalogSelection } from "./catalogSelection";
import { analyticsItem, trackAnalytics } from "./analytics";
import type { AnalyticsEventName } from "./analyticsTypes";

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
      } catch (error) { trackAnalytics("site_error", { errorCode: "storage" }); setError(error instanceof Error ? error.message : "Unable to load cart."); }
    };
    fetchCatalogSelection(controller.signal).then(({ items }) => {
      if (!active) return;
      currentCatalog = items;
      setCatalog(items);
      refresh();
    }).catch((error) => {
      if (active) {
        trackAnalytics("site_error", { errorCode: "catalog" });
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
  const run = (action: () => CartItem[], message: string, event: AnalyticsEventName, id?: number) => {
    try {
      const previous = readCart();
      const next = action();
      const before = previous.find((item) => item.id === id);
      const after = next.find((item) => item.id === id);
      setCart(next); setError(null);
      if (event === "cart_add" && (after?.quantity ?? 0) <= (before?.quantity ?? 0)) {
        setNotice("Maximum 10 sale units of this item are already in your cart. No additional quantity was added.");
        return false;
      }
      setNotice(event === "cart_add" ? `${message} Your cart now has ${next.reduce((sum, item) => sum + item.quantity, 0)} sale units.` : message);
      if (JSON.stringify(previous) !== JSON.stringify(next)) {
        const item = after ?? before;
        trackAnalytics(event, {
          ...(item ? analyticsItem(item) : {}),
          ...(item ? { quantity: event === "cart_add" ? (after?.quantity ?? 0) - (before?.quantity ?? 0) : event === "cart_remove" ? before?.quantity ?? 0 : after?.quantity ?? 0 } : {}),
          lineCount: next.length, saleUnits: next.reduce((sum, item) => sum + item.quantity, 0),
        });
      }
      return true;
    }
    catch (error) {
      trackAnalytics("site_error", { errorCode: "storage" });
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
        trackAnalytics("item_unavailable", analyticsItem(product));
        setError("This item is not currently available for your location. Refresh the catalog and try again.");
        return false;
      }
      return run(() => addProductToCart(current, quantity), `${current.name} added to your cart.`, "cart_add", current.id);
    },
    update: (id: number, delta: number) => !loading && !error && run(() => updateCartQuantity(id, delta), "Quantity updated.", "cart_quantity_change", id),
    remove: (id: number) => run(() => removeProductFromCart(id), "Item removed.", "cart_remove", id),
    clear: () => run(clearCart, "Cart cleared.", "cart_clear"),
  };
}
