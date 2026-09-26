"use client";

import { useCallback, useEffect, useRef } from "react";

export function useUnsavedChanges(dirty: boolean, busy: boolean) {
  const protectedState = dirty || busy;
  const state = useRef({ dirty, busy });
  const guarded = useRef(false);
  useEffect(() => { state.current = { dirty, busy }; }, [dirty, busy]);

  const confirmLeave = useCallback(() => {
    if (state.current.busy) return false;
    return !state.current.dirty || window.confirm("Discard your unsaved changes?");
  }, []);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (state.current.dirty || state.current.busy) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!(target instanceof HTMLAnchorElement) || target.target === "_blank" || target.hasAttribute("download") || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      if (target.href === window.location.href) return;
      if (!confirmLeave()) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", onClick, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", onClick, true);
    };
  }, [confirmLeave]);

  // Keep the same-URL entry until Back is used, avoiding asynchronous history
  // changes while saving or switching editors. A clean form skips it silently.
  useEffect(() => {
    const url = window.location.href;
    guarded.current = Boolean(window.history.state?.stylAdminGuard);
    const onPopState = () => {
      if (!guarded.current || window.location.href !== url) return;
      if (!confirmLeave()) {
        window.history.pushState({ ...window.history.state, stylAdminGuard: true }, "", url);
      } else {
        guarded.current = false;
        window.history.back();
      }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [confirmLeave]);

  useEffect(() => {
    if (!protectedState || guarded.current) return;
    window.history.pushState({ ...window.history.state, stylAdminGuard: true }, "", window.location.href);
    guarded.current = true;
  }, [protectedState, confirmLeave]);

  return confirmLeave;
}
