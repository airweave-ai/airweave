import { queryOptions, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import {
  queryClient as defaultQueryClient,
  getSourcesShortNameGetOptions,
  listSourcesGetOptions,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

export function listSourcesQueryOptions(organizationId: string) {
  return listSourcesGetOptions(withOrganizationHeaders({ organizationId }));
}

export function useListSourcesQueryOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return listSourcesQueryOptions(currentOrganizationId);
}

export function prefetchSources({
  queryClient,
  organizationId,
}: {
  queryClient: QueryClient;
  organizationId: string;
}) {
  return queryClient.prefetchQuery(listSourcesQueryOptions(organizationId));
}

type GetSourceParams = NonNullable<
  Parameters<typeof getSourcesShortNameGetOptions>[0]
>;

type ShortNameParams = {
  sourceShortName: string;
};

export function getSourceQueryOptions(
  organizationId: string,
  { sourceShortName }: ShortNameParams,
  queryClient = defaultQueryClient,
) {
  const params: GetSourceParams = {
    path: {
      short_name: sourceShortName,
    },
  };

  const listQueryOptions = listSourcesQueryOptions(organizationId);

  return queryOptions({
    ...getSourcesShortNameGetOptions(
      withOrganizationHeaders({ organizationId }, params),
    ),
    initialData: () => {
      const sources = queryClient.getQueryData(listQueryOptions.queryKey);
      return sources?.find((source) => source.short_name === sourceShortName);
    },
    initialDataUpdatedAt: () =>
      queryClient.getQueryState(listQueryOptions.queryKey)?.dataUpdatedAt,
  });
}

export function useGetSourceQueryOptions(params: ShortNameParams) {
  const queryClient = useQueryClient();
  const currentOrganizationId = useCurrentOrganizationId();

  return getSourceQueryOptions(currentOrganizationId, params, queryClient);
}

export function ensureSource({
  queryClient,
  organizationId,
  sourceShortName,
}: {
  queryClient: QueryClient;
  organizationId: string;
  sourceShortName: string;
}) {
  return queryClient.ensureQueryData(
    getSourceQueryOptions(organizationId, { sourceShortName }, queryClient),
  );
}
