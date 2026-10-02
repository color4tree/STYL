"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import type { AnalyticsEmailSettings } from "@/lib/analyticsTypes";
import { AdminNotice, type AdminMessage } from "./AdminFields";

function isSettings(value: unknown): value is AnalyticsEmailSettings {
  if (!value || typeof value !== "object") return false;
  const settings = value as Record<string, unknown>;
  return typeof settings.enabled === "boolean" && typeof settings.effectiveEnabled === "boolean"
    && Array.isArray(settings.recipients) && settings.recipients.length <= 20 && settings.recipients.every(address => typeof address === "string")
    && typeof settings.revision === "number" && Number.isSafeInteger(settings.revision) && settings.revision >= 0
    && ["environment", "admin"].includes(String(settings.source))
    && ["local", "test", "staging", "production"].includes(String(settings.environment))
    && settings.effectiveEnabled === (settings.enabled && settings.recipients.length > 0 && settings.environment === "production")
    && typeof settings.timezone === "string" && typeof settings.nextRunAt === "string"
    && Number.isFinite(Date.parse(settings.nextRunAt));
}

async function check(response: Response) {
  if (response.ok) return;
  let detail = `Email settings request failed (HTTP ${response.status}). Please retry.`;
  try {
    const value: unknown = await response.json();
    if (value && typeof value === "object" && "detail" in value && typeof value.detail === "string") detail = value.detail;
  } catch {
    // Keep the HTTP error if the proxy returned something other than JSON.
  }
  throw new Error(detail);
}

export default function DailyEmailSettings({ adminToken, active, onSaved }: {
  adminToken: string; active: boolean; onSaved: () => void;
}) {
  const [settings, setSettings] = useState<AnalyticsEmailSettings | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [recipients, setRecipients] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);
  const [notice, setNotice] = useState<AdminMessage | null>(null);
  const loaded = useRef(false);
  const token = useRef(adminToken);
  const pending = useRef(false);
  const saveController = useRef<AbortController | null>(null);
  const dirty = !!settings && (enabled !== settings.enabled || recipients !== settings.recipients.join("\n"));

  useEffect(() => {
    if (token.current !== adminToken) { token.current = adminToken; loaded.current = false; setSettings(null); }
    if (!active || loaded.current) return;
    const controller = new AbortController();
    async function load() {
      setLoading(true); setNotice(null);
      try {
        const response = await fetch(`${API_BASE}/api/admin/analytics/email-settings`, {
          headers: { Authorization: `Bearer ${adminToken}` }, cache: "no-store", signal: controller.signal,
        });
        await check(response);
        const value: unknown = await response.json();
        if (!isSettings(value)) throw new Error("Email settings response is invalid. Reload before editing.");
        if (!controller.signal.aborted) {
          setSettings(value); setEnabled(value.enabled); setRecipients(value.recipients.join("\n"));
          loaded.current = true;
        }
      } catch (error) {
        if (!controller.signal.aborted) setNotice({ type: "error", text: error instanceof Error ? error.message : "Unable to load email settings. Please retry." });
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => controller.abort();
  }, [active, adminToken, reload]);

  useEffect(() => () => { saveController.current?.abort(); }, []);
  useEffect(() => {
    if (!dirty && !saving) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, saving]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!settings || pending.current) return;
    const addresses = recipients.split(/[,\n]/).map(value => value.trim()).filter(Boolean);
    if (enabled && !addresses.length) {
      setNotice({ type: "error", text: "Add at least one recipient before enabling daily email." }); return;
    }
    if (addresses.length > 20) {
      setNotice({ type: "error", text: "Enter at most 20 recipient email addresses." }); return;
    }
    const controller = new AbortController();
    saveController.current = controller;
    pending.current = true;
    setSaving(true); setNotice(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/analytics/email-settings`, {
        method: "PUT", headers: { Authorization: `Bearer ${adminToken}`, "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, recipients: addresses, expectedRevision: settings.revision }),
        signal: controller.signal,
      });
      await check(response);
      const value: unknown = await response.json();
      if (!isSettings(value)) throw new Error("Unable to confirm saved settings. Your entries are retained; reload to verify.");
      if (!controller.signal.aborted) {
        setSettings(value); setEnabled(value.enabled); setRecipients(value.recipients.join("\n"));
        setNotice({ type: "success", text: "Daily email settings saved. Saving does not send an email." });
        onSaved();
      }
    } catch (error) {
      if (!controller.signal.aborted) setNotice({ type: "error", text: error instanceof Error ? error.message : "Unable to save email settings. Your entries are retained." });
    } finally { pending.current = false; if (!controller.signal.aborted) setSaving(false); }
  };

  return <section className="min-w-0 rounded-2xl border border-[var(--line)] bg-white p-4 sm:p-5" aria-labelledby="email-settings-title" data-testid="daily-email-settings" aria-busy={loading || saving}>
    <h3 id="email-settings-title" className="text-lg font-semibold">Daily email settings</h3>
    <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Choose who receives the daily usage summary and turn scheduled sending on or off.</p>
    <AdminNotice message={notice} />
    {loading ? <p role="status" className="mt-3 text-sm">Loading email settings...</p> : null}
    {settings ? <form onSubmit={save} className="mt-4">
      <fieldset disabled={loading || saving} className="min-w-0 space-y-4">
        <label className="flex min-h-12 items-center gap-3 text-sm font-medium">
          <input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} className="h-5 w-5" />
          Enable daily summary emails
        </label>
        <label className="block text-sm font-medium">Recipients
          <textarea aria-label="Daily email recipients" value={recipients} onChange={event => setRecipients(event.target.value)}
            rows={3} maxLength={5200} spellCheck={false} autoCapitalize="none" autoComplete="off"
            placeholder="owner@example.com" className="mt-2 block w-full min-w-0 rounded-xl border border-[var(--line)] px-3 py-3 text-base font-normal" />
          <span className="mt-1 block text-xs font-normal text-[var(--muted)]">One address per line, or separate with commas. Up to 20 addresses; duplicates are removed.</span>
        </label>
        <p className="text-sm leading-6" data-testid="daily-email-effective-state">
          {settings.environment !== "production"
            ? `This is the ${settings.environment} environment: real emails are never sent, even with the switch saved on.`
            : settings.enabled && !settings.recipients.length
              ? "Sending is blocked: add at least one recipient."
              : settings.effectiveEnabled ? "Scheduled sending is on." : "Scheduled sending is off."}
        </p>
        <p className="text-xs leading-5 text-[var(--muted)]">Schedule: 12:15 AM Pacific (00:15 America/Los_Angeles), covering the previous completed calendar day. When enabled, the latest due report may send on the next scheduler check (within 15 minutes). Changes apply to future deliveries; an email already in progress cannot be recalled. Server SMTP settings are unchanged.</p>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={!dirty} className="min-h-12 rounded-full bg-[var(--ink)] px-5 py-2 text-sm text-white disabled:opacity-50">{saving ? "Saving settings..." : "Save email settings"}</button>
          {dirty ? <span className="text-sm text-[var(--muted)]">Unsaved changes</span> : null}
        </div>
      </fieldset>
    </form> : !loading ? <p className="mt-3 text-sm">Settings are unavailable; no defaults have been substituted.</p> : null}
    <button type="button" disabled={loading || saving} className="mt-3 min-h-12 text-sm underline underline-offset-4 disabled:opacity-50" onClick={() => {
      if (dirty && !window.confirm("Discard your unsaved email settings and reload the saved values?")) return;
      loaded.current = false; setReload(value => value + 1);
    }}>{dirty ? "Discard changes and reload" : "Reload email settings"}</button>
  </section>;
}
