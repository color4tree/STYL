export function moveCatalogId(ids: readonly number[], id: number, position: number): number[] {
  const from = ids.indexOf(id);
  if (from < 0 || !Number.isInteger(position) || position < 0 || position >= ids.length) {
    throw new Error("Choose an existing item and a valid listing position.");
  }
  const next = [...ids];
  next.splice(from, 1);
  next.splice(position, 0, id);
  return next;
}

export function orderByIds<T extends { id: number }>(items: readonly T[], ids: readonly number[]): T[] {
  const positions = new Map(ids.map((id, index) => [id, index]));
  return [...items].sort((left, right) => (positions.get(left.id) ?? Infinity) - (positions.get(right.id) ?? Infinity));
}
