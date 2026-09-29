"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { AdminNotice, type AdminMessage } from "./AdminFields";

function backupFilename(disposition: string | null): string {
  const encoded = disposition?.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)?.[1];
  const plain = disposition?.match(/filename\s*=\s*(?:"([^"]+)"|([^;\s]+))/i);
  let filename = plain?.[1] ?? plain?.[2] ?? "";
  if (encoded) {
    try { filename = decodeURIComponent(encoded.trim()); } catch { /* Use the plain filename instead. */ }
  }
  return /^styl-catalog-backup-[a-z0-9_.-]+\.zip$/i.test(filename)
    ? filename
    : `styl-catalog-backup-${new Date().toISOString().replace(/[:.]/g, "-")}.zip`;
}

export default function CatalogBackup({ adminToken, hasUnsavedChanges, onBusyChange }: {
  adminToken: string;
  hasUnsavedChanges: boolean;
  onBusyChange: (busy: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{ received: number; total: number | null } | null>(null);
  const [message, setMessage] = useState<AdminMessage | null>(null);
  const inFlight = useRef<AbortController | null>(null);
  const objectUrls = useRef(new Map<string, number>());

  useEffect(() => {
    const urls = objectUrls.current;
    return () => {
      inFlight.current?.abort();
      for (const [url, timer] of urls) {
        window.clearTimeout(timer);
        URL.revokeObjectURL(url);
      }
      urls.clear();
    };
  }, []);

  const download = async () => {
    if (inFlight.current) return;
    const controller = new AbortController();
    inFlight.current = controller;
    setBusy(true);
    onBusyChange(true);
    setProgress(null);
    setMessage(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/catalog-backup`, {
        headers: { Authorization: `Bearer ${adminToken}` },
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) {
        let detail = `Unable to create catalog backup (HTTP ${response.status}). Please retry.`;
        try {
          const error = await response.json();
          if (typeof error.detail === "string" && error.detail.trim()) detail = error.detail;
        } catch { /* Non-JSON failures still display the HTTP status. */ }
        if (response.status === 401) detail += " Check your admin access before retrying. Your open editor has not been cleared.";
        throw new Error(detail);
      }
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/zip") {
        throw new Error("The server did not return a ZIP archive. No backup was downloaded. Please retry.");
      }
      const length = Number(response.headers.get("content-length"));
      const total = Number.isSafeInteger(length) && length > 0 ? length : null;
      let blob: Blob;
      if (response.body) {
        const reader = response.body.getReader();
        const chunks: BlobPart[] = [];
        let received = 0;
        setProgress({ received, total });
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            chunks.push(value);
            received += value.byteLength;
            setProgress({ received, total });
          }
        } finally {
          reader.releaseLock();
        }
        blob = new Blob(chunks, { type: "application/zip" });
      } else {
        blob = await response.blob();
      }
      if (!blob.size || (total !== null && blob.size !== total)) {
        throw new Error("The backup download was incomplete. No archive was saved. Please retry.");
      }
      const filename = backupFilename(response.headers.get("content-disposition"));
      const url = URL.createObjectURL(blob);
      // Give Safari time to consume the download before releasing its Blob URL.
      objectUrls.current.set(url, window.setTimeout(() => {
        URL.revokeObjectURL(url);
        objectUrls.current.delete(url);
      }, 60_000));
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      try { link.click(); } finally { link.remove(); }
      setMessage({ type: "success", text: `Download started: ${filename}. Check your browser downloads and keep the archive in a secure location.` });
    } catch (error) {
      if (!controller.signal.aborted) {
        setMessage({ type: "error", text: error instanceof Error ? error.message : "Unable to download the catalog backup. Please retry." });
      }
    } finally {
      if (!controller.signal.aborted) {
        inFlight.current = null;
        setBusy(false);
        onBusyChange(false);
      }
    }
  };

  return (
    <section aria-labelledby="catalog-backup-title" className="min-w-0 max-w-3xl rounded-[28px] border border-[var(--line)] bg-white/80 p-5 sm:p-7">
      <h2 id="catalog-backup-title" className="text-xl font-semibold">Download a catalog recovery ZIP</h2>
      <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
        Recover the saved catalog on a clean STYL installation. This is a catalog recovery archive, not a machine or full website backup.
      </p>
      <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6">
        <li>All equipment and accessories, including drafts, private provenance, CAD and USD prices, and record IDs.</li>
        <li>Home banner settings and referenced local images, videos, and video posters.</li>
        <li>No admin tokens, secrets, customer inquiries, or AWS configuration.</li>
      </ul>
      <div className="mt-5 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <p className="font-semibold">Private, unencrypted archive</p>
        <p>It contains internal catalog information. Store it securely, restrict access, and do not share it publicly.</p>
      </div>
      <p className="mt-4 text-sm leading-6">
        Saved changes only. Unsaved form edits are not included. Opening Backup does not save or discard your editor.
      </p>
      {hasUnsavedChanges ? <p role="status" className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">You have unsaved changes. Return to your editor and save first if you want them in this backup.</p> : null}
      <p className="mt-4 text-sm leading-6 text-[var(--muted)]">
        Browser upload/import is not implemented. Recovery is an administrator-operated process on a clean STYL installation; server setup and credentials must be configured separately.
      </p>
      <button type="button" disabled={busy} onClick={download} className="mt-6 min-h-12 w-full rounded-full bg-[var(--ink)] px-5 py-3 text-sm font-medium text-white disabled:cursor-wait disabled:opacity-60 sm:w-auto">
        {busy ? "Preparing backup…" : message?.type === "error" ? "Retry backup download" : "Download catalog backup"}
      </button>
      {busy ? <p role="status" aria-live="polite" className="mt-3 text-sm">
        {progress ? `Downloading ZIP: ${(progress.received / 1024 / 1024).toFixed(1)} MiB${progress.total ? ` of ${(progress.total / 1024 / 1024).toFixed(1)} MiB` : ""}.` : "Preparing the catalog and media ZIP."} Keep this page open; large catalogs may take a while.
      </p> : null}
      <AdminNotice message={message} />
    </section>
  );
}
