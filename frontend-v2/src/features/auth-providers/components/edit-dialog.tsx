import { useForm } from "@tanstack/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

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
import { useIsDark } from "@/hooks/use-is-dark";
import {
  fetchAuthProviderConnection,
  fetchAuthProviderDetail,
  updateAuthProviderConnection,
  type AuthProvider,
  type AuthProviderConnection,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

import { getAuthProviderIconUrl } from "../utils/helpers";

interface EditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  authProvider: AuthProvider | null;
  connection: AuthProviderConnection | null;
  onSuccess?: () => void;
  orgId: string;
}

export function EditDialog({
  open,
  onOpenChange,
  authProvider,
  connection,
  onSuccess,
  orgId,
}: EditDialogProps) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const isDark = useIsDark();

  // Fetch connection details
  const { data: connectionDetails, isLoading: isLoadingConnection } = useQuery({
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

  // Fetch auth provider details for auth fields
  const { data: providerDetails, isLoading: isLoadingProvider } = useQuery({
    queryKey: queryKeys.authProviders.detail(
      orgId,
      authProvider?.short_name ?? ""
    ),
    queryFn: async () => {
      if (!authProvider?.short_name) return null;
      const token = await getAccessTokenSilently();
      return fetchAuthProviderDetail(token, orgId, authProvider.short_name);
    },
    enabled: open && !!authProvider?.short_name,
  });

  const isLoading = isLoadingConnection || isLoadingProvider;

  if (!authProvider || !connection) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] flex-col overflow-hidden sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit {authProvider.name} Connection</DialogTitle>
          <DialogDescription>
            Update your connection details. Leave fields empty to keep current
            values.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
          </div>
        ) : (
          // Use key to reset form when connection changes
          <EditDialogForm
            key={connection.readable_id}
            authProvider={authProvider}
            connection={connection}
            connectionDetails={connectionDetails}
            providerDetails={providerDetails}
            orgId={orgId}
            isDark={isDark}
            queryClient={queryClient}
            getAccessTokenSilently={getAccessTokenSilently}
            onOpenChange={onOpenChange}
            onSuccess={onSuccess}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

// Separate form component that resets when key changes
function EditDialogForm({
  authProvider,
  connection,
  connectionDetails,
  providerDetails,
  orgId,
  isDark,
  queryClient,
  getAccessTokenSilently,
  onOpenChange,
  onSuccess,
}: {
  authProvider: AuthProvider;
  connection: AuthProviderConnection;
  connectionDetails:
    | Awaited<ReturnType<typeof fetchAuthProviderConnection>>
    | null
    | undefined;
  providerDetails:
    | Awaited<ReturnType<typeof fetchAuthProviderDetail>>
    | null
    | undefined;
  orgId: string;
  isDark: boolean;
  queryClient: ReturnType<typeof useQueryClient>;
  getAccessTokenSilently: () => Promise<string>;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}) {
  // Form setup with default values from fetched data
  const form = useForm({
    defaultValues: {
      name: connectionDetails?.name ?? "",
      authFields: {} as Record<string, string>,
    },
    onSubmit: async ({ value }) => {
      updateMutation.mutate(value);
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async (values: {
      name: string;
      authFields: Record<string, string>;
    }) => {
      if (!connection?.readable_id) throw new Error("No connection ID");

      const token = await getAccessTokenSilently();

      // Build update payload - only include fields that have values
      const updateData: {
        name?: string;
        auth_fields?: Record<string, string>;
      } = {};

      // Include name only if it changed
      if (values.name && values.name !== connectionDetails?.name) {
        updateData.name = values.name;
      }

      // Include auth_fields only if any field has a value
      const filledAuthFields = Object.entries(values.authFields)
        .filter(([, value]) => value && String(value).trim() !== "")
        .reduce(
          (acc, [key, value]) => ({ ...acc, [key]: value }),
          {} as Record<string, string>
        );

      if (Object.keys(filledAuthFields).length > 0) {
        updateData.auth_fields = filledAuthFields;
      }

      // If nothing to update, just return the current connection
      if (Object.keys(updateData).length === 0) {
        return null;
      }

      return updateAuthProviderConnection(
        token,
        orgId,
        connection.readable_id,
        updateData
      );
    },
    onSuccess: (result) => {
      if (result === null) {
        toast.info("No changes to update");
        onOpenChange(false);
        return;
      }

      queryClient.invalidateQueries({
        queryKey: queryKeys.authProviders.connections(orgId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.authProviders.connection(
          orgId,
          connection?.readable_id ?? ""
        ),
      });
      toast.success(`Successfully updated ${authProvider?.name} connection`);
      onOpenChange(false);
      form.reset();
      onSuccess?.();
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  // Handle auth field change
  const handleAuthFieldChange = (fieldName: string, value: string) => {
    const currentFields = form.getFieldValue("authFields");
    form.setFieldValue("authFields", { ...currentFields, [fieldName]: value });
  };

  const handleClose = () => {
    form.reset();
    onOpenChange(false);
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        form.handleSubmit();
      }}
      className="flex flex-1 flex-col overflow-hidden"
    >
      <div className="flex-1 space-y-6 overflow-y-auto py-4">
        {/* Auth Provider Icon */}
        <div className="flex justify-center py-4">
          <div
            className={cn(
              "flex h-20 w-20 items-center justify-center rounded-xl p-3",
              "border shadow-sm",
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
        </div>

        {/* Name field */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Name</label>
          <form.Field name="name">
            {(field) => (
              <Input
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
                placeholder={connectionDetails?.name || "Connection name"}
              />
            )}
          </form.Field>
        </div>

        {/* Auth fields */}
        {providerDetails?.auth_fields?.fields &&
          providerDetails.auth_fields.fields.length > 0 && (
            <div className="space-y-4 pt-2">
              <p className="text-muted-foreground text-sm">
                Update authentication credentials (leave empty to keep current
                values)
              </p>

              {providerDetails.auth_fields.fields.map((field) => (
                <div key={field.name} className="space-y-2">
                  <label className="text-sm font-medium">
                    {field.title || field.name}
                  </label>
                  {field.description && (
                    <p className="text-muted-foreground text-xs">
                      {field.description}
                    </p>
                  )}
                  <form.Field name="authFields">
                    {() => (
                      <Input
                        type={field.secret ? "password" : "text"}
                        value={
                          form.getFieldValue("authFields")[field.name] || ""
                        }
                        onChange={(e) =>
                          handleAuthFieldChange(field.name, e.target.value)
                        }
                        placeholder={
                          field.secret
                            ? "••••••••"
                            : `Enter new ${field.title || field.name}`
                        }
                      />
                    )}
                  </form.Field>
                </div>
              ))}
            </div>
          )}
      </div>

      <DialogFooter className="border-t pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={handleClose}
          disabled={updateMutation.isPending}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={updateMutation.isPending}>
          {updateMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Updating...
            </>
          ) : (
            "Update"
          )}
        </Button>
      </DialogFooter>
    </form>
  );
}
