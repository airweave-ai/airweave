import { type ColumnDef, type RowSelectionState } from "@tanstack/react-table";
import {
  Braces,
  CheckCircle2,
  Copy,
  MoreHorizontal,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DataTable,
  DataTableFloatingToolbar,
  getSelectionColumn,
  type FloatingToolbarAction,
} from "@/components/ui/data-table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { APIKey } from "@/lib/api";
import { DeleteApiKeyDialog } from "./delete-dialog";

import {
  formatDate,
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

function ActionsDropdown({
  apiKey,
  onDelete,
}: {
  apiKey: APIKey;
  onDelete: (keyIds: string[]) => void;
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

      <DeleteApiKeyDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        keys={[apiKey]}
        onConfirm={() => onDelete([apiKey.id])}
      />
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
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);
  const [selectedKeysForBulkDelete, setSelectedKeysForBulkDelete] = useState<
    APIKey[]
  >([]);

  // Build columns with domain-specific renderers
  const columns: ColumnDef<APIKey>[] = useMemo(
    () => [
      getSelectionColumn<APIKey>(),
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

  // Get selected keys from selection state
  const selectedKeys = useMemo(() => {
    return Object.keys(rowSelection)
      .filter((id) => rowSelection[id])
      .map((id) => data.find((key) => key.id === id))
      .filter((key): key is APIKey => key !== undefined);
  }, [rowSelection, data]);

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
    setBulkDeleteDialogOpen(false);
  };

  const handleClearSelection = () => {
    setRowSelection({});
  };

  // Floating toolbar actions
  const floatingToolbarActions: FloatingToolbarAction[] = [
    {
      id: "copy-json",
      label: "Copy as JSON",
      icon: Braces,
      onClick: handleBulkCopyAsJson,
    },
    {
      id: "delete",
      label: "Delete selected",
      icon: Trash2,
      variant: "destructive",
      onClick: () => {
        setSelectedKeysForBulkDelete(selectedKeys);
        setBulkDeleteDialogOpen(true);
      },
    },
  ];

  return (
    <>
      <DataTable
        columns={columns}
        data={data}
        enableRowSelection
        enableFiltering
        filterColumn="decrypted_key"
        filterPlaceholder="Filter by key prefix..."
        emptyMessage="No API keys found."
        getRowId={(row) => row.id}
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
        highlightedRow={selectedKey}
        onRowHover={onSelectKey}
        renderFloatingToolbar={() => (
          <DataTableFloatingToolbar
            selectedCount={selectedKeys.length}
            actions={floatingToolbarActions}
            onClearSelection={handleClearSelection}
          />
        )}
      />

      {/* Bulk delete dialog */}
      <DeleteApiKeyDialog
        open={bulkDeleteDialogOpen}
        onOpenChange={setBulkDeleteDialogOpen}
        keys={selectedKeysForBulkDelete}
        onConfirm={handleBulkDelete}
      />

      {/* Delete dialog controlled from parent (for command menu) */}
      {selectedKey && (
        <DeleteApiKeyDialog
          open={deleteDialogOpen}
          onOpenChange={onDeleteDialogChange}
          keys={[selectedKey]}
          onConfirm={() => {
            onDelete([selectedKey.id]);
            onSelectKey(null);
          }}
        />
      )}
    </>
  );
}
