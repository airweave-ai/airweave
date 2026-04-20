import * as React from 'react';
import { filterApiKeys } from '../lib/api-key-search';
import type { ApiKey } from '@/shared/api';

export function useFilteredApiKeys(
  apiKeys: Array<ApiKey> | undefined,
  search?: string,
) {
  return React.useMemo(() => {
    if (!apiKeys) {
      return [];
    }

    return filterApiKeys(apiKeys, search);
  }, [apiKeys, search]);
}
