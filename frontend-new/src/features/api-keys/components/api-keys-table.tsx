import { getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { MoreVertical } from 'lucide-react';
import { IconCopy, IconRefresh, IconTrash } from '@tabler/icons-react';
import { useDeleteApiKeyMutation, useRotateApiKeyMutation } from '../api';
import type { ColumnDef } from '@tanstack/react-table';
import type { ReactNode } from 'react';
import type { ApiKey } from '@/shared/api';
import { CardRowsTable } from '@/shared/components/card-rows-table';
import {
  formatDate,
  formatRelativeDate,
  parseDate,
} from '@/shared/format/date';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';

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
      <ValueCell>{row.original.created_by_email ?? 'Unknown'}</ValueCell>
    ),
  },
  {
    accessorKey: 'created_at',
    header: 'Created at',
    cell: ({ row }) => (
      <ValueCell>
        {formatDate(row.original.created_at) ?? row.original.created_at}
      </ValueCell>
    ),
  },
  {
    accessorKey: 'expiration_date',
    header: 'Expiration date',
    cell: ({ row }) => (
      <ExpirationDateCell expirationDate={row.original.expiration_date} />
    ),
  },
  {
    accessorKey: 'last_used_date',
    header: 'Last used',
    cell: ({ row }) => (
      <ValueCell className="first-letter:uppercase">
        {formatRelativeDate(row.original.last_used_date) ??
          row.original.last_used_date ??
          'Never'}
      </ValueCell>
    ),
  },
  {
    id: 'actions',
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <ApiKeyActionsMenu apiKey={row.original} />
      </div>
    ),
  },
];

type ApiKeysTableProps = {
  apiKeys: Array<ApiKey>;
  className?: string;
};

export function ApiKeysTable({ apiKeys, className }: ApiKeysTableProps) {
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

function ValueCell({
  children = '-',
  className,
}: {
  children?: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-block font-mono text-xs text-muted-foreground',
        className,
      )}
    >
      {children}
    </span>
  );
}

function ExpirationDateCell({ expirationDate }: { expirationDate: string }) {
  const parsedExpirationDate = parseDate(expirationDate);
  const isExpired =
    parsedExpirationDate !== null &&
    parsedExpirationDate.getTime() <= Date.now();

  return (
    <ValueCell className={cn(isExpired && 'text-destructive')}>
      {isExpired ? 'Expired' : 'Expires'}{' '}
      {formatRelativeDate(parsedExpirationDate, { unit: 'day' }) ??
        expirationDate}
    </ValueCell>
  );
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

function ApiKeyActionsMenu({ apiKey }: { apiKey: ApiKey }) {
  const { copy } = useCopyToClipboard();
  const decryptedKey = apiKey.decrypted_key;
  const deleteApiKeyMutation = useDeleteApiKeyMutation();
  const rotateApiKeyMutation = useRotateApiKeyMutation();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="icon" type="button" variant="ghost">
          <MoreVertical className="size-4" />
          <span className="sr-only">Open API key actions</span>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="min-w-47" side="bottom">
        {decryptedKey && (
          <DropdownMenuItem onClick={() => copy(decryptedKey)}>
            <IconCopy />
            Copy key
          </DropdownMenuItem>
        )}
        <DropdownMenuItem
          onClick={() =>
            rotateApiKeyMutation.mutate({
              path: {
                id: apiKey.id,
              },
            })
          }
        >
          <IconRefresh />
          Rotate key
        </DropdownMenuItem>
        <DropdownMenuItem
          variant="destructive"
          onClick={() =>
            deleteApiKeyMutation.mutate({ query: { id: apiKey.id } })
          }
        >
          <IconTrash />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
