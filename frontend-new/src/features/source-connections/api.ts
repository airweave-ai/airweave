import * as React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import {
  createSourceConnectionsPostMutation,
  matchQueryKey,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

export function createSourceConnectionMutationOptions(organizationId: string) {
  return createSourceConnectionsPostMutation(
    withOrganizationHeaders({ organizationId }),
  );
}

export function useCreateSourceConnectionMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => createSourceConnectionMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useCreateSourceConnectionMutation() {
  const queryClient = useQueryClient();
  const mutationOptions = useCreateSourceConnectionMutationOptions();

  return useMutation({
    ...mutationOptions,
    onSuccess: async () => {
      await invalidateSourceConnectionQueries(queryClient);
    },
  });
}

export async function invalidateSourceConnectionQueries(
  queryClient: QueryClient,
) {
  await queryClient.invalidateQueries({
    predicate: matchQueryKey({ tags: ['source-connections', 'collections'] }),
  });
}
