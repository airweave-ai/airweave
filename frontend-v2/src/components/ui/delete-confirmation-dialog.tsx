import {
  AlertCircle,
  AlertTriangle,
  Check,
  Loader2,
  Trash,
} from "lucide-react";
import { useState } from "react";

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

interface DeleteConfirmationDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** The title of the dialog */
  title: string;
  /** The value the user must type to confirm deletion */
  confirmValue: string;
  /** Callback when delete is confirmed */
  onConfirm: () => void;
  /** Whether the delete action is in progress */
  isDeleting?: boolean;
  /** List of items that will be deleted */
  deletedItems?: string[];
  /** Critical warning message */
  criticalWarning?: {
    title: string;
    description: string;
  };
  /** Text for the delete button (default: "Delete") */
  deleteButtonText?: string;
}

/**
 * Reusable delete confirmation dialog with type-to-confirm validation.
 * Shows a destructive warning with list of affected items and requires
 * the user to type a confirmation value before deletion.
 */
export function DeleteConfirmationDialog({
  open,
  onOpenChange,
  title,
  confirmValue,
  onConfirm,
  isDeleting = false,
  deletedItems = [],
  criticalWarning,
  deleteButtonText = "Delete",
}: DeleteConfirmationDialogProps) {
  const [confirmText, setConfirmText] = useState("");

  const isConfirmValid = confirmText === confirmValue;

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      setConfirmText("");
    }
    onOpenChange(newOpen);
  };

  const handleConfirm = () => {
    if (!isConfirmValid) return;
    onConfirm();
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent className="sm:max-w-md">
        <AlertDialogHeader className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="bg-destructive/10 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full">
              <AlertTriangle className="text-destructive h-5 w-5" />
            </div>
            <div>
              <AlertDialogTitle>{title}</AlertDialogTitle>
              <p className="text-muted-foreground mt-1 text-sm">
                This action cannot be undone
              </p>
            </div>
          </div>

          <AlertDialogDescription asChild>
            <div className="space-y-4">
              {deletedItems.length > 0 && (
                <div className="bg-destructive/5 border-destructive/20 rounded-lg border p-4">
                  <p className="text-foreground mb-3 font-medium">
                    This will permanently delete:
                  </p>
                  <ul className="text-muted-foreground space-y-2 text-sm">
                    {deletedItems.map((item, index) => (
                      <li key={index} className="flex items-start gap-2">
                        <div className="bg-destructive/60 mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {criticalWarning && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/20">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600 dark:text-amber-400" />
                    <div className="text-sm">
                      <p className="mb-1 font-medium text-amber-800 dark:text-amber-200">
                        {criticalWarning.title}
                      </p>
                      <p className="text-amber-700 dark:text-amber-300">
                        {criticalWarning.description}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <div className="space-y-3">
                <div>
                  <label
                    htmlFor="confirm-delete"
                    className="text-foreground mb-2 block text-sm font-medium"
                  >
                    Type{" "}
                    <span className="text-destructive bg-destructive/10 rounded px-1.5 py-0.5 font-mono font-semibold">
                      {confirmValue}
                    </span>{" "}
                    to confirm deletion
                  </label>
                  <Input
                    id="confirm-delete"
                    value={confirmText}
                    onChange={(e) => setConfirmText(e.target.value)}
                    disabled={isDeleting}
                    className={cn(
                      "transition-colors",
                      isConfirmValid && confirmText.length > 0
                        ? "border-green-500 focus-visible:ring-green-500/20"
                        : confirmText.length > 0
                          ? "border-destructive focus-visible:ring-destructive/20"
                          : ""
                    )}
                    placeholder={confirmValue}
                  />
                </div>

                {confirmText.length > 0 && !isDeleting && (
                  <div className="flex items-center gap-2 text-sm">
                    {isConfirmValid ? (
                      <>
                        <Check className="h-4 w-4 text-green-500" />
                        <span className="text-green-600 dark:text-green-400">
                          Confirmation matches
                        </span>
                      </>
                    ) : (
                      <>
                        <AlertCircle className="text-destructive h-4 w-4" />
                        <span className="text-destructive">
                          Confirmation does not match
                        </span>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter className="gap-3">
          <AlertDialogCancel
            disabled={isDeleting}
            onClick={() => setConfirmText("")}
          >
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={!isConfirmValid || isDeleting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isDeleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deleting...
              </>
            ) : (
              <>
                <Trash className="mr-2 h-4 w-4" />
                {deleteButtonText}
              </>
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
