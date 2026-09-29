"use client";

import { useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { moveCatalogId } from "@/lib/catalogOrder";
import { AdminNotice, type AdminMessage } from "./AdminFields";

type OrderItem = { id: number; name: string; publicationStatus?: string };

export default function CatalogOrderControls<T extends OrderItem>({ catalog, items, adminToken, onReordered, onRefresh, onBusyChange, selectedId, onSelect, children }: {
  catalog: "products" | "accessories";
  items: readonly T[];
  adminToken: string;
  onReordered: (ids: number[]) => void;
  onRefresh: () => Promise<void>;
  onBusyChange: (busy: boolean) => void;
  selectedId: number | null;
  onSelect: (item: T) => void;
  children: (item: T) => ReactNode;
}) {
  const [arranging, setArranging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<AdminMessage | null>(null);
  const [movedId, setMovedId] = useState<number | null>(null);
  const pending = useRef(false);
  const focusAfterMove = useRef<number | null>(null);
  const list = useRef<HTMLOListElement>(null);
  const listId = useId();
  useLayoutEffect(() => {
    if (busy || focusAfterMove.current === null) return;
    const card = list.current?.querySelector<HTMLElement>(`[data-catalog-card="${focusAfterMove.current}"]`);
    focusAfterMove.current = null;
    card?.focus({ preventScroll: true });
    card?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [busy, items]);
  const setPending = (value: boolean) => {
    pending.current = value;
    setBusy(value);
    onBusyChange(value);
  };
  const move = async (id: number, position: number) => {
    if (pending.current || !arranging) return;
    setMessage(null);
    setPending(true);
    try {
      const expectedIds = items.map((item) => item.id);
      const ids = moveCatalogId(expectedIds, id, position);
      const response = await fetch(`${API_BASE}/api/admin/${catalog}/order`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${adminToken}`, "Content-Type": "application/json" },
        body: JSON.stringify({ ids, expectedIds }),
      });
      let result: unknown;
      try {
        result = await response.json();
      } catch {
        throw new Error("The server returned an invalid order response. Refresh the list to check the saved order.");
      }
      if (!response.ok) {
        const detail = typeof result === "object" && result !== null && "detail" in result && typeof result.detail === "string" ? result.detail : "Unable to save listing order. Please retry.";
        throw new Error(detail);
      }
      if (typeof result !== "object" || result === null || !("ids" in result) || JSON.stringify(result.ids) !== JSON.stringify(ids)) {
        throw new Error("The order response was invalid. Refresh the list to check the saved order.");
      }
      focusAfterMove.current = id;
      setMovedId(id);
      onReordered(ids);
      setMessage({ type: "success", text: `Listing order saved. Position ${position + 1} of ${items.length}.` });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Listing order was not confirmed. Refresh the list and retry." });
    } finally { setPending(false); }
  };
  const refresh = async () => {
    if (pending.current) return;
    setPending(true);
    setMessage(null);
    try {
      await onRefresh();
      setMovedId(null);
      setMessage({ type: "success", text: "Listing order refreshed. Open form edits were kept." });
    } catch (error) {
      setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to refresh the catalog order." });
    } finally { setPending(false); }
  };
  return <div className="min-w-0">
    <div className="mb-3 flex flex-wrap gap-2">
      <button type="button" aria-pressed={arranging} aria-controls={listId} disabled={busy || !items.length}
        onClick={() => { setArranging(!arranging); setMessage(null); setMovedId(null); }}
        className={`min-h-11 rounded-full border px-4 text-sm font-medium disabled:opacity-40 ${arranging ? "border-[var(--ink)] bg-[var(--ink)] text-white" : "border-[var(--line)] bg-white"}`}>
        {arranging ? "Done arranging" : "Arrange listing order"}
      </button>
      {arranging ? <button type="button" disabled={busy} onClick={() => void refresh()} className="min-h-11 px-2 text-sm underline">Refresh listing order</button> : null}
    </div>
    {arranging ? <div className="mb-3 text-sm leading-6 text-[var(--muted)]">
      <p>Use the arrows on each card to move it up or down. Each move saves immediately.</p>
      <p className="mt-1 text-xs">Choose Done arranging to edit items. Open form edits are kept; Featured does not change this sequence.</p>
      <p role="status" aria-live="polite" className="min-h-12 pt-2 text-[var(--ink)]">
        {busy ? "Saving or refreshing listing order..." : message?.type === "success" ? message.text : "Arrange mode is on."}
      </p>
      <AdminNotice message={message?.type === "error" ? message : null} />
    </div> : null}
    <ol ref={list} id={listId} aria-label={catalog === "products" ? "Product listings" : "Accessory listings"} className="space-y-3">
      {items.map((item, index) => <li key={item.id} tabIndex={arranging ? -1 : undefined}
        data-catalog-card={item.id} data-position={index + 1}
        aria-label={arranging ? `${item.name}, position ${index + 1} of ${items.length}` : undefined}
        className={`min-w-0 rounded-[22px] border text-left transition-colors ${selectedId === item.id ? "border-[var(--ink)] bg-[#f5f1ea]" : "border-[var(--line)] bg-white"} ${arranging && movedId === item.id ? "ring-2 ring-neutral-400" : ""}`}>
        {arranging ? <div className="min-w-0 p-3">{children(item)}</div>
          : <button type="button" onClick={() => onSelect(item)} className="block w-full min-w-0 rounded-[22px] p-3 text-left">{children(item)}</button>}
        {arranging ? <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--line)] px-3 py-2">
          <span className="text-xs text-[var(--muted)]">Position {index + 1} of {items.length}</span>
          <div className="flex gap-2">
            <button type="button" disabled={busy || index === 0} aria-label={`Move ${item.name} up`} title="Move up"
              onClick={() => void move(item.id, index - 1)} className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--line)] bg-white hover:bg-neutral-100 disabled:opacity-40">
              <ArrowUp size={18} aria-hidden="true" />
            </button>
            <button type="button" disabled={busy || index === items.length - 1} aria-label={`Move ${item.name} down`} title="Move down"
              onClick={() => void move(item.id, index + 1)} className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--line)] bg-white hover:bg-neutral-100 disabled:opacity-40">
              <ArrowDown size={18} aria-hidden="true" />
            </button>
          </div>
        </div> : null}
      </li>)}
    </ol>
    {!items.length ? <p className="mt-3 text-sm text-[var(--muted)]">No saved items to arrange.</p> : null}
  </div>;
}
