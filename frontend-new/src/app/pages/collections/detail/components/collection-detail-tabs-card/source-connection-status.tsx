import { IconClock, IconCloudCheck, IconRefresh } from '@tabler/icons-react';
import type { SourceConnection, SourceConnectionStatus } from '@/shared/api';
import { StatusDot } from '@/shared/components/status-dot';
import { formatRelativeDate, formatTime } from '@/shared/format/date';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { Separator } from '@/shared/ui/separator';
import { Skeleton } from '@/shared/ui/skeleton';
import { Spinner } from '@/shared/ui/spinner';

const sourceConnectionStatusLabel = {
  active: 'Sync completed',
  error: 'Sync failed',
  inactive: 'Sync disabled',
  pending_auth: 'Source not connected',
  pending_sync: 'Sync not started',
  syncing: 'Syncing...',
} satisfies Record<SourceConnectionStatus, string>;

type SourceConnectionStatusHeaderProps = {
  isSyncing?: boolean;
  onSync: () => void;
  sourceConnection: Pick<SourceConnection, 'status' | 'schedule' | 'sync'>;
};

export function SourceConnectionStatusHeader({
  isSyncing = false,
  onSync,
  sourceConnection,
}: SourceConnectionStatusHeaderProps) {
  const resolvedStatus = isSyncing ? 'syncing' : sourceConnection.status;

  return (
    <div className="flex flex-wrap items-center gap-1">
      <ConnectionStatusLabel>
        <ConnectionStatusIndicator status={resolvedStatus} />
        <span
          className={cn('font-mono capitalize', {
            'text-destructive': resolvedStatus === 'error',
          })}
        >
          {sourceConnectionStatusLabel[resolvedStatus]}
        </span>
      </ConnectionStatusLabel>
      <Separator
        className="my-auto hidden h-4 sm:block"
        orientation="vertical"
      />
      <ConnectionStatusLabel>
        <IconClock className="size-3" />
        {formatNextRun(sourceConnection.schedule?.next_run)}
      </ConnectionStatusLabel>
      <Separator
        className="my-auto hidden h-4 sm:block"
        orientation="vertical"
      />
      <ConnectionStatusLabel>
        <IconCloudCheck className="size-3" />
        Last sync:{' '}
        <LastSyncValue
          isSyncing={isSyncing}
          startedAt={sourceConnection.sync?.last_job?.started_at}
        />
      </ConnectionStatusLabel>
      <Button
        size="icon-sm"
        variant="ghost"
        className="shrink-0 sm:ml-1"
        disabled={isSyncing}
        onClick={onSync}
      >
        {isSyncing ? (
          <Spinner className="size-4" />
        ) : (
          <IconRefresh className="size-4" />
        )}
      </Button>
    </div>
  );
}

export function SourceConnectionStatusHeaderSkeleton() {
  return (
    <div className="flex min-h-9 flex-wrap items-center gap-1">
      <Skeleton className="h-8 w-28 rounded-sm" />
      <Separator
        className="my-auto hidden h-4 sm:block"
        orientation="vertical"
      />
      <Skeleton className="h-8 w-20 rounded-sm" />
      <Separator
        className="my-auto hidden h-4 sm:block"
        orientation="vertical"
      />
      <Skeleton className="h-8 w-36 rounded-sm" />
      <Skeleton className="ml-1 size-8 rounded-sm" />
    </div>
  );
}

function LastSyncValue({
  isSyncing,
  startedAt,
}: {
  isSyncing: boolean;
  startedAt: string | null | undefined;
}) {
  if (isSyncing) {
    return <span className="text-muted-foreground">Syncing...</span>;
  }

  return formatLastSync(startedAt);
}

function formatNextRun(nextRun: string | null | undefined) {
  if (!nextRun) {
    return 'None';
  }

  const formattedTime = formatTime(nextRun);

  return formattedTime ? `At ${formattedTime}` : nextRun;
}

function formatLastSync(completedAt: string | null | undefined) {
  if (!completedAt) {
    return 'Never';
  }

  return (
    formatRelativeDate(completedAt, {
      numeric: 'auto',
      style: 'short',
    }) ?? completedAt
  );
}

function ConnectionStatusLabel({ children }: React.PropsWithChildren) {
  return (
    <span className="flex min-w-0 items-center gap-1.5 p-2 whitespace-nowrap">
      {children}
    </span>
  );
}

export function ConnectionStatusIndicator({
  status,
}: {
  status: SourceConnectionStatus;
}) {
  const variant = ['active', 'syncing'].includes(status)
    ? 'success'
    : ['pending_auth', 'error'].includes(status)
      ? 'destructive'
      : 'muted';

  return <StatusDot className="size-1.5" variant={variant} />;
}
