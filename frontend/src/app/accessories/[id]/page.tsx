"use client";

import { useParams } from "next/navigation";
import CatalogDetail from "@/components/CatalogDetail";

export default function AccessoryDetailPage() {
  const params = useParams<{ id: string }>();
  return <CatalogDetail itemType="accessory" identifier={params?.id} />;
}
