import { type ColumnDef } from "@tanstack/react-table";

import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { ShiftSelectMeta } from "./data-table";

/**
 * Creates a selection column with header and row checkboxes.
 * Use this as the first column when enabling row selection.
 * Supports shift-click to select a range of rows.
 */
export function getSelectionColumn<TData>(): ColumnDef<TData> {
  return {
    id: "select",
    header: ({ table }) => {
      const hasSelection =
        table.getIsSomePageRowsSelected() || table.getIsAllPageRowsSelected();

      return (
        <Checkbox
          checked={table.getIsAllPageRowsSelected()}
          indeterminate={
            table.getIsSomePageRowsSelected() &&
            !table.getIsAllPageRowsSelected()
          }
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
          className={cn(
            "translate-y-px transition-opacity",
            hasSelection ? "opacity-100" : "opacity-10 hover:opacity-50"
          )}
        />
      );
    },
    cell: ({ row, table }) => {
      const meta = table.options.meta as ShiftSelectMeta | undefined;
      const isSelected = row.getIsSelected();

      return (
        <Checkbox
          checked={isSelected}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
          className={cn(
            "transition-opacity",
            isSelected ? "opacity-100" : "opacity-10 group-hover:opacity-50"
          )}
          onClick={(e) => {
            e.stopPropagation();
            const rowIndex = row.index;

            // Handle shift-click for range selection
            if (e.shiftKey && meta?.lastClickedRowRef?.current !== null) {
              meta?.handleShiftSelect?.(rowIndex, !row.getIsSelected());
            }

            // Update last clicked row index
            if (meta?.lastClickedRowRef) {
              meta.lastClickedRowRef.current = rowIndex;
            }
          }}
        />
      );
    },
    enableSorting: false,
    enableHiding: false,
    size: 40,
  };
}
