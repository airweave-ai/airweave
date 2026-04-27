import * as React from 'react';
import {
  mutationOptions,
  queryOptions,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import {
  connectAuthProviderAuthProvidersPostMutation,
  queryClient as defaultQueryClient,
  getAuthProviderAuthProvidersDetailShortNameGetOptions,
  getAuthProviderConnectionAuthProvidersConnectionsReadableIdGetOptions,
  listAuthProviderConnectionsAuthProvidersConnectionsGetOptions,
  listAuthProvidersAuthProvidersListGetOptions,
  updateAuthProviderConnectionAuthProvidersReadableIdPutMutation,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

const authProviderInvalidationTags = ['auth-providers'] as const;

type ShortNameParams = {
  shortName: string;
};

type ReadableIdParams = {
  readableId: string;
};

type GetAuthProviderDetailParams = NonNullable<
  Parameters<typeof getAuthProviderAuthProvidersDetailShortNameGetOptions>[0]
>;

type GetAuthProviderConnectionParams = NonNullable<
  Parameters<
    typeof getAuthProviderConnectionAuthProvidersConnectionsReadableIdGetOptions
  >[0]
>;

export function listAuthProvidersQueryOptions(organizationId: string) {
  return listAuthProvidersAuthProvidersListGetOptions(
    withOrganizationHeaders({ organizationId }),
  );
}

export function useListAuthProvidersQueryOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => listAuthProvidersQueryOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function ensureListAuthProviders({
  queryClient,
  organizationId,
}: {
  queryClient: QueryClient;
  organizationId: string;
}) {
  return queryClient.ensureQueryData(listAuthProvidersQueryOptions(organizationId));
}

export function getAuthProviderDetailQueryOptions(
  organizationId: string,
  { shortName }: ShortNameParams,
  queryClient = defaultQueryClient,
) {
  const params: GetAuthProviderDetailParams = {
    path: {
      short_name: shortName,
    },
  };
  const listQueryOptions = listAuthProvidersQueryOptions(organizationId);

  return queryOptions({
    ...getAuthProviderAuthProvidersDetailShortNameGetOptions(
      withOrganizationHeaders({ organizationId }, params),
    ),
    initialData: () => {
      const authProviders = queryClient.getQueryData(listQueryOptions.queryKey);

      return authProviders?.find((provider) => provider.short_name === shortName);
    },
    initialDataUpdatedAt: () =>
      queryClient.getQueryState(listQueryOptions.queryKey)?.dataUpdatedAt,
  });
}

export function useGetAuthProviderDetailQueryOptions(params: ShortNameParams) {
  const queryClient = useQueryClient();
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () =>
      getAuthProviderDetailQueryOptions(
        currentOrganizationId,
        params,
        queryClient,
      ),
    [currentOrganizationId, params, queryClient],
  );
}

export function prefetchAuthProviderDetail({
  organizationId,
  queryClient,
  shortName,
}: {
  organizationId: string;
  queryClient: QueryClient;
  shortName: string;
}) {
  return queryClient.prefetchQuery(
    getAuthProviderDetailQueryOptions(
      organizationId,
      { shortName },
      queryClient,
    ),
  );
}

export function listAuthProviderConnectionsQueryOptions(organizationId: string) {
  return listAuthProviderConnectionsAuthProvidersConnectionsGetOptions(
    withOrganizationHeaders({ organizationId }),
  );
}

export function useListAuthProviderConnectionsQueryOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => listAuthProviderConnectionsQueryOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function ensureListAuthProviderConnections({
  queryClient,
  organizationId,
}: {
  queryClient: QueryClient;
  organizationId: string;
}) {
  return queryClient.ensureQueryData(
    listAuthProviderConnectionsQueryOptions(organizationId),
  );
}

export function getAuthProviderConnectionQueryOptions(
  organizationId: string,
  { readableId }: ReadableIdParams,
  queryClient = defaultQueryClient,
) {
  const params: GetAuthProviderConnectionParams = {
    path: {
      readable_id: readableId,
    },
  };
  const listQueryOptions = listAuthProviderConnectionsQueryOptions(organizationId);

  return queryOptions({
    ...getAuthProviderConnectionAuthProvidersConnectionsReadableIdGetOptions(
      withOrganizationHeaders({ organizationId }, params),
    ),
    initialData: () => {
      const connections = queryClient.getQueryData(listQueryOptions.queryKey);

      return connections?.find(
        (connection) => connection.readable_id === readableId,
      );
    },
    initialDataUpdatedAt: () =>
      queryClient.getQueryState(listQueryOptions.queryKey)?.dataUpdatedAt,
  });
}

export function useGetAuthProviderConnectionQueryOptions(
  params: ReadableIdParams,
) {
  const queryClient = useQueryClient();
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () =>
      getAuthProviderConnectionQueryOptions(
        currentOrganizationId,
        params,
        queryClient,
      ),
    [currentOrganizationId, params, queryClient],
  );
}

export function prefetchAuthProviderConnection({
  organizationId,
  queryClient,
  readableId,
}: {
  organizationId: string;
  queryClient: QueryClient;
  readableId: string;
}) {
  return queryClient.prefetchQuery(
    getAuthProviderConnectionQueryOptions(
      organizationId,
      { readableId },
      queryClient,
    ),
  );
}

export function connectAuthProviderMutationOptions(organizationId: string) {
  return mutationOptions({
    ...connectAuthProviderAuthProvidersPostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: false,
      invalidateTags: authProviderInvalidationTags,
    },
  });
}

export function useConnectAuthProviderMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => connectAuthProviderMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useConnectAuthProviderMutation() {
  const options = useConnectAuthProviderMutationOptions();

  return useMutation(options);
}

export function updateAuthProviderConnectionMutationOptions(
  organizationId: string,
) {
  return mutationOptions({
    ...updateAuthProviderConnectionAuthProvidersReadableIdPutMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: false,
      invalidateTags: authProviderInvalidationTags,
    },
  });
}

export function useUpdateAuthProviderConnectionMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => updateAuthProviderConnectionMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useUpdateAuthProviderConnectionMutation() {
  const options = useUpdateAuthProviderConnectionMutationOptions();

  return useMutation(options);
}
