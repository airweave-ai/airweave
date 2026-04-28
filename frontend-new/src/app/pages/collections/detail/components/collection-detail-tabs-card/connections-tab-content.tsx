import { Link } from '@tanstack/react-router';
import { IconAlertTriangleFilled, IconPlus } from '@tabler/icons-react';
import {
  ConnectionStatusIndicator,
  SourceConnectionStatusHeader,
  SourceConnectionStatusHeaderSkeleton,
} from './source-connection-status';
import { SourceConnectionCredentialErrorCard } from './source-connection-credential-error-card';
import { SourceConnectionSyncErrorCard } from './source-connection-sync-error-card';
import { useSelectedSourceConnection } from './use-selected-source-connection';
import { useSourceConnectionSyncState } from './use-source-connection-sync-state';
import type { SourceConnection, SourceConnectionListItem } from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';
import { ErrorState } from '@/shared/components/error-state';
import { LoadingState } from '@/shared/components/loading-state';
import { SourceIcon } from '@/shared/components/source-icon';
import { AirweaveLogo } from '@/shared/ui/airweave-logo';
import { Button } from '@/shared/ui/button';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/shared/ui/empty';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select';

type ConnectionsTabContentProps = {
  collectionId: string;
  sourceConnections: Array<SourceConnectionListItem>;
};

type SourceConnectionQueryState = {
  data: SourceConnection | undefined;
  error: unknown;
  isError: boolean;
  isLoading: boolean;
  refetch: () => Promise<unknown>;
};

export function ConnectionsTabContent({
  collectionId,
  sourceConnections,
}: ConnectionsTabContentProps) {
  const {
    selectedSourceConnectionSummary,
    setSelectedSourceConnectionId,
    sourceConnection,
    sourceConnectionQuery,
  } = useSelectedSourceConnection(sourceConnections);
  const { isSyncing, runSync } = useSourceConnectionSyncState({
    sourceConnection,
    sourceConnectionId: selectedSourceConnectionSummary?.id,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0 flex-1 basis-64 lg:w-50 lg:flex-none">
          <SourceConnectionSelect
            selectedSourceConnectionId={selectedSourceConnectionSummary?.id}
            sourceConnections={sourceConnections}
            onSourceConnectionSelected={setSelectedSourceConnectionId}
          />
        </div>

        <div className="min-w-0 flex-1 basis-80 sm:flex sm:justify-end">
          {sourceConnectionQuery.isLoading ? (
            <SourceConnectionStatusHeaderSkeleton />
          ) : selectedSourceConnectionSummary && sourceConnection ? (
            <SourceConnectionStatusHeader
              isSyncing={isSyncing}
              onSync={runSync}
              sourceConnection={sourceConnection}
            />
          ) : null}
        </div>
      </div>

      <div className="flex min-h-77 flex-col justify-center">
        {selectedSourceConnectionSummary ? (
          <SourceConnectionEntitiesPanel
            collectionId={collectionId}
            query={sourceConnectionQuery}
            onResync={runSync}
          />
        ) : (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <AirweaveLogo />
              </EmptyMedia>
              <EmptyTitle>No sources connected yet</EmptyTitle>
              <EmptyDescription>
                Connect a source to start syncing data into this collection.
                Once synced, you can search and query it here.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button asChild size="sm">
                <Link
                  params={{ collectionId }}
                  to="/collections/$collectionId/connect-source"
                >
                  <IconPlus />
                  Add source
                </Link>
              </Button>
            </EmptyContent>
          </Empty>
        )}
      </div>
    </div>
  );
}

function SourceConnectionEntitiesPanel({
  collectionId,
  query,
  onResync,
}: {
  collectionId: string;
  query: SourceConnectionQueryState;
  onResync: () => void;
}) {
  if (query.isLoading) {
    return <LoadingState />;
  }

  if (query.isError && !query.data) {
    return (
      <ErrorState
        description={getApiErrorMessage(
          query.error,
          'Could not load source connection details.',
        )}
        onRetry={() => void query.refetch()}
        title="We couldn't load this source"
      />
    );
  }

  const sourceConnection = query.data;

  if (!sourceConnection) {
    return null;
  }

  if (sourceConnection.status === 'pending_auth') {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon" className="bg-destructive">
            <IconAlertTriangleFilled className="text-card" />
          </EmptyMedia>
          <EmptyTitle>Source not connected</EmptyTitle>
          <EmptyDescription>
            Connect this source to start indexing entities in this collection.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button asChild size="sm">
            <Link
              params={{ collectionId, source: sourceConnection.short_name }}
              search={{ source_connection_id: sourceConnection.id }}
              to="/collections/$collectionId/connect-source/$source/auth"
            >
              Connect source
            </Link>
          </Button>
        </EmptyContent>
      </Empty>
    );
  }

  return (
    <div className="flex-1 space-y-4">
      {sourceConnection.status === 'needs_reauth' ? (
        <SourceConnectionCredentialErrorCard
          sourceConnection={sourceConnection}
        />
      ) : null}

      {sourceConnection.status === 'error' ? (
        <SourceConnectionSyncErrorCard
          error={sourceConnection.sync?.last_job?.error ?? undefined}
          onResync={onResync}
        />
      ) : null}

      <pre>{JSON.stringify(sourceConnection.entities ?? null, null, 2)}</pre>
    </div>
  );
}

type SourceConnectionSelectProps = {
  sourceConnections: Array<
    Pick<SourceConnectionListItem, 'id' | 'name' | 'short_name' | 'status'>
  >;
  selectedSourceConnectionId: string | undefined;
  onSourceConnectionSelected: (sourceConnectionId: string) => void;
};

function SourceConnectionSelect({
  sourceConnections,
  selectedSourceConnectionId,
  onSourceConnectionSelected,
}: SourceConnectionSelectProps) {
  if (!sourceConnections.length) {
    return (
      <Select disabled value="none">
        <SelectTrigger className="w-full min-w-0 border-none">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="none">No sources</SelectItem>
        </SelectContent>
      </Select>
    );
  }

  return (
    <Select
      value={selectedSourceConnectionId}
      onValueChange={onSourceConnectionSelected}
    >
      <SelectTrigger className="w-full min-w-0 border-none">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {sourceConnections.map((sourceConnection) => (
            <SelectItem key={sourceConnection.id} value={sourceConnection.id}>
              <SourceIcon
                className="size-4"
                name={sourceConnection.short_name}
                shortName={sourceConnection.short_name}
                variant="color"
              />
              <ConnectionStatusIndicator status={sourceConnection.status} />
              {sourceConnection.name}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
