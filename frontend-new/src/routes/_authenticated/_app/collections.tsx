import * as React from 'react';
import { createFileRoute, stripSearchParams } from '@tanstack/react-router';
import type { ConnectSourceStep } from '@/features/source-connections';
import {
  CollectionsPage,
  collectionsSearchSchema,
} from '@/app/pages/collections';
import {
  ensureListCollections,
  normalizeCollectionSearch,
  prefetchCollectionCount,
} from '@/features/collections';

export const Route = createFileRoute('/_authenticated/_app/collections')({
  component: RouteComponent,
  loaderDeps: ({ search }) => ({
    search: normalizeCollectionSearch(search.search),
  }),
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
  const { connectSource, search } = Route.useSearch();
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

  const handleConnectSourceChange = React.useCallback(
    (
      nextConnectSource: ConnectSourceStep | undefined,
      options?: { replace?: boolean },
    ) =>
      navigate({
        replace: options?.replace,
        search: (prev) => ({
          ...prev,
          connectSource: nextConnectSource,
        }),
      }),
    [navigate],
  );

  return (
    <CollectionsPage
      connectSource={connectSource}
      search={search}
      onConnectSourceChange={handleConnectSourceChange}
      onSearchChange={handleSearchChange}
    />
  );
}
