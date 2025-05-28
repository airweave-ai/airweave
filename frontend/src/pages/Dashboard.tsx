import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Copy, Eye, Key, Plus, ExternalLink, FileText, Github } from "lucide-react";
import { useNavigate, Link, useLocation, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import {
  CollectionCard,
  SourceButton,
  ApiKeyCard,
  ExampleProjectCard,
} from "@/components/dashboard";
import { cn } from "@/lib/utils";
import { getStoredErrorDetails, clearStoredErrorDetails } from "@/lib/error-utils";
import { DialogFlow } from "@/components/shared/DialogFlow";
import { useCollectionsStore, useSourcesStore } from "@/lib/stores";

// Collection type definition
interface Collection {
  id: string;
  name: string;
  readable_id: string;
  status: string;
}

// Source type definition
interface Source {
  id: string;
  name: string;
  description?: string | null;
  short_name: string;
  labels?: string[];
}

// Source Connection definition
interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
  collection: string;
  status?: string;
}

// API Key type
interface APIKey {
  decrypted_key: string;
}

const Dashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { resolvedTheme } = useTheme();

  // Use collections store
  const {
    collections,
    isLoading: isLoadingCollections,
    fetchCollections,
    sourceConnections,
    fetchSourceConnections
  } = useCollectionsStore();

  // Use sources store
  const { sources, isLoading: isLoadingSources, fetchSources } = useSourcesStore();

  const [apiKey, setApiKey] = useState<APIKey | null>(null);
  const [isLoadingApiKey, setIsLoadingApiKey] = useState(true);

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState<{ id: string; name: string; short_name: string } | null>(null);

  // Error state for connection errors
  const [connectionError, setConnectionError] = useState<any>(null);

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

    // Load sources - will use cached data if available
    fetchSources().then(sources => {
      console.log(`🔄 [Dashboard] Sources loaded: ${sources.length} sources available`);
    });

    return () => {
      unsubscribeCollections();
    };
  }, [fetchCollections, fetchSources]);

  // Fetch API key
  useEffect(() => {
    const fetchApiKey = async () => {
      setIsLoadingApiKey(true);
      try {
        const response = await apiClient.get("/api-keys");
        if (response.ok) {
          const data = await response.json();
          // Get the first API key if available
          if (Array.isArray(data) && data.length > 0) {
            setApiKey(data[0]);
          }
        } else {
          console.error("Failed to load API key:", await response.text());
        }
      } catch (err) {
        console.error("Error fetching API key:", err);
      } finally {
        setIsLoadingApiKey(false);
      }
    };

    fetchApiKey();
  }, []);

  const handleRequestNewKey = () => {
    // Placeholder for requesting a new API key
    toast.info("New API key feature coming soon");
  };

  const handleSourceClick = (source: Source) => {
    setSelectedSource(source);
    setDialogOpen(true);
  };

  // Handle dialog close
  const handleDialogClose = () => {
    setDialogOpen(false);
    setSelectedSource(null);
    setConnectionError(null);
    clearStoredErrorDetails(); // Ensure error data is cleared
    // Refresh collections
    fetchCollections();
  };

  // Top 3 collections
  const topCollections = collections.slice(0, 3);

  // Example projects data
  const exampleProjects = [
    {
      id: 1,
      title: "Integrate Google Drive",
      description: "This is an example project",
    },
    {
      id: 2,
      title: "Informed Langraph Agent",
      description: "This is an example project",
    },
    {
      id: 3,
      title: "White label react app",
      description: "This is an example project",
    },
    {
      id: 4,
      title: "Custom SQL Integration",
      description: "This is an example project",
    },
    {
      id: 5,
      title: "Notion Knowledge Base",
      description: "This is an example project",
    },
  ];

  // Log when dialog open state changes
  useEffect(() => {
    console.log("🚪 Dashboard dialog open state:", dialogOpen);
  }, [dialogOpen]);

  // Modify the dialog open handler
  const handleDialogOpen = (open: boolean) => {
    console.log("🚪 Dashboard handleDialogOpen called with:", open);
    setDialogOpen(open);
  };

  return (
    <div className="mx-auto w-full max-w-[1800px] px-6 py-6 pb-8">
      <DialogFlow
        isOpen={dialogOpen}
        onOpenChange={handleDialogOpen}
        mode="source-button"
        sourceId={selectedSource?.id}
        sourceName={selectedSource?.name}
        sourceShortName={selectedSource?.short_name}
        dialogId="dashboard-source-dialog"
        onComplete={() => {
          // Handle completion
          fetchCollections(false);
        }}
      />

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
                  <span>See all {collections.length > 0 ? `(${collections.length})` : ''}</span>
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
                [...sources].sort((a, b) => a.name.localeCompare(b.name)).map((source) => (
                  <SourceButton
                    key={source.id}
                    id={source.id}
                    name={source.name}
                    shortName={source.short_name}
                    onClick={() => handleSourceClick(source)}
                  />
                ))
              )}
            </div>
          </section>
        </div>

        {/* Right Column */}
        <div className="md:col-span-1 space-y-6">
          {/* API Key Card */}
          <ApiKeyCard
            apiKey={apiKey}
            onRequestNewKey={handleRequestNewKey}
          />

          {/* Example Projects */}
          <section>
            <h2 className="text-xl sm:text-2xl font-semibold mb-1 sm:mb-2">Example projects</h2>
            <p className="text-xs sm:text-sm text-muted-foreground mb-3 sm:mb-5">Use a template to get started</p>

            <div className="space-y-3 sm:space-y-4">
              {exampleProjects.map((project) => (
                <ExampleProjectCard
                  key={project.id}
                  id={project.id}
                  title={project.title}
                  description={project.description}
                  onClick={() => toast.info(`Opening ${project.title} template`)}
                />
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
