"use client";

import { useLayoutEffect, useRef } from "react";

export function useQuoteNavigation(layoutReady: boolean) {
  const navigation = useRef({ initialized: false, pending: false, interrupted: false });

  // Stabilize initial layout commits before paint, then stop once ready or interrupted.
  useLayoutEffect(() => {
    const state = navigation.current;
    if (!state.initialized) {
      state.initialized = true;
      state.pending = window.location.hash === "#contact";
    }

    const align = () => {
      if (!state.pending || state.interrupted || window.location.hash !== "#contact") return;
      const target = document.getElementById("contact");
      if (!target) return;
      const offset = (document.querySelector("header")?.getBoundingClientRect().height ?? 0) + 16;
      // Client-side history navigation does not always update CSS :target.
      target.dataset.quoteTarget = "true";
      target.style.setProperty("--quote-header-offset", `${offset}px`);
      window.scrollTo({ top: Math.max(0, window.scrollY + target.getBoundingClientRect().top - offset), behavior: "instant" });
      if (layoutReady) state.pending = false;
    };
    const begin = () => {
      state.pending = window.location.hash === "#contact";
      state.interrupted = false;
      if (!state.pending) document.getElementById("contact")?.removeAttribute("data-quote-target");
      align();
    };
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const anchor = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!(anchor instanceof HTMLAnchorElement) || anchor.target === "_blank" || anchor.hasAttribute("download")) return;
      const url = new URL(anchor.href);
      if (url.origin !== window.location.origin || url.pathname !== window.location.pathname) return;
      if (url.hash !== "#contact") {
        state.pending = false;
        document.getElementById("contact")?.removeAttribute("data-quote-target");
        return;
      }
      event.preventDefault();
      const catalog = new URLSearchParams(window.location.search).get("catalog");
      if (!url.search && (catalog === "equipment" || catalog === "accessories")) url.searchParams.set("catalog", catalog);
      if (url.href !== window.location.href) window.history.pushState(null, "", url);
      state.pending = true;
      state.interrupted = false;
      align();
    };
    const interrupt = () => {
      state.interrupted = true;
      state.pending = false;
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " ", "Tab"].includes(event.key)) interrupt();
    };
    const onFocus = (event: FocusEvent) => {
      if (event.target instanceof HTMLElement && event.target.matches("input, textarea, select, [contenteditable='true']")) interrupt();
    };

    window.addEventListener("hashchange", begin);
    document.addEventListener("click", onClick, true);
    window.addEventListener("wheel", interrupt, { passive: true });
    window.addEventListener("touchstart", interrupt, { passive: true });
    window.addEventListener("pointerdown", interrupt, { passive: true });
    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("focusin", onFocus);
    align();
    return () => {
      window.removeEventListener("hashchange", begin);
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("wheel", interrupt);
      window.removeEventListener("touchstart", interrupt);
      window.removeEventListener("pointerdown", interrupt);
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("focusin", onFocus);
    };
  });
}
