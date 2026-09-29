"use client";

import { useLayoutEffect } from "react";
import { useSearchParams } from "next/navigation";
import { catalogView, type CatalogView } from "@/lib/publicCatalog";

export default function CatalogViewSync({ onChange }: { onChange: (view: CatalogView) => void }) {
  const params = useSearchParams();
  const view = catalogView(params.get("catalog"));
  useLayoutEffect(() => { onChange(view); }, [view, onChange]);
  return null;
}
