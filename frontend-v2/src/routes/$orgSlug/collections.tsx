import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { FolderOpen, Loader2, Plus } from "lucide-react";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import {
  CollectionCard,
  CollectionsCode,
  CollectionsDocs,
  CollectionsHelp,
  CreateCollectionDialog,
  SourceCard,
} from "@/features/collections";
import { fetchCollections, fetchSources, type Collection } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";
import { useCreateCollectionStore } from "@/stores/create-collection-store";

export const Route = createFileRoute("/$orgSlug/collections")({
  component: CollectionsPage,
});

const PAGE_SIZE = 24;

function CollectionsPage() {
  const navigate = useNavigate();
  const { getAccessTokenSilently } = useAuth0();
  const { organization, getOrgSlug } = useOrg();
  const openCreateCollection = useCreateCollectionStore((s) => s.open);
  const isCreateDialogOpen = useCreateCollectionStore((s) => s.isOpen);
  const closeCreateCollection = useCreateCollectionStore((s) => s.close);

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
        New Collection
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

  // Flatten collections pages
  const collections = useMemo(
    () => collectionsData?.pages.flat() ?? [],
    [collectionsData?.pages]
  );

  // Sort sources alphabetically
  const sortedSources = useMemo(() => {
    if (!sources) return [];
    return [...sources].sort((a, b) => a.name.localeCompare(b.name));
  }, [sources]);

  // Handle source click - open create collection dialog
  const handleSourceClick = (_source: { short_name: string; name: string }) => {
    openCreateCollection();
  };

  // Handle collection click - navigate to collection detail
  const handleCollectionClick = (collection: Collection) => {
    navigate({ to: `/${orgSlug}/collections/${collection.readable_id}` });
  };

  // Handle collection creation success
  const handleCollectionCreated = (collection: Collection) => {
    // Navigate to the new collection
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
          icon={<FolderOpen />}
          title="Create your first collection"
          description="Collections help you organize and search your data from multiple sources."
        >
          <Button variant="outline" onClick={openCreateCollection}>
            <Plus className="mr-2 size-4" />
            New Collection
          </Button>
        </EmptyState>

        {/* Still show sources grid even when no collections */}
        {sortedSources.length > 0 && (
          <div>
            <h2 className="mb-2 text-xl font-semibold sm:text-2xl">
              Or start with a source
            </h2>
            <p className="text-muted-foreground mb-4 text-xs sm:text-sm">
              Choose a source to add to your new collection
            </p>
            <div className="xs:grid-cols-2 grid auto-rows-fr grid-cols-1 gap-3 sm:grid-cols-3 md:grid-cols-4">
              {sortedSources.map((source) => (
                <SourceCard
                  key={source.id}
                  id={source.id}
                  name={source.name}
                  shortName={source.short_name}
                  onClick={() => handleSourceClick(source)}
                />
              ))}
            </div>
          </div>
        )}

        <CreateCollectionDialog
          open={isCreateDialogOpen}
          onOpenChange={(open) => {
            if (!open) closeCreateCollection();
          }}
          orgId={orgId}
          onSuccess={handleCollectionCreated}
        />
      </div>
    );
  }

  // Main content - collections grid and sources
  return (
    <div className="space-y-8 p-6">
      {/* Collections Grid */}
      <div>
        <div className="flex flex-wrap gap-4">
          {collections.map((collection) => (
            <CollectionCard
              className="w-64"
              key={collection.id}
              id={collection.id}
              name={collection.name}
              readableId={collection.readable_id}
              status={collection.status}
              onClick={() => handleCollectionClick(collection)}
            />
          ))}
        </div>

        {/* Load more button */}
        {hasNextPage && (
          <div className="flex justify-center pt-6">
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
      </div>

      {/* Sources Grid */}
      {sortedSources.length > 0 && (
        <div>
          <h2 className="mb-2 text-xl font-semibold sm:text-2xl">
            Add a new source
          </h2>
          <p className="text-muted-foreground mb-4 text-xs sm:text-sm">
            Choose a source to add to a collection
          </p>
          <div className="xs:grid-cols-2 grid auto-rows-fr grid-cols-1 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {sortedSources.map((source) => (
              <SourceCard
                key={source.id}
                id={source.id}
                name={source.name}
                shortName={source.short_name}
                onClick={() => handleSourceClick(source)}
              />
            ))}
          </div>
        </div>
      )}

      <CreateCollectionDialog
        open={isCreateDialogOpen}
        onOpenChange={(open) => {
          if (!open) closeCreateCollection();
        }}
        orgId={orgId}
        onSuccess={handleCollectionCreated}
      />
    </div>
  );
}
