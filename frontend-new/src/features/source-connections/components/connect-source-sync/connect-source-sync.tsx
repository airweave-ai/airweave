import { useRunSourceConnectionSyncMutation } from '../../api';
import {
  ConnectSourceBackActionButton,
  ConnectSourcePrimaryActionButton,
  ConnectSourceStepLayoutActions,
  ConnectSourceStepLayoutContent,
} from '../connect-source-step-layout';
import { ConnectSourceSyncAutoNavigateAction } from './connect-source-sync-auto-navigate-action';
import { ConnectSourceSyncErrorState } from './connect-source-sync-error-state';
import { ConnectSourceSyncHeader } from './connect-source-sync-header';
import { ConnectSourceSyncJobProgress } from './connect-source-sync-job-progress';
import { ConnectSourceSyncStatusCard } from './connect-source-sync-status-card';
import type { Source, SourceConnection, SyncJobDetails } from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';

interface ConnectSourceSyncProps {
  lastJob: SyncJobDetails | null;
  onBack: () => void;
  onClose: () => void;
  source: Pick<Source, 'name' | 'short_name'>;
  sourceConnection: SourceConnection;
}

export function ConnectSourceSync({
  lastJob,
  onBack,
  onClose,
  source,
  sourceConnection,
}: ConnectSourceSyncProps) {
  const runSyncMutation = useRunSourceConnectionSyncMutation();

  if (lastJob) {
    return (
      <ConnectSourceSyncJobProgress
        job={lastJob}
        onBack={onBack}
        onClose={onClose}
        source={source}
        sourceConnection={sourceConnection}
      />
    );
  }

  if (sourceConnection.federated_search === true) {
    return (
      <>
        <ConnectSourceSyncHeader source={source} variant="completed" />

        <ConnectSourceStepLayoutContent>
          <ConnectSourceSyncStatusCard
            completed
            showProgressBar={false}
            subtitle={`${source.name} is queried live at search time. No initial sync is needed.`}
            title={`${source.name} connected`}
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

  const canRetrySync = Boolean(sourceConnection.sync_id);
  const retryErrorMessage = getApiErrorMessage(
    runSyncMutation.error,
    'Could not retry the sync job.',
  );

  return (
    <>
      <ConnectSourceSyncHeader source={source} variant="error" />
      <ConnectSourceSyncErrorState
        title={canRetrySync ? 'No sync job found' : 'Sync unavailable'}
        description={
          canRetrySync ? (
            <>
              The source connection is configured for syncing, but no last sync
              job was returned.
              <br />
              Retry to start a new sync job.
            </>
          ) : (
            <>
              This source connection does not have a sync configured yet.
              <br />
              There is nothing to retry from this step.
            </>
          )
        }
        details={retryErrorMessage}
        onClose={onClose}
        primaryAction={
          canRetrySync ? (
            <ConnectSourcePrimaryActionButton
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
          ) : undefined
        }
      />
    </>
  );
}
