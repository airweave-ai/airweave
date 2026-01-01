import { useForm } from "@tanstack/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Loader2 } from "lucide-react";
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
import { useIsDark } from "@/hooks/use-is-dark";
import {
  createAuthProviderConnection,
  fetchAuthProviderDetail,
  type AuthProvider,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { cn } from "@/lib/utils";

import {
  generateRandomSuffix,
  generateReadableId,
  getAuthProviderIconUrl,
} from "../utils/helpers";

interface ConfigureDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  authProvider: AuthProvider | null;
  onSuccess?: (connectionId: string) => void;
}

export function ConfigureDialog({
  open,
  onOpenChange,
  authProvider,
  onSuccess,
}: ConfigureDialogProps) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();

  // Generate a random suffix once per dialog open
  const randomSuffix = useMemo(() => generateRandomSuffix(), [open]);

  // Track if user has manually edited the readable ID
  const [userEditedId, setUserEditedId] = useState(false);

  const isDark = useIsDark();

  // Default connection name
  const defaultName = authProvider
    ? `My ${authProvider.name} Connection`
    : "My Connection";

  // Fetch auth provider details for auth fields
  const { data: providerDetails, isLoading: isLoadingDetails } = useQuery({
    queryKey: ["auth-provider-detail", authProvider?.short_name],
    queryFn: async () => {
      if (!authProvider?.short_name) return null;
      const token = await getAccessTokenSilently();
      return fetchAuthProviderDetail(token, authProvider.short_name);
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
      return createAuthProviderConnection(token, {
        name: values.name,
        readable_id: values.readableId,
        short_name: authProvider?.short_name || "",
        auth_fields: values.authFields,
      });
    },
    onSuccess: (connection) => {
      queryClient.invalidateQueries({
        queryKey: ["auth-provider-connections"],
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

  // Handle name change and auto-generate readable ID
  const handleNameChange = (newName: string) => {
    form.setFieldValue("name", newName);
    if (!userEditedId) {
      form.setFieldValue(
        "readableId",
        generateReadableId(newName, randomSuffix),
      );
    }
  };

  // Handle readable ID change
  const handleReadableIdChange = (newId: string) => {
    form.setFieldValue("readableId", newId);
    setUserEditedId(true);
  };

  // Handle auth field change
  const handleAuthFieldChange = (fieldName: string, value: string) => {
    const currentFields = form.getFieldValue("authFields");
    form.setFieldValue("authFields", { ...currentFields, [fieldName]: value });
  };

  // Check if form is valid
  const isFormValid = () => {
    const name = form.getFieldValue("name");
    const authFields = form.getFieldValue("authFields");

    if (!name || name.trim() === "") return false;

    // Check all auth fields are filled
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
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Connect to {authProvider.name}</DialogTitle>
          <DialogDescription>
            Create a connection to {authProvider.name} that can be used to
            authenticate to data sources
          </DialogDescription>
        </DialogHeader>

        {isLoadingDetails ? (
          <div className="flex justify-center items-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              form.handleSubmit();
            }}
            className="flex flex-col flex-1 overflow-hidden"
          >
            <ApiForm
              method="POST"
              endpoint="https://api.airweave.ai/auth-providers/"
              className="flex flex-col flex-1 overflow-hidden"
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
                    newBody.auth_fields as Record<string, string>,
                  );
                }
              }}
            >
              <ApiForm.Toggle />

              <ApiForm.FormView className="flex-1 overflow-y-auto space-y-6">
                {/* Connection Animation */}
                <div className="flex justify-center py-4">
                  <div className="flex items-center gap-6">
                    {/* Airweave Logo */}
                    <div
                      className={cn(
                        "w-14 h-14 rounded-xl flex items-center justify-center p-2.5",
                        "shadow-lg ring-2 ring-muted-foreground/20",
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

                    {/* Connecting text */}
                    <span className="text-sm text-muted-foreground">
                      Waiting for connection...
                    </span>

                    {/* Auth Provider Logo */}
                    <div
                      className={cn(
                        "w-14 h-14 rounded-xl flex items-center justify-center p-2.5",
                        "shadow-lg ring-2 ring-muted-foreground/20",
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
                  </div>
                </div>

                {/* Name field */}
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
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
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
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
                {providerDetails?.auth_fields?.fields &&
                  providerDetails.auth_fields.fields.length > 0 && (
                    <div className="space-y-4 pt-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                          Authentication
                        </label>

                        {/* Platform link button */}
                        {(authProvider.short_name === "composio" ||
                          authProvider.short_name === "pipedream") && (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => {
                              const url =
                                authProvider.short_name === "composio"
                                  ? "https://platform.composio.dev/"
                                  : "https://pipedream.com/settings/api";
                              window.open(url, "_blank");
                            }}
                          >
                            <img
                              src={getAuthProviderIconUrl(
                                authProvider.short_name,
                                isDark ? "dark" : "light",
                              )}
                              alt={authProvider.short_name}
                              className="w-3 h-3 mr-1.5 object-contain"
                            />
                            {authProvider.short_name === "composio"
                              ? "Get API Key from Composio"
                              : "Get Client ID & Secret from Pipedream"}
                            <ExternalLink className="w-3 h-3 ml-1.5" />
                          </Button>
                        )}
                      </div>

                      {providerDetails.auth_fields.fields.map((field) => (
                        <div key={field.name} className="space-y-2">
                          <label className="text-sm font-medium">
                            {field.title || field.name}
                            {field.required && (
                              <span className="text-destructive ml-1">*</span>
                            )}
                          </label>
                          {field.description && (
                            <p className="text-xs text-muted-foreground">
                              {field.description}
                            </p>
                          )}
                          <form.Field name="authFields">
                            {() => (
                              <Input
                                type={field.secret ? "password" : "text"}
                                value={
                                  form.getFieldValue("authFields")[
                                    field.name
                                  ] || ""
                                }
                                onChange={(e) =>
                                  handleAuthFieldChange(
                                    field.name,
                                    e.target.value,
                                  )
                                }
                                placeholder={
                                  field.secret
                                    ? "••••••••"
                                    : `Enter ${field.title || field.name}`
                                }
                              />
                            )}
                          </form.Field>
                        </div>
                      ))}
                    </div>
                  )}
              </ApiForm.FormView>

              <ApiForm.CodeView editable className="flex-1 overflow-y-auto" />

              <ApiForm.Footer className="pt-4 border-t">
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
