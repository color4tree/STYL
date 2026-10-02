"use client";

import { useEffect } from "react";
import StoreHeader from "@/components/StoreHeader";
import { SupportLink, useSupportWidget } from "@/components/SupportWidget";
import { useCart } from "@/lib/useCart";
import { getCartCount } from "@/lib/cart";

export default function SupportPage() {
  const { cart } = useCart();
  const { openChat } = useSupportWidget();
  // A direct /support visit is an explicit request for chat, not a storefront popup.
  useEffect(() => { openChat(); }, [openChat]);
  return <>
    <StoreHeader cartCount={getCartCount(cart)} />
    <main className="container py-12">
      <h1 className="text-3xl font-semibold">Ask STYL</h1>
      <p className="mt-4">Use the chat in the lower-right corner while you browse. No account required.</p>
      <SupportLink className="mt-4 inline-flex min-h-12 items-center underline">Open Ask STYL</SupportLink>
    </main>
  </>;
}
