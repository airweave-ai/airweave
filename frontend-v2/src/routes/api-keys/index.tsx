import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Key, Loader2, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import { deleteApiKey, fetchApiKeys, type APIKey } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";

import { ApiKeyItem } from "@/features/api-keys/components/api-key-item";
import { CreateApiKeyDialog } from "@/features/api-keys/components/create-dialog";
import {
  ApiKeysCode,
  ApiKeysDocs,
  ApiKeysHelp,
} from "@/features/api-keys/components/sidebar-content";

export const Route = createFileRoute("/api-keys/")({ component: ApiKeysPage });

function ApiKeysPage() {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const handleOpenCreateDialog = () => {
    setCreateDialogOpen(true);
  };

  usePageHeader({
    title: "API Keys",
    description: "Manage your API keys for programmatic access",
    actions: (
      <Button onClick={handleOpenCreateDialog}>
        <Plus className="mr-2 size-4" />
        Create key
      </Button>
    ),
  });

  useRightSidebarContent({
    docs: <ApiKeysDocs />,
    code: <ApiKeysCode />,
    help: <ApiKeysHelp />,
  });

  const {
    data: apiKeys,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchApiKeys(token);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (keyId: string) => {
      const token = await getAccessTokenSilently();
      return deleteApiKey(token, keyId);
    },
    onMutate: async (keyId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["api-keys"] });

      // Snapshot the previous value
      const previousKeys = queryClient.getQueryData<APIKey[]>(["api-keys"]);

      // Optimistically update to the new value
      queryClient.setQueryData<APIKey[]>(["api-keys"], (old) =>
        old?.filter((key) => key.id !== keyId),
      );

      // Return a context object with the snapshotted value
      return { previousKeys };
    },
    onError: (_err, _keyId, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousKeys) {
        queryClient.setQueryData(["api-keys"], context.previousKeys);
      }
    },
    onSuccess: () => {
      toast.success("API key deleted");
    },
    onSettled: () => {
      // Always refetch after error or success to ensure sync with server
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  // Loading state
  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {error instanceof Error ? error.message : "Failed to load API keys"}
        </div>
      </div>
    );
  }

  // Empty state
  if (!apiKeys || apiKeys.length === 0) {
    return (
      <div className="p-6">
        <EmptyState
          icon={<Key />}
          title="No API keys yet"
          description="Create your first key to start using the API programmatically."
        >
          <Button variant="outline" size="sm" onClick={handleOpenCreateDialog}>
            <Plus className="mr-2 size-4" />
            Create key
          </Button>
        </EmptyState>

        <CreateApiKeyDialog
          open={createDialogOpen}
          onOpenChange={setCreateDialogOpen}
        />
      </div>
    );
  }

  // Keys list
  return (
    <div className="p-6">
      <div className="space-y-3">
        {apiKeys.map((apiKey) => (
          <ApiKeyItem
            key={apiKey.id}
            apiKey={apiKey}
            onDelete={(id) => deleteMutation.mutate(id)}
          />
        ))}
      </div>

      <CreateApiKeyDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
    </div>
  );
}

