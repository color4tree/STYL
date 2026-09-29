"use client";

import { useState, useSyncExternalStore } from "react";
import { getAnalyticsStatus, getServerAnalyticsStatus, setAnalyticsOptOut, subscribeAnalytics } from "@/lib/analytics";

export default function PrivacyPreference() {
  const status = useSyncExternalStore(subscribeAnalytics, getAnalyticsStatus, getServerAnalyticsStatus);
  const [error, setError] = useState(false);
  return <div className="rounded-2xl border border-[var(--line)] p-4">
    <p>{status.optedOut ? "Optional usage measurement is turned off for this browser." : "You can turn off optional usage measurement without affecting shopping."}</p>
    <button type="button" disabled={!status.ready} className="mt-3 min-h-12 rounded-full border border-[var(--ink)] px-5 py-2 disabled:opacity-50" onClick={() => {
      setError(!setAnalyticsOptOut(!status.optedOut));
    }}>{status.optedOut ? "Allow aggregate measurement" : "Turn off usage measurement"}</button>
    {error ? <p role="alert" className="mt-3 text-red-800">Your preference could not be saved for future visits. Measurement remains off on this page. Check this site&apos;s browser storage settings and try again.</p> : null}
  </div>;
}
