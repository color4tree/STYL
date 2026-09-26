import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Accessories | STYL",
  description: "Attachments and accessories for racks, cable machines, and your training space.",
};

export default function AccessoriesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
