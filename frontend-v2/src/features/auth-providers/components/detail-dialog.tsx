import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Link, Loader2, Pencil, Trash } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useIsDark } from "@/hooks/use-is-dark";
import {
  deleteAuthProviderConnection,
  fetchAuthProviderConnection,
  type AuthProvider,
  type AuthProviderConnection,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

import { formatDate, getAuthProviderIconUrl } from "../utils/helpers";

interface DetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  authProvider: AuthProvider | null;
  connection: AuthProviderConnection | null;
  onEdit?: () => void;
  orgId: string;
}

export function DetailDialog({
  open,
  onOpenChange,
  authProvider,
  connection,
  onEdit,
  orgId,
}: DetailDialogProps) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();

  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const isDark = useIsDark();

  // Fetch connection details
  const { data: connectionDetails, isLoading } = useQuery({
    queryKey: queryKeys.authProviders.connection(
      orgId,
      connection?.readable_id ?? ""
    ),
    queryFn: async () => {
      if (!connection?.readable_id) return null;
      const token = await getAccessTokenSilently();
      return fetchAuthProviderConnection(token, orgId, connection.readable_id);
    },
    enabled: open && !!connection?.readable_id,
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!connection?.readable_id) return;
      const token = await getAccessTokenSilently();
      return deleteAuthProviderConnection(token, orgId, connection.readable_id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.authProviders.connections(orgId),
      });
      toast.success("Auth provider connection deleted successfully");
      setShowDeleteDialog(false);
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

  const handleClose = (newOpen: boolean) => {
    if (!newOpen) {
      setCopiedField(null);
    }
    onOpenChange(newOpen);
  };

  if (!authProvider || !connection) return null;

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
                <DetailField label="Name" value={connectionDetails.name} />

                <DetailField
                  label="Readable ID"
                  value={connectionDetails.readable_id}
                  mono
                  copyable
                  onCopy={() =>
                    handleCopy(connectionDetails.readable_id, "Readable ID")
                  }
                  copied={copiedField === "Readable ID"}
                />

                {connectionDetails.created_by_email && (
                  <DetailField
                    label="Created By"
                    value={connectionDetails.created_by_email}
                  />
                )}

                <DetailField
                  label="Created At"
                  value={formatDate(connectionDetails.created_at)}
                />

                <DetailField
                  label="Modified At"
                  value={formatDate(connectionDetails.modified_at)}
                />

                {connectionDetails.masked_client_id && (
                  <DetailField
                    label="Client ID"
                    value={connectionDetails.masked_client_id}
                    mono
                    copyable
                    onCopy={() =>
                      handleCopy(
                        connectionDetails.masked_client_id!,
                        "Client ID"
                      )
                    }
                    copied={copiedField === "Client ID"}
                  />
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

      <DeleteConfirmationDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        title="Delete Auth Provider Connection"
        confirmValue={connectionDetails?.readable_id ?? ""}
        onConfirm={() => deleteMutation.mutate()}
        isDeleting={deleteMutation.isPending}
        deletedItems={[
          "This auth provider connection",
          "All source connections using this auth provider",
          "All associated sync configurations and data",
        ]}
        criticalWarning={{
          title: "Critical Impact",
          description:
            "Source connections will stop working immediately and cannot be recovered.",
        }}
        deleteButtonText="Delete Connection"
      />
    </>
  );
}

interface DetailFieldProps {
  label: string;
  value: string;
  mono?: boolean;
  copyable?: boolean;
  onCopy?: () => void;
  copied?: boolean;
}

function DetailField({
  label,
  value,
  mono,
  copyable,
  onCopy,
  copied,
}: DetailFieldProps) {
  return (
    <div className="space-y-1.5">
      <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
        {label}
      </label>
      <div
        className={cn(
          "bg-muted/50 rounded-md border px-3 py-2 text-sm",
          copyable && "group flex items-center justify-between"
        )}
      >
        <span className={cn(mono && "font-mono break-all")}>{value}</span>
        {copyable && onCopy && (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 opacity-0 transition-opacity group-hover:opacity-100"
            onClick={onCopy}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
