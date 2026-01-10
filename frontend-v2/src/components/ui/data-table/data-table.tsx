import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type OnChangeFn,
  type Row,
  type RowSelectionState,
  type SortingState,
  type Table as TanstackTable,
} from "@tanstack/react-table";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Meta type for shift-select functionality.
 * Passed via table.options.meta to selection columns.
 */
export interface ShiftSelectMeta {
  lastClickedRowRef: React.MutableRefObject<number | null>;
  handleShiftSelect: (currentIndex: number, isSelecting: boolean) => void;
}

export interface DataTableProps<TData, TValue> {
  /** Column definitions for the table */
  columns: ColumnDef<TData, TValue>[];
  /** Data array to display */
  data: TData[];
  /** Enable row selection with checkboxes */
  enableRowSelection?: boolean;
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
  const [internalRowSelection, setInternalRowSelection] =
    useState<RowSelectionState>({});
  const [sorting, setSorting] = useState<SortingState>([]);

  const rowRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());

  const rowSelection = controlledRowSelection ?? internalRowSelection;
  const handleRowSelectionChange =
    onRowSelectionChange ?? setInternalRowSelection;

  const lastClickedRowRef = useRef<number | null>(null);
  const tableRef = useRef<TanstackTable<TData> | null>(null);

  const handleShiftSelect = useCallback(
    (currentIndex: number, isSelecting: boolean) => {
      const lastIndex = lastClickedRowRef.current;
      if (lastIndex === null || !tableRef.current) return;

      const rows = tableRef.current.getRowModel().rows;
      const [start, end] = [
        Math.min(lastIndex, currentIndex),
        Math.max(lastIndex, currentIndex),
      ];

      for (let i = start; i <= end; i++) {
        rows[i]?.toggleSelected(isSelecting);
      }
    },
    []
  );

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    ...(enableSorting && { getSortedRowModel: getSortedRowModel() }),
    ...(enablePagination && { getPaginationRowModel: getPaginationRowModel() }),
    enableRowSelection,
    onRowSelectionChange: handleRowSelectionChange,
    onSortingChange: setSorting,
    ...(getRowId && { getRowId }),
    state: {
      rowSelection,
      sorting,
    },
    initialState: {
      pagination: {
        pageSize,
      },
    },
    meta: {
      lastClickedRowRef,
      handleShiftSelect,
    } satisfies ShiftSelectMeta,
  });

  tableRef.current = table;

  const getHighlightedRowIndex = useCallback((): number | null => {
    if (!highlightedRow || !getRowId) return null;
    const rows = table.getRowModel().rows;
    const highlightedId = getRowId(highlightedRow);
    const index = rows.findIndex(
      (row) => getRowId(row.original) === highlightedId
    );
    return index >= 0 ? index : null;
  }, [highlightedRow, getRowId, table]);

  useEffect(() => {
    const rows = table.getRowModel().rows;
    const rowCount = rows.length;

    if (rowCount === 0 || !onRowHover) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const activeElement = document.activeElement;
      const nothingFocused =
        !activeElement ||
        activeElement === document.body ||
        activeElement === document.documentElement;

      const currentIndex = getHighlightedRowIndex();

      switch (e.key) {
        case "ArrowDown": {
          e.preventDefault();
          const nextIndex =
            currentIndex === null
              ? 0
              : Math.min(currentIndex + 1, rowCount - 1);
          const nextRow = rows[nextIndex];
          if (nextRow) {
            onRowHover(nextRow.original);
            const rowEl = rowRefs.current.get(nextIndex);
            rowEl?.scrollIntoView({ block: "nearest", behavior: "smooth" });
          }
          break;
        }
        case "ArrowUp": {
          e.preventDefault();
          const prevIndex =
            currentIndex === null
              ? rowCount - 1
              : Math.max(currentIndex - 1, 0);
          const prevRow = rows[prevIndex];
          if (prevRow) {
            onRowHover(prevRow.original);
            const rowEl = rowRefs.current.get(prevIndex);
            rowEl?.scrollIntoView({ block: "nearest", behavior: "smooth" });
          }
          break;
        }
        case " ": {
          if (!nothingFocused) return;
          if (currentIndex !== null && enableRowSelection) {
            e.preventDefault();
            const row = rows[currentIndex];
            row?.toggleSelected();
          }
          break;
        }
        case "Enter": {
          if (!nothingFocused) return;
          if (currentIndex !== null && onRowClick) {
            e.preventDefault();
            const row = rows[currentIndex];
            if (row) {
              onRowClick(row.original);
            }
          }
          break;
        }
        case "Escape": {
          onRowHover(null);
          break;
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [
    table,
    getHighlightedRowIndex,
    enableRowSelection,
    onRowClick,
    onRowHover,
  ]);

  const selectedRows = table.getSelectedRowModel().rows;

  const isHighlightedRow = (row: TData): boolean => {
    if (!highlightedRow || !getRowId) return false;
    return getRowId(row) === getRowId(highlightedRow);
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Custom toolbar */}
      {renderToolbar?.(table)}

      {/* Table */}
      <div className="border-b">
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
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row, index) => {
                const isSelected = row.getIsSelected();
                const isHovered = isHighlightedRow(row.original);

                return (
                  <TableRow
                    key={row.id}
                    ref={(el) => {
                      if (el) {
                        rowRefs.current.set(index, el);
                      } else {
                        rowRefs.current.delete(index);
                      }
                    }}
                    data-state={isSelected ? "selected" : undefined}
                    className={cn(
                      "group",
                      onRowClick && "cursor-pointer",
                      isSelected
                        ? "bg-muted/50"
                        : isHovered
                          ? "bg-muted/30"
                          : ""
                    )}
                    onClick={() => onRowClick?.(row.original)}
                    onMouseEnter={() => onRowHover?.(row.original)}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
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
                  className="text-muted-foreground h-24 text-center"
                >
                  {emptyMessage}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Floating toolbar for bulk actions */}
      {renderFloatingToolbar &&
        selectedRows.length > 0 &&
        renderFloatingToolbar({ table, selectedRows })}
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
