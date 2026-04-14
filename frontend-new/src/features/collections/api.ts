import * as React from 'react';
import {
  queryOptions,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import {
  classicSearchCollectionsReadableIdSearchClassicPostMutation,
  countCollectionsCountGetOptions,
  createCollectionsPostMutation,
  queryClient as defaultQueryClient,
  getCollectionsReadableIdGetOptions,
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

export function classicCollectionSearchMutationOptions(organizationId: string) {
  return classicSearchCollectionsReadableIdSearchClassicPostMutation(
    withOrganizationHeaders({ organizationId }),
  );
}

export function useClassicCollectionSearchMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => classicCollectionSearchMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useClassicCollectionSearchMutation() {
  const mutationOptions = useClassicCollectionSearchMutationOptions();

  return useMutation(mutationOptions);
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

type GetCollectionParams = NonNullable<
  Parameters<typeof getCollectionsReadableIdGetOptions>[0]
>;

type ReadableIdParams = {
  collectionId: string;
};

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

export function getCollectionQueryOptions(
  organizationId: string,
  { collectionId }: ReadableIdParams,
  queryClient = defaultQueryClient,
) {
  const params: GetCollectionParams = {
    path: {
      readable_id: collectionId,
    },
  };

  const listQueryOptions = listCollectionsQueryOptions(organizationId);

  return queryOptions({
    ...getCollectionsReadableIdGetOptions(
      withOrganizationHeaders({ organizationId }, params),
    ),
    initialData: () => {
      const collections = queryClient.getQueryData(listQueryOptions.queryKey);
      return collections?.find((collection) => collection.id === collectionId);
    },
    initialDataUpdatedAt: () =>
      queryClient.getQueryState(listQueryOptions.queryKey)?.dataUpdatedAt,
  });
}

export function useGetCollectionQueryOptions(params: ReadableIdParams) {
  const queryClient = useQueryClient();
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => getCollectionQueryOptions(currentOrganizationId, params, queryClient),
    [currentOrganizationId, params, queryClient],
  );
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

export function ensureCollection({
  collectionId,
  queryClient,
  organizationId,
}: {
  collectionId: string;
  queryClient: QueryClient;
  organizationId: string;
}) {
  return queryClient.ensureQueryData(
    getCollectionQueryOptions(organizationId, { collectionId }),
  );
}

export async function invalidateCollectionQueries(queryClient: QueryClient) {
  await queryClient.invalidateQueries({
    predicate: matchQueryKey({ tags: ['collections'] }),
  });
}
