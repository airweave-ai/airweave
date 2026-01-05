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
import type { Collection } from "@/lib/api";

interface BulkDeleteCollectionsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  collections: Collection[];
  onConfirm: () => void;
}

/**
 * Reusable delete confirmation dialog for collections.
 * Handles both single and bulk deletion with appropriate messaging.
 */
export function BulkDeleteCollectionsDialog({
  open,
  onOpenChange,
  collections,
  onConfirm,
}: BulkDeleteCollectionsDialogProps) {
  const count = collections.length;
  const isMultiple = count > 1;

  if (count === 0) return null;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="sm:max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>
            Delete {isMultiple ? `${count} collections` : "collection"}
          </AlertDialogTitle>
          <AlertDialogDescription>
            This action cannot be undone.{" "}
            {isMultiple ? "These collections" : "This collection"} and all
            associated source connections, synced data, and configuration will
            be permanently deleted.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div
          className={`bg-muted my-4 rounded-lg border p-3 ${isMultiple ? "max-h-32 space-y-1 overflow-y-auto" : ""}`}
        >
          {collections.map((collection) => (
            <div key={collection.id} className="flex items-center gap-2">
              <span className="font-medium">{collection.name}</span>
              <code className="text-muted-foreground font-mono text-xs">
                {collection.readable_id}.airweave.ai
              </code>
            </div>
          ))}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive hover:bg-destructive/90 text-white"
            onClick={() => {
              onConfirm();
              onOpenChange(false);
            }}
          >
            Delete {isMultiple ? "collections" : "collection"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
