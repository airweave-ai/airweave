import * as React from 'react';

import type { Source } from '@/shared/api';
import { normalizeSearchQuery } from '@/shared/search/normalize-search-query';

export function useSourceFilters({ sources }: { sources: Array<Source> }) {
  const [search, setSearch] = React.useState('');
  const [activeLabel, setActiveLabel] = React.useState<string | undefined>();

  const filteredSources = React.useMemo(
    () => filterSources({ activeLabel, search, sources }),
    [activeLabel, search, sources],
  );

  const labelCounts = React.useMemo(
    () => getSourceLabelCounts(sources),
    [sources],
  );

  const clearFilters = React.useCallback(() => {
    setSearch('');
    setActiveLabel(undefined);
  }, []);

  return {
    activeLabel,
    clearFilters,
    filteredSourceCount: filteredSources.length,
    filteredSources,
    labelCounts,
    search,
    setActiveLabel,
    setSearch,
    totalSourceCount: sources.length,
  };
}

function filterSources({
  activeLabel,
  search,
  sources,
}: {
  activeLabel?: string;
  search?: string;
  sources: Array<Source>;
}) {
  const normalizedSearch = normalizeSearchQuery(search)?.toLowerCase() || '';

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

function getSourceLabelCounts(sources: Array<Source>) {
  const counts = new Map<string, number>();

  for (const source of sources) {
    for (const label of new Set(source.labels ?? [])) {
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
  }

  return [...counts.entries()]
    .filter(([_, count]) => count > 1)
    .map(([label, count]) => ({ count, label }))
    .sort((left, right) => left.label.localeCompare(right.label));
}
