import {
  getSourcesShortNameGetOptions,
  listSourcesGetOptions,
  queryClient as defaultQueryClient,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';
import { queryOptions, useQueryClient } from '@tanstack/react-query';

export function listSourcesQueryOptions(organizationId: string) {
  return listSourcesGetOptions(withOrganizationHeaders({ organizationId }));
}

export function useListSourcesQueryOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return listSourcesQueryOptions(currentOrganizationId);
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
