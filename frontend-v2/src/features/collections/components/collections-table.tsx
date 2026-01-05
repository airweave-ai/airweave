import { type ColumnDef, type RowSelectionState } from "@tanstack/react-table";
import {
  Braces,
  CopyIcon,
  Download,
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
} from "@/components/ui/data-table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Collection } from "@/lib/api";
import { cn } from "@/lib/utils";

import { formatDate, getCollectionStatusDisplay } from "../utils/helpers";
import { BulkDeleteCollectionsDialog } from "./bulk-delete-collections-dialog";

interface CollectionsTableProps {
  data: Collection[];
  onDelete: (readableIds: string[]) => void;
  onRowClick?: (collection: Collection) => void;
  selectedCollection: Collection | null;
  onSelectCollection: (collection: Collection | null) => void;
  deleteDialogOpen: boolean;
  onDeleteDialogChange: (open: boolean) => void;
}

function StatusBadge({ status }: { status: string }) {
  const statusDisplay = getCollectionStatusDisplay(status);

  return (
    <Badge
      variant={
        statusDisplay.variant === "success"
          ? "default"
          : statusDisplay.variant === "warning"
            ? "secondary"
            : statusDisplay.variant === "destructive"
              ? "destructive"
              : "outline"
      }
      className={cn(
        "w-fit",
        statusDisplay.variant === "success" &&
          "border-transparent bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
        statusDisplay.variant === "warning" &&
          "border-transparent bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
      )}
    >
      {statusDisplay.label}
    </Badge>
  );
}

function ActionsDropdown({
  collection,
  onDelete,
}: {
  collection: Collection;
  onDelete: (readableIds: string[]) => void;
}) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              "text-muted-foreground size-8 transition-opacity",
              isOpen ? "opacity-100" : "opacity-10 group-hover:opacity-50"
            )}
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="size-4" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onClick={() => {
              navigator.clipboard.writeText(collection.id);
              toast.success("Copied to clipboard");
            }}
          >
            <CopyIcon className="size-4" />
            Copy ID
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => {
              navigator.clipboard.writeText(
                JSON.stringify(collection, null, 2)
              );
              toast.success("Copied to clipboard");
            }}
          >
            <Braces className="size-4" />
            Copy as JSON
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onClick={() => setShowDeleteDialog(true)}
          >
            <Trash2 className="size-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <BulkDeleteCollectionsDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        collections={[collection]}
        onConfirm={() => onDelete([collection.readable_id])}
      />
    </>
  );
}

export function CollectionsTable({
  data,
  onDelete,
  onRowClick,
  selectedCollection,
  onSelectCollection,
  deleteDialogOpen,
  onDeleteDialogChange,
}: CollectionsTableProps) {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);
  const [collectionsToDelete, setCollectionsToDelete] = useState<Collection[]>(
    []
  );

  // Build columns with domain-specific renderers
  const columns: ColumnDef<Collection>[] = useMemo(
    () => [
      getSelectionColumn<Collection>(),
      {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => (
          <span className="font-medium">{row.original.name}</span>
        ),
      },
      {
        accessorKey: "readable_id",
        header: "Domain",
        cell: ({ row }) => (
          <code className="text-muted-foreground font-mono text-xs">
            {row.original.readable_id}.airweave.ai
          </code>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        accessorKey: "created_at",
        header: "Created",
        cell: ({ row }) => (
          <span className="text-muted-foreground text-sm">
            {formatDate(row.original.created_at)}
          </span>
        ),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <div className="flex justify-end">
            <ActionsDropdown collection={row.original} onDelete={onDelete} />
          </div>
        ),
      },
    ],
    [onDelete]
  );

  return (
    <>
      <DataTable
        columns={columns}
        data={data}
        enableRowSelection
        emptyMessage="No collections found."
        getRowId={(row) => row.id}
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
        highlightedRow={selectedCollection}
        onRowHover={onSelectCollection}
        onRowClick={onRowClick}
        renderFloatingToolbar={({ selectedRows, table }) => {
          const selectedCollections = selectedRows.map((row) => row.original);
          return (
            <DataTableFloatingToolbar
              selectedCount={selectedCollections.length}
              actions={[
                {
                  id: "copy-json",
                  label: "Export",
                  icon: Download,
                  onClick: () => {
                    navigator.clipboard
                      .writeText(JSON.stringify(selectedCollections, null, 2))
                      .then(() => {
                        toast.success(
                          `Copied ${selectedCollections.length} collection${selectedCollections.length > 1 ? "s" : ""} as JSON`
                        );
                      });
                  },
                },
                {
                  id: "delete",
                  label: "Delete",
                  icon: Trash2,
                  variant: "destructive",
                  onClick: () => {
                    setCollectionsToDelete(selectedCollections);
                    setBulkDeleteDialogOpen(true);
                  },
                },
              ]}
              onClearSelection={() => table.resetRowSelection()}
            />
          );
        }}
      />

      {/* Bulk delete dialog */}
      <BulkDeleteCollectionsDialog
        open={bulkDeleteDialogOpen}
        onOpenChange={setBulkDeleteDialogOpen}
        collections={collectionsToDelete}
        onConfirm={() => {
          onDelete(collectionsToDelete.map((c) => c.readable_id));
          setRowSelection({});
        }}
      />

      {/* Delete dialog controlled from parent (for command menu) */}
      {selectedCollection && (
        <BulkDeleteCollectionsDialog
          open={deleteDialogOpen}
          onOpenChange={onDeleteDialogChange}
          collections={[selectedCollection]}
          onConfirm={() => {
            onDelete([selectedCollection.readable_id]);
            onSelectCollection(null);
          }}
        />
      )}
    </>
  );
}
