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
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
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
                className="h-8 w-8 hover:text-destructive"
                onClick={() => setShowDeleteDialog(true)}
                title="Delete connection"
              >
                <Trash className="h-4 w-4" />
              </Button>
            </div>
          </DialogHeader>

          {isLoading ? (
            <div className="flex justify-center items-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : connectionDetails ? (
            <div className="flex-1 overflow-y-auto space-y-6 py-4">
              {/* Connected Animation */}
              <div className="flex justify-center py-4">
                <div className="flex items-center gap-8">
                  {/* Airweave Logo */}
                  <div className="relative">
                    <div
                      className={cn(
                        "w-14 h-14 rounded-xl flex items-center justify-center p-2.5",
                        "shadow-lg ring-2 ring-green-400/30",
                        "bg-card",
                      )}
                    >
                      <img
                        src={
                          isDark
                            ? "/airweave-logo-svg-white-darkbg.svg"
                            : "/airweave-logo-svg-lightbg-blacklogo.svg"
                        }
                        alt="Airweave"
                        className="w-full h-full object-contain"
                      />
                    </div>
                    {/* Connection icon */}
                    <div className="absolute -bottom-1 -right-1">
                      <div
                        className={cn(
                          "w-5 h-5 rounded-full flex items-center justify-center border-2",
                          "border-green-500 bg-background",
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
                        "w-14 h-14 rounded-xl flex items-center justify-center p-2.5",
                        "shadow-lg ring-2 ring-green-400/30",
                        "bg-card",
                      )}
                    >
                      <img
                        src={getAuthProviderIconUrl(
                          authProvider.short_name,
                          isDark ? "dark" : "light",
                        )}
                        alt={authProvider.name}
                        className="w-full h-full object-contain"
                      />
                    </div>
                    {/* Connection icon */}
                    <div className="absolute -bottom-1 -right-1">
                      <div
                        className={cn(
                          "w-5 h-5 rounded-full flex items-center justify-center border-2",
                          "border-green-500 bg-background",
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
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Name
                  </label>
                  <div className="px-3 py-2 rounded-md border bg-muted/50 text-sm">
                    {connectionDetails.name}
                  </div>
                </div>

                {/* Readable ID */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Readable ID
                  </label>
                  <div className="px-3 py-2 rounded-md border bg-muted/50 text-sm flex items-center justify-between group">
                    <span className="font-mono break-all">
                      {connectionDetails.readable_id}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
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
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Created By
                    </label>
                    <div className="px-3 py-2 rounded-md border bg-muted/50 text-sm">
                      {connectionDetails.created_by_email}
                    </div>
                  </div>
                )}

                {/* Created At */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Created At
                  </label>
                  <div className="px-3 py-2 rounded-md border bg-muted/50 text-sm">
                    {formatDate(connectionDetails.created_at)}
                  </div>
                </div>

                {/* Modified At */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Modified At
                  </label>
                  <div className="px-3 py-2 rounded-md border bg-muted/50 text-sm">
                    {formatDate(connectionDetails.modified_at)}
                  </div>
                </div>

                {/* Client ID (if available) */}
                {connectionDetails.masked_client_id && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Client ID
                    </label>
                    <div className="px-3 py-2 rounded-md border bg-muted/50 text-sm flex items-center justify-between group">
                      <span className="font-mono">
                        {connectionDetails.masked_client_id}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() =>
                          handleCopy(
                            connectionDetails.masked_client_id!,
                            "Client ID",
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
            <div className="text-center py-8 text-muted-foreground">
              No connection details available
            </div>
          )}

          <DialogFooter className="pt-4 border-t">
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
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-destructive" />
              </div>
              <div>
                <AlertDialogTitle>
                  Delete Auth Provider Connection
                </AlertDialogTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  This action cannot be undone
                </p>
              </div>
            </div>

            <AlertDialogDescription asChild>
              <div className="space-y-4">
                <div className="bg-destructive/5 border border-destructive/20 rounded-lg p-4">
                  <p className="font-medium text-foreground mb-3">
                    This will permanently delete:
                  </p>
                  <ul className="space-y-2 text-sm text-muted-foreground">
                    <li className="flex items-start gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                      <span>This auth provider connection</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                      <span>
                        All source connections using this auth provider
                      </span>
                    </li>
                    <li className="flex items-start gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                      <span>All associated sync configurations and data</span>
                    </li>
                  </ul>
                </div>

                {/* Critical warning */}
                <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
                    <div className="text-sm">
                      <p className="font-medium text-amber-800 dark:text-amber-200 mb-1">
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
                      className="text-sm font-medium text-foreground block mb-2"
                    >
                      Type{" "}
                      <span className="font-mono font-semibold text-destructive bg-destructive/10 px-1.5 py-0.5 rounded">
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
                            : "",
                      )}
                      placeholder={connectionDetails?.readable_id}
                    />
                  </div>

                  {/* Validation feedback */}
                  {confirmText.length > 0 && !deleteMutation.isPending && (
                    <div className="flex items-center gap-2 text-sm">
                      {isConfirmValid ? (
                        <>
                          <Check className="w-4 h-4 text-green-500" />
                          <span className="text-green-600 dark:text-green-400">
                            Confirmation matches
                          </span>
                        </>
                      ) : (
                        <>
                          <AlertCircle className="w-4 h-4 text-destructive" />
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
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash className="w-4 h-4 mr-2" />
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
