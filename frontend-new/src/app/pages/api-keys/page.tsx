import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
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
  useListApiKeysQueryOptions,
} from '@/features/api-keys';
import { ErrorState } from '@/shared/components/error-state';
import { LoadingState } from '@/shared/components/loading-state';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';

function normalizeApiKeySearch(search: string | undefined) {
  const normalizedSearch = search?.trim().toLowerCase();

  return normalizedSearch || undefined;
}

export function ApiKeysPage() {
  const [search, setSearch] = React.useState<string | undefined>(undefined);
  const deferredSearch = React.useDeferredValue(search);
  const handleCreateApiKey = React.useCallback(() => {}, []);
  const apiKeysQueryOptions = useListApiKeysQueryOptions();
  const {
    data: apiKeys,
    error,
    isFetching,
    refetch,
  } = useQuery(apiKeysQueryOptions);
  const normalizedSearch = normalizeApiKeySearch(deferredSearch);
  const filteredApiKeys = React.useMemo(() => {
    if (!apiKeys) {
      return [];
    }

    if (!normalizedSearch) {
      return apiKeys;
    }

    return apiKeys.filter((apiKey) => {
      const searchableText = [
        apiKey.id,
        apiKey.decrypted_key,
        apiKey.created_by_email,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();

      return searchableText.includes(normalizedSearch);
    });
  }, [apiKeys, normalizedSearch]);

  const emptyState = normalizedSearch ? (
    <ApiKeysNoSearchResultsState
      search={normalizedSearch}
      onClearSearch={() => setSearch(undefined)}
    />
  ) : (
    <ApiKeysEmptyState onCreateApiKey={handleCreateApiKey} />
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
        badge={
          !error ? (
            <Badge
              variant="secondary"
              className="text-[0.625rem] text-muted-foreground"
            >
              {apiKeys?.length ?? 0}
            </Badge>
          ) : null
        }
        actions={
          <Button onClick={handleCreateApiKey} type="button">
            Create API Key
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
