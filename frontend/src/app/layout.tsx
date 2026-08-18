import type { Metadata } from "next";
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
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
