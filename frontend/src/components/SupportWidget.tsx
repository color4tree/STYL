"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ComponentProps, type CSSProperties, type ReactNode } from "react";
import SupportConversation from "./SupportConversation";

export type SupportPageContext = Readonly<{ itemType: "product" | "accessory"; id: number; name: string }>;
type PageRegistration = { owner: symbol; pathname: string; item: SupportPageContext };
type SupportContextValue = {
  openChat: () => void;
  excluded: boolean;
  registerPageContext: (item: SupportPageContext) => () => void;
};
const SupportContext = createContext<SupportContextValue>({ openChat: () => {}, excluded: false, registerPageContext: () => () => {} });
export const useSupportWidget = () => useContext(SupportContext);

export function SupportLink({ children, onClick, ...props }: Omit<ComponentProps<typeof Link>, "href">) {
  const { openChat, excluded } = useSupportWidget();
  if (excluded) return null;
  return <Link {...props} href="/support" onClick={(event) => {
    onClick?.(event);
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    openChat();
  }}>{children}</Link>;
}

export default function SupportWidget({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const excluded = pathname === "/admin" || pathname.startsWith("/admin/");
  const [open, setOpen] = useState(false);
  const [activated, setActivated] = useState(false);
  const [activity, setActivity] = useState({ unread: 0, responding: false });
  const [blocked, setBlocked] = useState(false);
  const [placement, setPlacement] = useState<CSSProperties>({});
  const [focusRequest, setFocusRequest] = useState(0);
  const [pageRegistration, setPageRegistration] = useState<PageRegistration | null>(null);
  const pageRevision = useRef<{ key: string; version: string } | null>(null);
  const focusPending = useRef(false);
  const launcher = useRef<HTMLButtonElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const openChat = useCallback(() => {
    focusPending.current = true;
    setFocusRequest((current) => current + 1);
    setActivated(true); setOpen(true);
  }, []);
  const minimize = useCallback(() => {
    setOpen(false);
    window.requestAnimationFrame(() => launcher.current?.focus({ preventScroll: true }));
  }, []);
  const onActivity = useCallback((next: typeof activity) => setActivity((current) => current.unread === next.unread && current.responding === next.responding ? current : next), []);
  const registerPageContext = useCallback((item: SupportPageContext) => {
    const owner = Symbol("support-page");
    setPageRegistration({ owner, pathname, item: { itemType: item.itemType, id: item.id, name: item.name } });
    // An outgoing page (or Strict Mode cleanup) must not remove a newer registration.
    return () => setPageRegistration((current) => current?.owner === owner ? null : current);
  }, [pathname]);
  const pageContext = pageRegistration?.pathname === pathname ? pageRegistration.item : null;
  const pageContextKey = JSON.stringify([pathname, pageContext?.itemType ?? null, pageContext?.id ?? null]);
  const getPageContextVersion = useCallback(() => {
    if (pageRevision.current?.key !== pageContextKey) {
      pageRevision.current = { key: pageContextKey, version: crypto.randomUUID() };
    }
    return pageRevision.current.version;
  }, [pageContextKey]);
  // Track committed navigation even when no question is sent between page visits.
  useLayoutEffect(() => { getPageContextVersion(); }, [getPageContextVersion]);

  useEffect(() => {
    if (excluded) return;
    let frame = 0;
    const resize = new ResizeObserver(() => schedule());
    const observed = new Set<Element>();
    const measure = () => {
      frame = 0;
      const viewport = window.visualViewport;
      const height = viewport?.height ?? window.innerHeight;
      const width = viewport?.width ?? window.innerWidth;
      const top = viewport?.offsetTop ?? 0;
      const left = viewport?.offsetLeft ?? 0;
      let clearance = 0;
      for (const element of document.querySelectorAll(".safe-action")) {
        if (!observed.has(element)) { observed.add(element); resize.observe(element); }
        const box = element.getBoundingClientRect();
        if (getComputedStyle(element).position === "fixed" && box.height && box.top < top + height && box.bottom > top) {
          clearance = Math.max(clearance, top + height - box.top);
        }
      }
      for (const element of observed) {
        if (!element.isConnected) { resize.unobserve(element); observed.delete(element); }
      }
      setBlocked(Boolean(document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')));
      const bottom = Math.max(0, window.innerHeight - top - height) + clearance;
      const values = {
        "--support-bottom": `${bottom}px`,
        "--support-right": `${Math.max(0, window.innerWidth - left - width)}px`,
        "--support-width": `${width}px`,
        "--support-height": `${Math.max(80, Math.min(height * 0.76, height - clearance - 32))}px`,
      } as CSSProperties;
      setPlacement((current) => JSON.stringify(current) === JSON.stringify(values) ? current : values);
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(measure); };
    const observer = new MutationObserver((mutations) => {
      if (mutations.some((mutation) => !root.current?.contains(mutation.target))) schedule();
    });
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["open", "aria-modal", "class"] });
    window.addEventListener("resize", schedule);
    window.addEventListener("scroll", schedule, { passive: true });
    window.visualViewport?.addEventListener("resize", schedule);
    window.visualViewport?.addEventListener("scroll", schedule);
    schedule();
    return () => {
      window.cancelAnimationFrame(frame); observer.disconnect(); resize.disconnect();
      window.removeEventListener("resize", schedule); window.removeEventListener("scroll", schedule);
      window.visualViewport?.removeEventListener("resize", schedule);
      window.visualViewport?.removeEventListener("scroll", schedule);
    };
  }, [excluded]);

  useEffect(() => {
    if (!open || blocked || excluded || !focusPending.current) return;
    const frame = window.requestAnimationFrame(() => {
      focusPending.current = false;
      closeButton.current?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [open, blocked, excluded, focusRequest]);

  return <SupportContext.Provider value={{ openChat, excluded, registerPageContext }}>
    {children}
    {!excluded ? <div ref={root} className="support-widget" style={placement} hidden={blocked} data-support-widget>
      <div id="styl-support-dialog" role="dialog" aria-modal="false" aria-labelledby="styl-support-title" hidden={!open} className="support-panel" onKeyDown={(event) => {
        if (event.key === "Escape" && !event.nativeEvent.isComposing) { event.preventDefault(); event.stopPropagation(); minimize(); }
      }}>
        <div className="support-titlebar">
          <div><h2 id="styl-support-title" className="font-semibold">STYL Assistant</h2></div>
          <button ref={closeButton} type="button" className="support-minimize" onClick={minimize} aria-label="Minimize chat">−</button>
        </div>
        {activated ? <SupportConversation visible={open && !blocked} onActivity={onActivity} onMinimize={minimize} pageContext={pageContext} getPageContextVersion={getPageContextVersion} /> : null}
      </div>
      <button ref={launcher} type="button" className="support-launcher" aria-label={`Ask STYL chat${activity.unread ? `, ${activity.unread} unread ${activity.unread === 1 ? "message" : "messages"}` : ""}${activity.responding ? ", responding" : ""}`} aria-haspopup="dialog" aria-controls="styl-support-dialog" aria-expanded={open} data-responding={activity.responding || undefined} hidden={open} onClick={openChat}>
        <svg aria-hidden="true" viewBox="0 0 40 40" className="support-avatar"><path d="M9 6h22a6 6 0 0 1 6 6v14a6 6 0 0 1-6 6H18l-9 6v-6a6 6 0 0 1-6-6V12a6 6 0 0 1 6-6Z" fill="currentColor" /><circle cx="14" cy="19" r="2" fill="white" /><circle cx="26" cy="19" r="2" fill="white" /><path d="M15 25q5 4 10 0" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" /></svg>
        {activity.unread ? <span className="support-unread" aria-hidden="true">{activity.unread > 99 ? "99+" : activity.unread}</span> : null}
      </button>
    </div> : null}
  </SupportContext.Provider>;
}
