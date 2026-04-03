import {
  listSourcesGetOptions,
  getSourcesShortNameGetOptions,
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

type GetSourceParams = NonNullable<
  Parameters<typeof getSourcesShortNameGetOptions>[0]
>;

type ShortNameParams = {
  sourceShortName: string;
};

export function getSourceQueryOptions(
  organizationId: string,
  { sourceShortName }: ShortNameParams,
) {
  const params: GetSourceParams = {
    path: {
      short_name: sourceShortName,
    },
  };

  return getSourcesShortNameGetOptions(
    withOrganizationHeaders({ organizationId }, params),
  );
}

export function useGetSourceQueryOptions(params: ShortNameParams) {
  const currentOrganizationId = useCurrentOrganizationId();

  return getSourceQueryOptions(currentOrganizationId, params);
}
