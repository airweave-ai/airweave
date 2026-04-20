import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { IconPlus } from '@tabler/icons-react';
import { Link } from '@tanstack/react-router';
import {
  ListPage,
  ListPageHeader,
  ListPageSearch,
  ListPageState,
} from '@/app/pages/components';
import {
  ApiKeysEmptyState,
  ApiKeysNoSearchResultsState,
  ApiKeysTable,
  useFilteredApiKeys,
  useListApiKeysQueryOptions,
} from '@/features/api-keys';
import { ErrorState } from '@/shared/components/error-state';
import { LoadingState } from '@/shared/components/loading-state';
import { normalizeSearchQuery } from '@/shared/search/normalize-search-query';
import { Button } from '@/shared/ui/button';
import { CountBadge } from '@/shared/components/count-badge';

export function ApiKeysPage() {
  const [search, setSearch] = React.useState<string | undefined>(undefined);
  const deferredSearch = React.useDeferredValue(search);
  const apiKeysQueryOptions = useListApiKeysQueryOptions();
  const {
    data: apiKeys,
    error,
    isFetching,
    refetch,
  } = useQuery(apiKeysQueryOptions);
  const normalizedSearch = normalizeSearchQuery(deferredSearch);
  const filteredApiKeys = useFilteredApiKeys(apiKeys, normalizedSearch);

  const emptyState = normalizedSearch ? (
    <ApiKeysNoSearchResultsState
      search={normalizedSearch}
      onClearSearch={() => setSearch(undefined)}
    />
  ) : (
    <ApiKeysEmptyState
      action={
        <Button asChild variant="outline">
          <Link to="/api-keys/create">
            <IconPlus />
            Create API Key
          </Link>
        </Button>
      }
    />
  );

  const stateBody = error ? (
    <ErrorState
      title="We couldn't load API keys"
      description="There was a problem loading the API key list for this organization."
      onRetry={() => {
        void refetch();
      }}
      retryLabel="Reload API keys"
    />
  ) : !apiKeys ? (
    <LoadingState title="Loading API keys..." />
  ) : filteredApiKeys.length === 0 ? (
    emptyState
  ) : null;

  return (
    <ListPage>
      <ListPageHeader
        title="API Keys"
        badge={!error ? <CountBadge>{apiKeys?.length ?? 0}</CountBadge> : null}
        actions={
          <Button asChild>
            <Link to="/api-keys/create">
              <IconPlus />
              Create API Key
            </Link>
          </Button>
        }
      />

      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <ListPageSearch
          value={search}
          onChange={setSearch}
          placeholder="Search Keys..."
          isFetching={isFetching}
          loadingLabel="Loading API keys"
        />

        {stateBody ? (
          <ListPageState>{stateBody}</ListPageState>
        ) : (
          <ApiKeysTable apiKeys={filteredApiKeys} className="min-h-0" />
        )}
      </div>
    </ListPage>
  );
}
