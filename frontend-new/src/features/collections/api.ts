import type { RequestContext } from '@/shared/api';
import {
  countCollectionsCountGetOptions,
  listCollectionsGetOptions,
  useCurrentRequestContext,
  withRequestContext,
} from '@/shared/api';

type CollectionListParams = NonNullable<
  Parameters<typeof listCollectionsGetOptions>[0]
>;

type SearchParams = { search?: string };

export function listCollectionsQueryOptions(
  { search }: SearchParams = {},
  requestContext: RequestContext,
) {
  const params: CollectionListParams = {
    query: {
      limit: 100,
      skip: 0,
      search,
    },
  };
  return listCollectionsGetOptions(withRequestContext(params, requestContext));
}

export function useListCollectionsQueryOptions(searchParams?: SearchParams) {
  const requestContext = useCurrentRequestContext();

  return listCollectionsQueryOptions(searchParams, requestContext);
}

type CollectionCountParams = NonNullable<
  Parameters<typeof countCollectionsCountGetOptions>[0]
>;

export function useCollectionCountQueryOptions({ search }: SearchParams = {}) {
  const requestContext = useCurrentRequestContext();
  const collectionCountParams: CollectionCountParams = {
    query: {
      search,
    },
  };
  return countCollectionsCountGetOptions(
    withRequestContext(collectionCountParams, requestContext),
  );
}
