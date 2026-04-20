import * as React from 'react';
import { mutationOptions, useMutation } from '@tanstack/react-query';
import { sourceConnectionInvalidationTags } from './source-connections';
import type { SubscribeSyncJobStateStreamOptions } from '@/shared/api';
import {
  cancelJobSourceConnectionsSourceConnectionIdJobsJobIdCancelPostMutation,
  getSourceConnectionJobsSourceConnectionsSourceConnectionIdJobsGetOptions,
  runSourceConnectionsSourceConnectionIdRunPostMutation,
  subscribeSyncJobStateStreamOptions,
  withOrganizationHeaders,
} from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

type SourceConnectionIdParams = {
  sourceConnectionId: string;
};

type SourceConnectionJobsParams = SourceConnectionIdParams & {
  limit?: number;
};

type SyncJobIdParams = {
  jobId: string;
};

type GetSourceConnectionJobsParams = NonNullable<
  Parameters<
    typeof getSourceConnectionJobsSourceConnectionsSourceConnectionIdJobsGetOptions
  >[0]
>;

export function getSourceConnectionJobsQueryOptions(
  organizationId: string,
  { limit, sourceConnectionId }: SourceConnectionJobsParams,
) {
  const params: GetSourceConnectionJobsParams = {
    path: {
      source_connection_id: sourceConnectionId,
    },
    ...(limit === undefined ? {} : { query: { limit } }),
  };

  return getSourceConnectionJobsSourceConnectionsSourceConnectionIdJobsGetOptions(
    withOrganizationHeaders({ organizationId }, params),
  );
}

export function useGetSourceConnectionJobsQueryOptions(
  params: SourceConnectionJobsParams,
) {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => getSourceConnectionJobsQueryOptions(currentOrganizationId, params),
    [currentOrganizationId, params],
  );
}

export function getSyncJobStateStreamQueryOptions(
  organizationId: string,
  { jobId }: SyncJobIdParams,
) {
  const params: SubscribeSyncJobStateStreamOptions = {
    path: {
      job_id: jobId,
    },
  };

  return subscribeSyncJobStateStreamOptions(
    withOrganizationHeaders({ organizationId }, params),
  );
}

export function useGetSyncJobStateStreamQueryOptions(params: SyncJobIdParams) {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => getSyncJobStateStreamQueryOptions(currentOrganizationId, params),
    [currentOrganizationId, params],
  );
}

export function runSourceConnectionSyncMutationOptions(organizationId: string) {
  return mutationOptions({
    ...runSourceConnectionsSourceConnectionIdRunPostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      invalidateTags: sourceConnectionInvalidationTags,
    },
  });
}

export function useRunSourceConnectionSyncMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => runSourceConnectionSyncMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useRunSourceConnectionSyncMutation() {
  const options = useRunSourceConnectionSyncMutationOptions();
  return useMutation(options);
}

export function cancelSourceConnectionSyncJobMutationOptions(
  organizationId: string,
) {
  return mutationOptions({
    ...cancelJobSourceConnectionsSourceConnectionIdJobsJobIdCancelPostMutation(
      withOrganizationHeaders({ organizationId }),
    ),
    meta: {
      invalidateTags: sourceConnectionInvalidationTags,
    },
  });
}

export function useCancelSourceConnectionSyncJobMutationOptions() {
  const currentOrganizationId = useCurrentOrganizationId();

  return React.useMemo(
    () => cancelSourceConnectionSyncJobMutationOptions(currentOrganizationId),
    [currentOrganizationId],
  );
}

export function useCancelSourceConnectionSyncJobMutation() {
  const options = useCancelSourceConnectionSyncJobMutationOptions();
  return useMutation(options);
}
