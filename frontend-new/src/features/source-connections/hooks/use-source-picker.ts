import { useAvailableSources } from './use-available-sources';
import { useSourceFilters } from './use-source-filters';

export function useSourcePicker() {
  const availableSources = useAvailableSources();
  const sourceFilters = useSourceFilters({ sources: availableSources.sources });

  return {
    ...availableSources,
    ...sourceFilters,
  };
}
