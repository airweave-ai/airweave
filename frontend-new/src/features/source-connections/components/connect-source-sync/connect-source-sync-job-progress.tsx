import { IconReload } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import {
  ConnectSourceBackActionButton,
  ConnectSourcePrimaryActionButton,
  ConnectSourceStepLayoutActions,
  ConnectSourceStepLayoutContent,
} from '../connect-source-step-layout';
import {
  useGetSyncJobStateStreamQueryOptions,
  useRunSourceConnectionSyncMutation,
} from '../../api';
import { isActiveSyncJobStatus } from '../../lib/sync-job-status';
import { ConnectSourceSyncAutoNavigateAction } from './connect-source-sync-auto-navigate-action';
import { ConnectSourceSyncErrorState } from './connect-source-sync-error-state';
import { ConnectSourceSyncHeader } from './connect-source-sync-header';
import { ConnectSourceSyncStatusCard } from './connect-source-sync-status-card';
import type {
  Source,
  SourceConnection,
  SyncJobDetails,
  SyncJobStatus,
} from '@/shared/api';
import { formatUtcTimestamp } from '@/shared/format/date';
import { formatNumber } from '@/shared/format/format-number';
import { pluralize } from '@/shared/format/pluralize';
import { getApiErrorMessage } from '@/shared/api';

interface ConnectSourceSyncJobProgressProps {
  job: SyncJobDetails;
  onBack: () => void;
  onClose: () => void;
  source: Pick<Source, 'name' | 'short_name'>;
  sourceConnection: SourceConnection;
}

export function ConnectSourceSyncJobProgress({
  job,
  onBack,
  onClose,
  source,
  sourceConnection,
}: ConnectSourceSyncJobProgressProps) {
  const initialIsActiveJob = isActiveSyncJobStatus(job.status);
  const runSyncMutation = useRunSourceConnectionSyncMutation();
  const syncJobStateQueryOptions = useGetSyncJobStateStreamQueryOptions({
    jobId: job.id,
  });
  const syncJobStateQuery = useQuery({
    ...syncJobStateQueryOptions,
    enabled: initialIsActiveJob,
  });
  const status = syncJobStateQuery.data?.jobStatus ?? job.status;
  const totalEntities =
    syncJobStateQuery.data?.totalEntities ??
    sourceConnection.entities?.total_entities ??
    0;
  const syncError =
    syncJobStateQuery.data?.error ??
    getApiErrorMessage(
      syncJobStateQuery.error,
      'Could not load sync job state.',
    ) ??
    job.error ??
    undefined;

  if (status === 'failed' || status === 'cancelled') {
    return (
      <>
        <ConnectSourceSyncHeader source={source} variant="error" />
        <ConnectSourceSyncErrorState
          title={status === 'failed' ? 'Last sync failed' : 'Sync cancelled'}
          timestamp={
            formatUtcTimestamp(job.completed_at ?? job.started_at) ?? undefined
          }
          description={
            status === 'failed' ? (
              <>
                Something went wrong on our end during sync.
                <br />
                Your existing data is still available - only the latest sync was
                affected.
              </>
            ) : (
              <>
                This sync was cancelled before completion.
                <br />
                Your existing data is still available and you can retry the
                sync.
              </>
            )
          }
          details={buildSyncErrorDetails({
            error: syncError,
            job,
            totalEntities,
          })}
          onClose={onClose}
          primaryAction={
            <ConnectSourcePrimaryActionButton
              icon={<IconReload className="size-4" />}
              isLoading={runSyncMutation.isPending}
              onClick={() =>
                runSyncMutation.mutate({
                  path: {
                    source_connection_id: sourceConnection.id,
                  },
                })
              }
            >
              Retry sync
            </ConnectSourcePrimaryActionButton>
          }
        />
      </>
    );
  }

  return (
    <>
      <ConnectSourceSyncHeader
        source={source}
        variant={status === 'completed' ? 'completed' : 'active'}
      />

      <ConnectSourceStepLayoutContent>
        <ConnectSourceSyncStatusCard
          completed={status === 'completed'}
          progress={getIndexedEntitiesPseudoProgress(totalEntities)}
          subtitle={formatIndexedEntities(totalEntities)}
          title={getProgressCardTitle(status, source.name)}
        />
      </ConnectSourceStepLayoutContent>

      <ConnectSourceStepLayoutActions
        backAction={
          <ConnectSourceBackActionButton onClick={onBack}>
            Connect another source
          </ConnectSourceBackActionButton>
        }
      >
        <ConnectSourceSyncAutoNavigateAction onNavigate={onClose} />
      </ConnectSourceStepLayoutActions>
    </>
  );
}

function buildSyncErrorDetails({
  error,
  job,
  totalEntities,
}: {
  error?: string;
  job: SyncJobDetails;
  totalEntities: number;
}) {
  const lines = [
    `Sync job ID: ${job.id}`,
    `Started: ${job.started_at ?? 'Unknown'}`,
    `Finished: ${job.completed_at ?? 'Unknown'}`,
    `Entities before failure: ${formatNumber(totalEntities)}`,
  ];

  if (error) {
    lines.push(`Error: ${error}`);
  }

  return lines.join('\n');
}

function getProgressCardTitle(
  status: Exclude<SyncJobStatus, 'failed' | 'cancelled'>,
  sourceName: string,
) {
  switch (status) {
    case 'created':
    case 'pending':
    case 'running':
      return `Syncing ${sourceName}...`;
    case 'cancelling':
      return `Cancelling ${sourceName} sync...`;
    case 'completed':
      return `${sourceName} synced`;
  }
}

function formatIndexedEntities(totalEntities: number) {
  const label = pluralize(totalEntities, 'entity', 'entities');
  return `${formatNumber(totalEntities)} ${label} indexed`;
}

function getIndexedEntitiesPseudoProgress(totalEntities: number) {
  if (totalEntities <= 0) {
    return 0;
  }

  // Grow quickly at the start, then taper off so the bar feels alive without
  // implying an exact denominator we do not have from the backend.
  return Math.min(0.95, 1 - 1 / (1 + totalEntities * 0.15));
}
