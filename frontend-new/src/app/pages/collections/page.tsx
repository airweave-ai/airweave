import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { getRouteApi } from '@tanstack/react-router';
import type { CollectionsSearch } from './search';
import {
  ListPage,
  ListPageHeader,
  ListPageSearch,
  ListPageState,
} from '@/app/pages/components';
import { CreateCollectionButton } from '@/app/components/create-collection-button';
import {
  CollectionCountBadge,
  CollectionFilterButtonGroup,
  CollectionsEmptyState,
  CollectionsNoSearchResultsState,
  CollectionsTable,
  useListCollectionsQueryOptions,
} from '@/features/collections';
import { ErrorState } from '@/shared/components/error-state';
import { LoadingState } from '@/shared/components/loading-state';
import { normalizeSearchQuery } from '@/shared/search/normalize-search-query';

type CollectionsPageProps = CollectionsSearch & {
  onSearchChange: (search: string | undefined) => void;
};

const collectionsPageFilters = [
  'Health',
  'Connections',
  'Status',
  'Last Sync',
] as const;

const routeApi = getRouteApi('/_authenticated/_app/collections/');

export function CollectionsPage({
  search,
  onSearchChange,
}: CollectionsPageProps) {
  const navigate = routeApi.useNavigate();
  const normalizedSearch = normalizeSearchQuery(search);
  const collectionsQueryOptions = useListCollectionsQueryOptions({
    search: normalizedSearch,
  });
  const {
    data: collections,
    error,
    isFetching,
    refetch,
  } = useQuery({
    ...collectionsQueryOptions,
    placeholderData: keepPreviousData,
  });

  const emptyState = normalizedSearch ? (
    <CollectionsNoSearchResultsState
      search={normalizedSearch}
      onClearSearch={() => onSearchChange(undefined)}
    />
  ) : (
    <CollectionsEmptyState
      onCreateCollection={() =>
        navigate({
          to: '.',
          search: (prev) => ({
            ...prev,
            dialog: { type: 'create-collection' },
          }),
        })
      }
    />
  );

  const stateBody = error ? (
    <ErrorState
      title="We couldn't load collections"
      description="There was a problem loading the collections list for this organization."
      onRetry={() => {
        void refetch();
      }}
      retryLabel="Reload collections"
    />
  ) : !collections ? (
    <LoadingState title="Loading collections..." />
  ) : collections.length === 0 ? (
    emptyState
  ) : null;

  return (
    <ListPage>
      <ListPageHeader
        title="Collections"
        badge={<CollectionCountBadge />}
        actions={
          <>
            {collectionsPageFilters.map((filter) => (
              <CollectionFilterButtonGroup key={filter} label={filter} />
            ))}

            <CreateCollectionButton data-icon="inline-start">
              <Plus />
              Create Collection
            </CreateCollectionButton>
          </>
        }
      />

      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <ListPageSearch
          value={search}
          onChange={onSearchChange}
          placeholder="Search collections by name or ID..."
          isFetching={isFetching}
          loadingLabel="Loading collections"
        />

        {stateBody ? (
          <ListPageState>{stateBody}</ListPageState>
        ) : (
          <CollectionsTable collections={collections!} className="min-h-0" />
        )}
      </div>
    </ListPage>
  );
}
