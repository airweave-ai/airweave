import { useState, useEffect, useCallback } from "react";

import { Copy, Eye, Key, Plus, ExternalLink, FileText, Github, Code, Sparkles, TrendingUp, Search, Package } from "lucide-react";
import { useNavigate, Link, useLocation, useSearchParams } from "react-router-dom";
import { useTheme } from "@/lib/theme-provider";
import {
  CollectionCard,
  SourceButton,
  ApiKeyCard,
  ExampleProjectCard,
  RequestConnectorButton,
} from "@/components/dashboard";
import { clearStoredErrorDetails, getStoredErrorDetails } from "@/lib/error-utils";
import { useCollectionCreationStore } from "@/stores/collectionCreationStore";
import { useCollectionsStore, useSourcesStore } from "@/lib/stores";
import { useUsageStore } from "@/lib/stores/usage";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { SingleActionCheckResponse } from "@/types";

// Collection type definition
interface Collection {
  id: string;
  name: string;
  readable_id: string;
  status: string;
}

// Source type definition
interface Source {
  name: string;
  description?: string | null;
  short_name: string;
  labels?: string[];
  auth_type?: string;
}

// Source Connection definition
interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
  collection: string;
  status?: string;
}


const Dashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { resolvedTheme } = useTheme();

  // Use collections store
  const {
    collections,
    totalCount,
    isLoading: isLoadingCollections,
    fetchCollections,
    fetchCollectionsCount,
    sourceConnections,
    fetchSourceConnections
  } = useCollectionsStore();

  // Use sources store
  const { sources, isLoading: isLoadingSources, fetchSources } = useSourcesStore();



  // Usage check from store
  const checkActions = useUsageStore(state => state.checkActions);
  const actionChecks = useUsageStore(state => state.actionChecks);
  const isCheckingUsage = useUsageStore(state => state.isLoading);

  // Derived states from usage store
  const sourceConnectionsAllowed = actionChecks.source_connections?.allowed ?? true;
  const entitiesAllowed = actionChecks.entities?.allowed ?? true;
  const usageCheckDetails = {
    source_connections: actionChecks.source_connections ?? null,
    entities: actionChecks.entities ?? null
  };

  // Usage checking is now handled by UsageChecker component at app level

  // Check for connection errors on mount
  useEffect(() => {
    const connectionStatus = searchParams.get('connected');
    if (connectionStatus === 'error') {
      const errorDetails = getStoredErrorDetails();
      if (errorDetails) {
        console.log("🔔 [Dashboard] Found stored error details:", errorDetails);
        // TODO: Handle error display in new modal system

        // Clean up URL
        const newUrl = window.location.pathname;
        window.history.replaceState({}, '', newUrl);
      }
    }
  }, [searchParams]);

  // Initialize Zustand store subscribers
  useEffect(() => {
    // Subscribe to collections events
    const unsubscribeCollections = useCollectionsStore.getState().subscribeToEvents();

    // Initial fetch - use console logging to track API calls
    console.log("🔄 [Dashboard] Initializing collections and sources");

    // Load collections (will use cache if available)
    fetchCollections().then(collections => {
      console.log(`🔄 [Dashboard] Collections loaded: ${collections.length} collections available`);
    });

    // Load collections count
    fetchCollectionsCount();

    // Load sources - will use cached data if available
    fetchSources().then(sources => {
      console.log(`🔄 [Dashboard] Sources loaded: ${sources.length} sources available`);
    });

    return () => {
      unsubscribeCollections();
    };
  }, [fetchCollections, fetchCollectionsCount, fetchSources]);

  // Usage limits are now checked by UsageChecker component


  const handleSourceClick = (source: Source) => {
    const store = useCollectionCreationStore.getState();
    // Determine auth mode based on source
    let authMode: 'oauth2' | 'direct_auth' | undefined;
    if (source.auth_type?.startsWith('oauth2')) {
      authMode = 'oauth2';
    } else if (source.auth_type === 'api_key' || source.auth_type === 'basic') {
      authMode = 'direct_auth';
    }
    // Use the new flow-specific method
    store.openForCreateWithSource(source.short_name, source.name, authMode);
  };



  // Top 3 collections
  const topCollections = collections.slice(0, 3);

  return (
    <div className="mx-auto w-full max-w-[1800px] px-6 py-6 pb-8">

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Main content (left column) */}
        <div className="md:col-span-2 space-y-6 md:space-y-8">
          {/* Collections Section - only show when loading or has collections */}
          {(isLoadingCollections || collections.length > 0) && (
            <section>
              <div className="flex items-center justify-between mb-4 sm:mb-6">
                <h2 className="text-2xl sm:text-3xl font-bold">Collections</h2>
                <Link
                  to="/collections"
                  className="flex items-center text-sm text-primary hover:text-primary/80 hover:bg-accent/30 px-2 py-1.5 rounded-md"
                >
                  <ExternalLink className="mr-2 h-3.5 w-3.5 opacity-70" />
                  <span>See all {totalCount !== null ? `(${totalCount})` : collections.length > 0 ? `(${collections.length})` : ''}</span>
                </Link>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 auto-rows-fr">
                {isLoadingCollections ? (
                  Array.from({ length: 3 }).map((_, index) => (
                    <div
                      key={index}
                      className="h-[160px] rounded-xl animate-pulse bg-slate-100 dark:bg-slate-800/50"
                    />
                  ))
                ) : (
                  topCollections.map((collection) => (
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
            </section>
          )}

          {/* Create Collection Section */}
          <section>
            <h2 className="text-xl sm:text-2xl font-semibold mb-1 sm:mb-2">Create collection</h2>
            <p className="text-xs sm:text-sm text-muted-foreground mb-3 sm:mb-5">
              Choose a first source to add to your new collection
            </p>

            <div className="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-3 md:grid-cols-3 gap-3 auto-rows-fr">
              {isLoadingSources ? (
                <div className="col-span-full h-40 flex items-center justify-center">
                  <div className="animate-pulse flex flex-col items-center">
                    <div className="h-10 w-10 bg-gray-200 dark:bg-gray-700 rounded-md mb-4"></div>
                    <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-2"></div>
                    <div className="h-3 w-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                  </div>
                </div>
              ) : sources.length === 0 ? (
                <div className="col-span-full text-center py-10 text-muted-foreground">
                  No sources found
                </div>
              ) : (
                <>
                  {[...sources].sort((a, b) => a.name.localeCompare(b.name)).map((source) => (
                    <SourceButton
                      key={source.short_name}
                      id={source.short_name}
                      name={source.name}
                      shortName={source.short_name}
                      onClick={() => handleSourceClick(source)}
                      disabled={!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage}
                      usageCheckDetails={usageCheckDetails}
                    />
                  ))}
                  {/* Request Connector Button */}
                  <RequestConnectorButton />
                </>
              )}
            </div>
          </section>
        </div>

        {/* Right Column */}
        <div className="md:col-span-1 space-y-6">
          {/* API Key Card */}
          <ApiKeyCard />

          {/* Example Projects Section */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Learn & Explore</h3>
            <div className="space-y-3">
              <ExampleProjectCard
                id="quickstart-guide"
                title="Quickstart Guide"
                description="Get started with Airweave in minutes. Learn how to create collections, connect data sources, and search your data."
                tags={["Documentation", "Getting Started"]}
                icon={<FileText className="h-5 w-5 text-primary" />}
                onClick={() => {
                  window.open('https://docs.airweave.ai/quickstart', '_blank');
                }}
              />

              <ExampleProjectCard
                id="mcp-server"
                title="MCP Server Integration"
                description="Serve your Airweave collection over an MCP server so clients like Cursor or Claude can query it."
                tags={["Documentation"]}
                icon={<FileText className="h-5 w-5 text-primary" />}
                onClick={() => {
                  window.open('https://docs.airweave.ai/mcp-server', '_blank');
                }}
              />

              <ExampleProjectCard
                id="advanced-search"
                title="Advanced Search Guide"
                description="Master Airweave's powerful search capabilities including AI-powered query expansion, hybrid search, metadata filtering, and AI-generated answers."
                tags={["Documentation", "Search"]}
                icon={<FileText className="h-5 w-5 text-primary" />}
                onClick={() => {
                  window.open('https://docs.airweave.ai/search', '_blank');
                }}
              />

              <ExampleProjectCard
                id="auth-providers"
                title="Authentication Providers"
                description="Reuse existing connections from third-party platforms instead of requiring users to authenticate again."
                tags={["Documentation"]}
                icon={<FileText className="h-5 w-5 text-primary" />}
                onClick={() => {
                  window.open('https://docs.airweave.ai/auth-providers', '_blank');
                }}
              />

            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default Dashboard;
