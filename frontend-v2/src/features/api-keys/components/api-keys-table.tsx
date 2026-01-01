import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnFiltersState,
  type RowSelectionState,
} from "@tanstack/react-table";
import {
  Braces,
  CheckCircle2,
  Copy,
  MoreHorizontal,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { APIKey } from "@/lib/api";

import {
  formatDate,
  getApiKeyActions,
  getDaysRemaining,
  getStatusColor,
  maskKey,
} from "../utils/helpers";

interface ApiKeysTableProps {
  data: APIKey[];
  onDelete: (keyIds: string[]) => void;
  selectedKey: APIKey | null;
  onSelectKey: (key: APIKey | null) => void;
  deleteDialogOpen: boolean;
  onDeleteDialogChange: (open: boolean) => void;
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(value).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      },
      () => {
        console.error("Failed to copy key");
      },
    );
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={handleCopy}
      className="size-8"
      title="Copy key"
    >
      {copied ? (
        <CheckCircle2 className="size-4 text-green-500" />
      ) : (
        <Copy className="size-4" />
      )}
    </Button>
  );
}

function ActionsDropdown({
  apiKey,
  onDelete,
}: {
  apiKey: APIKey;
  onDelete: (keyIds: string[]) => void;
}) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const actions = getApiKeyActions({
    apiKey,
    onCopyAsJson: () => {
      navigator.clipboard.writeText(JSON.stringify(apiKey, null, 2));
      toast.success("Copied to clipboard");
    },
    onDelete: () => setShowDeleteDialog(true),
  });

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 text-muted-foreground"
          >
            <MoreHorizontal className="size-4" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {actions.map((action) => (
            <DropdownMenuItem
              key={action.id}
              variant={action.variant}
              onClick={action.onSelect}
            >
              {action.id === "copy-json" && <Braces className="size-4" />}
              {action.id === "delete-key" && <Trash2 className="size-4" />}
              {action.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete API key</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. Any applications using this key will
              lose access immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="my-4 rounded-lg border bg-muted p-3">
            <code className="text-sm font-mono">
              {maskKey(apiKey.decrypted_key)}
            </code>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => onDelete([apiKey.id])}
            >
              Delete key
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function StatusBadge({ expirationDate }: { expirationDate: string }) {
  const daysRemaining = getDaysRemaining(expirationDate);
  const isExpired = daysRemaining < 0;
  const isExpiringSoon = daysRemaining >= 0 && daysRemaining <= 7;

  if (isExpired) {
    return (
      <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border-transparent">
        Expired
      </Badge>
    );
  }

  if (isExpiringSoon) {
    return (
      <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border-transparent">
        Expiring soon
      </Badge>
    );
  }

  return (
    <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 border-transparent">
      Active
    </Badge>
  );
}

interface FloatingToolbarProps {
  selectedCount: number;
  selectedKeys: APIKey[];
  onClearSelection: () => void;
  onCopyAsJson: () => void;
  onDelete: () => void;
}

function FloatingToolbar({
  selectedCount,
  selectedKeys,
  onClearSelection,
  onCopyAsJson,
  onDelete,
}: FloatingToolbarProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  if (selectedCount === 0) return null;

  return (
    <>
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-4 fade-in duration-200">
        <div className="flex items-center gap-3 rounded-lg border bg-background px-4 py-3 shadow-lg">
          <span className="text-sm font-medium text-muted-foreground">
            {selectedCount} selected
          </span>
          <div className="h-4 w-px bg-border" />
          <Button variant="ghost" size="sm" onClick={onCopyAsJson}>
            <Braces className="mr-2 size-4" />
            Copy as JSON
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={() => setShowDeleteDialog(true)}
          >
            <Trash2 className="mr-2 size-4" />
            Delete selected
          </Button>
          <div className="h-4 w-px bg-border" />
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={onClearSelection}
          >
            <X className="size-4" />
            <span className="sr-only">Clear selection</span>
          </Button>
        </div>
      </div>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selectedCount} API key{selectedCount > 1 ? "s" : ""}
            </AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. Any applications using{" "}
              {selectedCount > 1 ? "these keys" : "this key"} will lose access
              immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="my-4 max-h-32 overflow-y-auto rounded-lg border bg-muted p-3 space-y-1">
            {selectedKeys.map((key) => (
              <code key={key.id} className="block text-sm font-mono">
                {maskKey(key.decrypted_key)}
              </code>
            ))}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => {
                onDelete();
                setShowDeleteDialog(false);
              }}
            >
              Delete {selectedCount > 1 ? "keys" : "key"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export function ApiKeysTable({
  data,
  onDelete,
  selectedKey,
  onSelectKey,
  deleteDialogOpen,
  onDeleteDialogChange,
}: ApiKeysTableProps) {
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const columns: ColumnDef<APIKey>[] = useMemo(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllPageRowsSelected()}
            indeterminate={
              table.getIsSomePageRowsSelected() &&
              !table.getIsAllPageRowsSelected()
            }
            onCheckedChange={(value) =>
              table.toggleAllPageRowsSelected(!!value)
            }
            aria-label="Select all"
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(value) => row.toggleSelected(!!value)}
            aria-label="Select row"
            onClick={(e) => e.stopPropagation()}
          />
        ),
        enableSorting: false,
        enableHiding: false,
        size: 40,
      },
      {
        accessorKey: "decrypted_key",
        header: "Key",
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <code className="text-xs font-mono font-medium">
              {maskKey(row.original.decrypted_key)}
            </code>
            <CopyButton value={row.original.decrypted_key} />
          </div>
        ),
        filterFn: (row, _columnId, filterValue) => {
          const key = row.original.decrypted_key.toLowerCase();
          return key.startsWith(filterValue.toLowerCase());
        },
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => (
          <StatusBadge expirationDate={row.original.expiration_date} />
        ),
      },
      {
        accessorKey: "created_at",
        header: "Created",
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground">
            {formatDate(row.original.created_at)}
          </span>
        ),
      },
      {
        accessorKey: "expiration_date",
        header: "Expires",
        cell: ({ row }) => {
          const daysRemaining = getDaysRemaining(row.original.expiration_date);
          const isExpired = daysRemaining < 0;

          return (
            <span className={`text-sm ${getStatusColor(daysRemaining)}`}>
              {isExpired
                ? `Expired ${Math.abs(daysRemaining)} day${Math.abs(daysRemaining) === 1 ? "" : "s"} ago`
                : `${daysRemaining} day${daysRemaining === 1 ? "" : "s"}`}
            </span>
          );
        },
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <div className="flex justify-end">
            <ActionsDropdown apiKey={row.original} onDelete={onDelete} />
          </div>
        ),
      },
    ],
    [onDelete],
  );

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    enableRowSelection: true,
    onColumnFiltersChange: setColumnFilters,
    onRowSelectionChange: setRowSelection,
    getRowId: (row) => row.id,
    state: {
      columnFilters,
      rowSelection,
    },
  });

  // Get selected keys for bulk actions
  const selectedKeys = useMemo(() => {
    return table.getSelectedRowModel().rows.map((row) => row.original);
  }, [table.getSelectedRowModel().rows]);

  const handleBulkCopyAsJson = () => {
    const jsonData = JSON.stringify(selectedKeys, null, 2);
    navigator.clipboard.writeText(jsonData).then(
      () => {
        toast.success(
          `Copied ${selectedKeys.length} key${selectedKeys.length > 1 ? "s" : ""} as JSON`,
        );
      },
      () => {
        toast.error("Failed to copy to clipboard");
      },
    );
  };

  const handleBulkDelete = () => {
    const keyIds = selectedKeys.map((key) => key.id);
    onDelete(keyIds);
    setRowSelection({});
  };

  const handleClearSelection = () => {
    setRowSelection({});
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center">
        <Input
          placeholder="Filter by key prefix..."
          value={
            (table.getColumn("decrypted_key")?.getFilterValue() as string) ?? ""
          }
          onChange={(event) =>
            table.getColumn("decrypted_key")?.setFilterValue(event.target.value)
          }
          className="max-w-sm"
        />
      </div>
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
                const isHovered = selectedKey?.id === row.original.id;
                return (
                  <TableRow
                    key={row.id}
                    data-state={row.getIsSelected() ? "selected" : undefined}
                    className={
                      row.getIsSelected()
                        ? "bg-muted/50"
                        : isHovered
                          ? "bg-muted/30"
                          : ""
                    }
                    onMouseEnter={() => onSelectKey(row.original)}
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
                  No API keys found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Floating toolbar for bulk actions */}
      <FloatingToolbar
        selectedCount={selectedKeys.length}
        selectedKeys={selectedKeys}
        onClearSelection={handleClearSelection}
        onCopyAsJson={handleBulkCopyAsJson}
        onDelete={handleBulkDelete}
      />

      {/* Delete dialog controlled from parent (for command menu) */}
      {selectedKey && (
        <AlertDialog
          open={deleteDialogOpen}
          onOpenChange={onDeleteDialogChange}
        >
          <AlertDialogContent className="sm:max-w-md">
            <AlertDialogHeader>
              <AlertDialogTitle>Delete API key</AlertDialogTitle>
              <AlertDialogDescription>
                This action cannot be undone. Any applications using this key
                will lose access immediately.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="my-4 rounded-lg border bg-muted p-3">
              <code className="text-sm font-mono">
                {maskKey(selectedKey.decrypted_key)}
              </code>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-white hover:bg-destructive/90"
                onClick={() => {
                  onDelete([selectedKey.id]);
                  onSelectKey(null);
                }}
              >
                Delete key
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}
