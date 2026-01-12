import { LoadingScreen } from "@/components/LoadingScreen";
import { PoweredByAirweave } from "@/components/PoweredByAirweave";
import { Menu } from "@base-ui/react/menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  Link2,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { apiClient } from "../lib/api";
import { getAppIconUrl } from "../lib/icons";
import { useTheme } from "../lib/theme";
import type {
  ConnectLabels,
  ConnectSessionContext,
  ConnectSessionMode,
  NavigateView,
  Source,
  SourceConnectionListItem,
  SourceConnectionStatus,
} from "../lib/types";

interface SuccessScreenProps {
  session: ConnectSessionContext;
  initialView?: NavigateView | null;
  onViewChange?: (view: NavigateView) => void;
}

function canConnect(mode: ConnectSessionMode): boolean {
  return mode === "all" || mode === "connect";
}

function getStatusColor(status: SourceConnectionStatus): string {
  switch (status) {
    case "active":
      return "var(--connect-success)";
    case "syncing":
      return "var(--connect-primary)";
    case "pending_auth":
      return "#f59e0b";
    case "error":
      return "var(--connect-error)";
    case "inactive":
    default:
      return "var(--connect-text-muted)";
  }
}

function getStatusLabel(
  status: SourceConnectionStatus,
  labels: Required<ConnectLabels>,
): string {
  switch (status) {
    case "active":
      return labels.statusActive;
    case "syncing":
      return labels.statusSyncing;
    case "pending_auth":
      return labels.statusPendingAuth;
    case "error":
      return labels.statusError;
    case "inactive":
      return labels.statusInactive;
    default:
      return status;
  }
}

function ConnectionItem({
  connection,
  onDelete,
  isDeleting,
  labels,
}: {
  connection: SourceConnectionListItem;
  onDelete: () => void;
  isDeleting: boolean;
  labels: Required<ConnectLabels>;
}) {
  const { resolvedMode } = useTheme();
  const [imgError, setImgError] = useState(false);
  const statusColor = getStatusColor(connection.status);
  const entitiesText = labels.entitiesCount.replace(
    "{count}",
    String(connection.entity_count),
  );

  return (
    <div
      className="flex items-center justify-between p-4 rounded-lg"
      style={{
        backgroundColor: "var(--connect-surface)",
        border: "1px solid var(--connect-border)",
        opacity: isDeleting ? 0.5 : 1,
      }}
    >
      <div className="flex items-center gap-3">
        {imgError ? (
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-medium uppercase"
            style={{
              backgroundColor:
                "color-mix(in srgb, var(--connect-primary) 20%, transparent)",
              color: "var(--connect-primary)",
            }}
          >
            {connection.short_name.slice(0, 2)}
          </div>
        ) : (
          <img
            src={getAppIconUrl(connection.short_name, resolvedMode)}
            alt={connection.name}
            className="w-10 h-10 object-contain"
            onError={() => setImgError(true)}
          />
        )}
        <div>
          <p
            className="font-medium text-sm"
            style={{ color: "var(--connect-text)" }}
          >
            {connection.name}
          </p>
          <p className="text-xs" style={{ color: "var(--connect-text-muted)" }}>
            {entitiesText}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span
          className="text-xs px-2 py-1 rounded-full"
          style={{
            backgroundColor: `color-mix(in srgb, ${statusColor} 20%, transparent)`,
            color: statusColor,
          }}
        >
          {getStatusLabel(connection.status, labels)}
        </span>
        <Menu.Root>
          <Menu.Trigger className="p-1 rounded cursor-pointer border-none bg-transparent flex items-center justify-center transition-colors duration-150 hover:bg-black/10 dark:hover:bg-white/10 [color:var(--connect-text-muted)] hover:[color:var(--connect-text)]">
            <MoreHorizontal size={16} />
          </Menu.Trigger>
          <Menu.Portal>
            <Menu.Positioner side="bottom" align="end" sideOffset={4}>
              <Menu.Popup className="dropdown-popup min-w-[140px] rounded-lg p-1 shadow-lg [background-color:var(--connect-surface)] [border:1px_solid_var(--connect-border)]">
                <Menu.Item
                  onClick={() => {
                    /* no-op for now */
                  }}
                  className="cursor-pointer flex items-center gap-2 px-3 py-2 rounded text-sm border-none bg-transparent w-full transition-colors duration-150 [color:var(--connect-text)] hover:bg-slate-500/10"
                >
                  <RefreshCw size={14} />
                  <span>{labels.menuReconnect}</span>
                </Menu.Item>
                <Menu.Item
                  onClick={onDelete}
                  className="cursor-pointer flex items-center gap-2 px-3 py-2 rounded text-sm border-none bg-transparent w-full transition-colors duration-150 [color:var(--connect-error)] hover:bg-red-500/10"
                >
                  <Trash2 size={14} />
                  <span>{labels.menuDelete}</span>
                </Menu.Item>
              </Menu.Popup>
            </Menu.Positioner>
          </Menu.Portal>
        </Menu.Root>
      </div>
    </div>
  );
}

function SourceItem({
  source,
  onClick,
}: {
  source: Source;
  onClick: () => void;
}) {
  const { resolvedMode } = useTheme();
  const [imgError, setImgError] = useState(false);

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3 p-4 rounded-lg w-full text-left transition-colors duration-150 cursor-pointer border-none"
      style={{
        backgroundColor: "var(--connect-surface)",
        border: "1px solid var(--connect-border)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor =
          "color-mix(in srgb, var(--connect-surface) 80%, var(--connect-primary) 20%)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = "var(--connect-surface)";
      }}
    >
      {imgError ? (
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-medium uppercase"
          style={{
            backgroundColor:
              "color-mix(in srgb, var(--connect-primary) 20%, transparent)",
            color: "var(--connect-primary)",
          }}
        >
          {source.short_name.slice(0, 2)}
        </div>
      ) : (
        <img
          src={getAppIconUrl(source.short_name, resolvedMode)}
          alt={source.name}
          className="w-10 h-10 object-contain"
          onError={() => setImgError(true)}
        />
      )}
      <p
        className="font-medium text-sm"
        style={{ color: "var(--connect-text)" }}
      >
        {source.name}
      </p>
    </button>
  );
}

function EmptyState({
  labels,
  showConnect,
  onConnect,
}: {
  labels: Required<ConnectLabels>;
  showConnect: boolean;
  onConnect: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center mb-4"
        style={{
          backgroundColor:
            "color-mix(in srgb, var(--connect-text-muted) 20%, transparent)",
        }}
      >
        <Link2
          className="w-6 h-6"
          strokeWidth={1.5}
          style={{ color: "var(--connect-text-muted)" }}
        />
      </div>
      <p className="font-medium mb-1" style={{ color: "var(--connect-text)" }}>
        {labels.emptyStateHeading}
      </p>
      <p
        className="text-sm mb-4"
        style={{ color: "var(--connect-text-muted)" }}
      >
        {labels.emptyStateDescription}
      </p>
      {showConnect && (
        <button
          onClick={onConnect}
          className="px-4 py-2 font-medium rounded-md text-sm transition-colors flex items-center gap-2"
          style={{
            backgroundColor: "var(--connect-primary)",
            color: "white",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.backgroundColor =
              "var(--connect-primary-hover)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.backgroundColor = "var(--connect-primary)")
          }
        >
          <Plus className="w-4 h-4" />
          {labels.buttonConnect}
        </button>
      )}
    </div>
  );
}

function SourcesList({
  labels,
  onBack,
  onSelectSource,
}: {
  labels: Required<ConnectLabels>;
  onBack: (() => void) | null;
  onSelectSource: (source: Source) => void;
}) {
  const {
    data: sources,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["sources"],
    queryFn: () => apiClient.getSources(),
  });

  return (
    <div
      className="h-screen flex flex-col"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      {/* Fixed Header */}
      <header className="flex-shrink-0 p-6 pb-4">
        <div className="flex items-center gap-3">
          {onBack && (
            <button
              onClick={onBack}
              className="p-1 rounded cursor-pointer border-none bg-transparent flex items-center justify-center transition-colors duration-150 hover:bg-black/10 dark:hover:bg-white/10"
              style={{ color: "var(--connect-text-muted)" }}
            >
              <ArrowLeft size={20} />
            </button>
          )}
          <div>
            <h1
              className="font-medium text-lg"
              style={{ color: "var(--connect-text)" }}
            >
              {labels.sourcesListHeading}
            </h1>
          </div>
        </div>
      </header>

      {/* Scrollable Content */}
      <main className="flex-1 overflow-y-auto px-6 scrollable-content">
        {isLoading && (
          <div className="h-full flex items-center justify-center">
            <LoadingScreen inline />
          </div>
        )}

        {error && (
          <div
            className="h-full flex items-center justify-center"
            style={{ color: "var(--connect-error)" }}
          >
            {error instanceof Error ? error.message : "An error occurred"}
          </div>
        )}

        {sources && sources.length === 0 && (
          <div
            className="h-full flex items-center justify-center"
            style={{ color: "var(--connect-text-muted)" }}
          >
            {labels.sourcesListEmpty}
          </div>
        )}

        {sources && sources.length > 0 && (
          <div className="flex flex-col gap-2 pb-4">
            {sources.map((source) => (
              <SourceItem
                key={source.short_name}
                source={source}
                onClick={() => onSelectSource(source)}
              />
            ))}
          </div>
        )}
      </main>

      {/* Fixed Footer */}
      <footer className="flex-shrink-0">
        <PoweredByAirweave />
      </footer>
    </div>
  );
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
    return (
      <div
        className="h-screen flex flex-col"
        style={{ backgroundColor: "var(--connect-bg)" }}
      >
        {/* Fixed Header */}
        <header className="flex-shrink-0 p-6 pb-4">
          <h1
            className="font-medium text-lg"
            style={{ color: "var(--connect-text)" }}
          >
            {labels.loadErrorHeading}
          </h1>
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto px-6 scrollable-content flex flex-col items-center justify-center text-center">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{
              backgroundColor:
                "color-mix(in srgb, var(--connect-error) 20%, transparent)",
            }}
          >
            <AlertCircle
              className="w-8 h-8"
              strokeWidth={1.5}
              style={{ color: "var(--connect-error)" }}
            />
          </div>
          <p style={{ color: "var(--connect-text-muted)" }}>
            {error instanceof Error ? error.message : "An error occurred"}
          </p>
        </main>

        {/* Fixed Footer */}
        <footer className="flex-shrink-0">
          <PoweredByAirweave />
        </footer>
      </div>
    );
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
