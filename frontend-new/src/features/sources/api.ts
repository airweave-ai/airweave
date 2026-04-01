import { listSourcesGetOptions, withOrganizationHeaders } from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

export function listSourcesQueryOptions(organizationId: string) {
  return listSourcesGetOptions(withOrganizationHeaders({ organizationId }));
}

export function useListSourcesQueryOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return listSourcesQueryOptions(currentOrganizationId);
}
