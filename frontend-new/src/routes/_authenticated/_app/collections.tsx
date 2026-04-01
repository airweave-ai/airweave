import * as React from 'react';
import { createFileRoute, stripSearchParams } from '@tanstack/react-router';
import {
  CollectionsPage,
  collectionsSearchSchema,
} from '@/app/pages/collections';
import {
  ensureListCollections,
  normalizeSearch,
  prefetchCollectionCount,
} from '@/features/collections';

export const Route = createFileRoute('/_authenticated/_app/collections')({
  component: RouteComponent,
  loaderDeps: ({ search }) => ({ search: normalizeSearch(search.search) }),
  loader: async ({ context, deps }) => {
    const collectionListPromise = ensureListCollections({
      queryClient: context.queryClient,
      organizationId: context.currentOrganizationId,
      search: deps.search,
    });

    void prefetchCollectionCount({
      queryClient: context.queryClient,
      organizationId: context.currentOrganizationId,
    });

    await collectionListPromise;
  },
  staticData: {
    breadcrumb: 'Collections',
  },
  validateSearch: collectionsSearchSchema,
  search: {
    middlewares: [stripSearchParams({ search: '' })],
  },
});

function RouteComponent() {
  const { search } = Route.useSearch();
  const navigate = Route.useNavigate();
  const handleSearchChange = React.useCallback(
    (nextSearch: string | undefined) =>
      navigate({
        replace: true,
        search: (prev) => ({
          ...prev,
          search: nextSearch,
        }),
      }),
    [navigate],
  );

  return (
    <CollectionsPage search={search} onSearchChange={handleSearchChange} />
  );
}
