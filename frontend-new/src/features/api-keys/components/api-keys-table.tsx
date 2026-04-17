import { getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { MoreVertical } from 'lucide-react';
import { IconCopy, IconRefresh, IconTrash } from '@tabler/icons-react';
import type { ColumnDef } from '@tanstack/react-table';
import type { ReactNode } from 'react';
import type { ApiKey } from '@/shared/api';
import { CardRowsTable } from '@/shared/components/card-rows-table';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';

const apiKeyDateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export const apiKeysTableColumns: Array<ColumnDef<ApiKey>> = [
  {
    id: 'api-key',
    header: 'API Key',
    cell: ({ row }) => <ApiKeyValueCell apiKey={row.original} />,
  },
  {
    accessorKey: 'created_by_email',
    header: 'Created by',
    cell: ({ row }) => (
      <PlaceholderCell>
        {row.original.created_by_email ?? 'Unknown'}
      </PlaceholderCell>
    ),
  },
  {
    accessorKey: 'created_at',
    header: 'Created at',
    cell: ({ row }) => (
      <PlaceholderCell>
        {formatApiKeyDate(row.original.created_at, 'Unknown')}
      </PlaceholderCell>
    ),
  },
  {
    accessorKey: 'expiration_date',
    header: 'Expiration date',
    cell: ({ row }) => (
      <PlaceholderCell>
        {formatApiKeyDate(row.original.expiration_date, 'Unknown')}
      </PlaceholderCell>
    ),
  },
  {
    accessorKey: 'last_used_date',
    header: 'Last used',
    cell: ({ row }) => (
      <PlaceholderCell>
        {formatApiKeyDate(row.original.last_used_date)}
      </PlaceholderCell>
    ),
  },
  {
    id: 'actions',
    header: () => <span className="sr-only">Actions</span>,
    cell: () => (
      <div className="flex justify-end">
        <ApiKeyActionsMenu />
      </div>
    ),
  },
];

type ApiKeysTableProps = {
  apiKeys: Array<ApiKey>;
  className?: string;
};

export function ApiKeysTable({
  apiKeys,
  className,
}: ApiKeysTableProps) {
  const table = useReactTable({
    data: apiKeys,
    columns: apiKeysTableColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  });

  return (
    <CardRowsTable
      table={table}
      className={className}
      getHeaderCellClassName={(header) => cn(header.id === 'actions' && 'w-0')}
      getBodyCellClassName={(cell) =>
        cn(cell.column.id === 'actions' && 'w-0 pr-3')
      }
    />
  );
}

function PlaceholderCell({ children = '-' }: { children?: ReactNode }) {
  return <span className="text-muted-foreground">{children}</span>;
}

function ApiKeyValueCell({ apiKey }: { apiKey: ApiKey }) {
  return (
    <div className="max-w-96 space-y-px whitespace-normal">
      <p className="truncate font-mono text-xs leading-5 text-foreground">
        {apiKey.id}
      </p>

      {apiKey.decrypted_key ? (
        <p className="truncate font-mono text-xs leading-5 text-muted-foreground">
          {truncateApiKey(apiKey.decrypted_key)}
        </p>
      ) : null}
    </div>
  );
}

function truncateApiKey(value: string, startLength = 16, endLength = 8) {
  if (value.length <= startLength + endLength + 3) {
    return value;
  }

  return `${value.slice(0, startLength)}...${value.slice(-endLength)}`;
}

function ApiKeyActionsMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="icon" type="button" variant="ghost">
          <MoreVertical className="size-4" />
          <span className="sr-only">Open API key actions</span>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="min-w-47" side="bottom">
        <DropdownMenuItem>
          <IconCopy />
          Copy key
        </DropdownMenuItem>
        <DropdownMenuItem>
          <IconRefresh />
          Rotate key
        </DropdownMenuItem>
        <DropdownMenuItem variant="destructive">
          <IconTrash />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function formatApiKeyDate(
  date: string | null | undefined,
  emptyLabel = 'Never',
) {
  if (!date) {
    return emptyLabel;
  }

  const parsedDate = new Date(date);

  if (Number.isNaN(parsedDate.getTime())) {
    return date;
  }

  return apiKeyDateFormatter.format(parsedDate);
}
