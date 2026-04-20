import * as React from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { SourceConnection } from '@/shared/api';
import { invalidateQueriesByTags } from '@/shared/api';
import {
  isActiveSyncJobStatus,
  sourceConnectionInvalidationTags,
  useGetSyncJobStateStreamQueryOptions,
  useRunSourceConnectionSyncMutation,
} from '@/features/source-connections';

type UseSourceConnectionSyncStateParams = {
  sourceConnection: SourceConnection | undefined;
  sourceConnectionId: string | undefined;
};

export function useSourceConnectionSyncState({
  sourceConnection,
  sourceConnectionId,
}: UseSourceConnectionSyncStateParams) {
  const queryClient = useQueryClient();
  const runSourceConnectionSyncMutation = useRunSourceConnectionSyncMutation();
  const activeLastJob = sourceConnection?.sync?.last_job;
  const activeLastJobId =
    activeLastJob?.id && isActiveSyncJobStatus(activeLastJob.status)
      ? activeLastJob.id
      : undefined;
  const syncJobStateQueryOptions = useGetSyncJobStateStreamQueryOptions({
    jobId: activeLastJobId ?? '',
  });
  const syncJobStateQuery = useQuery({
    ...syncJobStateQueryOptions,
    enabled: Boolean(activeLastJobId),
  });
  const streamJobStatus = syncJobStateQuery.data?.jobStatus;
  const isActiveSyncJob =
    isActiveSyncJobStatus(activeLastJob?.status) ||
    isActiveSyncJobStatus(streamJobStatus);

  React.useEffect(() => {
    if (!sourceConnectionId || !syncJobStateQuery.data?.finalStatus) {
      return;
    }

    void invalidateQueriesByTags(queryClient, sourceConnectionInvalidationTags);
  }, [queryClient, sourceConnectionId, syncJobStateQuery.data?.finalStatus]);

  const handleRunSync = React.useCallback(() => {
    if (!sourceConnectionId) {
      return;
    }

    runSourceConnectionSyncMutation.mutate({
      path: {
        source_connection_id: sourceConnectionId,
      },
    });
  }, [runSourceConnectionSyncMutation, sourceConnectionId]);

  return {
    isSyncing: runSourceConnectionSyncMutation.isPending || isActiveSyncJob,
    runSync: handleRunSync,
  };
}
