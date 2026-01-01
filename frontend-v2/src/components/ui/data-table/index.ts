// Core component
export { DataTable, type DataTableProps } from "./data-table";

// Helper components
export { DataTableColumnHeader } from "./data-table-column-header";
export { DataTablePagination } from "./data-table-pagination";
export { DataTableRowActions, type RowAction } from "./data-table-row-actions";
export { getSelectionColumn } from "./data-table-selection-column";
export {
  DataTableFloatingToolbar,
  type FloatingToolbarAction,
} from "./data-table-floating-toolbar";

// Re-export types from TanStack Table for convenience
export type {
  ColumnDef,
  OnChangeFn,
  Row,
  RowSelectionState,
  SortingState,
  TanstackTable,
} from "./data-table";

