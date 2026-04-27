import { Link } from '@tanstack/react-router';
import { getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { MoreVertical } from 'lucide-react';
import { IconPencil, IconTrash } from '@tabler/icons-react';
import { ProvidersListEmptyState } from './providers-list-empty-state';
import type { ColumnDef } from '@tanstack/react-table';
import type { AuthProviderConnection } from '@/shared/api';
import { CardRowsTable } from '@/shared/components/card-rows-table';
import { AuthProviderIcon } from '@/shared/components/auth-provider-icon';
import { ErrorState } from '@/shared/components/error-state';
import {
  StatusBadge,
  StatusBadgeIndicator,
} from '@/shared/components/status-badge';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';
import { Separator } from '@/shared/ui/separator';
import { Skeleton } from '@/shared/ui/skeleton';

const placeholderAccounts = 'michal@company.com, +2 more';
const placeholderConnections = 'Linear + Slack, +3 more';
const placeholderLastUsed = '5 min ago';

const connectedProvidersTableColumns: Array<ColumnDef<AuthProviderConnection>> =
  [
    {
      accessorKey: 'name',
      header: 'Name',
      cell: ({ row }) => (
        <ConnectedProviderNameCell connection={row.original} />
      ),
    },
    {
      id: 'accounts',
      header: 'Accounts',
      cell: () => (
        <SeparatedPlaceholderValueCell>
          {placeholderAccounts}
        </SeparatedPlaceholderValueCell>
      ),
    },
    {
      id: 'connections',
      header: 'Connections',
      cell: () => (
        <SeparatedPlaceholderValueCell>
          {placeholderConnections}
        </SeparatedPlaceholderValueCell>
      ),
    },
    {
      id: 'last-used',
      header: 'Last used',
      cell: () => (
        <SeparatedPlaceholderValueCell>
          {placeholderLastUsed}
        </SeparatedPlaceholderValueCell>
      ),
    },
    {
      id: 'actions',
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <ConnectedProviderActionsMenu connection={row.original} />
        </div>
      ),
    },
  ];

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
  const table = useReactTable({
    data: connections ?? [],
    columns: connectedProvidersTableColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  });

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
    <CardRowsTable
      table={table}
      className="overflow-x-auto"
      getHeaderCellClassName={(header) =>
        cn(
          header.id === 'name' && 'min-w-60',
          header.id === 'accounts' && 'min-w-60 pl-[33px]',
          header.id === 'connections' && 'min-w-60 pl-[33px]',
          header.id === 'last-used' && 'min-w-28 pl-[33px]',
          header.id === 'actions' && 'w-0',
        )
      }
      getBodyCellClassName={(cell) =>
        cn(
          'h-14 border-y first:border-l last:border-r',
          cell.column.id === 'name' && 'min-w-60',
          cell.column.id === 'accounts' && 'min-w-60',
          cell.column.id === 'connections' && 'min-w-60',
          cell.column.id === 'last-used' && 'min-w-28',
          cell.column.id === 'actions' && 'w-0 pr-3',
        )
      }
    />
  );
}

function ConnectedProviderNameCell({
  connection,
}: {
  connection: AuthProviderConnection;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <div className="flex min-w-0 items-center gap-1.5">
        <AuthProviderIcon
          className="size-5"
          name={connection.name}
          shortName={connection.short_name}
        />
        <p className="truncate text-sm font-medium text-foreground">
          {connection.name}
        </p>
      </div>
      <AuthProviderConnectionStatusBadge />
    </div>
  );
}

function PlaceholderValueCell({ children }: { children: string }) {
  return (
    <p className="truncate font-mono text-sm font-medium text-foreground">
      {children}
    </p>
  );
}

function SeparatedPlaceholderValueCell({ children }: { children: string }) {
  return (
    <div className="flex min-w-0 items-center gap-5">
      <Separator className="h-5" orientation="vertical" />
      <PlaceholderValueCell>{children}</PlaceholderValueCell>
    </div>
  );
}

function AuthProviderConnectionStatusBadge() {
  return (
    <StatusBadge variant="success">
      <StatusBadgeIndicator />
      Active
    </StatusBadge>
  );
}

function ConnectedProviderActionsMenu({
  connection,
}: {
  connection: AuthProviderConnection;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="icon" type="button" variant="ghost">
          <MoreVertical className="size-4" />
          <span className="sr-only">Open {connection.name} actions</span>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="min-w-36" side="bottom">
        <DropdownMenuItem asChild>
          <Link
            params={{ readableId: connection.readable_id }}
            to="/auth-providers/connections/$readableId/edit"
          >
            <IconPencil />
            Edit
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild variant="destructive">
          <Link
            params={{ readableId: connection.readable_id }}
            to="/auth-providers/connections/$readableId/delete"
          >
            <IconTrash />
            Delete
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
