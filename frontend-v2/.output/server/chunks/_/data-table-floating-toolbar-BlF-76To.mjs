import { c as createLucideIcon, a as cn, B as Button, X } from "./router-BGxBdlkD.mjs";
import { jsx, jsxs } from "react/jsx-runtime";
import { C as Checkbox, T as Table, b as TableHeader, c as TableRow, d as TableHead, e as TableBody, f as TableCell } from "./checkbox-L51m4-da.mjs";
import { useReactTable, getPaginationRowModel, getSortedRowModel, getCoreRowModel, flexRender } from "@tanstack/react-table";
import { useState, useRef, useCallback, useEffect } from "react";
const __iconNode$2 = [
  [
    "path",
    { d: "M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5c0 1.1.9 2 2 2h1", key: "ezmyqa" }
  ],
  [
    "path",
    {
      d: "M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1",
      key: "e1hn23"
    }
  ]
];
const Braces = createLucideIcon("braces", __iconNode$2);
const __iconNode$1 = [
  ["path", { d: "M12 15V3", key: "m9g1x1" }],
  ["path", { d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", key: "ih7n3h" }],
  ["path", { d: "m7 10 5 5 5-5", key: "brsn70" }]
];
const Download = createLucideIcon("download", __iconNode$1);
const __iconNode = [
  ["circle", { cx: "12", cy: "12", r: "1", key: "41hilf" }],
  ["circle", { cx: "19", cy: "12", r: "1", key: "1wjl8i" }],
  ["circle", { cx: "5", cy: "12", r: "1", key: "1pcz8c" }]
];
const Ellipsis = createLucideIcon("ellipsis", __iconNode);
function DataTable({
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
  className
}) {
  const [internalRowSelection, setInternalRowSelection] = useState({});
  const [sorting, setSorting] = useState([]);
  const rowRefs = useRef(/* @__PURE__ */ new Map());
  const rowSelection = controlledRowSelection ?? internalRowSelection;
  const handleRowSelectionChange = onRowSelectionChange ?? setInternalRowSelection;
  const lastClickedRowRef = useRef(null);
  const tableRef = useRef(null);
  const handleShiftSelect = useCallback(
    (currentIndex, isSelecting) => {
      const lastIndex = lastClickedRowRef.current;
      if (lastIndex === null || !tableRef.current) return;
      const rows = tableRef.current.getRowModel().rows;
      const [start, end] = [
        Math.min(lastIndex, currentIndex),
        Math.max(lastIndex, currentIndex)
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
    ...enableSorting && { getSortedRowModel: getSortedRowModel() },
    ...enablePagination && { getPaginationRowModel: getPaginationRowModel() },
    enableRowSelection,
    onRowSelectionChange: handleRowSelectionChange,
    onSortingChange: setSorting,
    ...getRowId && { getRowId },
    state: {
      rowSelection,
      sorting
    },
    initialState: {
      pagination: {
        pageSize
      }
    },
    meta: {
      lastClickedRowRef,
      handleShiftSelect
    }
  });
  tableRef.current = table;
  const getHighlightedRowIndex = useCallback(() => {
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
    const handleKeyDown = (e) => {
      const activeElement = document.activeElement;
      const nothingFocused = !activeElement || activeElement === document.body || activeElement === document.documentElement;
      const currentIndex = getHighlightedRowIndex();
      switch (e.key) {
        case "ArrowDown": {
          e.preventDefault();
          const nextIndex = currentIndex === null ? 0 : Math.min(currentIndex + 1, rowCount - 1);
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
          const prevIndex = currentIndex === null ? rowCount - 1 : Math.max(currentIndex - 1, 0);
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
    onRowHover
  ]);
  const selectedRows = table.getSelectedRowModel().rows;
  const isHighlightedRow = (row) => {
    if (!highlightedRow || !getRowId) return false;
    return getRowId(row) === getRowId(highlightedRow);
  };
  return /* @__PURE__ */ jsxs("div", { className: cn("space-y-4", className), children: [
    renderToolbar?.(table),
    /* @__PURE__ */ jsx("div", { className: "border-b", children: /* @__PURE__ */ jsxs(Table, { children: [
      /* @__PURE__ */ jsx(TableHeader, { children: table.getHeaderGroups().map((headerGroup) => /* @__PURE__ */ jsx(TableRow, { className: "hover:bg-transparent", children: headerGroup.headers.map((header) => /* @__PURE__ */ jsx(
        TableHead,
        {
          style: {
            width: header.column.columnDef.size !== void 0 ? header.column.columnDef.size : void 0
          },
          children: header.isPlaceholder ? null : flexRender(
            header.column.columnDef.header,
            header.getContext()
          )
        },
        header.id
      )) }, headerGroup.id)) }),
      /* @__PURE__ */ jsx(TableBody, { children: table.getRowModel().rows?.length ? table.getRowModel().rows.map((row, index) => {
        const isSelected = row.getIsSelected();
        const isHovered = isHighlightedRow(row.original);
        return /* @__PURE__ */ jsx(
          TableRow,
          {
            ref: (el) => {
              if (el) {
                rowRefs.current.set(index, el);
              } else {
                rowRefs.current.delete(index);
              }
            },
            "data-state": isSelected ? "selected" : void 0,
            className: cn(
              "group",
              onRowClick && "cursor-pointer",
              isSelected ? "bg-muted/50" : isHovered ? "bg-muted/30" : ""
            ),
            onClick: () => onRowClick?.(row.original),
            onMouseEnter: () => onRowHover?.(row.original),
            children: row.getVisibleCells().map((cell) => /* @__PURE__ */ jsx(TableCell, { children: flexRender(
              cell.column.columnDef.cell,
              cell.getContext()
            ) }, cell.id))
          },
          row.id
        );
      }) : /* @__PURE__ */ jsx(TableRow, { children: /* @__PURE__ */ jsx(
        TableCell,
        {
          colSpan: columns.length,
          className: "text-muted-foreground h-24 text-center",
          children: emptyMessage
        }
      ) }) })
    ] }) }),
    renderFloatingToolbar && selectedRows.length > 0 && renderFloatingToolbar({ table, selectedRows })
  ] });
}
function getSelectionColumn() {
  return {
    id: "select",
    header: ({ table }) => {
      const hasSelection = table.getIsSomePageRowsSelected() || table.getIsAllPageRowsSelected();
      return /* @__PURE__ */ jsx(
        Checkbox,
        {
          checked: table.getIsAllPageRowsSelected(),
          indeterminate: table.getIsSomePageRowsSelected() && !table.getIsAllPageRowsSelected(),
          onCheckedChange: (value) => table.toggleAllPageRowsSelected(!!value),
          "aria-label": "Select all",
          className: cn(
            "translate-y-px transition-opacity",
            hasSelection ? "opacity-100" : "opacity-10 hover:opacity-50"
          )
        }
      );
    },
    cell: ({ row, table }) => {
      const meta = table.options.meta;
      const isSelected = row.getIsSelected();
      return /* @__PURE__ */ jsx(
        Checkbox,
        {
          checked: isSelected,
          onCheckedChange: (value) => row.toggleSelected(!!value),
          "aria-label": "Select row",
          className: cn(
            "transition-opacity",
            isSelected ? "opacity-100" : "opacity-10 group-hover:opacity-50"
          ),
          onClick: (e) => {
            e.stopPropagation();
            const rowIndex = row.index;
            if (e.shiftKey && meta?.lastClickedRowRef?.current !== null) {
              meta?.handleShiftSelect?.(rowIndex, !row.getIsSelected());
            }
            if (meta?.lastClickedRowRef) {
              meta.lastClickedRowRef.current = rowIndex;
            }
          }
        }
      );
    },
    enableSorting: false,
    enableHiding: false,
    size: 40
  };
}
function DataTableFloatingToolbar({
  selectedCount,
  actions,
  onClearSelection,
  children
}) {
  if (selectedCount === 0) return null;
  return /* @__PURE__ */ jsx("div", { className: "animate-in slide-in-from-bottom-4 fade-in fixed bottom-6 left-1/2 z-50 -translate-x-1/2 duration-200", children: /* @__PURE__ */ jsxs("div", { className: "bg-background flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg", children: [
    /* @__PURE__ */ jsxs("span", { className: "text-muted-foreground text-sm font-medium", children: [
      selectedCount,
      " selected"
    ] }),
    /* @__PURE__ */ jsx("div", { className: "bg-border h-4 w-px" }),
    actions.map((action) => {
      const buttonVariant = action.variant === "destructive" ? "ghost" : action.variant ?? "ghost";
      return /* @__PURE__ */ jsxs(
        Button,
        {
          variant: buttonVariant,
          size: "sm",
          onClick: action.onClick,
          className: action.variant === "destructive" ? "text-destructive hover:text-destructive hover:bg-destructive/10" : void 0,
          children: [
            action.icon && /* @__PURE__ */ jsx(action.icon, { className: "mr-2 size-4" }),
            action.label
          ]
        },
        action.id
      );
    }),
    children,
    /* @__PURE__ */ jsx("div", { className: "bg-border h-4 w-px" }),
    /* @__PURE__ */ jsxs(
      Button,
      {
        variant: "ghost",
        size: "icon",
        className: "size-8",
        onClick: onClearSelection,
        children: [
          /* @__PURE__ */ jsx(X, { className: "size-4" }),
          /* @__PURE__ */ jsx("span", { className: "sr-only", children: "Clear selection" })
        ]
      }
    )
  ] }) });
}
export {
  Braces as B,
  DataTable as D,
  Ellipsis as E,
  DataTableFloatingToolbar as a,
  Download as b,
  getSelectionColumn as g
};
