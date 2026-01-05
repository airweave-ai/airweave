/**
 * DeleteCollectionDialog - Confirmation dialog for deleting a collection
 */

import {
  AlertCircle,
  AlertTriangle,
  Check,
  Loader2,
  Trash,
} from "lucide-react";
import { useEffect, useState } from "react";

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
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface DeleteCollectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  collectionReadableId: string;
  isDeleting: boolean;
}

export function DeleteCollectionDialog({
  open,
  onOpenChange,
  onConfirm,
  collectionReadableId,
  isDeleting,
}: DeleteCollectionDialogProps) {
  const [confirmText, setConfirmText] = useState("");
  const isConfirmValid = confirmText === collectionReadableId;

  useEffect(() => {
    if (!open) {
      setConfirmText("");
    }
  }, [open]);

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="bg-destructive/10 flex size-10 flex-shrink-0 items-center justify-center rounded-full">
              <AlertTriangle className="text-destructive size-5" />
            </div>
            <div>
              <AlertDialogTitle className="text-foreground text-lg font-semibold">
                Delete Collection
              </AlertDialogTitle>
              <p className="text-muted-foreground mt-1 text-sm">
                This action cannot be undone
              </p>
            </div>
          </div>

          <AlertDialogDescription className="space-y-4">
            <div className="bg-destructive/5 border-destructive/20 rounded-lg border p-4">
              <p className="text-foreground mb-3 font-medium">
                This will permanently delete:
              </p>
              <ul className="text-muted-foreground space-y-2 text-sm">
                <li className="flex items-start gap-2">
                  <div className="bg-destructive/60 mt-2 size-1.5 flex-shrink-0 rounded-full" />
                  <span>The collection and all its source connections</span>
                </li>
                <li className="flex items-start gap-2">
                  <div className="bg-destructive/60 mt-2 size-1.5 flex-shrink-0 rounded-full" />
                  <span>All synced data from the knowledge base</span>
                </li>
                <li className="flex items-start gap-2">
                  <div className="bg-destructive/60 mt-2 size-1.5 flex-shrink-0 rounded-full" />
                  <span>All sync history and configuration</span>
                </li>
              </ul>
            </div>

            <div className="space-y-3">
              <div>
                <label
                  htmlFor="confirm-delete"
                  className="text-foreground mb-2 block text-sm font-medium"
                >
                  Type{" "}
                  <span className="bg-destructive/10 text-destructive rounded px-1.5 py-0.5 font-mono font-semibold">
                    {collectionReadableId}
                  </span>{" "}
                  to confirm deletion
                </label>
                <Input
                  id="confirm-delete"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  className={cn(
                    "w-full transition-colors",
                    isConfirmValid && confirmText.length > 0
                      ? "border-green-500 focus:border-green-500 focus:ring-green-500/20"
                      : confirmText.length > 0
                        ? "border-destructive focus:border-destructive focus:ring-destructive/20"
                        : ""
                  )}
                  placeholder={collectionReadableId}
                />
              </div>

              {confirmText.length > 0 && (
                <div className="flex items-center gap-2 text-sm">
                  {isConfirmValid ? (
                    <>
                      <Check className="size-4 text-green-500" />
                      <span className="text-green-600 dark:text-green-400">
                        Confirmation matches
                      </span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="text-destructive size-4" />
                      <span className="text-destructive">
                        Confirmation does not match
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter className="gap-3">
          <AlertDialogCancel className="flex-1">Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={!isConfirmValid || isDeleting}
            className={cn(
              "bg-destructive text-destructive-foreground hover:bg-destructive/90 flex-1",
              "disabled:cursor-not-allowed disabled:opacity-50",
              "transition-all duration-200"
            )}
          >
            {isDeleting ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <Trash className="mr-2 size-4" />
            )}
            Delete Collection
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
