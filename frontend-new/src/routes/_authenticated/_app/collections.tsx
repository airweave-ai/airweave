import {
  CollectionsPage,
  collectionsSearchSchema,
} from '@/app/pages/collections';
import { ensureListCollections } from '@/features/collections';
import { createFileRoute } from '@tanstack/react-router';
import * as React from 'react';

export const Route = createFileRoute('/_authenticated/_app/collections')({
  component: RouteComponent,
  loaderDeps: ({ search }) => ({ search: search.search }),
  loader: ({ context, deps }) =>
    ensureListCollections({
      queryClient: context.queryClient,
      organizationId: context.currentOrganizationId,
      search: deps.search,
    }),
  staticData: {
    breadcrumb: 'Collections',
  },
  validateSearch: collectionsSearchSchema,
});

function RouteComponent() {
  const initialCollections = Route.useLoaderData();
  const search = Route.useSearch();
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
    <CollectionsPage
      initialCollections={initialCollections}
      search={search.search}
      onSearchChange={handleSearchChange}
    />
  );
}
