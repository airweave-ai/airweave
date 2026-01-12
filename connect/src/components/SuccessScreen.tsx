import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { apiClient } from "../lib/api";
import { canConnect } from "../lib/connection-utils";
import { useTheme } from "../lib/theme";
import type {
  ConnectSessionContext,
  NavigateView,
  Source,
} from "../lib/types";
import { ConnectionItem } from "./ConnectionItem";
import { ConnectionsErrorView } from "./ConnectionsErrorView";
import { EmptyState } from "./EmptyState";
import { LoadingScreen } from "./LoadingScreen";
import { PoweredByAirweave } from "./PoweredByAirweave";
import { SourcesList } from "./SourcesList";

interface SuccessScreenProps {
  session: ConnectSessionContext;
  initialView?: NavigateView | null;
  onViewChange?: (view: NavigateView) => void;
}

export function SuccessScreen({
  session,
  initialView,
  onViewChange,
}: SuccessScreenProps) {
  const { labels } = useTheme();
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Determine default view based on session mode
  const defaultView: NavigateView =
    session.mode === "connect" ? "sources" : "connections";

  // Internal state for user-initiated navigation
  const [internalView, setInternalView] = useState<NavigateView | null>(null);

  // Use initialView (from parent) if set, otherwise use internal state or default
  const view: NavigateView = initialView ?? internalView ?? defaultView;

  // Wrapper to handle view changes (user-initiated)
  const setView = (newView: NavigateView) => {
    setInternalView(newView);
    onViewChange?.(newView);
  };

  const allowConnect = canConnect(session.mode);

  const {
    data: connections,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["source-connections"],
    queryFn: () => apiClient.getSourceConnections(),
    enabled: session.mode !== "connect",
  });

  const deleteMutation = useMutation({
    mutationFn: (connectionId: string) =>
      apiClient.deleteSourceConnection(connectionId),
    onMutate: (connectionId) => {
      setDeletingId(connectionId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["source-connections"] });
    },
    onSettled: () => {
      setDeletingId(null);
    },
  });

  const handleSelectSource = (source: Source) => {
    // TODO: Handle source selection (will be implemented later)
    console.log("Selected source:", source);
  };

  // Show sources list when in "connect" mode or when user clicked Connect
  if (view === "sources") {
    return (
      <SourcesList
        labels={labels}
        onBack={
          session.mode === "connect" ? null : () => setView("connections")
        }
        onSelectSource={handleSelectSource}
      />
    );
  }

  if (isLoading) return <LoadingScreen />;

  if (error) {
    return <ConnectionsErrorView error={error} labels={labels} />;
  }

  return (
    <div
      className="h-screen flex flex-col"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      {/* Fixed Header */}
      <header className="flex-shrink-0 p-6 pb-4">
        <div className="flex items-center justify-between">
          <h1
            className="font-medium text-lg"
            style={{ color: "var(--connect-text)" }}
          >
            {labels.sourcesHeading}
          </h1>
          {allowConnect && connections && connections.length > 0 && (
            <button
              onClick={() => setView("sources")}
              className="px-3 py-1.5 font-medium rounded-md text-sm transition-colors flex items-center gap-1.5"
              style={{
                backgroundColor: "var(--connect-primary)",
                color: "white",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.backgroundColor =
                  "var(--connect-primary-hover)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.backgroundColor =
                  "var(--connect-primary)")
              }
            >
              <Plus className="w-4 h-4" />
              {labels.buttonConnect}
            </button>
          )}
        </div>
      </header>

      {/* Scrollable Content */}
      <main className="flex-1 overflow-y-auto px-6 scrollable-content">
        {connections && connections.length > 0 ? (
          <div className="flex flex-col gap-3 pb-4">
            {connections.map((connection) => (
              <ConnectionItem
                key={connection.id}
                connection={connection}
                onDelete={() => deleteMutation.mutate(connection.id)}
                isDeleting={deletingId === connection.id}
                labels={labels}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            labels={labels}
            showConnect={allowConnect}
            onConnect={() => setView("sources")}
          />
        )}
      </main>

      {/* Fixed Footer */}
      <footer className="flex-shrink-0">
        <PoweredByAirweave />
      </footer>
    </div>
  );
}
