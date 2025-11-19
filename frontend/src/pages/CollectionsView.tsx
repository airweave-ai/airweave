import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, Plus, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { CollectionCard } from "@/components/dashboard";
import { useCollectionsStore } from "@/lib/stores";
import { useCollectionCreationStore } from "@/stores/collectionCreationStore";
import { apiClient } from "@/lib/api";
import { useUsageStore } from "@/lib/stores/usage";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { SingleActionCheckResponse } from "@/types";
import type { Collection } from "@/lib/stores/collections";

const CollectionsView = () => {
  const navigate = useNavigate();
  const {
    totalCount,
    fetchCollectionsPaginated,
    fetchCollectionsCount,
  } = useCollectionsStore();

  const [collections, setCollections] = useState<Collection[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [filteredCount, setFilteredCount] = useState<number | null>(null);
  const itemsPerPage = 24; // 4 cols × 6 rows

  // Modal state
  const { openModal } = useCollectionCreationStore();

  // Usage check from store
  const checkActions = useUsageStore(state => state.checkActions);
  const actionChecks = useUsageStore(state => state.actionChecks);
  const isCheckingUsage = useUsageStore(state => state.isLoading);

  // Derived states from usage store
  const sourceConnectionsAllowed = actionChecks.source_connections?.allowed ?? true;
  const entitiesAllowed = actionChecks.entities?.allowed ?? true;
  const usageCheckDetails = {
    source_connections: actionChecks.source_connections,
    entities: actionChecks.entities
  };

  // Calculate pagination (use filtered count when searching, otherwise total)
  const displayCount = filteredCount !== null ? filteredCount : (totalCount || 0);
  const totalPages = Math.ceil(displayCount / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;

  // Helper: Fetch filtered count
  const updateFilteredCount = useCallback(async (query: string) => {
    const params = new URLSearchParams({ search: query });
    const response = await apiClient.get(`/collections/count?${params}`);
    if (response.ok) {
      const count = await response.json();
      setFilteredCount(count);
    }
  }, []);

  // Debounce search query (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
      setCurrentPage(1); // Reset to first page on search
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch collections (with search support)
  useEffect(() => {
    const loadCollections = async () => {
      setIsLoading(true);
      const data = await fetchCollectionsPaginated(
        startIndex,
        itemsPerPage,
        debouncedSearchQuery || undefined
      );
      setCollections(data);
      setIsLoading(false);
    };

    loadCollections();
  }, [currentPage, debouncedSearchQuery, fetchCollectionsPaginated, startIndex, itemsPerPage]);

  // Fetch total count on mount (never filtered)
  useEffect(() => {
    fetchCollectionsCount();
  }, [fetchCollectionsCount]);

  // Fetch filtered count when searching
  useEffect(() => {
    if (debouncedSearchQuery) {
      updateFilteredCount(debouncedSearchQuery);
    } else {
      setFilteredCount(null);
    }
  }, [debouncedSearchQuery, updateFilteredCount]);

  // Handle collection events
  useEffect(() => {
    const handleRefresh = async () => {
      // Refresh total count
      await fetchCollectionsCount();

      // Refresh filtered count if searching
      if (debouncedSearchQuery) {
        await updateFilteredCount(debouncedSearchQuery);
      }

      // Refresh collections
      const data = await fetchCollectionsPaginated(
        startIndex,
        itemsPerPage,
        debouncedSearchQuery || undefined
      );
      setCollections(data);
    };

    window.addEventListener('collection-created', handleRefresh);
    window.addEventListener('collection-updated', handleRefresh);
    window.addEventListener('collection-deleted', handleRefresh);

    return () => {
      window.removeEventListener('collection-created', handleRefresh);
      window.removeEventListener('collection-updated', handleRefresh);
      window.removeEventListener('collection-deleted', handleRefresh);
    };
  }, [fetchCollectionsCount, fetchCollectionsPaginated, startIndex, itemsPerPage, debouncedSearchQuery, updateFilteredCount]);

  // Open create collection modal
  const handleCreateCollection = () => {
    openModal();
  };

  return (
    <div className="mx-auto w-full max-w-[1800px] px-6 py-6 pb-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-3xl font-bold">Collections</h1>
            {totalCount !== null && (
              <span className="px-2.5 py-1 text-xs font-medium bg-muted text-muted-foreground rounded-full">
                {totalCount}
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            View and manage all your collections
          </p>
        </div>
        <TooltipProvider delayDuration={100}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0}>
                <Button
                  onClick={handleCreateCollection}
                  disabled={!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage}
                  className={cn(
                    "bg-primary text-white rounded-lg h-9 px-4 transition-all duration-200",
                    (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                      ? "opacity-50 cursor-not-allowed hover:bg-primary"
                      : "hover:bg-primary/90"
                  )}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Create Collection
                </Button>
              </span>
            </TooltipTrigger>
            {(!sourceConnectionsAllowed || !entitiesAllowed) && (
              <TooltipContent className="max-w-xs">
                <p className="text-xs">
                  {!sourceConnectionsAllowed && usageCheckDetails.source_connections?.reason === 'usage_limit_exceeded' ? (
                    <>
                      Source connection limit reached.{' '}
                      <a
                        href="/organization/settings?tab=billing"
                        className="underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Upgrade your plan
                      </a>
                      {' '}for more connections.
                    </>
                  ) : !entitiesAllowed && usageCheckDetails.entities?.reason === 'usage_limit_exceeded' ? (
                    <>
                      Entity processing limit reached.{' '}
                      <a
                        href="/organization/settings?tab=billing"
                        className="underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Upgrade your plan
                      </a>
                      {' '}to process more data.
                    </>
                  ) : (
                    'Unable to create collection at this time.'
                  )}
                </p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </div>

      {/* Search bar */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search collections by name or ID..."
            className="pl-10 h-10 rounded-xl border-border focus:border-text/50 focus:ring-0 focus:ring-offset-0 focus:ring-text/50 dark:bg-background dark:focus:bg-background/80 transition-colors"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        {searchQuery && filteredCount !== null && (
          <div className="mt-2 text-sm text-muted-foreground">
            Found {filteredCount} collection{filteredCount !== 1 ? 's' : ''}
          </div>
        )}
      </div>

      {/* Collections Grid */}
      <div className="relative">
        {/* Loading overlay */}
        {isLoading && collections.length > 0 && (
          <div className="absolute inset-0 bg-background/60 backdrop-blur-sm z-10 flex items-center justify-center rounded-xl">
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">
                {searchQuery ? 'Searching collections...' : 'Loading collections...'}
              </p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-6 sm:gap-8 auto-rows-fr">
          {isLoading && collections.length === 0 ? (
            Array.from({ length: 8 }).map((_, index) => (
              <div
                key={index}
                className="h-[220px] rounded-xl animate-pulse bg-slate-100 dark:bg-slate-800/50"
              />
            ))
          ) : collections.length === 0 ? (
            <div className="col-span-full text-center py-20 text-muted-foreground">
              {searchQuery ? `No collections found matching "${searchQuery}"` : "No collections found"}
            </div>
          ) : (
            collections.map((collection) => (
              <CollectionCard
                key={collection.id}
                id={collection.id}
                name={collection.name}
                readableId={collection.readable_id}
                status={collection.status}
                onClick={() => navigate(`/collections/${collection.readable_id}`)}
              />
            ))
          )}
        </div>
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="mt-8 flex items-center justify-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1 || isLoading}
            className={cn(
              "gap-1 hover:bg-accent",
              currentPage === 1 && "opacity-40 cursor-not-allowed"
            )}
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>

          <div className="flex items-center gap-1.5">
            {[...Array(totalPages)].map((_, i) => {
              const page = i + 1;
              // Show first, last, current, and adjacent pages
              if (
                page === 1 ||
                page === totalPages ||
                (page >= currentPage - 1 && page <= currentPage + 1)
              ) {
                return (
                  <Button
                    key={page}
                    variant="ghost"
                    size="sm"
                    onClick={() => setCurrentPage(page)}
                    disabled={isLoading}
                    className={cn(
                      "min-w-[40px] hover:bg-accent transition-colors",
                      currentPage === page
                        ? "bg-muted font-medium text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {page}
                  </Button>
                );
              } else if (page === currentPage - 2 || page === currentPage + 2) {
                return <span key={page} className="px-2 text-muted-foreground">...</span>;
              }
              return null;
            })}
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages || isLoading}
            className={cn(
              "gap-1 hover:bg-accent",
              currentPage === totalPages && "opacity-40 cursor-not-allowed"
            )}
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
};

export default CollectionsView;
