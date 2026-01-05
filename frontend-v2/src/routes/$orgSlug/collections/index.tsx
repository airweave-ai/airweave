import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { LayoutGrid, Loader2, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import {
  CollectionsCode,
  CollectionsDocs,
  CollectionsHelp,
  CollectionsTable,
  SourcesGrid,
} from "@/features/collections";
import {
  deleteCollection,
  fetchCollections,
  fetchSources,
  type Collection,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";
import { useCreateCollectionStore } from "@/stores/create-collection-store";

export const Route = createFileRoute("/$orgSlug/collections/")({
  component: CollectionsPage,
});

const PAGE_SIZE = 24;

function CollectionsPage() {
  const navigate = useNavigate();
  const { getAccessTokenSilently } = useAuth0();
  const { organization, getOrgSlug } = useOrg();
  const queryClient = useQueryClient();
  const openCreateCollection = useCreateCollectionStore((s) => s.open);
  const openWithSource = useCreateCollectionStore((s) => s.openWithSource);

  const [selectedCollectionId, setSelectedCollectionId] = useState<
    string | null
  >(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Organization is guaranteed to be available (layout shows loading state)
  if (!organization) {
    throw new Error("Organization context is required but not available");
  }
  const orgId = organization.id;
  const orgSlug = getOrgSlug(organization);

  usePageHeader({
    title: "Collections",
    description: "Manage your searchable knowledge bases",
    actions: (
      <Button onClick={openCreateCollection}>
        <Plus className="mr-2 size-4" />
        Create Collection
      </Button>
    ),
  });

  useRightSidebarContent({
    docs: <CollectionsDocs />,
    code: <CollectionsCode />,
    help: <CollectionsHelp />,
  });

  // Fetch collections with infinite query
  const {
    data: collectionsData,
    isLoading: isLoadingCollections,
    error: collectionsError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: queryKeys.collections.list(orgId),
    queryFn: async ({ pageParam = 0 }) => {
      const token = await getAccessTokenSilently();
      return fetchCollections(token, orgId, pageParam, PAGE_SIZE);
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

  // Fetch sources
  const {
    data: sources,
    isLoading: isLoadingSources,
    error: sourcesError,
  } = useQuery({
    queryKey: queryKeys.sources.list(orgId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSources(token, orgId);
    },
  });

  // Delete mutation with optimistic updates
  const deleteMutation = useMutation({
    mutationFn: async (readableIds: string[]) => {
      const token = await getAccessTokenSilently();
      await Promise.all(
        readableIds.map((readableId) =>
          deleteCollection(token, orgId, readableId)
        )
      );
    },
    onMutate: async (readableIds) => {
      const listKey = queryKeys.collections.list(orgId);

      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: listKey });

      // Snapshot the previous value
      const previousData = queryClient.getQueryData(listKey);

      // Create a Set for faster lookup
      const readableIdsSet = new Set(readableIds);

      // Optimistically update to remove the collections from all pages
      queryClient.setQueryData(
        listKey,
        (old: { pages: Collection[][]; pageParams: number[] } | undefined) => {
          if (!old) return old;
          return {
            ...old,
            pages: old.pages.map((page) =>
              page.filter(
                (collection) => !readableIdsSet.has(collection.readable_id)
              )
            ),
          };
        }
      );

      return { previousData };
    },
    onError: (_err, _readableIds, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousData) {
        queryClient.setQueryData(
          queryKeys.collections.list(orgId),
          context.previousData
        );
      }
    },
    onSuccess: (_data, readableIds) => {
      const count = readableIds.length;
      toast.success(
        count > 1 ? `${count} collections deleted` : "Collection deleted"
      );
    },
    onSettled: () => {
      // Always refetch after error or success to ensure sync with server
      queryClient.invalidateQueries({
        queryKey: queryKeys.collections.list(orgId),
      });
    },
  });

  // Flatten collections pages
  const collections = useMemo(
    () => collectionsData?.pages.flat() ?? [],
    [collectionsData?.pages]
  );

  // Derive selectedCollection from selectedCollectionId
  const selectedCollection = useMemo(() => {
    if (collections.length === 0) return null;
    if (selectedCollectionId) {
      const found = collections.find((c) => c.id === selectedCollectionId);
      if (found) return found;
    }
    return collections[0];
  }, [collections, selectedCollectionId]);

  // Sort sources alphabetically
  const sortedSources = useMemo(() => {
    if (!sources) return [];
    return [...sources].sort((a, b) => a.name.localeCompare(b.name));
  }, [sources]);

  // Handle source click - open create collection dialog with pre-selected source
  const handleSourceClick = (source: { short_name: string; name: string }) => {
    openWithSource(source.short_name, source.name);
  };

  // Handle collection click - navigate to collection detail
  const handleCollectionClick = (collection: Collection) => {
    navigate({ to: `/${orgSlug}/collections/${collection.readable_id}` });
  };

  const isLoading = isLoadingCollections || isLoadingSources;
  const error = collectionsError || sourcesError;

  // Loading state
  if (isLoading && collections.length === 0) {
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
          error={error instanceof Error ? error : "Failed to load collections"}
        />
      </div>
    );
  }

  // Empty state - no collections yet
  if (collections.length === 0 && !isLoadingCollections) {
    return (
      <div className="space-y-8 p-6">
        <EmptyState
          icon={<LayoutGrid />}
          title="Create your first collection"
          description="Collections help you organize and search your data from multiple sources."
        >
          <Button variant="outline" onClick={openCreateCollection}>
            <Plus className="mr-2 size-4" />
            Create Collection
          </Button>
        </EmptyState>

        <SourcesGrid
          sources={sortedSources}
          onSourceClick={handleSourceClick}
        />
      </div>
    );
  }

  // Main content - collections table and sources
  return (
    <div className="space-y-8">
      {/* Collections Table */}
      <CollectionsTable
        data={collections}
        onDelete={(readableIds) => deleteMutation.mutate(readableIds)}
        onRowClick={handleCollectionClick}
        selectedCollection={selectedCollection}
        onSelectCollection={(collection) =>
          setSelectedCollectionId(collection?.id ?? null)
        }
        deleteDialogOpen={deleteDialogOpen}
        onDeleteDialogChange={setDeleteDialogOpen}
      />

      {/* Load more button */}
      {hasNextPage && (
        <div className="flex justify-center">
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

      <div className="px-6 pb-6">
        <SourcesGrid
          sources={sortedSources}
          onSourceClick={handleSourceClick}
        />
      </div>
    </div>
  );
}
