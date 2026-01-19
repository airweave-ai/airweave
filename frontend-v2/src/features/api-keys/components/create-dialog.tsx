import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
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
import { createApiKey } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

import { EXPIRATION_PRESETS } from "../utils/helpers";

interface CreateApiKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
}

export function CreateApiKeyDialog({
  open,
  onOpenChange,
  orgId,
}: CreateApiKeyDialogProps) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();

  const createForm = useForm({
    defaultValues: {
      expirationDays: 90,
    },
    onSubmit: async ({ value }) => {
      createMutation.mutate(value.expirationDays);
    },
  });

  const createMutation = useMutation({
    mutationFn: async (expirationDays: number) => {
      const token = await getAccessTokenSilently();
      return createApiKey(token, orgId, expirationDays);
    },
    onSuccess: async (newKey) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.apiKeys.list(orgId),
      });
      onOpenChange(false);
      createForm.reset();

      navigator.clipboard.writeText(newKey.decrypted_key).then(
        () => {
          toast.success("API key created and copied to clipboard");
        },
        () => {
          toast.success("API key created", {
            description: "Failed to copy to clipboard automatically",
          });
        }
      );
    },
    onError: (error: Error) => {
      const message = error.message || "Failed to create API key";
      const commaIndex = message.indexOf(", ");
      if (commaIndex > 0) {
        toast.error(message.substring(0, commaIndex), {
          description: message.substring(commaIndex + 2),
        });
      } else {
        toast.error("An error occurred", {
          description: message,
        });
      }
    },
  });

  const handleClose = (newOpen: boolean) => {
    if (!newOpen) {
      createForm.reset();
    }
    onOpenChange(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create API key</DialogTitle>
          <DialogDescription>
            Choose how long this key should remain valid
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            createForm.handleSubmit();
          }}
        >
          <createForm.Field name="expirationDays">
            {(field) => (
              <ApiForm
                method="POST"
                endpoint="https://api.airweave.ai/api-keys"
                body={{ expiration_days: field.state.value }}
                onBodyChange={(newBody) =>
                  field.handleChange((newBody.expiration_days as number) || 90)
                }
              >
                <ApiForm.Toggle />

                <ApiForm.FormView className="space-y-2">
                  {EXPIRATION_PRESETS.map((preset) => (
                    <button
                      key={preset.days}
                      type="button"
                      onClick={() => field.handleChange(preset.days)}
                      className={cn(
                        "flex w-full items-center justify-between rounded-lg border px-4 py-3.5 text-left transition-colors",
                        field.state.value === preset.days
                          ? "border-primary bg-primary/5 dark:bg-primary/10"
                          : "border-border hover:border-muted-foreground/25"
                      )}
                    >
                      <span
                        className={cn(
                          "text-sm font-medium",
                          field.state.value === preset.days
                            ? "text-foreground"
                            : "text-muted-foreground"
                        )}
                      >
                        {preset.label}
                      </span>
                      {preset.recommended && (
                        <span className="rounded-md bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-600 dark:text-blue-400">
                          Recommended
                        </span>
                      )}
                    </button>
                  ))}
                </ApiForm.FormView>

                <ApiForm.CodeView editable />

                <ApiForm.Footer>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => handleClose(false)}
                    disabled={createMutation.isPending}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createMutation.isPending}>
                    {createMutation.isPending ? (
                      <>
                        <Loader2 className="mr-2 size-4 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      "Create key"
                    )}
                  </Button>
                </ApiForm.Footer>
              </ApiForm>
            )}
          </createForm.Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}
