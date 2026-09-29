"use client";

import { useParams } from "next/navigation";
import CatalogDetail from "@/components/CatalogDetail";

export default function ProductDetailPage() {
  const params = useParams<{ slug: string }>();
  return <CatalogDetail itemType="product" identifier={params?.slug} />;
}
