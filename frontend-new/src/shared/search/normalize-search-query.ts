export function normalizeSearchQuery(search?: string) {
  return search?.trim() || undefined;
}
