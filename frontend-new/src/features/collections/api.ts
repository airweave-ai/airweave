import * as React from 'react';
import {
  mutationOptions,
  queryOptions,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import type { CollectionSearchRequest } from './lib/collection-search-request';
import {
  classicSearchCollectionsReadableIdSearchClassicPostOptions,
  countCollectionsCountGetOptions,
  createCollectionsPostMutation,
  queryClient as defaultQueryClient,
  getCollectionsReadableIdGetOptions,
  instantSearchCollectionsReadableIdSearchInstantPostOptions,
  listCollectionsGetOptions,
  subscribeSearchAgenticStreamOptions,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

const collectionInvalidationTags = ['collections'] as const;

type CollectionListParams = NonNullable<
  Parameters<typeof listCollectionsGetOptions>[0]
>;

type ClassicCollectionSearchParams = Extract<
  CollectionSearchRequest,
  { tier: 'classic' }
>;

type InstantCollectionSearchParams = Extract<
  CollectionSearchRequest,
  { tier: 'instant' }
>;

type AgenticCollectionSearchParams = Extract<
  CollectionSearchRequest,
  { tier: 'agentic' }
>;

type ClassicCollectionSearchQueryOptions = NonNullable<
  Parameters<
    typeof classicSearchCollectionsReadableIdSearchClassicPostOptions
  >[0]
>;

type InstantCollectionSearchQueryOptions = NonNullable<
  Parameters<
    typeof instantSearchCollectionsReadableIdSearchInstantPostOptions
  >[0]
>;

type AgenticCollectionSearchStreamQueryOptions = NonNullable<
  Parameters<typeof subscribeSearchAgenticStreamOptions>[0]
>;

type SearchParams = { search?: string };

const collectionSearchQueryDefaults = {
  refetchOnMount: false,
  refetchOnReconnect: false,
  refetchOnWindowFocus: false,
  retry: false,
  staleTime: 'static',
} as const;

export function createCollectionMutationOptions(organizationId: string) {
  return mutationOptions({
    ...createCollectionsPostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: false,
      invalidateTags: collectionInvalidationTags,
    },
  });
}

export function useCreateCollectionMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => createCollectionMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useCreateCollectionMutation() {
  const options = useCreateCollectionMutationOptions();
  return useMutation(options);
}

export function classicCollectionSearchQueryOptions(
  organizationId: string,
  { collectionId, filter, query }: ClassicCollectionSearchParams,
) {
  const params: ClassicCollectionSearchQueryOptions = {
    body: {
      ...(filter ? { filter } : {}),
      query,
    },
    path: {
      readable_id: collectionId,
    },
  };

  return queryOptions({
    ...classicSearchCollectionsReadableIdSearchClassicPostOptions(
      withOrganizationHeaders({ organizationId }, params),
    ),
    ...collectionSearchQueryDefaults,
  });
}

export function instantCollectionSearchQueryOptions(
  organizationId: string,
  {
    collectionId,
    filter,
    query,
    retrievalStrategy,
  }: InstantCollectionSearchParams,
) {
  const params: InstantCollectionSearchQueryOptions = {
    body: {
      ...(filter ? { filter } : {}),
      query,
      retrieval_strategy: retrievalStrategy,
    },
    path: {
      readable_id: collectionId,
    },
  };

  return queryOptions({
    ...instantSearchCollectionsReadableIdSearchInstantPostOptions(
      withOrganizationHeaders({ organizationId }, params),
    ),
    ...collectionSearchQueryDefaults,
  });
}

export function agenticCollectionSearchStreamQueryOptions(
  organizationId: string,
  { collectionId, filter, query, thinking }: AgenticCollectionSearchParams,
) {
  const params: AgenticCollectionSearchStreamQueryOptions = {
    body: {
      ...(filter ? { filter } : {}),
      query,
      thinking,
    },
    path: {
      readable_id: collectionId,
    },
  };

  return queryOptions({
    ...subscribeSearchAgenticStreamOptions(
      withOrganizationHeaders({ organizationId }, params),
    ),
    ...collectionSearchQueryDefaults,
  });
}

export function useClassicCollectionSearchQueryOptions(
  params: Pick<
    ClassicCollectionSearchParams,
    'collectionId' | 'filter' | 'query'
  > | null,
) {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () =>
      classicCollectionSearchQueryOptions(currentOrganizationId, {
        collectionId: params?.collectionId ?? '',
        filter: params?.filter,
        query: params?.query ?? '',
        tier: 'classic',
      }),
    [
      currentOrganizationId,
      params?.collectionId,
      params?.filter,
      params?.query,
    ],
  );
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
