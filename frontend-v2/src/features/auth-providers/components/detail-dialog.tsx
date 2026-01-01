import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  Copy,
  Link,
  Loader2,
  Pencil,
  Trash,
} from "lucide-react";
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
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  deleteAuthProviderConnection,
  fetchAuthProviderConnection,
  type AuthProvider,
  type AuthProviderConnection,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { cn } from "@/lib/utils";
import { useIsDark } from "@/hooks/use-is-dark";

import { formatDate, getAuthProviderIconUrl } from "../utils/helpers";

interface DetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  authProvider: AuthProvider | null;
  connection: AuthProviderConnection | null;
  onEdit?: () => void;
}

export function DetailDialog({
  open,
  onOpenChange,
  authProvider,
  connection,
  onEdit,
}: DetailDialogProps) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();

  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [confirmText, setConfirmText] = useState("");

  const isDark = useIsDark();

  // Fetch connection details
  const { data: connectionDetails, isLoading } = useQuery({
    queryKey: ["auth-provider-connection", connection?.readable_id],
    queryFn: async () => {
      if (!connection?.readable_id) return null;
      const token = await getAccessTokenSilently();
      return fetchAuthProviderConnection(token, connection.readable_id);
    },
    enabled: open && !!connection?.readable_id,
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!connection?.readable_id) return;
      const token = await getAccessTokenSilently();
      return deleteAuthProviderConnection(token, connection.readable_id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["auth-provider-connections"],
      });
      toast.success("Auth provider connection deleted successfully");
      setShowDeleteDialog(false);
      setConfirmText("");
      onOpenChange(false);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const handleCopy = async (value: string, fieldName: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(fieldName);
      toast.success(`${fieldName} copied to clipboard`);
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      toast.error("Failed to copy to clipboard");
    }
  };

  const handleDeleteConfirm = () => {
    if (confirmText !== connectionDetails?.readable_id) return;
    deleteMutation.mutate();
  };

  const handleClose = (newOpen: boolean) => {
    if (!newOpen) {
      setCopiedField(null);
    }
    onOpenChange(newOpen);
  };

  if (!authProvider || !connection) return null;

  const isConfirmValid = confirmText === connectionDetails?.readable_id;

  return (
    <>
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="flex max-h-[90vh] flex-col overflow-hidden sm:max-w-lg">
          <DialogHeader className="flex flex-row items-start justify-between space-y-0">
            <div>
              <DialogTitle>{authProvider.name} Connection</DialogTitle>
              <DialogDescription>
                View and manage your {authProvider.name} connection details
              </DialogDescription>
            </div>
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={onEdit}
                title="Edit connection"
              >
                <Pencil className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="hover:text-destructive h-8 w-8"
                onClick={() => setShowDeleteDialog(true)}
                title="Delete connection"
              >
                <Trash className="h-4 w-4" />
              </Button>
            </div>
          </DialogHeader>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
            </div>
          ) : connectionDetails ? (
            <div className="flex-1 space-y-6 overflow-y-auto py-4">
              {/* Connected Animation */}
              <div className="flex justify-center py-4">
                <div className="flex items-center gap-8">
                  {/* Airweave Logo */}
                  <div className="relative">
                    <div
                      className={cn(
                        "flex h-14 w-14 items-center justify-center rounded-xl p-2.5",
                        "shadow-lg ring-2 ring-green-400/30",
                        "bg-card"
                      )}
                    >
                      <img
                        src={
                          isDark
                            ? "/airweave-logo-svg-white-darkbg.svg"
                            : "/airweave-logo-svg-lightbg-blacklogo.svg"
                        }
                        alt="Airweave"
                        className="h-full w-full object-contain"
                      />
                    </div>
                    {/* Connection icon */}
                    <div className="absolute -right-1 -bottom-1">
                      <div
                        className={cn(
                          "flex h-5 w-5 items-center justify-center rounded-full border-2",
                          "bg-background border-green-500"
                        )}
                      >
                        <Link className="h-2.5 w-2.5 text-green-500" />
                      </div>
                    </div>
                  </div>

                  {/* Active Connection text */}
                  <span className="text-sm font-medium text-green-600 dark:text-green-400">
                    Active Connection
                  </span>

                  {/* Auth Provider Logo */}
                  <div className="relative">
                    <div
                      className={cn(
                        "flex h-14 w-14 items-center justify-center rounded-xl p-2.5",
                        "shadow-lg ring-2 ring-green-400/30",
                        "bg-card"
                      )}
                    >
                      <img
                        src={getAuthProviderIconUrl(
                          authProvider.short_name,
                          isDark ? "dark" : "light"
                        )}
                        alt={authProvider.name}
                        className="h-full w-full object-contain"
                      />
                    </div>
                    {/* Connection icon */}
                    <div className="absolute -right-1 -bottom-1">
                      <div
                        className={cn(
                          "flex h-5 w-5 items-center justify-center rounded-full border-2",
                          "bg-background border-green-500"
                        )}
                      >
                        <Link className="h-2.5 w-2.5 text-green-500" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Connection Details */}
              <div className="space-y-4">
                {/* Name */}
                <div className="space-y-1.5">
                  <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
                    Name
                  </label>
                  <div className="bg-muted/50 rounded-md border px-3 py-2 text-sm">
                    {connectionDetails.name}
                  </div>
                </div>

                {/* Readable ID */}
                <div className="space-y-1.5">
                  <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
                    Readable ID
                  </label>
                  <div className="bg-muted/50 group flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                    <span className="font-mono break-all">
                      {connectionDetails.readable_id}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 transition-opacity group-hover:opacity-100"
                      onClick={() =>
                        handleCopy(connectionDetails.readable_id, "Readable ID")
                      }
                    >
                      {copiedField === "Readable ID" ? (
                        <Check className="h-3.5 w-3.5 text-green-500" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Created By */}
                {connectionDetails.created_by_email && (
                  <div className="space-y-1.5">
                    <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
                      Created By
                    </label>
                    <div className="bg-muted/50 rounded-md border px-3 py-2 text-sm">
                      {connectionDetails.created_by_email}
                    </div>
                  </div>
                )}

                {/* Created At */}
                <div className="space-y-1.5">
                  <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
                    Created At
                  </label>
                  <div className="bg-muted/50 rounded-md border px-3 py-2 text-sm">
                    {formatDate(connectionDetails.created_at)}
                  </div>
                </div>

                {/* Modified At */}
                <div className="space-y-1.5">
                  <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
                    Modified At
                  </label>
                  <div className="bg-muted/50 rounded-md border px-3 py-2 text-sm">
                    {formatDate(connectionDetails.modified_at)}
                  </div>
                </div>

                {/* Client ID (if available) */}
                {connectionDetails.masked_client_id && (
                  <div className="space-y-1.5">
                    <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
                      Client ID
                    </label>
                    <div className="bg-muted/50 group flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                      <span className="font-mono">
                        {connectionDetails.masked_client_id}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 opacity-0 transition-opacity group-hover:opacity-100"
                        onClick={() =>
                          handleCopy(
                            connectionDetails.masked_client_id!,
                            "Client ID"
                          )
                        }
                      >
                        {copiedField === "Client ID" ? (
                          <Check className="h-3.5 w-3.5 text-green-500" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-muted-foreground py-8 text-center">
              No connection details available
            </div>
          )}

          <DialogFooter className="border-t pt-4">
            <Button
              variant="outline"
              onClick={() => handleClose(false)}
              className="w-full"
            >
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="sm:max-w-md">
          <AlertDialogHeader className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="bg-destructive/10 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full">
                <AlertTriangle className="text-destructive h-5 w-5" />
              </div>
              <div>
                <AlertDialogTitle>
                  Delete Auth Provider Connection
                </AlertDialogTitle>
                <p className="text-muted-foreground mt-1 text-sm">
                  This action cannot be undone
                </p>
              </div>
            </div>

            <AlertDialogDescription asChild>
              <div className="space-y-4">
                <div className="bg-destructive/5 border-destructive/20 rounded-lg border p-4">
                  <p className="text-foreground mb-3 font-medium">
                    This will permanently delete:
                  </p>
                  <ul className="text-muted-foreground space-y-2 text-sm">
                    <li className="flex items-start gap-2">
                      <div className="bg-destructive/60 mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full" />
                      <span>This auth provider connection</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <div className="bg-destructive/60 mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full" />
                      <span>
                        All source connections using this auth provider
                      </span>
                    </li>
                    <li className="flex items-start gap-2">
                      <div className="bg-destructive/60 mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full" />
                      <span>All associated sync configurations and data</span>
                    </li>
                  </ul>
                </div>

                {/* Critical warning */}
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/20">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600 dark:text-amber-400" />
                    <div className="text-sm">
                      <p className="mb-1 font-medium text-amber-800 dark:text-amber-200">
                        Critical Impact
                      </p>
                      <p className="text-amber-700 dark:text-amber-300">
                        Source connections will stop working immediately and
                        cannot be recovered.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Confirmation input */}
                <div className="space-y-3">
                  <div>
                    <label
                      htmlFor="confirm-delete"
                      className="text-foreground mb-2 block text-sm font-medium"
                    >
                      Type{" "}
                      <span className="text-destructive bg-destructive/10 rounded px-1.5 py-0.5 font-mono font-semibold">
                        {connectionDetails?.readable_id}
                      </span>{" "}
                      to confirm deletion
                    </label>
                    <Input
                      id="confirm-delete"
                      value={confirmText}
                      onChange={(e) => setConfirmText(e.target.value)}
                      disabled={deleteMutation.isPending}
                      className={cn(
                        "transition-colors",
                        isConfirmValid && confirmText.length > 0
                          ? "border-green-500 focus-visible:ring-green-500/20"
                          : confirmText.length > 0
                            ? "border-destructive focus-visible:ring-destructive/20"
                            : ""
                      )}
                      placeholder={connectionDetails?.readable_id}
                    />
                  </div>

                  {/* Validation feedback */}
                  {confirmText.length > 0 && !deleteMutation.isPending && (
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
              disabled={deleteMutation.isPending}
              onClick={() => {
                setConfirmText("");
              }}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={!isConfirmValid || deleteMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash className="mr-2 h-4 w-4" />
                  Delete Connection
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
