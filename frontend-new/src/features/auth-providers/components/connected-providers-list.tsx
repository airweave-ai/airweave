import { Link } from '@tanstack/react-router';
import { ProvidersListEmptyState } from './providers-list-empty-state';
import type { AuthProviderConnection } from '@/shared/api';
import { ErrorState } from '@/shared/components/error-state';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { Skeleton } from '@/shared/ui/skeleton';

type ConnectedProvidersListProps = {
  connections?: Array<AuthProviderConnection>;
  error?: unknown;
  onRetry?: () => void;
};

export function ConnectedProvidersList({
  connections,
  error,
  onRetry,
}: ConnectedProvidersListProps) {
  if (error) {
    return (
      <ErrorState
        description="There was a problem loading connected providers for this organization."
        onRetry={onRetry}
        retryLabel="Reload connected providers"
        title="We couldn't load connected providers"
      />
    );
  }

  if (!connections) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-14 rounded-sm bg-muted/60" />
        <Skeleton className="h-14 rounded-sm bg-muted/40" />
      </div>
    );
  }

  if (connections.length === 0) {
    return (
      <ProvidersListEmptyState
        className="py-4"
        message="Connected providers will appear here."
      />
    );
  }

  return (
    <div className="space-y-2">
      {connections.map((connection) => (
        <ConnectedProviderRow key={connection.id} connection={connection} />
      ))}
    </div>
  );
}

function ConnectedProviderRow({
  connection,
}: {
  connection: AuthProviderConnection;
}) {
  const detail =
    connection.description?.trim() ||
    (connection.masked_client_id
      ? `Client ID ${connection.masked_client_id}`
      : connection.readable_id);

  return (
    <div className="flex min-h-14 items-center justify-between gap-3 rounded-sm border border-input bg-background/30 px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">
          {connection.name}
        </p>
        <p className="truncate font-mono text-xs text-muted-foreground">
          {detail}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Badge
          variant="outline"
          className="rounded-full border-border/70 bg-transparent font-mono text-[0.625rem] text-muted-foreground"
        >
          {connection.short_name}
        </Badge>
        <Button asChild size="sm" variant="outline">
          <Link
            params={{ readableId: connection.readable_id }}
            to="/auth-providers/connections/$readableId/edit"
          >
            Edit
          </Link>
        </Button>
      </div>
    </div>
  );
}
