import * as React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import {
  createSourceConnectionsPostMutation,
  getSourceConnectionsSourceConnectionIdGetOptions,
  matchQueryKey,
  reinitiateOauthSourceConnectionsSourceConnectionIdReinitiateOauthPostMutation,
  verifyOauthSourceConnectionsSourceConnectionIdVerifyOauthPostMutation,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

export function createSourceConnectionMutationOptions(organizationId: string) {
  return createSourceConnectionsPostMutation(
    withOrganizationHeaders({ organizationId }),
  );
}

type GetSourceConnectionParams = NonNullable<
  Parameters<typeof getSourceConnectionsSourceConnectionIdGetOptions>[0]
>;

type SourceConnectionIdParams = {
  sourceConnectionId: string;
};

export function getSourceConnectionQueryOptions(
  organizationId: string,
  { sourceConnectionId }: SourceConnectionIdParams,
) {
  const params: GetSourceConnectionParams = {
    path: {
      source_connection_id: sourceConnectionId,
    },
  };

  return getSourceConnectionsSourceConnectionIdGetOptions(
    withOrganizationHeaders({ organizationId }, params),
  );
}

export function useGetSourceConnectionQueryOptions(
  params: SourceConnectionIdParams,
) {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => getSourceConnectionQueryOptions(currentOrganizationId, params),
    [currentOrganizationId, params],
  );
}

export function prefetchSourceConnection({
  queryClient,
  organizationId,
  sourceConnectionId,
}: {
  queryClient: QueryClient;
  organizationId: string;
  sourceConnectionId: string;
}) {
  return queryClient.prefetchQuery(
    getSourceConnectionQueryOptions(organizationId, { sourceConnectionId }),
  );
}

export function verifySourceConnectionOAuthMutationOptions(
  organizationId: string,
) {
  return verifyOauthSourceConnectionsSourceConnectionIdVerifyOauthPostMutation(
    withOrganizationHeaders({ organizationId }),
  );
}

export function useVerifySourceConnectionOAuthMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => verifySourceConnectionOAuthMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function reinitiateSourceConnectionOAuthMutationOptions(
  organizationId: string,
) {
  return reinitiateOauthSourceConnectionsSourceConnectionIdReinitiateOauthPostMutation(
    withOrganizationHeaders({ organizationId }),
  );
}

export function useReinitiateSourceConnectionOAuthMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => reinitiateSourceConnectionOAuthMutationOptions(currentOrganizationId),
    [currentOrganizationId],
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
