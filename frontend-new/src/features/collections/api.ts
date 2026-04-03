import * as React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import {
  countCollectionsCountGetOptions,
  createCollectionsPostMutation,
  listCollectionsGetOptions,
  matchQueryKey,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

type CollectionListParams = NonNullable<
  Parameters<typeof listCollectionsGetOptions>[0]
>;

type SearchParams = { search?: string };

export function createCollectionMutationOptions(organizationId: string) {
  return createCollectionsPostMutation(
    withOrganizationHeaders({ organizationId }),
  );
}

export function useCreateCollectionMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => createCollectionMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useCreateCollectionMutation() {
  const queryClient = useQueryClient();
  const mutationOptions = useCreateCollectionMutationOptions();

  return useMutation({
    ...mutationOptions,
    onSuccess: async () => {
      await invalidateCollectionQueries(queryClient);
    },
  });
}

export function listCollectionsQueryOptions(
  organizationId: string,
  { search }: SearchParams = {},
) {
  const params: CollectionListParams = {
    query: {
      limit: 100,
      skip: 0,
      search,
    },
  };
  return listCollectionsGetOptions(
    withOrganizationHeaders({ organizationId }, params),
  );
}

export function useListCollectionsQueryOptions(searchParams?: SearchParams) {
  const currentOrganizationId = useCurrentOrganizationId();

  return listCollectionsQueryOptions(currentOrganizationId, searchParams);
}

type CollectionCountParams = NonNullable<
  Parameters<typeof countCollectionsCountGetOptions>[0]
>;

export function collectionCountQueryOptions(
  organizationId: string,
  searchParams?: SearchParams,
) {
  const params: CollectionCountParams | undefined = searchParams?.search
    ? {
        query: {
          search: searchParams.search,
        },
      }
    : undefined;

  return countCollectionsCountGetOptions(
    withOrganizationHeaders({ organizationId }, params),
  );
}

export function useCollectionCountQueryOptions(searchParams?: SearchParams) {
  const currentOrganizationId = useCurrentOrganizationId();

  return collectionCountQueryOptions(currentOrganizationId, searchParams);
}

export function prefetchCollectionCount({
  queryClient,
  organizationId,
  search,
}: {
  queryClient: QueryClient;
  organizationId: string;
  search?: string;
}) {
  return queryClient.prefetchQuery(
    collectionCountQueryOptions(organizationId, { search }),
  );
}

export function ensureCollectionCount({
  queryClient,
  organizationId,
  search,
}: {
  queryClient: QueryClient;
  organizationId: string;
  search?: string;
}) {
  return queryClient.ensureQueryData(
    collectionCountQueryOptions(organizationId, { search }),
  );
}

export function ensureListCollections({
  queryClient,
  organizationId,
  search,
}: {
  queryClient: QueryClient;
  organizationId: string;
  search?: string;
}) {
  return queryClient.ensureQueryData(
    listCollectionsQueryOptions(organizationId, { search }),
  );
}

export async function invalidateCollectionQueries(queryClient: QueryClient) {
  await queryClient.invalidateQueries({
    predicate: matchQueryKey({ tags: ['collections'] }),
  });
}
