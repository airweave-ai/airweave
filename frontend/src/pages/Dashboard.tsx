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
  ConnectFlow
} from "@/components/dashboard";
import { cn } from "@/lib/utils";
import { getStoredErrorDetails, clearStoredErrorDetails } from "@/lib/error-utils";

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
  const [collections, setCollections] = useState<Collection[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [apiKey, setApiKey] = useState<APIKey | null>(null);
  const [isLoadingCollections, setIsLoadingCollections] = useState(true);
  const [isLoadingSources, setIsLoadingSources] = useState(true);
  const [isLoadingApiKey, setIsLoadingApiKey] = useState(true);
  const [collectionsWithSources, setCollectionsWithSources] = useState<Record<string, SourceConnection[]>>({});

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);

  // Error state for connection errors
  const [connectionError, setConnectionError] = useState<any>(null);

  // Check for error parameters in URL and read details from localStorage
  useEffect(() => {
    const connected = searchParams.get('connected');
    if (connected === 'error') {
      console.log("🔔 [Dashboard] Detected 'connected=error' parameter in URL");

      // Retrieve error details from localStorage
      const errorDetails = getStoredErrorDetails();

      if (errorDetails) {
        console.log("🔔 [Dashboard] Found error details in localStorage:", errorDetails);

        // Set error state and open dialog
        setConnectionError({
          serviceName: errorDetails.serviceName || "the service",
          errorMessage: errorDetails.errorMessage || "Connection failed",
          errorDetails: errorDetails.errorDetails
        });

        // Open the dialog in error view mode
        setDialogOpen(true);
      } else {
        console.warn("⚠️ [Dashboard] 'connected=error' detected but no error details found in localStorage");

        // Fallback to URL parameters for backwards compatibility
        const errorMessage = searchParams.get('errorMessage');
        const errorDetails = searchParams.get('errorDetails');
        const sourceName = searchParams.get('source');

        if (errorMessage) {
          console.log("🔔 [Dashboard] Using URL parameters for error details");
          setConnectionError({
            serviceName: sourceName ? decodeURIComponent(sourceName) : "the service",
            errorMessage: decodeURIComponent(errorMessage),
            errorDetails: errorDetails ? decodeURIComponent(errorDetails) : undefined
          });

          setDialogOpen(true);
        }
      }

      // Clean localStorage and URL parameters
      clearStoredErrorDetails();

      // Clean URL parameters
      const newUrl = location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }, [searchParams, location]);

  // Fetch source connections for a specific collection
  const fetchSourceConnectionsForCollection = async (
    collectionId: string,
    sourcesMap: Record<string, SourceConnection[]>
  ) => {
    try {
      const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);
      if (response.ok) {
        const data = await response.json();
        sourcesMap[collectionId] = data;
      } else {
        console.error(`Failed to load source connections for collection ${collectionId}:`, await response.text());
        sourcesMap[collectionId] = [];
      }
    } catch (err) {
      console.error(`Error fetching source connections for collection ${collectionId}:`, err);
      sourcesMap[collectionId] = [];
    }
  };

  // Define fetchCollections function at component level
  const fetchCollections = async (showLoading: boolean = true) => {
    if (showLoading) {
      setIsLoadingCollections(true);
    }

    try {
      const response = await apiClient.get("/collections");
      if (response.ok) {
        const data = await response.json();
        setCollections(data);

        // Only fetch source connections for the top 3 collections
        const topCollections = data.slice(0, 3);
        const sourcesMap: Record<string, SourceConnection[]> = {};
        for (const collection of topCollections) {
          await fetchSourceConnectionsForCollection(collection.readable_id, sourcesMap);
        }
        setCollectionsWithSources(sourcesMap);
      } else {
        console.error("Failed to load collections:", await response.text());
      }
    } catch (err) {
      console.error("Error fetching collections:", err);
    } finally {
      if (showLoading) {
        setIsLoadingCollections(false);
      }
    }
  };

  // Fetch collections on component mount
  useEffect(() => {
    fetchCollections();
  }, []);

  // Fetch sources
  useEffect(() => {
    const fetchSources = async () => {
      setIsLoadingSources(true);
      try {
        const response = await apiClient.get("/sources/list");
        if (response.ok) {
          const data = await response.json();
          setSources(data);
        } else {
          console.error("Failed to load sources:", await response.text());
        }
      } catch (err) {
        console.error("Error fetching sources:", err);
      } finally {
        setIsLoadingSources(false);
      }
    };

    fetchSources();
  }, []);

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
    // Set the selected source
    setSelectedSource(source);
    // Open the dialog
    setDialogOpen(true);
  };

  // Handle dialog close
  const handleDialogClose = () => {
    setDialogOpen(false);
    setSelectedSource(null);
    setConnectionError(null);
    clearStoredErrorDetails(); // Ensure error data is cleared
    // Refresh collections without showing loading state
    fetchCollections(false);
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

  return (
    <div className="mx-auto w-full max-w-[1800px] px-6 py-6 pb-8">
      {/* Connect Flow Dialog */}
      <ConnectFlow
        isOpen={dialogOpen}
        onOpenChange={handleDialogClose}
        mode={connectionError ? "error-view" : "create-collection"}
        sourceId={selectedSource?.id}
        sourceName={selectedSource?.name}
        sourceShortName={selectedSource?.short_name}
        onComplete={() => fetchCollections(false)}
        errorData={connectionError}
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
        {/* Main content (left column) */}
        <div className="sm:col-span-2 space-y-8 sm:space-y-10">
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

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8 auto-rows-fr">
                {isLoadingCollections ? (
                  Array.from({ length: 3 }).map((_, index) => (
                    <div
                      key={index}
                      className="h-[220px] rounded-xl animate-pulse bg-slate-100 dark:bg-slate-800/50"
                    />
                  ))
                ) : (
                  topCollections.map((collection) => (
                    <CollectionCard
                      key={collection.id}
                      id={collection.id}
                      name={collection.name}
                      readableId={collection.readable_id}
                      sourceConnections={collectionsWithSources[collection.readable_id] || []}
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

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4 auto-rows-fr">
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
        <div className="sm:col-span-1 space-y-6 sm:space-y-8">
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
