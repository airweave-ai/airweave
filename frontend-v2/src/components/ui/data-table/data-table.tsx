"use client";

import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnFiltersState,
  type OnChangeFn,
  type Row,
  type RowSelectionState,
  type SortingState,
  type Table as TanstackTable,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export interface DataTableProps<TData, TValue> {
  /** Column definitions for the table */
  columns: ColumnDef<TData, TValue>[];
  /** Data array to display */
  data: TData[];
  /** Enable row selection with checkboxes */
  enableRowSelection?: boolean;
  /** Enable column filtering */
  enableFiltering?: boolean;
  /** Column key to filter on */
  filterColumn?: string;
  /** Placeholder text for filter input */
  filterPlaceholder?: string;
  /** Message to show when no data */
  emptyMessage?: string;
  /** Enable sorting */
  enableSorting?: boolean;
  /** Enable pagination */
  enablePagination?: boolean;
  /** Page size for pagination */
  pageSize?: number;
  /** Callback when row is clicked */
  onRowClick?: (row: TData) => void;
  /** Callback when row is hovered */
  onRowHover?: (row: TData | null) => void;
  /** Currently hovered/selected row for highlighting */
  highlightedRow?: TData | null;
  /** Function to get unique row ID */
  getRowId?: (row: TData) => string;
  /** Controlled row selection state */
  rowSelection?: RowSelectionState;
  /** Callback when row selection changes (TanStack Table updater pattern) */
  onRowSelectionChange?: OnChangeFn<RowSelectionState>;
  /** Render function for custom toolbar */
  renderToolbar?: (table: TanstackTable<TData>) => React.ReactNode;
  /** Render function for floating selection toolbar */
  renderFloatingToolbar?: (props: {
    table: TanstackTable<TData>;
    selectedRows: Row<TData>[];
  }) => React.ReactNode;
  /** Additional class name for the container */
  className?: string;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  enableRowSelection = false,
  enableFiltering = false,
  filterColumn,
  filterPlaceholder = "Filter...",
  emptyMessage = "No results.",
  enableSorting = false,
  enablePagination = false,
  pageSize = 10,
  onRowClick,
  onRowHover,
  highlightedRow,
  getRowId,
  rowSelection: controlledRowSelection,
  onRowSelectionChange,
  renderToolbar,
  renderFloatingToolbar,
  className,
}: DataTableProps<TData, TValue>) {
  // Internal state for uncontrolled mode
  const [internalRowSelection, setInternalRowSelection] =
    useState<RowSelectionState>({});
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [sorting, setSorting] = useState<SortingState>([]);

  // Use controlled or uncontrolled selection
  const rowSelection = controlledRowSelection ?? internalRowSelection;
  const handleRowSelectionChange = onRowSelectionChange ?? setInternalRowSelection;

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    ...(enableFiltering && { getFilteredRowModel: getFilteredRowModel() }),
    ...(enableSorting && { getSortedRowModel: getSortedRowModel() }),
    ...(enablePagination && { getPaginationRowModel: getPaginationRowModel() }),
    enableRowSelection,
    onRowSelectionChange: handleRowSelectionChange,
    onColumnFiltersChange: setColumnFilters,
    onSortingChange: setSorting,
    ...(getRowId && { getRowId }),
    state: {
      rowSelection,
      columnFilters,
      sorting,
    },
    initialState: {
      pagination: {
        pageSize,
      },
    },
  });

  // Get selected rows for floating toolbar
  const selectedRows = useMemo(() => {
    return table.getSelectedRowModel().rows;
  }, [table.getSelectedRowModel().rows]);

  // Check if a row is the highlighted row
  const isHighlightedRow = (row: TData): boolean => {
    if (!highlightedRow || !getRowId) return false;
    return getRowId(row) === getRowId(highlightedRow);
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Custom toolbar or default filter */}
      {renderToolbar ? (
        renderToolbar(table)
      ) : enableFiltering && filterColumn ? (
        <div className="flex items-center">
          <Input
            placeholder={filterPlaceholder}
            value={
              (table.getColumn(filterColumn)?.getFilterValue() as string) ?? ""
            }
            onChange={(event) =>
              table.getColumn(filterColumn)?.setFilterValue(event.target.value)
            }
            className="max-w-sm"
          />
        </div>
      ) : null}

      {/* Table */}
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent">
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    style={{
                      width:
                        header.column.columnDef.size !== undefined
                          ? header.column.columnDef.size
                          : undefined,
                    }}
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
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => {
                const isSelected = row.getIsSelected();
                const isHovered = isHighlightedRow(row.original);

                return (
                  <TableRow
                    key={row.id}
                    data-state={isSelected ? "selected" : undefined}
                    className={cn(
                      onRowClick && "cursor-pointer",
                      isSelected
                        ? "bg-muted/50"
                        : isHovered
                          ? "bg-muted/30"
                          : "",
                    )}
                    onClick={() => onRowClick?.(row.original)}
                    onMouseEnter={() => onRowHover?.(row.original)}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext(),
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                );
              })
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  {emptyMessage}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Floating toolbar for bulk actions */}
      {renderFloatingToolbar && selectedRows.length > 0 && (
        renderFloatingToolbar({ table, selectedRows })
      )}
    </div>
  );
}

// Re-export types for convenience
export type {
  ColumnDef,
  OnChangeFn,
  Row,
  RowSelectionState,
  SortingState,
  TanstackTable,
};

