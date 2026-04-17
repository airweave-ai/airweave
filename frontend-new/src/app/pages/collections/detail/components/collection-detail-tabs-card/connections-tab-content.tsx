import { Link } from '@tanstack/react-router';
import {
  IconAlertTriangleFilled,
  IconPlus,
  IconRefresh,
} from '@tabler/icons-react';
import {
  ConnectionStatusIndicator,
  SourceConnectionStatusHeader,
  SourceConnectionStatusHeaderSkeleton,
} from './source-connection-status';
import { useSelectedSourceConnection } from './use-selected-source-connection';
import { useSourceConnectionSyncState } from './use-source-connection-sync-state';
import type { SourceConnection, SourceConnectionListItem } from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';
import { ErrorState } from '@/shared/components/error-state';
import { SourceIcon } from '@/shared/components/source-icon';
import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from '@/shared/ui/alert';
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
import { Spinner } from '@/shared/ui/spinner';

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
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <SourceConnectionSelect
          selectedSourceConnectionId={selectedSourceConnectionSummary?.id}
          sourceConnections={sourceConnections}
          onSourceConnectionSelected={setSelectedSourceConnectionId}
        />
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
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Spinner className="size-4" />
          </EmptyMedia>
          <EmptyTitle>Loading…</EmptyTitle>
          <EmptyDescription>
            You can continue working while this completes.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
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

  const lastJobError = sourceConnection.sync?.last_job?.error;

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
    <div>
      {lastJobError && (
        <Alert variant="destructive">
          <IconAlertTriangleFilled />
          <AlertTitle>Last sync failed on our side</AlertTitle>
          <AlertDescription>
            Your existing data is still searchable. Only the latest sync was
            affected.
          </AlertDescription>
          <AlertAction className="top-1/2 -translate-y-1/2">
            <Button
              size="sm"
              variant="outline"
              className="text-foreground"
              onClick={onResync}
            >
              <IconRefresh className="size-3.5" /> Resync
            </Button>
          </AlertAction>
        </Alert>
      )}

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
        <SelectTrigger className="min-w-50 border-none">
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
      <SelectTrigger className="min-w-50 border-none">
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
