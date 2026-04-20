import * as React from 'react';
import {
  mutationOptions,
  useMutation,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query';
import {
  createApiKeyApiKeysPostMutation,
  matchQueryKey,
  queryClient as defaultQueryClient,
  readApiKeysApiKeysGetOptions,
  withOrganizationHeaders,
  deleteApiKeyApiKeysDeleteMutation,
  rotateApiKeyApiKeysIdRotatePostMutation,
} from '@/shared/api';
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

export function createApiKeyMutationOptions(
  organizationId: string,
  queryClient = defaultQueryClient,
) {
  return mutationOptions({
    ...createApiKeyApiKeysPostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    onSuccess: () => invalidateApiKeyQueries(queryClient),
  });
}

export function useCreateApiKeyMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();
  const queryClient = useQueryClient();

  return React.useMemo(
    () => createApiKeyMutationOptions(currentOrganizationId, queryClient),
    [currentOrganizationId],
  );
}

export function useCreateApiKeyMutation() {
  const mutationOptions = useCreateApiKeyMutationOptions();
  return useMutation(mutationOptions);
}

export function deleteApiKeyMutationOptions(
  organizationId: string,
  queryClient = defaultQueryClient,
) {
  return mutationOptions({
    ...deleteApiKeyApiKeysDeleteMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    onSuccess: () => invalidateApiKeyQueries(queryClient),
  });
}

export function useDeleteApiKeyMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();
  const queryClient = useQueryClient();

  return React.useMemo(
    () => deleteApiKeyMutationOptions(currentOrganizationId, queryClient),
    [currentOrganizationId],
  );
}

export function useDeleteApiKeyMutation() {
  const mutationOptions = useDeleteApiKeyMutationOptions();
  return useMutation(mutationOptions);
}

export function rotateApiKeyMutationOptions(
  organizationId: string,
  queryClient = defaultQueryClient,
) {
  return mutationOptions({
    ...rotateApiKeyApiKeysIdRotatePostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    onSuccess: () => invalidateApiKeyQueries(queryClient),
  });
}

export function useRotateApiKeyMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();
  const queryClient = useQueryClient();

  return React.useMemo(
    () => rotateApiKeyMutationOptions(currentOrganizationId, queryClient),
    [currentOrganizationId],
  );
}

export function useRotateApiKeyMutation() {
  const mutationOptions = useRotateApiKeyMutationOptions();
  return useMutation(mutationOptions);
}

export async function invalidateApiKeyQueries(queryClient: QueryClient) {
  await queryClient.invalidateQueries({
    predicate: matchQueryKey({ tags: ['api-keys'] }),
  });
}
