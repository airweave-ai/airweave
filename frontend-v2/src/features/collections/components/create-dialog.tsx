import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
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
import { createCollection, type Collection } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

interface CreateCollectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
  onSuccess?: (collection: Collection) => void;
}

/**
 * Generate a random alphanumeric suffix
 */
function generateRandomSuffix(length = 6): string {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

/**
 * Generate a readable ID from a name
 */
function generateReadableId(name: string, suffix: string): string {
  if (!name.trim()) return "";

  let readableId = name.toLowerCase().trim();
  readableId = readableId.replace(/[^a-z0-9\s]/g, "");
  readableId = readableId.replace(/\s+/g, "-");
  readableId = readableId.replace(/-+/g, "-");
  readableId = readableId.replace(/^-+|-+$/g, "");
  return readableId ? `${readableId}-${suffix}` : "";
}

export function CreateCollectionDialog({
  open,
  onOpenChange,
  orgId,
  onSuccess,
}: CreateCollectionDialogProps) {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();

  const [randomSuffix, setRandomSuffix] = useState(generateRandomSuffix);
  const [userEditedId, setUserEditedId] = useState(false);
  const [currentName, setCurrentName] = useState("");
  const [currentReadableId, setCurrentReadableId] = useState("");

  useEffect(() => {
    if (open) {
      setRandomSuffix(generateRandomSuffix());
    }
  }, [open]);

  const form = useForm({
    defaultValues: {
      name: "",
      readableId: "",
    },
    onSubmit: async ({ value }) => {
      createMutation.mutate(value);
    },
  });

  const createMutation = useMutation({
    mutationFn: async (values: { name: string; readableId: string }) => {
      const token = await getAccessTokenSilently();
      return createCollection(token, orgId, {
        name: values.name,
        readable_id: values.readableId || undefined,
      });
    },
    onSuccess: (collection) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.collections.all(orgId),
      });
      toast.success(`Collection "${collection.name}" created!`, {
        description: `ID: ${collection.readable_id}`,
      });
      onOpenChange(false);
      form.reset();
      setUserEditedId(false);
      setCurrentName("");
      setCurrentReadableId("");
      onSuccess?.(collection);
    },
    onError: (error: Error) => {
      const message = error.message || "Failed to create collection";
      const commaIndex = message.indexOf(", ");
      if (commaIndex > 0) {
        toast.error(message.substring(0, commaIndex), {
          description: message.substring(commaIndex + 2),
        });
      } else {
        toast.error("Failed to create collection", {
          description: message,
        });
      }
    },
  });

  const handleClose = (newOpen: boolean) => {
    if (!newOpen) {
      form.reset();
      setUserEditedId(false);
      setCurrentName("");
      setCurrentReadableId("");
    }
    onOpenChange(newOpen);
  };

  const displayReadableId = userEditedId
    ? currentReadableId
    : generateReadableId(currentName, randomSuffix);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create collection</DialogTitle>
          <DialogDescription>
            Collections are searchable knowledge bases for your data
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!userEditedId && displayReadableId) {
              form.setFieldValue("readableId", displayReadableId);
            }
            form.handleSubmit();
          }}
        >
          <ApiForm
            method="POST"
            endpoint="https://api.airweave.ai/collections"
            body={{
              name: currentName,
              ...(displayReadableId && { readable_id: displayReadableId }),
            }}
            onBodyChange={(newBody) => {
              if (typeof newBody.name === "string") {
                form.setFieldValue("name", newBody.name);
                setCurrentName(newBody.name);
              }
              if (typeof newBody.readable_id === "string") {
                form.setFieldValue("readableId", newBody.readable_id);
                setCurrentReadableId(newBody.readable_id);
                setUserEditedId(true);
              }
            }}
          >
            <ApiForm.Toggle />

            <ApiForm.FormView className="space-y-4">
              <form.Field
                name="name"
                validators={{
                  onChange: ({ value }) => {
                    if (!value.trim()) return "Name is required";
                    if (value.length < 4)
                      return "Name must be at least 4 characters";
                    if (value.length > 64)
                      return "Name must be less than 64 characters";
                    return undefined;
                  },
                }}
              >
                {(field) => (
                  <div className="space-y-2">
                    <label
                      htmlFor="name"
                      className="text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                      Name
                    </label>
                    <Input
                      id="name"
                      placeholder="e.g., Customer Support Tickets"
                      value={field.state.value}
                      onChange={(e) => {
                        field.handleChange(e.target.value);
                        setCurrentName(e.target.value);
                      }}
                      onBlur={field.handleBlur}
                      aria-invalid={
                        field.state.meta.errors.length > 0 ? "true" : undefined
                      }
                    />
                    {field.state.meta.errors.length > 0 && (
                      <p className="text-destructive text-sm">
                        {field.state.meta.errors[0]}
                      </p>
                    )}
                    <p className="text-muted-foreground text-xs">
                      4-64 characters. This is the display name for your
                      collection.
                    </p>
                  </div>
                )}
              </form.Field>

              <form.Field name="readableId">
                {(field) => (
                  <div className="space-y-2">
                    <label
                      htmlFor="readableId"
                      className="text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                      ID{" "}
                      <span className="text-muted-foreground font-normal">
                        (optional)
                      </span>
                    </label>
                    <Input
                      id="readableId"
                      placeholder="Auto-generated from name"
                      value={userEditedId ? field.state.value : ""}
                      onChange={(e) => {
                        field.handleChange(e.target.value);
                        setCurrentReadableId(e.target.value);
                        setUserEditedId(true);
                      }}
                      onBlur={field.handleBlur}
                    />
                    {displayReadableId && (
                      <p className="text-muted-foreground text-xs">
                        {userEditedId ? "Custom ID: " : "Generated ID: "}
                        <code
                          className={cn(
                            "rounded px-1 py-0.5",
                            "bg-muted font-mono text-xs"
                          )}
                        >
                          {displayReadableId}
                        </code>
                      </p>
                    )}
                  </div>
                )}
              </form.Field>
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
              <Button
                type="submit"
                disabled={createMutation.isPending || !currentName.trim()}
              >
                {createMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Create collection"
                )}
              </Button>
            </ApiForm.Footer>
          </ApiForm>
        </form>
      </DialogContent>
    </Dialog>
  );
}
