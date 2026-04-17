import * as React from 'react';
import type { QueryClient } from '@tanstack/react-query';
import { readApiKeysApiKeysGetOptions, withOrganizationHeaders } from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

export function listApiKeysQueryOptions(organizationId: string) {
  return readApiKeysApiKeysGetOptions(
    withOrganizationHeaders({ organizationId }),
  );
}

export function useListApiKeysQueryOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => listApiKeysQueryOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function ensureListApiKeys({
  queryClient,
  organizationId,
}: {
  queryClient: QueryClient;
  organizationId: string;
}) {
  return queryClient.ensureQueryData(listApiKeysQueryOptions(organizationId));
}
