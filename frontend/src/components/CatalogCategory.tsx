export default function CatalogCategory({ item }: { item: { category: string; brand?: string | null } }) {
  const brand = item.brand?.trim();
  return (
    <span data-testid="catalog-category" className="inline-flex max-w-full flex-wrap gap-x-3">
      {brand ? <><span className="min-w-0 [overflow-wrap:anywhere]">{brand}</span>{" "}</> : null}
      <span className="min-w-0 [overflow-wrap:anywhere]">{item.category}</span>
    </span>
  );
}
