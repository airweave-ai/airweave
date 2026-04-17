import * as React from 'react';
import { Link } from '@tanstack/react-router';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import { IconCheck, IconCopy } from '@tabler/icons-react';
import { CollectionBulkActionsMenu } from './collection-bulk-actions-menu';
import { CollectionActionsMenu } from './collection-actions-menu';
import { CollectionSourceConnections } from './collection-source-connections';
import { CollectionTooltipContent } from './collection-tooltip-content';
import type { ColumnDef, RowSelectionState } from '@tanstack/react-table';
import type { Collection } from '@/shared/api';
import type { ReactNode } from 'react';
import { StatusDot } from '@/shared/components/status-dot';
import { formatNumber } from '@/shared/format/format-number';
import { pluralize } from '@/shared/format/pluralize';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { cn } from '@/shared/tailwind/cn';
import { Button } from '@/shared/ui/button';
import { Checkbox } from '@/shared/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';
import { Tooltip, TooltipTrigger } from '@/shared/ui/tooltip';

export const collectionsTableColumns: Array<ColumnDef<Collection>> = [
  {
    id: 'select',
    header: () => null,
    cell: ({ row }) => (
      <Checkbox
        aria-label={`Select ${row.original.name}`}
        checked={row.getIsSelected()}
        onCheckedChange={(checked) => row.toggleSelected(!!checked)}
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    id: 'status',
    header: () => null,
    cell: ({ row }) => <CollectionStatusIndicator collection={row.original} />,
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: 'name',
    header: 'Name',
    cell: ({ row }) => <CollectionNameCell collection={row.original} />,
  },
  {
    id: 'connections',
    header: 'Connections',
    cell: ({ row }) => {
      const sourceConnections = row.original.source_connection_summaries ?? [];

      if (!sourceConnections.length) {
        return <PlaceholderCell />;
      }

      return (
        <CollectionSourceConnections
          size="sm"
          sourceConnections={sourceConnections}
        />
      );
    },
  },
  // TODO: update Last Sync, Entities, and Last Query columns to display data from backend
  {
    id: 'last-sync',
    header: 'Last Sync',
    cell: () => <PlaceholderCell>Never</PlaceholderCell>,
  },
  {
    id: 'entities',
    header: 'Entities',
    cell: () => <PlaceholderCell>0</PlaceholderCell>,
  },
  {
    id: 'last-query',
    header: 'Last Query',
    cell: () => <PlaceholderCell>Never</PlaceholderCell>,
  },
  {
    id: 'actions',
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <CollectionActionsMenu collectionId={row.original.id} />
      </div>
    ),
  },
];

type CollectionsTableProps = {
  collections: Array<Collection>;
  className?: string;
  emptyState?: ReactNode;
};

export function CollectionsTable({
  collections,
  className,
  emptyState,
}: CollectionsTableProps) {
  const [rowSelection, setRowSelection] = React.useState<RowSelectionState>({});

  const table = useReactTable({
    data: collections,
    columns: collectionsTableColumns,
    enableRowSelection: true,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
    onRowSelectionChange: setRowSelection,
    state: {
      rowSelection,
    },
  });

  const selectedRows = table.getSelectedRowModel().rows;
  const selectedCollectionIds = selectedRows.map((row) => row.id);
  const selectedCollectionsCount = selectedRows.length;
  const hasSelectedCollections = selectedCollectionsCount > 0;
  const hasRows = table.getRowModel().rows.length > 0;

  return (
    <div className={cn('relative', className)}>
      {hasSelectedCollections ? (
        <div className="absolute inset-x-0 top-1 z-10 flex h-10 items-center justify-between gap-4 text-xs font-medium tracking-wide">
          <div className="flex items-center gap-3">
            <CollectionBulkActionsMenu collectionIds={selectedCollectionIds} />
            <span className="text-left">
              {formatNumber(selectedCollectionsCount)}{' '}
              {pluralize(selectedCollectionsCount, 'Collection')} selected
            </span>
          </div>
          <Button
            onClick={() => table.resetRowSelection()}
            size="xs"
            type="button"
            variant="ghost"
          >
            Clear selection
          </Button>
        </div>
      ) : null}
      <Table className="border-separate border-spacing-x-0 border-spacing-y-1">
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-transparent">
              {headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className={cn(
                    'h-10 px-3 text-xs font-medium tracking-wide text-muted-foreground',
                    header.id === 'select' && 'w-0',
                    header.id === 'status' && 'w-0 px-0',
                    header.id === 'actions' && 'w-0',
                    hasSelectedCollections && 'pointer-events-none opacity-0',
                  )}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {hasRows ? (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className="group border-0 hover:bg-transparent data-[state=selected]:bg-transparent"
                data-state={row.getIsSelected() ? 'selected' : undefined}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    className={cn(
                      'bg-foreground/5 px-3 py-2 transition-colors group-hover:bg-foreground/10 group-data-[state=selected]:bg-foreground/10 first:rounded-l-sm last:rounded-r-sm',
                      cell.column.id === 'select' && 'w-0 pl-3',
                      cell.column.id === 'status' && 'w-0 pr-0',
                      cell.column.id === 'actions' && 'w-0 pr-3',
                    )}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={collectionsTableColumns.length}
                className="h-24 px-4 py-3 text-center text-muted-foreground"
              >
                {emptyState}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function PlaceholderCell({ children = '-' }: React.PropsWithChildren) {
  return <span className="text-muted-foreground">{children}</span>;
}

function CollectionStatusIndicator({ collection }: { collection: Collection }) {
  const hasConnections =
    (collection.source_connection_summaries?.length ?? 0) > 0;
  const statusTitle = hasConnections ? 'Healthy' : 'No data';

  return (
    <Tooltip>
      <TooltipTrigger
        aria-label={
          hasConnections ? 'Collection healthy' : 'No collection data'
        }
        className="flex size-8 items-center justify-center"
      >
        <StatusDot variant={hasConnections ? 'success' : 'default'} />
      </TooltipTrigger>
      <CollectionTooltipContent
        sideOffset={8}
        description={
          hasConnections
            ? 'All connections are syncing successfully.'
            : 'No connections added yet.'
        }
        title={
          <span className="inline-flex items-center gap-1">
            <StatusDot variant={hasConnections ? 'success' : 'default'} />
            {statusTitle}
          </span>
        }
      />
    </Tooltip>
  );
}

function CollectionNameCell({ collection }: { collection: Collection }) {
  const identifier = collection.readable_id || collection.id;

  return (
    <div className="space-y-px whitespace-normal">
      <Link
        to="/collections/$collectionId"
        params={{ collectionId: collection.readable_id }}
        className="text-sm font-medium text-foreground hover:underline"
      >
        {collection.name}
      </Link>
      <div className="flex items-center gap-1 text-muted-foreground">
        <span className="font-mono text-xs leading-5 text-nowrap">
          {identifier}
        </span>
        <CopyIdentifierButton value={identifier} />
      </div>
    </div>
  );
}

function CopyIdentifierButton({ value }: { value: string }) {
  const { copied, copy } = useCopyToClipboard();

  return (
    <Button
      aria-label={`Copy ${value}`}
      className="size-5 text-muted-foreground hover:text-foreground"
      onClick={() => void copy(value)}
      size="icon-xs"
      type="button"
      variant="ghost"
    >
      {copied ? (
        <IconCheck className="size-4" />
      ) : (
        <IconCopy className="size-4" />
      )}
    </Button>
  );
}
