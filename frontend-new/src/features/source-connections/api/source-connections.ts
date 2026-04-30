import * as React from 'react';
import { mutationOptions, useMutation } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import {
  createSourceConnectionsPostMutation,
  getSourceConnectionsSourceConnectionIdGetOptions,
  listSourceConnectionsGetOptions,
  reinitiateOauthSourceConnectionsSourceConnectionIdReinitiateOauthPostMutation,
  verifyOauthSourceConnectionsSourceConnectionIdVerifyOauthPostMutation,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

export const sourceConnectionInvalidationTags = [
  'source-connections',
  'collections',
] as const;

export function createSourceConnectionMutationOptions(organizationId: string) {
  return mutationOptions({
    ...createSourceConnectionsPostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: false,
      invalidateTags: sourceConnectionInvalidationTags,
    },
  });
}

type GetSourceConnectionParams = NonNullable<
  Parameters<typeof getSourceConnectionsSourceConnectionIdGetOptions>[0]
>;

type SourceConnectionIdParams = {
  sourceConnectionId: string;
};

type ListSourceConnectionsParams = NonNullable<
  Parameters<typeof listSourceConnectionsGetOptions>[0]
>;

type ListCollectionSourceConnectionsParams = {
  collectionId?: string;
};

export function listSourceConnectionsQueryOptions(
  organizationId: string,
  { collectionId }: ListCollectionSourceConnectionsParams = {},
) {
  const params: ListSourceConnectionsParams = {
    query: {
      collection: collectionId,
      limit: 100,
      skip: 0,
    },
  };

  return listSourceConnectionsGetOptions(
    withOrganizationHeaders({ organizationId }, params),
  );
}

export function useListSourceConnectionsQueryOptions(
  params?: ListCollectionSourceConnectionsParams,
) {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => listSourceConnectionsQueryOptions(currentOrganizationId, params),
    [currentOrganizationId, params],
  );
}

export function ensureListSourceConnections({
  collectionId,
  queryClient,
  organizationId,
}: {
  collectionId?: string;
  queryClient: QueryClient;
  organizationId: string;
}) {
  return queryClient.ensureQueryData(
    listSourceConnectionsQueryOptions(organizationId, { collectionId }),
  );
}

function getSourceConnectionQueryOptions(
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

export function ensureSourceConnection({
  queryClient,
  organizationId,
  sourceConnectionId,
}: {
  queryClient: QueryClient;
  organizationId: string;
  sourceConnectionId: string;
}) {
  return queryClient.fetchQuery(
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
  return mutationOptions({
    ...reinitiateOauthSourceConnectionsSourceConnectionIdReinitiateOauthPostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      invalidateTags: sourceConnectionInvalidationTags,
    },
  });
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
  const options = useCreateSourceConnectionMutationOptions();
  return useMutation(options);
}
