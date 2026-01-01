import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnFiltersState,
} from "@tanstack/react-table";
import { Braces, CheckCircle2, Copy, MoreHorizontal, Trash2 } from "lucide-react";
import { useState } from "react";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
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
  getDaysRemaining,
  getStatusColor,
  maskKey,
} from "../utils/helpers";

interface ApiKeysTableProps {
  data: APIKey[];
  onDelete: (keyId: string) => void;
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
  onDelete: (keyId: string) => void;
}) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

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
          <DropdownMenuItem
            onClick={() => {
              navigator.clipboard.writeText(JSON.stringify(apiKey, null, 2));
              toast.success("Copied to clipboard");
            }}
          >
            <Braces className="size-4" />
            Copy as JSON
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            variant="destructive"
            onClick={() => setShowDeleteDialog(true)}
          >
            <Trash2 className="size-4" />
            Delete API key
          </DropdownMenuItem>
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
              onClick={() => onDelete(apiKey.id)}
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

export function ApiKeysTable({
  data,
  onDelete,
  selectedKey,
  onSelectKey,
  deleteDialogOpen,
  onDeleteDialogChange,
}: ApiKeysTableProps) {
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

  const columns: ColumnDef<APIKey>[] = [
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
  ];

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnFiltersChange: setColumnFilters,
    state: {
      columnFilters,
    },
  });

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
                  <TableHead key={header.id}>
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
                const isSelected = selectedKey?.id === row.original.id;
                return (
                  <TableRow
                    key={row.id}
                    data-state={isSelected ? "selected" : undefined}
                    className={isSelected ? "bg-muted/50" : ""}
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

      {/* Delete dialog controlled from parent (for command menu) */}
      {selectedKey && (
        <AlertDialog open={deleteDialogOpen} onOpenChange={onDeleteDialogChange}>
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
                  onDelete(selectedKey.id);
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
