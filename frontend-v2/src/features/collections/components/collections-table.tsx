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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useIsDark } from "@/hooks/use-is-dark";
import type { Collection } from "@/lib/api";
import { cn } from "@/lib/utils";

import { useCollectionSourceConnections } from "../hooks/use-collection-source-connections";
import {
  formatDate,
  getAppIconUrl,
  getCollectionStatusDisplay,
} from "../utils/helpers";
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

/**
 * Avatar group component showing source connection icons with overflow indicator.
 * Fetches source connections per-row with React Query caching.
 */
function SourceAvatarGroup({
  collectionReadableId,
  maxVisible = 2,
}: {
  collectionReadableId: string;
  maxVisible?: number;
}) {
  const isDark = useIsDark();
  const { connections, isLoading } =
    useCollectionSourceConnections(collectionReadableId);

  if (isLoading) {
    return (
      <div className="flex -space-x-2">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="bg-muted size-7 animate-pulse rounded-md border"
            style={{ zIndex: maxVisible - i }}
          />
        ))}
      </div>
    );
  }

  if (connections.length === 0) {
    return <span className="text-muted-foreground text-xs">No sources</span>;
  }

  const visibleConnections = connections.slice(0, maxVisible);
  const overflowConnections = connections.slice(maxVisible);
  const overflow = connections.length - maxVisible;

  return (
    <TooltipProvider>
      <div className="flex items-center">
        <div className="flex -space-x-2">
          {visibleConnections.map((connection, index) => (
            <Tooltip key={connection.id}>
              <TooltipTrigger asChild>
                <div
                  className="bg-background flex size-7 items-center justify-center overflow-hidden rounded-md border p-1 transition-transform hover:z-10 hover:scale-110"
                  style={{ zIndex: maxVisible - index }}
                >
                  <img
                    src={getAppIconUrl(
                      connection.short_name,
                      isDark ? "dark" : "light"
                    )}
                    alt={connection.name}
                    className="size-full object-contain"
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                      const parent = e.currentTarget.parentElement;
                      if (parent) {
                        parent.innerHTML = `<span class="text-muted-foreground text-[10px] font-semibold">${connection.short_name.substring(0, 2).toUpperCase()}</span>`;
                      }
                    }}
                  />
                </div>
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs">
                {connection.name}
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
        {overflow > 0 && (
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="bg-muted text-muted-foreground ml-1 flex size-7 items-center justify-center rounded-md border text-xs font-medium">
                +{overflow}
              </div>
            </TooltipTrigger>
            <TooltipContent side="top" className="text-xs">
              {overflowConnections.map((c) => c.name).join(", ")}
            </TooltipContent>
          </Tooltip>
        )}
      </div>
    </TooltipProvider>
  );
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
        id: "sources",
        header: "Sources",
        cell: ({ row }) => (
          <SourceAvatarGroup collectionReadableId={row.original.readable_id} />
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

      <BulkDeleteCollectionsDialog
        open={bulkDeleteDialogOpen}
        onOpenChange={setBulkDeleteDialogOpen}
        collections={collectionsToDelete}
        onConfirm={() => {
          onDelete(collectionsToDelete.map((c) => c.readable_id));
          setRowSelection({});
        }}
      />

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
