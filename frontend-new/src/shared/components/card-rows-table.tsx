import { flexRender } from '@tanstack/react-table';
import type {
  Cell,
  Header,
  RowData,
  Table as TanstackTable,
} from '@tanstack/react-table';
import type { ReactNode } from 'react';
import { cn } from '@/shared/tailwind/cn';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';

type CardRowsTableProps<TData extends RowData> = {
  table: TanstackTable<TData>;
  className?: string;
  overlay?: ReactNode;
  getHeaderCellClassName?: (
    header: Header<TData, unknown>,
  ) => string | undefined;
  getBodyCellClassName?: (cell: Cell<TData, unknown>) => string | undefined;
};

export function CardRowsTable<TData extends RowData>({
  table,
  className,
  overlay,
  getHeaderCellClassName,
  getBodyCellClassName,
}: CardRowsTableProps<TData>) {
  const rows = table.getRowModel().rows;

  return (
    <div className={cn('relative flex min-h-0 flex-col', className)}>
      {overlay}

      <Table className="border-separate border-spacing-x-0 border-spacing-y-1">
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-transparent">
              {headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className={cn(
                    'h-10 px-3 text-xs font-medium tracking-wide text-muted-foreground',
                    getHeaderCellClassName?.(header),
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
          {rows.map((row) => (
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
                    getBodyCellClassName?.(cell),
                  )}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
