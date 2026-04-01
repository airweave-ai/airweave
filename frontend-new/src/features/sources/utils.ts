import type { Source } from '@/shared/api';

export interface SourceLabelCount {
  count: number;
  label: string;
}

export function normalizeSourceSearch(search?: string) {
  return search?.trim().toLowerCase() || '';
}

export function getSourcePrimaryLabel(source: Source) {
  return source.labels?.find((label) => label.trim().length > 0) ?? null;
}

export function filterSources({
  activeLabel,
  search,
  sources,
}: {
  activeLabel?: string;
  search?: string;
  sources: Array<Source>;
}) {
  const normalizedSearch = normalizeSourceSearch(search);

  return [...sources]
    .filter((source) => {
      if (activeLabel && !source.labels?.includes(activeLabel)) {
        return false;
      }

      if (!normalizedSearch) {
        return true;
      }

      const searchableFields = [
        source.name,
        source.short_name,
        source.description ?? '',
        ...(source.labels ?? []),
      ];

      return searchableFields.some((value) =>
        value.toLowerCase().includes(normalizedSearch),
      );
    })
    .sort((left, right) => left.name.localeCompare(right.name));
}

export function getSourceLabelCounts(sources: Array<Source>) {
  const counts = new Map<string, number>();

  for (const source of sources) {
    for (const label of new Set(source.labels ?? [])) {
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
  }

  return [...counts.entries()]
    .map(([label, count]) => ({ count, label }))
    .sort((left, right) => left.label.localeCompare(right.label));
}
