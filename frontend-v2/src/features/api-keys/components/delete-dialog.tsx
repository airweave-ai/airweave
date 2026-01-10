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
import type { APIKey } from "@/lib/api";

import { maskKey } from "../utils/helpers";

interface DeleteApiKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  keys: APIKey[];
  onConfirm: () => void;
}

/**
 * Reusable delete confirmation dialog for API keys.
 * Handles both single and bulk deletion with appropriate messaging.
 */
export function DeleteApiKeyDialog({
  open,
  onOpenChange,
  keys,
  onConfirm,
}: DeleteApiKeyDialogProps) {
  const count = keys.length;
  const isMultiple = count > 1;

  if (count === 0) return null;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="sm:max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>
            Delete {isMultiple ? `${count} API keys` : "API key"}
          </AlertDialogTitle>
          <AlertDialogDescription>
            This action cannot be undone. Any applications using{" "}
            {isMultiple ? "these keys" : "this key"} will lose access
            immediately.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div
          className={`bg-muted my-4 rounded-lg border p-3 ${isMultiple ? "max-h-32 space-y-1 overflow-y-auto" : ""}`}
        >
          {keys.map((key) => (
            <code key={key.id} className="block font-mono text-sm">
              {maskKey(key.decrypted_key)}
            </code>
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
            Delete {isMultiple ? "keys" : "key"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
