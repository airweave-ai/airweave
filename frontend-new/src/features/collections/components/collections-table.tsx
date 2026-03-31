import * as React from 'react';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import { IconCheck, IconCopy } from '@tabler/icons-react';
import { CollectionActionsMenu } from './collection-actions-menu';
import { CollectionSourceConnections } from './collection-source-connections';
import type { ColumnDef, RowSelectionState } from '@tanstack/react-table';
import type { Collection } from '@/shared/api';
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
        <CollectionSourceConnections sourceConnections={sourceConnections} />
      );
    },
  },
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
  emptyMessage?: string;
};

export function CollectionsTable({
  collections,
  className,
  emptyMessage = 'No collections found.',
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

  return (
    <div className={cn('', className)}>
      <Table className="border-separate border-spacing-x-0 border-spacing-y-1">
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className={cn(
                    'h-11 px-4 text-xs font-medium tracking-wide text-muted-foreground',
                    header.id === 'select' && 'w-0 px-3',
                    header.id === 'actions' && 'w-0',
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
          {table.getRowModel().rows.length ? (
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
                      'bg-foreground/5 px-5 py-2 transition-colors group-hover:bg-foreground/10 group-data-[state=selected]:bg-foreground/10 first:rounded-l-sm last:rounded-r-sm',
                      cell.column.id === 'select' && 'w-0 pl-3',
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
                {emptyMessage}
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

function CollectionNameCell({ collection }: { collection: Collection }) {
  const identifier = collection.readable_id || collection.id;

  return (
    <div className="space-y-px whitespace-normal">
      <p className="text-sm font-medium text-foreground">{collection.name}</p>
      <div className="flex items-center gap-1 text-muted-foreground">
        <span className="font-mono text-xs leading-5">{identifier}</span>
        <CopyIdentifierButton value={identifier} />
      </div>
    </div>
  );
}

function CopyIdentifierButton({ value }: { value: string }) {
  const [copied, setCopied] = React.useState(false);

  const handleClick = React.useCallback(async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }, [value]);

  return (
    <Button
      aria-label={`Copy ${value}`}
      className="size-5 text-muted-foreground hover:text-foreground"
      onClick={() => void handleClick()}
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
