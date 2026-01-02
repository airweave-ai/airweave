import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import {
  AuthProviderCard,
  AuthProvidersCode,
  AuthProvidersDocs,
  AuthProvidersHelp,
  COMING_SOON_PROVIDERS,
  ConfigureDialog,
  DetailDialog,
  EditDialog,
} from "@/features/auth-providers";
import {
  fetchAuthProviderConnections,
  fetchAuthProviders,
  type AuthProvider,
  type AuthProviderConnection,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";

export const Route = createFileRoute("/$orgSlug/auth-providers")({
  component: AuthProvidersPage,
});

type DialogMode = "configure" | "detail" | "edit" | null;

function AuthProvidersPage() {
  const { getAccessTokenSilently } = useAuth0();

  // Dialog state
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [selectedProvider, setSelectedProvider] = useState<AuthProvider | null>(
    null
  );
  const [selectedConnection, setSelectedConnection] =
    useState<AuthProviderConnection | null>(null);

  usePageHeader({
    title: "Auth Providers",
    description: "Authenticate data sources through third-party applications",
  });

  useRightSidebarContent({
    docs: <AuthProvidersDocs />,
    code: <AuthProvidersCode />,
    help: <AuthProvidersHelp />,
  });

  // Fetch auth providers
  const {
    data: authProviders,
    isLoading: isLoadingProviders,
    error: providersError,
  } = useQuery({
    queryKey: ["auth-providers"],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchAuthProviders(token);
    },
  });

  // Fetch auth provider connections
  const {
    data: connections,
    isLoading: isLoadingConnections,
    error: connectionsError,
  } = useQuery({
    queryKey: ["auth-provider-connections"],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchAuthProviderConnections(token);
    },
  });

  // Combine real providers with coming soon providers
  const allProviders = useMemo(() => {
    if (!authProviders) return COMING_SOON_PROVIDERS;
    return [...authProviders, ...COMING_SOON_PROVIDERS];
  }, [authProviders]);

  // Get connection for a provider
  const getConnectionForProvider = (shortName: string) => {
    return connections?.find((conn) => conn.short_name === shortName);
  };

  // Handle provider card click
  const handleProviderClick = (
    provider: AuthProvider | (typeof COMING_SOON_PROVIDERS)[0]
  ) => {
    // Don't handle clicks for coming soon providers
    if ("isComingSoon" in provider && provider.isComingSoon) return;

    const connection = getConnectionForProvider(provider.short_name);

    if (connection) {
      // Provider is connected, show details
      setSelectedProvider(provider as AuthProvider);
      setSelectedConnection(connection);
      setDialogMode("detail");
    } else {
      // Provider not connected, show configure dialog
      setSelectedProvider(provider as AuthProvider);
      setSelectedConnection(null);
      setDialogMode("configure");
    }
  };

  // Handle dialog close
  const handleDialogClose = () => {
    setDialogMode(null);
    setSelectedProvider(null);
    setSelectedConnection(null);
  };

  // Handle edit from detail dialog
  const handleEdit = () => {
    setDialogMode("edit");
  };

  // Handle success from configure dialog
  const handleConfigureSuccess = (connectionId: string) => {
    // Find the newly created connection
    const newConnection = connections?.find(
      (conn) => conn.readable_id === connectionId
    );
    if (newConnection && selectedProvider) {
      setSelectedConnection(newConnection);
      setDialogMode("detail");
    } else {
      handleDialogClose();
    }
  };

  // Handle success from edit dialog
  const handleEditSuccess = () => {
    // Go back to detail view
    setDialogMode("detail");
  };

  const isLoading = isLoadingProviders || isLoadingConnections;
  const error = providersError || connectionsError;

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
          error={
            error instanceof Error ? error : "Failed to load auth providers"
          }
        />
      </div>
    );
  }

  // Empty state (no providers available at all)
  if (allProviders.length === 0) {
    return (
      <div className="p-6">
        <EmptyState
          icon={<ShieldCheck />}
          title="No auth providers available"
          description="Auth providers enable secure OAuth connections to external services."
        />
      </div>
    );
  }

  // Main content - provider grid
  return (
    <div className="p-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {allProviders.map((provider) => {
          const connection = getConnectionForProvider(provider.short_name);
          const isComingSoon =
            "isComingSoon" in provider && provider.isComingSoon;

          return (
            <AuthProviderCard
              key={provider.id}
              id={provider.id}
              name={provider.name}
              shortName={provider.short_name}
              isConnected={!!connection}
              isComingSoon={isComingSoon}
              onClick={() => handleProviderClick(provider)}
            />
          );
        })}
      </div>

      {/* Configure Dialog */}
      <ConfigureDialog
        open={dialogMode === "configure"}
        onOpenChange={(open) => {
          if (!open) handleDialogClose();
        }}
        authProvider={selectedProvider}
        onSuccess={handleConfigureSuccess}
      />

      {/* Detail Dialog */}
      <DetailDialog
        open={dialogMode === "detail"}
        onOpenChange={(open) => {
          if (!open) handleDialogClose();
        }}
        authProvider={selectedProvider}
        connection={selectedConnection}
        onEdit={handleEdit}
      />

      {/* Edit Dialog */}
      <EditDialog
        open={dialogMode === "edit"}
        onOpenChange={(open) => {
          if (!open) {
            // Go back to detail view instead of closing completely
            setDialogMode("detail");
          }
        }}
        authProvider={selectedProvider}
        connection={selectedConnection}
        onSuccess={handleEditSuccess}
      />
    </div>
  );
}
