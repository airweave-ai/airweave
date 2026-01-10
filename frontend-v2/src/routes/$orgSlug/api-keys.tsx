import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Key, Loader2, Plus } from "lucide-react";
import { useMemo, useState } from "react";
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
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";

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
  const { organization } = useOrg();
  const queryClient = useQueryClient();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  if (!organization) {
    throw new Error("Organization context is required but not available");
  }
  const orgId = organization.id;

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
    queryKey: queryKeys.apiKeys.list(orgId),
    queryFn: async ({ pageParam = 0 }) => {
      const token = await getAccessTokenSilently();
      return fetchApiKeys(token, orgId, pageParam, PAGE_SIZE);
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage || !Array.isArray(lastPage)) {
        return undefined;
      }
      if (lastPage.length < PAGE_SIZE) {
        return undefined;
      }
      return allPages.flat().length;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (keyIds: string[]) => {
      const token = await getAccessTokenSilently();
      await Promise.all(keyIds.map((id) => deleteApiKey(token, orgId, id)));
    },
    onMutate: async (keyIds) => {
      const listKey = queryKeys.apiKeys.list(orgId);

      await queryClient.cancelQueries({ queryKey: listKey });

      const previousData = queryClient.getQueryData(listKey);

      const keyIdsSet = new Set(keyIds);

      queryClient.setQueryData(
        listKey,
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
      if (context?.previousData) {
        queryClient.setQueryData(
          queryKeys.apiKeys.list(orgId),
          context.previousData
        );
      }
    },
    onSuccess: async (_data, keyIds) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.apiKeys.list(orgId),
      });
      const count = keyIds.length;
      toast.success(
        count > 1 ? `${count} API keys deleted` : "API key deleted"
      );
    },
  });

  const apiKeys = useMemo(() => data?.pages.flat() ?? [], [data?.pages]);

  const selectedKey = useMemo(() => {
    if (apiKeys.length === 0) return null;
    if (selectedKeyId) {
      const found = apiKeys.find((k) => k.id === selectedKeyId);
      if (found) return found;
    }
    return apiKeys[0];
  }, [apiKeys, selectedKeyId]);

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

  if (isLoading) {
    return (
      <div className="p-6">
        <LoadingState />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <ErrorState
          error={error instanceof Error ? error : "Failed to load API keys"}
        />
      </div>
    );
  }

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
          orgId={orgId}
        />
      </div>
    );
  }

  return (
    <div>
      <ApiKeysTable
        data={apiKeys}
        onDelete={(ids) => deleteMutation.mutate(ids)}
        selectedKey={selectedKey}
        onSelectKey={(key) => setSelectedKeyId(key?.id ?? null)}
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
        orgId={orgId}
      />
    </div>
  );
}
