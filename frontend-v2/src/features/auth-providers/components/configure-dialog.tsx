/**
 * ConfigureDialog - Create a new auth provider connection
 */

import { useForm } from "@tanstack/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ApiForm } from "@/components/ui/api-form";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  createAuthProviderConnection,
  fetchAuthProviderDetail,
  type AuthProvider,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { queryKeys } from "@/lib/query-keys";

import { generateRandomSuffix, generateReadableId } from "../utils/helpers";
import { AuthFieldsForm } from "./auth-fields-form";
import { ConnectionPreview } from "./connection-preview";

interface ConfigureDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  authProvider: AuthProvider | null;
  onSuccess?: (connectionId: string) => void;
  orgId: string;
}

export function ConfigureDialog({
  open,
  onOpenChange,
  authProvider,
  onSuccess,
  orgId,
}: ConfigureDialogProps) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();

  // Generate a random suffix once per dialog open
  // eslint-disable-next-line react-hooks/exhaustive-deps -- Intentionally regenerate when dialog opens
  const randomSuffix = useMemo(() => generateRandomSuffix(), [open]);

  const [userEditedId, setUserEditedId] = useState(false);

  const defaultName = authProvider
    ? `My ${authProvider.name} Connection`
    : "My Connection";

  // Fetch auth provider details for auth fields
  const { data: providerDetails, isLoading: isLoadingDetails } = useQuery({
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

  // Form setup
  const form = useForm({
    defaultValues: {
      name: defaultName,
      readableId: generateReadableId(defaultName, randomSuffix),
      authFields: {} as Record<string, string>,
    },
    onSubmit: async ({ value }) => {
      createMutation.mutate(value);
    },
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: async (values: {
      name: string;
      readableId: string;
      authFields: Record<string, string>;
    }) => {
      const token = await getAccessTokenSilently();
      return createAuthProviderConnection(token, orgId, {
        name: values.name,
        readable_id: values.readableId,
        short_name: authProvider?.short_name || "",
        auth_fields: values.authFields,
      });
    },
    onSuccess: (connection) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.authProviders.connections(orgId),
      });
      toast.success(`Successfully connected to ${authProvider?.name}`, {
        description: "Your connection is now active and ready to use.",
      });
      onOpenChange(false);
      form.reset();
      setUserEditedId(false);
      onSuccess?.(connection.readable_id);
    },
    onError: (error: Error) => {
      toast.error("Connection Failed", {
        description: error.message,
      });
    },
  });

  const handleNameChange = (newName: string) => {
    form.setFieldValue("name", newName);
    if (!userEditedId) {
      form.setFieldValue(
        "readableId",
        generateReadableId(newName, randomSuffix)
      );
    }
  };

  const handleReadableIdChange = (newId: string) => {
    form.setFieldValue("readableId", newId);
    setUserEditedId(true);
  };

  const handleAuthFieldChange = (fieldName: string, value: string) => {
    const currentFields = form.getFieldValue("authFields");
    form.setFieldValue("authFields", { ...currentFields, [fieldName]: value });
  };

  const isFormValid = () => {
    const name = form.getFieldValue("name");
    const authFields = form.getFieldValue("authFields");

    if (!name || name.trim() === "") return false;

    if (providerDetails?.auth_fields?.fields) {
      for (const field of providerDetails.auth_fields.fields) {
        if (!authFields[field.name] || authFields[field.name].trim() === "") {
          return false;
        }
      }
    }

    return true;
  };

  const handleClose = (newOpen: boolean) => {
    if (!newOpen) {
      form.reset();
      setUserEditedId(false);
    }
    onOpenChange(newOpen);
  };

  if (!authProvider) return null;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="flex max-h-[90vh] flex-col overflow-hidden sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Connect to {authProvider.name}</DialogTitle>
          <DialogDescription>
            Create a connection to {authProvider.name} that can be used to
            authenticate to data sources
          </DialogDescription>
        </DialogHeader>

        {isLoadingDetails ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              form.handleSubmit();
            }}
            className="flex flex-1 flex-col overflow-hidden"
          >
            <ApiForm
              method="POST"
              endpoint="https://api.airweave.ai/auth-providers/"
              className="flex flex-1 flex-col overflow-hidden"
              body={{
                name: form.getFieldValue("name"),
                readable_id: form.getFieldValue("readableId"),
                short_name: authProvider.short_name,
                auth_fields: form.getFieldValue("authFields"),
              }}
              onBodyChange={(newBody) => {
                if (typeof newBody.name === "string") {
                  form.setFieldValue("name", newBody.name);
                }
                if (typeof newBody.readable_id === "string") {
                  form.setFieldValue("readableId", newBody.readable_id);
                  setUserEditedId(true);
                }
                if (
                  newBody.auth_fields &&
                  typeof newBody.auth_fields === "object"
                ) {
                  form.setFieldValue(
                    "authFields",
                    newBody.auth_fields as Record<string, string>
                  );
                }
              }}
            >
              <ApiForm.Toggle />

              <ApiForm.FormView className="flex-1 space-y-6 overflow-y-auto">
                <ConnectionPreview
                  providerShortName={authProvider.short_name}
                  providerName={authProvider.name}
                  status="pending"
                />

                {/* Name field */}
                <div className="space-y-2">
                  <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
                    Name
                  </label>
                  <form.Field name="name">
                    {(field) => (
                      <Input
                        value={field.state.value}
                        onChange={(e) => handleNameChange(e.target.value)}
                        placeholder="My Connection"
                      />
                    )}
                  </form.Field>
                </div>

                {/* Readable ID field */}
                <div className="space-y-2">
                  <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
                    Readable ID
                  </label>
                  <form.Field name="readableId">
                    {(field) => (
                      <Input
                        value={field.state.value}
                        onChange={(e) => handleReadableIdChange(e.target.value)}
                        placeholder="Auto-generated"
                        className="font-mono text-sm"
                      />
                    )}
                  </form.Field>
                </div>

                {/* Auth fields */}
                {providerDetails?.auth_fields?.fields && (
                  <AuthFieldsForm
                    providerShortName={authProvider.short_name}
                    fields={providerDetails.auth_fields.fields}
                    values={form.getFieldValue("authFields")}
                    onChange={handleAuthFieldChange}
                  />
                )}
              </ApiForm.FormView>

              <ApiForm.CodeView editable className="flex-1 overflow-y-auto" />

              <ApiForm.Footer className="border-t pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => handleClose(false)}
                  disabled={createMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createMutation.isPending || !isFormValid()}
                >
                  {createMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    "Connect"
                  )}
                </Button>
              </ApiForm.Footer>
            </ApiForm>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
