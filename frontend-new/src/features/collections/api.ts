import type { RequestContext } from '@/shared/api';
import {
  countCollectionsCountGetOptions,
  listCollectionsGetOptions,
  useCurrentRequestContext,
  withRequestContext,
} from '@/shared/api';
import { getCurrentRequestContext } from '@/shared/api/request-context';
import type { QueryClient } from '@tanstack/react-query';

type CollectionListParams = NonNullable<
  Parameters<typeof listCollectionsGetOptions>[0]
>;

type SearchParams = { search?: string };

export function listCollectionsQueryOptions(
  requestContext: RequestContext,
  { search }: SearchParams = {},
) {
  const params: CollectionListParams = {
    query: {
      limit: 100,
      skip: 0,
      search,
    },
  };
  return listCollectionsGetOptions(withRequestContext(requestContext, params));
}

export function useListCollectionsQueryOptions(searchParams?: SearchParams) {
  const requestContext = useCurrentRequestContext();

  return listCollectionsQueryOptions(requestContext, searchParams);
}

type CollectionCountParams = NonNullable<
  Parameters<typeof countCollectionsCountGetOptions>[0]
>;

function collectionCountQueryOptions(
  requestContext: RequestContext,
  searchParams?: SearchParams,
) {
  const params: CollectionCountParams = {
    query: searchParams,
  };

  return countCollectionsCountGetOptions(
    withRequestContext(requestContext, params),
  );
}

export function useCollectionCountQueryOptions(searchParams?: SearchParams) {
  const requestContext = useCurrentRequestContext();

  return collectionCountQueryOptions(requestContext, searchParams);
}

export function ensureListCollections({
  queryClient,
}: {
  queryClient: QueryClient;
}) {
  return queryClient.ensureQueryData(
    listCollectionsQueryOptions(getCurrentRequestContext()),
  );
}
