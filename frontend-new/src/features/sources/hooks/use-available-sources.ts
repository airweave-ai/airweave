import { useQuery } from '@tanstack/react-query';

import { useListSourcesQueryOptions } from '../api';

export function useAvailableSources() {
  const sourcesQueryOptions = useListSourcesQueryOptions();
  const {
    data: sources = [],
    error,
    isLoading,
    refetch,
  } = useQuery(sourcesQueryOptions);

  return {
    error,
    isLoading,
    refetch,
    sources,
  };
}
