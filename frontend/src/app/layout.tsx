import type { Metadata } from "next";
import { Suspense } from "react";
import Link from "next/link";
import AnalyticsTracker from "@/components/AnalyticsTracker";
import "./globals.css";

export const metadata: Metadata = {
  title: "STYL | Premium Fitness Equipment",
  description: "Premium fitness equipment brand website for STYL.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body suppressHydrationWarning>
        {children}
        <footer className="container py-3 text-center text-xs leading-5 text-[var(--muted)]">
          GeoLite data by <a href="https://www.maxmind.com/" className="underline underline-offset-2">MaxMind</a>
          {" · "}<a href="https://www.geonames.org/" className="underline underline-offset-2">GeoNames</a>
          {" · "}<Link href="/privacy" className="underline underline-offset-2">Privacy</Link>
        </footer>
        <Suspense fallback={null}><AnalyticsTracker /></Suspense>
      </body>
    </html>
  );
}
