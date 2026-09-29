"use client";

import { useEffect, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import { useReportWebVitals } from "next/web-vitals";
import { analyticsRouteChanged, getAnalyticsStatus, getServerAnalyticsStatus, initializeAnalytics, reportAnalyticsVital, subscribeAnalytics } from "@/lib/analytics";

export default function AnalyticsTracker() {
  const pathname = usePathname();
  const status = useSyncExternalStore(subscribeAnalytics, getAnalyticsStatus, getServerAnalyticsStatus);
  useEffect(() => initializeAnalytics(), []);
  useEffect(() => { analyticsRouteChanged(pathname); }, [pathname]);
  return status.active ? <AggregateVitals /> : null;
}

function AggregateVitals() {
  useReportWebVitals(reportAnalyticsVital);
  return null;
}
