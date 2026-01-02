import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Key, Loader2, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import { useCommandMenu } from "@/hooks/use-command-menu";
import { deleteApiKey, fetchApiKeys, type APIKey } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";

import {
  ApiKeysCode,
  ApiKeysDocs,
  ApiKeysHelp,
  ApiKeysTable,
  CreateApiKeyDialog,
  getApiKeyActions,
  maskKey,
} from "@/features/api-keys";

export const Route = createFileRoute("/$orgSlug/api-keys")({
  component: ApiKeysPage,
});

const PAGE_SIZE = 20;

function ApiKeysPage() {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<APIKey | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

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
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ["api-keys", "list"],
    queryFn: async ({ pageParam = 0 }) => {
      const token = await getAccessTokenSilently();
      return fetchApiKeys(token, pageParam, PAGE_SIZE);
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      // Handle case where lastPage might be undefined (stale cache)
      if (!lastPage || !Array.isArray(lastPage)) {
        return undefined;
      }
      // If we got less than PAGE_SIZE items, there are no more pages
      if (lastPage.length < PAGE_SIZE) {
        return undefined;
      }
      // Next page starts after all current items
      return allPages.flat().length;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (keyIds: string[]) => {
      const token = await getAccessTokenSilently();
      await Promise.all(keyIds.map((id) => deleteApiKey(token, id)));
    },
    onMutate: async (keyIds) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["api-keys", "list"] });

      // Snapshot the previous value
      const previousData = queryClient.getQueryData(["api-keys", "list"]);

      // Create a Set for faster lookup
      const keyIdsSet = new Set(keyIds);

      // Optimistically update to remove the keys from all pages
      queryClient.setQueryData(
        ["api-keys", "list"],
        (old: { pages: APIKey[][]; pageParams: number[] } | undefined) => {
          if (!old) return old;
          return {
            ...old,
            pages: old.pages.map((page) =>
              page.filter((key) => !keyIdsSet.has(key.id))
            ),
          };
        }
      );

      return { previousData };
    },
    onError: (_err, _keyIds, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousData) {
        queryClient.setQueryData(["api-keys", "list"], context.previousData);
      }
    },
    onSuccess: (_data, keyIds) => {
      const count = keyIds.length;
      toast.success(
        count > 1 ? `${count} API keys deleted` : "API key deleted"
      );
    },
    onSettled: () => {
      // Always refetch after error or success to ensure sync with server
      queryClient.invalidateQueries({ queryKey: ["api-keys", "list"] });
    },
  });

  // Flatten all pages into a single array - memoized to prevent unnecessary re-renders
  const apiKeys = useMemo(() => data?.pages.flat() ?? [], [data?.pages]);

  // Auto-select the first item when data loads or changes
  useEffect(() => {
    if (apiKeys.length > 0 && !selectedKey) {
      setSelectedKey(apiKeys[0]);
    }
    // If selected key was deleted, select the first item
    if (selectedKey && !apiKeys.find((k) => k.id === selectedKey.id)) {
      setSelectedKey(apiKeys[0] ?? null);
    }
  }, [apiKeys, selectedKey]);

  // Build context commands based on selected key
  const contextCommands = useMemo(() => {
    if (!selectedKey) return [];
    const actions = getApiKeyActions({
      apiKey: selectedKey,
      onCopyAsJson: () => {
        navigator.clipboard.writeText(JSON.stringify(selectedKey, null, 2));
        toast.success("Copied to clipboard");
      },
      onDelete: () => {
        setDeleteDialogOpen(true);
      },
    });
    return actions;
  }, [selectedKey]);

  // Register commands with the command menu
  useCommandMenu({
    pageTitle: "API Keys",
    pageCommands: [
      {
        id: "create-api-key",
        label: "Create API Key",
        icon: Plus,
        onSelect: handleOpenCreateDialog,
      },
    ],
    contextTitle: selectedKey ? maskKey(selectedKey.decrypted_key) : undefined,
    contextCommands,
  });

  // Loading state
  if (isLoading) {
    return (
      <div className="p-6">
        <LoadingState />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="p-6">
        <ErrorState
          error={error instanceof Error ? error : "Failed to load API keys"}
        />
      </div>
    );
  }

  // Empty state
  if (apiKeys.length === 0) {
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

  // Keys table
  return (
    <div>
      <ApiKeysTable
        data={apiKeys}
        onDelete={(ids) => deleteMutation.mutate(ids)}
        selectedKey={selectedKey}
        onSelectKey={setSelectedKey}
        deleteDialogOpen={deleteDialogOpen}
        onDeleteDialogChange={setDeleteDialogOpen}
      />

      {hasNextPage && (
        <div className="flex justify-center pt-4">
          <Button
            variant="outline"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Loading...
              </>
            ) : (
              "Load more"
            )}
          </Button>
        </div>
      )}

      <CreateApiKeyDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
    </div>
  );
}
