"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { AdminNotice, type AdminMessage } from "./AdminFields";

type Category = "inquiries" | "analytics" | "websiteLogs" | "support";
type RemovalState = "ready" | "removing" | "complete" | "failed";
type Removal = { inquiries: number; analyticsRows: number; websiteLogs: number; supportConversations?: number; skipped: number };
type Archive = {
  id: string;
  filename: string;
  createdAt: string;
  bytes: number;
  sha256: string;
  counts: { inquiries: number; analyticsRows: number; websiteLogs: number; supportConversations?: number; supportMessages?: number; knowledgeFiles?: number };
  verifiedAt: string | null;
  removedAt: string | null;
  archiveDeletedAt: string | null;
  removalState?: RemovalState;
  removal: Removal | null;
};
type RecordsIndex = {
  archives: Archive[];
  storage: { totalBytes: number; freeBytes: number; usedPercent: number };
  websiteLogs: { configured: boolean; activeFiles: number; sealedFiles: number; bytes: number };
  warnings: string[];
};

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const count = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const date = (value: unknown): value is string => typeof value === "string" && Number.isFinite(Date.parse(value));
const nullableDate = (value: unknown) => value === null || date(value);
const validCounts = (value: unknown) => record(value) && count(value.inquiries) && count(value.analyticsRows) && count(value.websiteLogs)
  && (value.supportConversations === undefined || count(value.supportConversations))
  && (value.supportMessages === undefined || count(value.supportMessages))
  && (value.knowledgeFiles === undefined || count(value.knowledgeFiles));
const bytes = (value: number) => value < 1024 ? `${value} B` : value < 1024 ** 2 ? `${(value / 1024).toFixed(1)} KiB` : value < 1024 ** 3 ? `${(value / 1024 ** 2).toFixed(1)} MiB` : `${(value / 1024 ** 3).toFixed(1)} GiB`;
const timestamp = (value: string) => new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
const button = "min-h-12 rounded-full border border-[var(--line)] bg-white px-5 py-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50";

function isArchive(value: unknown): value is Archive {
  return record(value) && typeof value.id === "string" && /^[a-f0-9]{32}$/.test(value.id)
    && typeof value.filename === "string" && /^[a-z0-9_.-]+\.zip$/i.test(value.filename)
    && date(value.createdAt) && count(value.bytes) && value.bytes > 0
    && typeof value.sha256 === "string" && /^[a-f0-9]{64}$/.test(value.sha256)
    && validCounts(value.counts) && nullableDate(value.verifiedAt) && nullableDate(value.removedAt) && nullableDate(value.archiveDeletedAt)
    && (value.removalState === undefined || (typeof value.removalState === "string" && ["ready", "removing", "complete", "failed"].includes(value.removalState)))
    && (value.removal === null || (record(value.removal) && validCounts(value.removal) && count(value.removal.skipped)));
}

function isIndex(value: unknown): value is RecordsIndex {
  return record(value) && Array.isArray(value.archives) && value.archives.every((archive) => isArchive(archive) && archive.removalState !== undefined)
    && new Set(value.archives.map((archive) => archive.id)).size === value.archives.length
    && record(value.storage) && count(value.storage.totalBytes) && count(value.storage.freeBytes)
    && value.storage.freeBytes <= value.storage.totalBytes
    && typeof value.storage.usedPercent === "number" && Number.isFinite(value.storage.usedPercent)
    && value.storage.usedPercent >= 0 && value.storage.usedPercent <= 100
    && record(value.websiteLogs) && typeof value.websiteLogs.configured === "boolean"
    && count(value.websiteLogs.activeFiles) && count(value.websiteLogs.sealedFiles) && count(value.websiteLogs.bytes)
    && Array.isArray(value.warnings) && value.warnings.every((warning) => typeof warning === "string");
}

export default function RecordsManager({ adminToken, active, hasUnsavedChanges, onBusyChange }: {
  adminToken: string;
  active: boolean;
  hasUnsavedChanges: boolean;
  onBusyChange: (busy: boolean) => void;
}) {
  const [index, setIndex] = useState<RecordsIndex | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [confirmation, setConfirmation] = useState("");
  const [backupDeletionConfirmation, setBackupDeletionConfirmation] = useState("");
  const [verificationRequired, setVerificationRequired] = useState<string[]>([]);
  const [unconfirmedRemovals, setUnconfirmedRemovals] = useState<string[]>([]);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState<AdminMessage | null>(null);
  const inFlight = useRef<AbortController | null>(null);
  const downloadUrls = useRef(new Map<string, number>());
  const fileInput = useRef<HTMLInputElement | null>(null);
  const selected = index?.archives.find((archive) => archive.id === selectedId) ?? null;
  const verified = Boolean(selected?.verifiedAt && !verificationRequired.includes(selected.id));
  const removalUnconfirmed = Boolean(selected && unconfirmedRemovals.includes(selected.id));
  const recoveryLocked = removalUnconfirmed || selected?.removalState === "failed" || selected?.removalState === "removing";
  const removable = Boolean(selected && verified && selected.removalState === "ready" && !recoveryLocked && !selected.removedAt && !selected.archiveDeletedAt);
  const backupDeletable = Boolean(selected && verified && !recoveryLocked && !selected.archiveDeletedAt);

  useEffect(() => {
    const urls = downloadUrls.current;
    return () => {
      inFlight.current?.abort();
      inFlight.current = null;
      for (const [url, timer] of urls) { window.clearTimeout(timer); URL.revokeObjectURL(url); }
      urls.clear();
      onBusyChange(false);
    };
  }, [onBusyChange]);

  const request = useCallback(async (path: string, signal: AbortSignal, options: RequestInit = {}) => {
    const response = await fetch(`${API_BASE}/api/admin/records${path}`, {
      ...options, headers: { ...options.headers, Authorization: `Bearer ${adminToken}` },
      cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal,
    });
    if (!response.ok) {
      let detail = `Records request failed (HTTP ${response.status}). Please retry.`;
      try {
        const error: unknown = await response.json();
        if (record(error) && typeof error.detail === "string" && error.detail.trim()) detail = error.detail;
      } catch { /* Keep the HTTP fallback for non-JSON errors. */ }
      if (response.status === 401) detail += " Check your admin access. Your selection and open editor have been preserved.";
      throw new Error(detail);
    }
    return response;
  }, [adminToken]);

  const perform = useCallback(async (label: string, action: (signal: AbortSignal) => Promise<void>) => {
    if (inFlight.current) return;
    const controller = new AbortController();
    inFlight.current = controller;
    setBusy(label);
    onBusyChange(true);
    setMessage(null);
    try {
      await action(controller.signal);
    } catch (error) {
      if (!controller.signal.aborted) {
        const detail = error instanceof Error ? error.message : "Unable to complete the records request. Please retry.";
        setMessage({ type: "error", text: adminToken ? detail.replaceAll(adminToken, "[redacted]") : detail });
      }
    } finally {
      if (!controller.signal.aborted) {
        inFlight.current = null;
        setBusy("");
        onBusyChange(false);
      }
    }
  }, [adminToken, onBusyChange]);

  const refreshIndex = useCallback(async (signal: AbortSignal) => {
    const value: unknown = await (await request("", signal)).json();
    if (!isIndex(value)) throw new Error("The records response is invalid. Please refresh or retry.");
    setIndex(value);
    setSelectedId((current) => value.archives.some((archive) => archive.id === current) ? current : value.archives[0]?.id ?? null);
    setUnconfirmedRemovals((current) => current.filter((id) => !value.archives.some((archive) => archive.id === id)));
  }, [request]);

  const load = useCallback(() => perform("Loading saved backups…", refreshIndex), [perform, refreshIndex]);

  useEffect(() => {
    async function initialize() { await load(); }
    if (active) void initialize();
  }, [active, load]);

  function resetChoice() {
    setFile(null);
    if (fileInput.current) fileInput.current.value = "";
    setCategories([]);
    setConfirmation("");
    setBackupDeletionConfirmation("");
  }

  function updateArchive(archive: Archive) {
    setIndex((current) => current ? { ...current, archives: [archive, ...current.archives.filter((item) => item.id !== archive.id)] } : current);
  }

  async function archiveResponse(response: Response, expectedId?: string): Promise<Archive & { removalState: RemovalState }> {
    const value: unknown = await response.json();
    if (!isArchive(value) || (expectedId && (value.id !== expectedId || value.removalState === undefined))) throw new Error("The backup response is invalid. Refresh records before trying again.");
    return { ...value, removalState: value.removalState ?? "ready" };
  }

  const create = () => perform("Creating persistent backup…", async (signal) => {
    const archive = await archiveResponse(await request("/archives", signal, { method: "POST" }));
    updateArchive(archive);
    setSelectedId(archive.id);
    resetChoice();
    setMessage({ type: "success", text: "Persistent backup created on the server. Next, download it, save it securely, and select that saved file for verification. No source records were removed." });
  });

  const download = () => {
    if (!selected || selected.archiveDeletedAt) return;
    void perform("Receiving backup ZIP…", async (signal) => {
      const response = await request(`/archives/${selected.id}/download`, signal);
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/zip") {
        throw new Error("The server did not return a ZIP archive. No download was started. Please retry.");
      }
      const blob = await response.blob();
      if (blob.size !== selected.bytes) throw new Error("The backup download was incomplete. No download was started. Please retry.");
      const url = URL.createObjectURL(blob);
      // Safari needs time to consume the Blob before its URL is revoked.
      downloadUrls.current.set(url, window.setTimeout(() => { URL.revokeObjectURL(url); downloadUrls.current.delete(url); }, 60_000));
      const link = document.createElement("a");
      link.href = url;
      link.download = selected.filename;
      document.body.appendChild(link);
      try { link.click(); } finally { link.remove(); }
      setMessage({ type: "success", text: "ZIP received; browser download started. This does not confirm a saved local copy. Check your downloads, then select the saved ZIP below. No source records were removed." });
    });
  };

  const verify = () => {
    if (!selected || !file || selected.archiveDeletedAt) return;
    void perform("Verifying the saved local ZIP…", async (signal) => {
      setVerificationRequired((current) => [...new Set([...current, selected.id])]);
      const archive = await archiveResponse(await request(`/archives/${selected.id}/verify`, signal, {
        method: "POST", headers: { "Content-Type": "application/zip" }, body: file,
      }), selected.id);
      if (!archive.verifiedAt) throw new Error("The server did not confirm verification. Removal remains disabled.");
      updateArchive(archive);
      setVerificationRequired((current) => current.filter((id) => id !== archive.id));
      setMessage({ type: "success", text: "Saved local backup verified: the server matched the complete file bytes and SHA-256. Keep this private copy safe. Verification did not remove any source records." });
    });
  };

  const remove = () => {
    if (!selected || !removable || !categories.length || confirmation !== `REMOVE ${selected.id}`) return;
    void perform("Removing only unchanged backed-up source records…", async (signal) => {
      setUnconfirmedRemovals((current) => [...new Set([...current, selected.id])]);
      try {
        const archive = await archiveResponse(await request(`/archives/${selected.id}/remove`, signal, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmation, categories }),
        }), selected.id);
        if (archive.removalState !== "complete" || !archive.removedAt || !archive.removal) throw new Error("The server did not confirm removal. Refresh records to check the result before retrying.");
        updateArchive(archive);
        setUnconfirmedRemovals((current) => current.filter((id) => id !== archive.id));
        setCategories([]);
        setConfirmation("");
        setMessage({ type: "success", text: "Selected source-record removal completed. The backup is retained. Review removed and skipped counts below; new or changed records and protected metadata remain untouched." });
      } catch (error) {
        try { await refreshIndex(signal); } catch { /* Keep cleanup locked if the removal outcome cannot be confirmed. */ }
        throw error;
      }
    });
  };

  const deleteBackup = () => {
    if (!selected || !backupDeletable || backupDeletionConfirmation !== `DELETE BACKUP ${selected.id}`) return;
    void perform("Deleting only the verified server backup ZIP…", async (signal) => {
      const archive = await archiveResponse(await request(`/archives/${selected.id}`, signal, {
        method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmation: backupDeletionConfirmation }),
      }), selected.id);
      if (!archive.archiveDeletedAt) throw new Error("The server did not confirm backup deletion. Refresh records to check the result before retrying.");
      updateArchive(archive);
      resetChoice();
      setMessage({ type: "success", text: "Server backup ZIP deleted; audit history retained. This action did not remove source records. Keep your verified local copy safe: download, verification, and source removal are now disabled for this archive." });
    });
  };

  return <section aria-labelledby="records-title" className="min-w-0 max-w-4xl space-y-5">
    <div className="min-w-0 rounded-[28px] border border-[var(--line)] bg-white/80 p-5 sm:p-7">
      <h2 id="records-title" className="text-xl font-semibold">Business, log and support records</h2>
      <p className="mt-3 text-sm leading-6">1. Create → 2. Download and verify your saved ZIP → 3. Optional cleanup.</p>
      <p className="mt-3 text-sm leading-6 text-[var(--muted)]">Confidential, unencrypted backup — includes personal information. Store securely; never publish. Downloading or verifying does not delete records.</p>
      <details className="mt-3 text-sm leading-6">
        <summary className="min-h-11 cursor-pointer py-2 font-medium">Details: privacy, coverage and retention</summary>
      <p className="mt-3 text-sm leading-6">Website access, runtime and error logs, analytics, and inquiries are not automatically deleted by age or size. Operational logs have a separate 14-day retention policy. Downloading or verifying never removes records.</p>
        <p className="mt-3">Verification sends your selected ZIP privately back to this server for a streaming full-file comparison; the upload is not stored.</p>
        <p className="mt-3">Includes a full SQLite snapshot, saved inquiry JSON, configured website log files, support history and follow-up contact details, private knowledge source files, and a standalone offline verify/restore tool. Use Catalog recovery for the separate catalog ZIP. Current catalog, configuration and settings are not removal targets.</p>
      </details>
      {hasUnsavedChanges ? <p role="status" className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm">You have unsaved editor changes. Opening Backup neither saves nor discards them.</p> : null}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button type="button" disabled={Boolean(busy)} onClick={() => void load()} className={button}>Refresh records</button>
        <button type="button" disabled={Boolean(busy) || !index} onClick={() => void create()} className={`${button} !bg-[var(--ink)] text-white`}>Create persistent backup</button>
      </div>
      {busy ? <p role="status" aria-live="polite" className="mt-3 text-sm">{busy} Keep this page open. Other admin actions are disabled until this request finishes.</p> : null}
      <AdminNotice message={message} />
      {index ? <>
        <p className="mt-4 text-sm">Storage at last refresh: {bytes(index.storage.freeBytes)} free of {bytes(index.storage.totalBytes)} · {index.storage.usedPercent.toFixed(1)}% used. Refresh after changes for current capacity.</p>
        {index.storage.usedPercent >= 80 ? <p role="alert" className="mt-3 rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm">Disk usage is at or above 80%. Arrange more storage or deliberately verify and remove eligible backed-up records or server backup ZIPs. No automatic deletion will run.</p> : null}
        <p className="mt-3 text-sm">{index.websiteLogs.configured ? `Website log coverage configured: ${index.websiteLogs.activeFiles} active files, ${index.websiteLogs.sealedFiles} sealed files, ${bytes(index.websiteLogs.bytes)}.` : "Website log coverage is NOT configured. A backup can protect business records, but does not provide website log coverage."}</p>
        <p className="mt-2 text-sm text-[var(--muted)]">Active log prefixes are included in backups; only unchanged sealed files can be removed. New log writes remain safe.</p>
        {index.warnings.length ? <ul aria-label="Records warnings" className="mt-3 list-disc space-y-2 pl-5 text-sm text-amber-950">{index.warnings.map((warning, position) => <li className="break-words" key={position}>{warning}</li>)}</ul> : null}
      </> : !busy ? <p className="mt-4 text-sm">Records are unavailable. Refresh records to retry without clearing your editor.</p> : null}
    </div>
    {index ? <div className="min-w-0 rounded-[28px] border border-[var(--line)] bg-white/80 p-5 sm:p-7">
      <h3 className="text-lg font-semibold">Download and verify a saved backup</h3>
      {!index.archives.length ? <p className="mt-3 text-sm">No persistent backups yet. Create one above; records stay on the server until you explicitly request eligible removal.</p> : <>
        <label className="mt-4 block text-sm font-medium">Saved server backup
          <select aria-label="Saved server backup" value={selectedId ?? ""} disabled={Boolean(busy)} onChange={(event) => { setSelectedId(event.target.value); resetChoice(); setMessage(null); }} className="mt-2 min-h-12 w-full min-w-0 max-w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2">
            {index.archives.map((archive) => <option key={archive.id} value={archive.id}>{timestamp(archive.createdAt)} · {archive.id}{archive.archiveDeletedAt ? " · Server ZIP deleted" : ""}</option>)}
          </select>
        </label>
        {selected ? <>
          <dl className="mt-4 space-y-2 text-sm">
            <div><dt className="font-semibold">Archive</dt><dd className="break-all">{selected.filename} · {bytes(selected.bytes)}</dd></div>
            <div><dt className="font-semibold">Backup ID</dt><dd className="break-all font-mono">{selected.id}</dd></div>
            <div><dt className="font-semibold">SHA-256</dt><dd className="break-all font-mono">{selected.sha256}</dd></div>
            <div><dt className="font-semibold">Backed-up records</dt><dd>{selected.counts.inquiries} inquiries · {selected.counts.analyticsRows} analytics rows (full database history) · {selected.counts.websiteLogs} website log files · {selected.counts.supportConversations ?? 0} support conversations / {selected.counts.supportMessages ?? 0} messages · {selected.counts.knowledgeFiles ?? 0} knowledge source files</dd></div>
            <div><dt className="font-semibold">Local-file verification</dt><dd>{verified ? `Verified ${timestamp(selected.verifiedAt!)}` : "Not verified for removal. Select the saved file and verify it below."}</dd></div>
            {selected.archiveDeletedAt ? <div><dt className="font-semibold">Server backup ZIP</dt><dd>Deleted {timestamp(selected.archiveDeletedAt)}. Audit history is retained; only your downloaded backup copy remains.</dd></div> : null}
          </dl>
          <button type="button" disabled={Boolean(busy) || Boolean(selected.archiveDeletedAt)} onClick={download} className={`mt-5 ${button}`}>Download selected backup</button>
          <label className="mt-5 block text-sm font-medium">Saved local backup ZIP
            <input ref={fileInput} type="file" accept=".zip,application/zip" disabled={Boolean(busy) || Boolean(selected.archiveDeletedAt)} onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setVerificationRequired((current) => [...new Set([...current, selected.id])]);
            }} className="mt-2 block min-h-12 w-full min-w-0 max-w-full rounded-xl border border-[var(--line)] bg-white p-2 text-sm file:mr-3 file:min-h-11 file:rounded-lg file:border-0 file:px-3" />
          </label>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Choose the ZIP you saved from your browser download, not another archive. Verification does not restore data. A matching filename alone is not proof of a complete backup.</p>
          <button type="button" disabled={Boolean(busy) || !file || Boolean(selected.archiveDeletedAt)} onClick={verify} className={`mt-3 ${button}`}>Verify saved file</button>
        </> : null}
      </>}
    </div> : null}
    {selected ? <div className="min-w-0 rounded-[28px] border border-red-200 bg-white/80 p-5 sm:p-7">
      <h3 className="text-lg font-semibold">Optional: remove backed-up source records</h3>
      <p className="mt-3 text-sm leading-6">Only selected, unchanged records in this verified backup can be removed, once per archive. This changes historical reports and inquiry counts; the backup is retained.</p>
      <details className="mt-3 text-sm leading-6">
        <summary className="min-h-11 cursor-pointer py-2 font-medium">Details: removal scope and protected records</summary>
      <p className="mt-3 text-sm leading-6">Nothing is selected by default. Current-hour analytics, pending inquiries, mail duplicate-prevention metadata, current catalog, configuration, and settings stay untouched.</p>
      <p className="mt-3 text-sm leading-6">Analytics removal covers only completed-hour aggregate counts/items, not every row in the full database backup. Email report history and safety metadata stay: all report snapshots, delivery metadata, settings, analytics metadata, and legacy privacy-related rows are protected. Legacy records require separate review.</p>
      <p className="mt-3 text-sm leading-6">Support cleanup removes only unchanged closed conversations and their messages, jobs and contact details. Active conversations, changed contacts or threads, pending work, support settings and knowledge sources/files remain. Old archives without the current support schema cannot authorize support cleanup.</p>
      <p className="mt-3 text-sm leading-6">This selection can be processed only once per archive. Unselected categories stay untouched; create another backup for a later removal. Keep your verified local copy. Source removal retains the server archive; deleting that ZIP is a separate choice below.</p>
      </details>
      {recoveryLocked ? <div role="alert" className="mt-4 rounded-xl border-2 border-amber-500 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <p className="font-semibold">Recovery review required</p>
        <p>{removalUnconfirmed ? "The removal outcome could not be confirmed. Refresh records to check its status." : selected.removalState === "removing" ? "Source removal is in progress or may have been interrupted." : "A source-removal attempt failed."} Some selected records may already have been removed. The verified backup is retained and locked for recovery. Source removal and server-ZIP deletion are disabled; do not retry cleanup. Download the retained ZIP for administrator-led recovery review.</p>
        {selected.removal ? <p className="mt-2">Recorded partial result: {selected.removal.inquiries} inquiries, {selected.removal.analyticsRows} analytics rows, {selected.removal.websiteLogs} website log files, {selected.removal.supportConversations ?? 0} support conversations removed; {selected.removal.skipped} skipped.</p> : null}
      </div> : null}
      {selected.removedAt && selected.removal ? <p role="status" className="mt-4 rounded-xl border border-[var(--line)] bg-white p-4 text-sm">
        Removal completed {timestamp(selected.removedAt)}: {selected.removal.inquiries} inquiries, {selected.removal.analyticsRows} analytics rows, {selected.removal.websiteLogs} website log files, {selected.removal.supportConversations ?? 0} support conversations removed; {selected.removal.skipped} records skipped. This archive cannot request removal again.
      </p> : selected.archiveDeletedAt ? <p className="mt-4 text-sm font-medium">Source removal is disabled because this archive&apos;s server backup ZIP was deleted. Source records were not removed by that deletion.</p> : <>
        {!verified ? <p className="mt-3 text-sm font-medium">Removal is locked until your saved local backup is verified.</p> : null}
        <fieldset disabled={Boolean(busy) || !removable} className="mt-4 min-w-0 space-y-2">
          <legend className="mb-2 text-sm font-semibold">Choose source-record categories to remove</legend>
          {([["inquiries", "Saved inquiries"], ["analytics", "Analytics history"], ["websiteLogs", "Sealed website logs"], ["support", "Closed support conversations"]] as const).map(([category, label]) => <label key={category} className="flex min-h-12 items-center gap-3 rounded-xl border border-[var(--line)] p-3 text-sm">
            <input type="checkbox" disabled={category === "support" && !selected.counts.supportConversations} checked={categories.includes(category)} onChange={(event) => setCategories((current) => event.target.checked ? [...current, category] : current.filter((item) => item !== category))} className="h-5 w-5 shrink-0" />{label}
          </label>)}
          <label className="block pt-3 text-sm font-medium">Removal confirmation
            <span className="mt-2 block font-normal">Type exactly <code className="break-all font-mono">REMOVE {selected.id}</code></span>
            <input type="text" aria-label="Removal confirmation" value={confirmation} autoComplete="off" spellCheck={false} onChange={(event) => setConfirmation(event.target.value)} className="mt-2 min-h-12 w-full min-w-0 rounded-xl border border-[var(--line)] bg-white px-3 py-2 font-mono" />
          </label>
        </fieldset>
        <button type="button" disabled={Boolean(busy) || !removable || !categories.length || confirmation !== `REMOVE ${selected.id}`} onClick={remove} className={`mt-5 ${button} !border-red-700 !bg-red-700 text-white`}>Remove selected source records</button>
      </>}
    </div> : null}
    {selected ? <div className="min-w-0 rounded-[28px] border border-amber-300 bg-white/80 p-5 sm:p-7">
      <h3 className="text-lg font-semibold">Optional: delete the server backup ZIP</h3>
      <p className="mt-3 text-sm leading-6">This is separate from source-record removal. It deletes only this server ZIP to reclaim its storage, keeps audit metadata, and never removes source records. Your verified downloaded copy will be the only backup copy left from this workflow; store it securely first.</p>
      <p className="mt-3 text-sm leading-6">Deleting the server ZIP permanently disables its download, verification, and source removal. Complete any desired source removal before deleting this server backup. No backup is deleted automatically.</p>
      {selected.archiveDeletedAt ? <p role="status" className="mt-4 rounded-xl border border-[var(--line)] bg-white p-4 text-sm">Server ZIP deleted {timestamp(selected.archiveDeletedAt)}. This history remains available; keep your verified local backup safe.</p> : <>
        {!verified ? <p className="mt-3 text-sm font-medium">Server-backup deletion is locked until your saved local backup is verified.</p> : null}
        {recoveryLocked ? <p className="mt-3 text-sm font-medium">This server ZIP is locked for recovery and cannot be deleted. Review the source-removal status above.</p> : null}
        <label className="mt-4 block text-sm font-medium">Server-backup deletion confirmation
          <span className="mt-2 block font-normal">Type exactly <code className="break-all font-mono">DELETE BACKUP {selected.id}</code></span>
          <input type="text" aria-label="Server-backup deletion confirmation" value={backupDeletionConfirmation} disabled={Boolean(busy) || !backupDeletable} autoComplete="off" spellCheck={false} onChange={(event) => setBackupDeletionConfirmation(event.target.value)} className="mt-2 min-h-12 w-full min-w-0 rounded-xl border border-[var(--line)] bg-white px-3 py-2 font-mono" />
        </label>
        <button type="button" disabled={Boolean(busy) || !backupDeletable || backupDeletionConfirmation !== `DELETE BACKUP ${selected.id}`} onClick={deleteBackup} className={`mt-5 ${button} !border-red-700 text-red-800`}>Delete server backup ZIP</button>
      </>}
    </div> : null}
  </section>;
}
