"use client";

import { useEffect, useRef, useState } from "react";
import { Check, CircleAlert } from "lucide-react";

export default function AddToCartButton({ onAdd, disabled, atLimit = false, className }: {
  onAdd: () => boolean;
  disabled: boolean;
  atLimit?: boolean;
  className: string;
}) {
  const [feedback, setFeedback] = useState<"added" | "failed" | null>(null);
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current !== null) window.clearTimeout(timer.current); }, []);

  return <button type="button" disabled={disabled || atLimit}
    aria-label={atLimit ? "Maximum 10 in cart" : "Add to cart"}
    data-cart-feedback={feedback ?? "idle"}
    onClick={() => {
      if (timer.current !== null) window.clearTimeout(timer.current);
      const saved = onAdd();
      setFeedback(saved ? "added" : "failed");
      if (saved) timer.current = window.setTimeout(() => setFeedback(null), 2500);
    }}
    className={`${className} inline-flex items-center justify-center gap-2`}>
    {feedback === "added" ? <><Check size={18} aria-hidden="true" /><span>Added</span></>
      : feedback === "failed" ? <><CircleAlert size={18} aria-hidden="true" /><span>Not added</span></>
        : atLimit ? "Maximum 10 in cart" : "Add to cart"}
  </button>;
}
