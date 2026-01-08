/**
 * SemanticMcp Page - Turn any app into a semantically searchable MCP server
 *
 * This page provides a standalone experience for connecting data sources
 * and querying them via MCP (Model Context Protocol), without requiring
 * a full organization setup.
 *
 * Features:
 * - Source connection grid with authentication flows
 * - Auto-created collection for connected sources
 * - Real-time sync status display
 * - Semantic search interface
 */

import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import {
  Check,
  Loader2,
  Moon,
  Plus,
  Sun,
  Monitor,
  Play,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { ValidatedInput } from "@/components/validated-input";
import { Search } from "@/features/search/components/search";
import { useIsDark } from "@/hooks/use-is-dark";
import {
  createApiKey,
  createCollection,
  createSourceConnection,
  fetchSource,
  fetchSourceConnections,
  fetchSources,
  runSourceConnectionSync,
  type Collection,
  type CreateSourceConnectionAuth,
  type Source,
  type SourceConnection,
} from "@/lib/api";
import { API_BASE_URL, getAuthHeaders } from "@/lib/api/client";
import { useAuth0 } from "@/lib/auth-provider";
import { cn } from "@/lib/utils";
import { getAuthFieldValidation } from "@/lib/validation";
import { useUISettings } from "@/stores/ui-settings";

import { getAppIconUrl } from "@/features/collections/utils/helpers";

export const Route = createFileRoute("/semantic-mcp")({
  component: SemanticMcpPage,
  validateSearch: (search: Record<string, unknown>) => ({
    error: (search.error as string) || undefined,
    restore_dialog: (search.restore_dialog as string) || undefined,
  }),
});

// Session storage keys
const SESSION_KEYS = {
  API_KEY: "semantic_mcp_api_key",
  COLLECTION: "semantic_mcp_collection",
  CONNECTED_SOURCES: "semantic_mcp_connected_sources",
  OAUTH_STATE: "oauth_dialog_state",
  ERROR: "semantic_mcp_error",
};

function SemanticMcpPage() {
  const isDark = useIsDark();
  const { theme, setTheme } = useUISettings();
  const { getAccessTokenSilently, isAuthenticated, isLoading: authLoading } = useAuth0();
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/semantic-mcp" });

  // State
  const [connectedSourceIds, setConnectedSourceIds] = useState<Set<string>>(
    new Set()
  );
  const [currentCollection, setCurrentCollection] = useState<Collection | null>(
    null
  );
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [authValues, setAuthValues] = useState<Record<string, string>>({});
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isAuthenticated_, setIsAuthenticated_] = useState(false);
  const [credentialId, setCredentialId] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<
    string | null
  >(null);

  // Track OAuth processing
  const hasProcessedOAuthRef = useRef(false);

  // Temporary org ID for API calls (will use default org context)
  const [tempOrgId] = useState<string | null>(null);

  // Fetch sources
  const { data: sources = [], isLoading: sourcesLoading } = useQuery({
    queryKey: ["semantic-mcp-sources"],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      // For semantic-mcp, we use a special endpoint or default org
      // The API should handle this gracefully
      return fetchSources(token, tempOrgId || "");
    },
    enabled: isAuthenticated && !authLoading,
  });

  // Fetch source connections for current collection
  const { data: sourceConnections = [], refetch: refetchConnections } =
    useQuery({
      queryKey: [
        "semantic-mcp-connections",
        currentCollection?.readable_id,
      ],
      queryFn: async () => {
        if (!currentCollection?.readable_id) return [];
        const token = await getAccessTokenSilently();
        return fetchSourceConnections(
          token,
          tempOrgId || "",
          currentCollection.readable_id
        );
      },
      enabled: isAuthenticated && !!currentCollection?.readable_id,
      refetchInterval: 5000, // Poll for updates
    });

  // Fetch source details when a source is selected
  const { data: sourceDetails, isLoading: sourceDetailsLoading } = useQuery({
    queryKey: ["semantic-mcp-source-details", selectedSource?.short_name],
    queryFn: async () => {
      if (!selectedSource?.short_name) return null;
      const token = await getAccessTokenSilently();
      return fetchSource(token, tempOrgId || "", selectedSource.short_name);
    },
    enabled: isAuthenticated && !!selectedSource?.short_name && isDialogOpen,
  });

  // Restore session state on mount
  useEffect(() => {
    const savedCollection = sessionStorage.getItem(SESSION_KEYS.COLLECTION);
    if (savedCollection) {
      try {
        setCurrentCollection(JSON.parse(savedCollection));
      } catch {
        sessionStorage.removeItem(SESSION_KEYS.COLLECTION);
      }
    }

    const savedSources = sessionStorage.getItem(SESSION_KEYS.CONNECTED_SOURCES);
    if (savedSources) {
      try {
        setConnectedSourceIds(new Set(JSON.parse(savedSources)));
      } catch {
        sessionStorage.removeItem(SESSION_KEYS.CONNECTED_SOURCES);
      }
    }
  }, []);

  // Save collection to session storage
  useEffect(() => {
    if (currentCollection) {
      sessionStorage.setItem(
        SESSION_KEYS.COLLECTION,
        JSON.stringify(currentCollection)
      );
    }
  }, [currentCollection]);

  // Save connected sources to session storage
  useEffect(() => {
    if (connectedSourceIds.size > 0) {
      sessionStorage.setItem(
        SESSION_KEYS.CONNECTED_SOURCES,
        JSON.stringify([...connectedSourceIds])
      );
    }
  }, [connectedSourceIds]);

  // Handle OAuth errors and dialog restoration
  useEffect(() => {
    if (hasProcessedOAuthRef.current) return;

    if (searchParams.error === "oauth") {
      hasProcessedOAuthRef.current = true;
      const errorData = sessionStorage.getItem(SESSION_KEYS.ERROR);
      if (errorData) {
        try {
          const parsed = JSON.parse(errorData);
          toast.error(`OAuth failed for ${parsed.sourceName}`, {
            description: parsed.message,
          });
        } catch {
          toast.error("OAuth authentication failed");
        }
        sessionStorage.removeItem(SESSION_KEYS.ERROR);
      } else {
        toast.error("OAuth authentication failed");
      }
      // Clear error from URL
      navigate({ to: "/semantic-mcp", search: { error: undefined, restore_dialog: undefined }, replace: true });
    } else if (searchParams.restore_dialog === "true") {
      hasProcessedOAuthRef.current = true;
      const savedState = sessionStorage.getItem(SESSION_KEYS.OAUTH_STATE);
      if (savedState) {
        try {
          const state = JSON.parse(savedState);
          if (state.selectedSource) setSelectedSource(state.selectedSource);
          if (state.authValues) setAuthValues(state.authValues);
          if (state.configValues) setConfigValues(state.configValues);
          if (state.isAuthenticated) setIsAuthenticated_(state.isAuthenticated);
          if (state.credentialId) setCredentialId(state.credentialId);
          if (state.currentCollection) setCurrentCollection(state.currentCollection);
          setIsDialogOpen(true);
          sessionStorage.removeItem(SESSION_KEYS.OAUTH_STATE);
        } catch {
          toast.error("Failed to restore dialog state");
        }
      }
      navigate({ to: "/semantic-mcp", search: { error: undefined, restore_dialog: undefined }, replace: true });
    }
  }, [searchParams, navigate]);

  // Ensure API key exists
  useEffect(() => {
    const ensureApiKey = async () => {
      if (!isAuthenticated) return;
      const existingKey = sessionStorage.getItem(SESSION_KEYS.API_KEY);
      if (existingKey) return;

      try {
        const token = await getAccessTokenSilently();
        const apiKey = await createApiKey(token, tempOrgId || "");
        sessionStorage.setItem(SESSION_KEYS.API_KEY, apiKey.decrypted_key);
      } catch (error) {
        console.error("Failed to create API key:", error);
      }
    };

    ensureApiKey();
  }, [isAuthenticated, getAccessTokenSilently, tempOrgId]);

  // Sorted and filtered sources
  const sortedSources = useMemo(() => {
    return [...sources]
      .filter(
        (s) =>
          s.short_name.toLowerCase() !== "ctti" &&
          s.short_name.toLowerCase() !== "oracle"
      )
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [sources]);

  // Handle source click
  const handleSourceClick = useCallback(
    (source: Source) => {
      if (connectedSourceIds.has(source.id)) return;
      setSelectedSource(source);
      setAuthValues({});
      setConfigValues({});
      setIsAuthenticated_(false);
      setCredentialId(null);
      setIsDialogOpen(true);
    },
    [connectedSourceIds]
  );

  // Handle dialog close
  const handleDialogClose = useCallback(() => {
    setIsDialogOpen(false);
    setTimeout(() => {
      setSelectedSource(null);
      setAuthValues({});
      setConfigValues({});
      setIsAuthenticated_(false);
      setCredentialId(null);
    }, 200);
  }, []);

  // Check if form is valid for authentication
  const isFormValid = useMemo(() => {
    if (!sourceDetails?.auth_fields?.fields) return true;
    return sourceDetails.auth_fields.fields
      .filter(
        (f) => f.name !== "refresh_token" && f.name !== "access_token"
      )
      .every((f) => !f.required || authValues[f.name]?.trim());
  }, [sourceDetails, authValues]);

  // Handle authentication (non-OAuth)
  const handleAuthenticate = useCallback(async () => {
    if (!sourceDetails || !selectedSource) return;

    const authType = sourceDetails.auth_type || "";
    const isOAuth = authType.startsWith("oauth2");

    if (isOAuth) {
      // OAuth flow - save state and redirect
      const dialogState = {
        selectedSource,
        detailedSource: sourceDetails,
        authValues,
        configValues,
        isAuthenticated: false,
        currentCollection,
        originPath: window.location.pathname,
        timestamp: Date.now(),
        source: "semantic-mcp",
      };
      sessionStorage.setItem(
        SESSION_KEYS.OAUTH_STATE,
        JSON.stringify(dialogState)
      );

      try {
        const token = await getAccessTokenSilently();
        let url = `${API_BASE_URL}/source-connections/${sourceDetails.short_name}/oauth2_url`;
        if (authValues.client_id) {
          url += `?client_id=${encodeURIComponent(authValues.client_id)}`;
        }

        const response = await fetch(url, {
          headers: getAuthHeaders(token, tempOrgId || ""),
        });

        if (!response.ok) {
          throw new Error("Failed to get OAuth URL");
        }

        const data = await response.json();
        if (data.url) {
          window.location.href = data.url;
        } else {
          throw new Error("No authorization URL returned");
        }
      } catch (error) {
        toast.error("Failed to start OAuth flow", {
          description: error instanceof Error ? error.message : "Unknown error",
        });
      }
    } else {
      // Direct auth flow - create credentials
      setIsAuthenticating(true);
      try {
        const token = await getAccessTokenSilently();
        const credentialData = {
          name: `${sourceDetails.name} Credential`,
          integration_short_name: sourceDetails.short_name,
          description: `Credential for ${sourceDetails.name}`,
          integration_type: "source",
          auth_type: sourceDetails.auth_type,
          auth_config_class: sourceDetails.auth_config_class,
          auth_fields: authValues,
        };

        const response = await fetch(
          `${API_BASE_URL}/connections/credentials/source/${sourceDetails.short_name}`,
          {
            method: "POST",
            headers: getAuthHeaders(token, tempOrgId || ""),
            body: JSON.stringify(credentialData),
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `Failed to authenticate with ${sourceDetails.name}`
          );
        }

        const credential = await response.json();
        setCredentialId(credential.id);
        setIsAuthenticated_(true);
        toast.success("Authentication successful");
      } catch (error) {
        toast.error("Authentication failed", {
          description: error instanceof Error ? error.message : "Unknown error",
        });
      } finally {
        setIsAuthenticating(false);
      }
    }
  }, [
    sourceDetails,
    selectedSource,
    authValues,
    configValues,
    currentCollection,
    getAccessTokenSilently,
    tempOrgId,
  ]);

  // Handle connect (create collection and source connection)
  const handleConnect = useCallback(async () => {
    if (!selectedSource || !sourceDetails) return;

    const currentCredentialId = credentialId;
    if (!currentCredentialId) {
      toast.error("Please authenticate first");
      return;
    }

    setIsConnecting(true);
    try {
      const token = await getAccessTokenSilently();
      let collection = currentCollection;

      // Create collection if needed
      if (!collection) {
        collection = await createCollection(token, tempOrgId || "", {
          name: "My Collection",
        });
        setCurrentCollection(collection);
      }

      // Create source connection
      const authentication: CreateSourceConnectionAuth = {
        credentials: authValues,
      };

      await createSourceConnection(token, tempOrgId || "", {
        name: `${selectedSource.name} Connection`,
        description: `Connection to ${selectedSource.name}`,
        short_name: selectedSource.short_name,
        readable_collection_id: collection.readable_id,
        authentication,
        config: Object.keys(configValues).length > 0 ? configValues : undefined,
        sync_immediately: true,
      });

      // Update state
      setConnectedSourceIds((prev) => new Set([...prev, selectedSource.id]));
      await refetchConnections();
      handleDialogClose();
      toast.success(`Connected to ${selectedSource.name}`);

      // Clear OAuth state if exists
      sessionStorage.removeItem(SESSION_KEYS.OAUTH_STATE);
    } catch (error) {
      toast.error("Failed to connect", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setIsConnecting(false);
    }
  }, [
    selectedSource,
    sourceDetails,
    credentialId,
    currentCollection,
    authValues,
    configValues,
    getAccessTokenSilently,
    tempOrgId,
    refetchConnections,
    handleDialogClose,
  ]);

  // Handle run sync
  const handleRunSync = useCallback(
    async (connectionId: string) => {
      try {
        const token = await getAccessTokenSilently();
        await runSourceConnectionSync(token, tempOrgId || "", connectionId);
        toast.success("Sync started");
        await refetchConnections();
      } catch (error) {
        toast.error("Failed to start sync", {
          description: error instanceof Error ? error.message : "Unknown error",
        });
      }
    },
    [getAccessTokenSilently, tempOrgId, refetchConnections]
  );

  // Get status color for connection
  const getStatusColor = (connection: SourceConnection) => {
    const status =
      connection.last_sync_job?.status || connection.status || "";
    switch (status.toLowerCase()) {
      case "completed":
        return "bg-green-500";
      case "in_progress":
        return "bg-blue-500 animate-pulse";
      case "failed":
        return "bg-red-500";
      case "pending":
        return "bg-yellow-500";
      default:
        return "bg-gray-500";
    }
  };

  // Determine if auth fields should show password type
  const isSensitiveField = (name: string): boolean => {
    return ["password", "token", "secret", "key"].some((s) =>
      name.toLowerCase().includes(s)
    );
  };

  // Logo based on theme
  const logoSrc = isDark
    ? "/airweave-logo-svg-white-darkbg.svg"
    : "/airweave-logo-svg-lightbg-blacklogo.svg";

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="bg-background min-h-screen">
      {/* Theme Toggle - Top Right */}
      <div className="absolute right-4 top-4 z-10">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-lg"
            >
              {isDark ? (
                <Moon className="h-[18px] w-[18px]" />
              ) : (
                <Sun className="h-[18px] w-[18px]" />
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-32">
            <DropdownMenuItem onClick={() => setTheme("light")}>
              <Sun className="mr-2 h-4 w-4" />
              Light
              {theme === "light" && <Check className="ml-auto h-4 w-4" />}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("dark")}>
              <Moon className="mr-2 h-4 w-4" />
              Dark
              {theme === "dark" && <Check className="ml-auto h-4 w-4" />}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("system")}>
              <Monitor className="mr-2 h-4 w-4" />
              System
              {theme === "system" && <Check className="ml-auto h-4 w-4" />}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Header */}
      <div className="flex flex-col items-center justify-center pt-8">
        <img src={logoSrc} alt="Airweave" className="h-16 w-auto" />
        <p className="text-muted-foreground mt-4 text-center text-lg">
          Turn any app into a semantically searchable MCP server
        </p>
      </div>

      {/* Sources Section */}
      <div className="mx-auto mt-6 max-w-[900px] px-10">
        <div
          className={cn(
            "rounded-xl border px-6 py-4 backdrop-blur-sm",
            isDark
              ? "border-gray-700 bg-gray-900/30"
              : "border-gray-200 bg-white/50"
          )}
        >
          <h2 className="mb-4 text-center text-2xl">
            Connect to your data sources
          </h2>

          <div className="mx-auto grid grid-cols-4 gap-2 sm:grid-cols-6 md:grid-cols-8">
            {sourcesLoading ? (
              <div className="col-span-full flex h-40 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : sources.length === 0 ? (
              <div className="text-muted-foreground col-span-full py-10 text-center">
                No sources available
              </div>
            ) : (
              sortedSources.map((source) => (
                <SmallSourceButton
                  key={source.id}
                  source={source}
                  connected={connectedSourceIds.has(source.id)}
                  onClick={() => handleSourceClick(source)}
                  isDark={isDark}
                />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Data Sync Section */}
      <div className="mx-auto mt-6 max-w-[900px] px-10">
        <div
          className={cn(
            "rounded-xl border px-6 py-4 backdrop-blur-sm",
            sourceConnections.length === 0
              ? isDark
                ? "border-gray-600/50 bg-gray-800/20"
                : "border-gray-300/50 bg-gray-100/30"
              : isDark
                ? "border-gray-700 bg-gray-900/30"
                : "border-gray-200 bg-white/50"
          )}
        >
          <h2
            className={cn(
              "mb-4 text-center text-2xl",
              sourceConnections.length === 0 && "text-muted-foreground/60"
            )}
          >
            {sourceConnections.length === 0
              ? "Data will start syncing once you connect your data"
              : "Data sync"}
          </h2>

          {sourceConnections.length > 0 && (
            <div className="space-y-3">
              {/* Connection cards */}
              <div className="flex flex-wrap gap-2">
                {sourceConnections.map((connection) => (
                  <button
                    key={connection.id}
                    onClick={() => setSelectedConnectionId(connection.id)}
                    className={cn(
                      "flex h-[60px] min-w-[100px] items-center justify-between gap-2 rounded-lg border p-2 transition-all",
                      selectedConnectionId === connection.id
                        ? "border-2 border-primary"
                        : isDark
                          ? "border-gray-700 bg-gray-800/50 hover:bg-gray-700/70"
                          : "border-gray-200 bg-white hover:bg-gray-50"
                    )}
                  >
                    <div
                      className={cn(
                        "flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full",
                        isDark ? "bg-gray-800/80" : "bg-gray-100/80"
                      )}
                    >
                      <span
                        className={cn(
                          "inline-flex h-3 w-3 rounded-full",
                          getStatusColor(connection)
                        )}
                      />
                    </div>
                    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center overflow-hidden rounded-md">
                      <img
                        src={getAppIconUrl(
                          connection.short_name,
                          isDark ? "dark" : "light"
                        )}
                        alt={connection.name}
                        className="h-9 w-9 object-contain"
                      />
                    </div>
                  </button>
                ))}
              </div>

              {/* Selected connection details */}
              {selectedConnectionId && (
                <ConnectionDetails
                  connectionId={selectedConnectionId}
                  onRunSync={handleRunSync}
                  isDark={isDark}
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* Query Section */}
      <div className="mx-auto mt-6 max-w-[900px] px-10 pb-10">
        <div
          className={cn(
            "relative rounded-xl border px-6 py-4 backdrop-blur-sm",
            sourceConnections.length === 0
              ? isDark
                ? "border-gray-600/50 bg-gray-800/20"
                : "border-gray-300/50 bg-gray-100/30"
              : isDark
                ? "border-gray-700 bg-gray-900/30"
                : "border-gray-200 bg-white/50"
          )}
        >
          <h2
            className={cn(
              "mb-4 text-center text-2xl",
              sourceConnections.length === 0 && "text-muted-foreground/60"
            )}
          >
            Query your data
          </h2>

          <div className="relative pt-2">
            <Search
              collectionReadableId={
                currentCollection?.readable_id || "my-collection"
              }
              disabled={sourceConnections.length === 0}
              disabledReason="Connect a data source to start querying"
            />

            {sourceConnections.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-gray-50/50 backdrop-blur-[1px] dark:bg-gray-900/50" />
            )}
          </div>
        </div>
      </div>

      {/* Source Connect Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={(open) => !open && handleDialogClose()}>
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-center gap-3 text-xl">
              Connect to {selectedSource?.name}
              {selectedSource && (
                <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-lg border">
                  <img
                    src={getAppIconUrl(
                      selectedSource.short_name,
                      isDark ? "dark" : "light"
                    )}
                    alt={selectedSource.short_name}
                    className="h-11 w-11 object-contain"
                  />
                </div>
              )}
            </DialogTitle>
          </DialogHeader>

          {sourceDetailsLoading ? (
            <div className="flex flex-col items-center justify-center py-8">
              <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
              <p className="text-muted-foreground mt-2 text-sm">
                Loading source details...
              </p>
            </div>
          ) : selectedSource && sourceDetails ? (
            <div className="space-y-6">
              {/* Auth Fields */}
              {sourceDetails.auth_fields?.fields &&
                sourceDetails.auth_fields.fields.length > 0 && (
                  <div className="space-y-4">
                    {sourceDetails.auth_fields.fields
                      .filter(
                        (field) =>
                          field.name !== "refresh_token" &&
                          field.name !== "access_token"
                      )
                      .map((field) => {
                        const validation = getAuthFieldValidation(field.name);
                        return (
                          <div key={field.name} className="space-y-2">
                            <Label className="text-sm font-medium">
                              {field.display_name || field.name}
                              {field.required && (
                                <span className="text-destructive ml-1">*</span>
                              )}
                            </Label>
                            {field.description && (
                              <p className="text-muted-foreground text-xs">
                                {field.description}
                              </p>
                            )}
                            <ValidatedInput
                              type={
                                isSensitiveField(field.name)
                                  ? "password"
                                  : "text"
                              }
                              value={authValues[field.name] || ""}
                              onChange={(value) =>
                                setAuthValues((prev) => ({
                                  ...prev,
                                  [field.name]: value,
                                }))
                              }
                              validation={validation ?? undefined}
                              placeholder={`Enter ${(field.display_name || field.name).toLowerCase()}`}
                            />
                          </div>
                        );
                      })}
                  </div>
                )}

              {/* Config Fields */}
              {sourceDetails.config_fields?.fields &&
                sourceDetails.config_fields.fields.length > 0 && (
                  <div className="space-y-4">
                    <Label className="text-muted-foreground text-xs uppercase tracking-wider">
                      Configuration
                    </Label>
                    {sourceDetails.config_fields.fields.map((field) => (
                      <div key={field.name} className="space-y-2">
                        <Label className="text-sm font-medium">
                          {field.display_name || field.name}
                          {field.required && (
                            <span className="text-destructive ml-1">*</span>
                          )}
                        </Label>
                        {field.description && (
                          <p className="text-muted-foreground text-xs">
                            {field.description}
                          </p>
                        )}
                        <ValidatedInput
                          type={
                            isSensitiveField(field.name) ? "password" : "text"
                          }
                          value={configValues[field.name] || ""}
                          onChange={(value) =>
                            setConfigValues((prev) => ({
                              ...prev,
                              [field.name]: value,
                            }))
                          }
                          placeholder={`Enter ${(field.display_name || field.name).toLowerCase()}`}
                        />
                      </div>
                    ))}
                  </div>
                )}

              {/* Action Buttons */}
              <div className="flex justify-center gap-3 pt-4">
                <Button
                  onClick={handleAuthenticate}
                  disabled={!isFormValid || isAuthenticating}
                  className={cn(
                    "flex items-center gap-2 px-6",
                    isAuthenticated_ && "bg-green-600 hover:bg-green-700"
                  )}
                >
                  {isAuthenticating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : isAuthenticated_ ? (
                    <Check className="h-4 w-4" />
                  ) : null}
                  {isAuthenticated_ ? "Authenticated" : "Authenticate"}
                </Button>

                <Button
                  onClick={handleConnect}
                  disabled={!isAuthenticated_ || isConnecting}
                  variant={isAuthenticated_ ? "default" : "secondary"}
                  className="px-6"
                >
                  {isConnecting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Connect
                </Button>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Small Source Button Component
interface SmallSourceButtonProps {
  source: Source;
  connected: boolean;
  onClick: () => void;
  isDark: boolean;
}

function SmallSourceButton({
  source,
  connected,
  onClick,
  isDark,
}: SmallSourceButtonProps) {
  return (
    <div
      onClick={connected ? undefined : onClick}
      className={cn(
        "group flex h-[60px] min-w-[100px] cursor-pointer items-center justify-between overflow-hidden rounded-lg border p-2 transition-all",
        connected
          ? isDark
            ? "border-blue-400 bg-blue-500/20"
            : "border-blue-500 bg-blue-50"
          : isDark
            ? "border-gray-800 bg-gray-900/50 hover:border-gray-700 hover:bg-gray-900"
            : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
      )}
      title={connected ? `${source.name} (Connected)` : source.name}
    >
      {connected ? (
        <div
          className={cn(
            "flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full",
            isDark
              ? "bg-blue-600/60 text-blue-200"
              : "bg-blue-500 text-white"
          )}
        >
          <Check className="h-3 w-3" />
        </div>
      ) : (
        <div
          className={cn(
            "flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full",
            isDark
              ? "bg-gray-800/80 text-blue-400 group-hover:bg-blue-600/30"
              : "bg-gray-100/80 text-blue-500 group-hover:bg-blue-100/80"
          )}
        >
          <Plus className="h-3 w-3 transition-all group-hover:h-3.5 group-hover:w-3.5" />
        </div>
      )}
      <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center overflow-hidden rounded-md">
        <img
          src={getAppIconUrl(source.short_name, isDark ? "dark" : "light")}
          alt={source.short_name}
          className="h-9 w-9 object-contain"
        />
      </div>
    </div>
  );
}

// Connection Details Component
interface ConnectionDetailsProps {
  connectionId: string;
  onRunSync: (connectionId: string) => void;
  isDark: boolean;
}

function ConnectionDetails({
  connectionId,
  onRunSync,
  isDark,
}: ConnectionDetailsProps) {
  const { getAccessTokenSilently } = useAuth0();
  const [isRunningSync, setIsRunningSync] = useState(false);

  const { data: connection, isLoading } = useQuery({
    queryKey: ["semantic-mcp-connection-detail", connectionId],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      const response = await fetch(
        `${API_BASE_URL}/source-connections/${connectionId}`,
        {
          headers: getAuthHeaders(token, ""),
        }
      );
      if (!response.ok) throw new Error("Failed to fetch connection");
      return response.json() as Promise<SourceConnection>;
    },
    refetchInterval: 5000,
  });

  const handleRunSync = async () => {
    setIsRunningSync(true);
    await onRunSync(connectionId);
    setIsRunningSync(false);
  };

  if (isLoading || !connection) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const syncJob = connection.last_sync_job;
  const status = syncJob?.status || connection.status || "unknown";
  const isInProgress = status === "in_progress";

  return (
    <div
      className={cn(
        "space-y-3 rounded-lg border p-4",
        isDark ? "border-gray-700 bg-gray-800/30" : "border-gray-200 bg-gray-50"
      )}
    >
      {/* Header with connection name and run sync button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <img
            src={getAppIconUrl(connection.short_name, isDark ? "dark" : "light")}
            alt={connection.name}
            className="h-6 w-6"
          />
          <span className="font-medium">{connection.name}</span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRunSync}
          disabled={isRunningSync || isInProgress}
        >
          {isRunningSync || isInProgress ? (
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="mr-2 h-3.5 w-3.5" />
          )}
          {isInProgress ? "Syncing..." : "Run Sync"}
        </Button>
      </div>

      {/* Status badges */}
      <div className="flex flex-wrap gap-2">
        <StatusBadge
          label="Status"
          value={status}
          color={
            status === "completed"
              ? "green"
              : status === "in_progress"
                ? "blue"
                : status === "failed"
                  ? "red"
                  : "gray"
          }
          isDark={isDark}
          pulse={isInProgress}
        />

        {syncJob?.entities_inserted !== undefined && (
          <StatusBadge
            label="Inserted"
            value={syncJob.entities_inserted.toLocaleString()}
            color="green"
            isDark={isDark}
          />
        )}

        {syncJob?.entities_updated !== undefined && (
          <StatusBadge
            label="Updated"
            value={syncJob.entities_updated.toLocaleString()}
            color="cyan"
            isDark={isDark}
          />
        )}

        {syncJob?.entities_deleted !== undefined && syncJob.entities_deleted > 0 && (
          <StatusBadge
            label="Deleted"
            value={syncJob.entities_deleted.toLocaleString()}
            color="red"
            isDark={isDark}
          />
        )}
      </div>

      {/* Error display */}
      {syncJob?.error && (
        <div
          className={cn(
            "rounded-md border p-3 text-sm",
            isDark
              ? "border-red-800 bg-red-900/20 text-red-400"
              : "border-red-200 bg-red-50 text-red-700"
          )}
        >
          {syncJob.error}
        </div>
      )}
    </div>
  );
}

// Status Badge Component
interface StatusBadgeProps {
  label: string;
  value: string | number;
  color: "green" | "cyan" | "blue" | "red" | "yellow" | "gray";
  isDark: boolean;
  pulse?: boolean;
}

function StatusBadge({ label, value, color, isDark, pulse }: StatusBadgeProps) {
  const colorClasses = {
    green: "bg-green-500",
    cyan: "bg-cyan-500",
    blue: "bg-blue-500",
    red: "bg-red-500",
    yellow: "bg-yellow-500",
    gray: "bg-gray-500",
  };

  return (
    <div
      className={cn(
        "flex h-8 items-center gap-2 rounded-lg border px-3 text-sm",
        isDark
          ? "border-gray-700 bg-gray-800/50"
          : "border-gray-200 bg-white"
      )}
    >
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          colorClasses[color],
          pulse && "animate-pulse"
        )}
      />
      <span className="text-muted-foreground text-xs uppercase">{label}</span>
      <span className="font-medium capitalize">{value}</span>
    </div>
  );
}
