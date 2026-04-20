import * as React from 'react';
import { mutationOptions, useMutation } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import {
  createApiKeyApiKeysPostMutation,
  deleteApiKeyApiKeysDeleteMutation,
  readApiKeysApiKeysGetOptions,
  rotateApiKeyApiKeysIdRotatePostMutation,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

const apiKeyInvalidationTags = ['api-keys'] as const;

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

export function createApiKeyMutationOptions(organizationId: string) {
  return mutationOptions({
    ...createApiKeyApiKeysPostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: 'Could not create API key.',
      invalidateTags: apiKeyInvalidationTags,
    },
  });
}

export function useCreateApiKeyMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => createApiKeyMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useCreateApiKeyMutation() {
  const options = useCreateApiKeyMutationOptions();
  return useMutation(options);
}

export function deleteApiKeyMutationOptions(organizationId: string) {
  return mutationOptions({
    ...deleteApiKeyApiKeysDeleteMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: 'Could not delete API key.',
      invalidateTags: apiKeyInvalidationTags,
    },
  });
}

export function useDeleteApiKeyMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => deleteApiKeyMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useDeleteApiKeyMutation() {
  const options = useDeleteApiKeyMutationOptions();
  return useMutation(options);
}

export function rotateApiKeyMutationOptions(organizationId: string) {
  return mutationOptions({
    ...rotateApiKeyApiKeysIdRotatePostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      errorToast: 'Could not rotate API key.',
      invalidateTags: apiKeyInvalidationTags,
    },
  });
}

export function useRotateApiKeyMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => rotateApiKeyMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useRotateApiKeyMutation() {
  const options = useRotateApiKeyMutationOptions();
  return useMutation(options);
}
