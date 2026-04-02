import * as React from 'react';

import { filterSources, getSourceLabelCounts } from '../utils';
import type { Source } from '@/shared/api';

export function useSourceFilters({
  sources,
}: {
  sources: Array<Source>;
}) {
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
    hasFilters: search.trim().length > 0 || Boolean(activeLabel),
    labelCounts,
    search,
    setActiveLabel,
    setSearch,
    totalSourceCount: sources.length,
  };
}
