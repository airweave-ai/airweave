import { LoadingScreen } from "@/components/LoadingScreen";
import { PoweredByAirweave } from "@/components/PoweredByAirweave";
import { Menu } from "@base-ui/react/menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Link2,
  MoreHorizontal,
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
  SourceConnectionListItem,
  SourceConnectionStatus,
} from "../lib/types";

interface SuccessScreenProps {
  session: ConnectSessionContext;
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

function EmptyState({ labels }: { labels: Required<ConnectLabels> }) {
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
      <p className="text-sm" style={{ color: "var(--connect-text-muted)" }}>
        {labels.emptyStateDescription}
      </p>
    </div>
  );
}

function ConnectModeError({ labels }: { labels: Required<ConnectLabels> }) {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-6 pb-12 text-center relative"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
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
      <h1
        className="font-medium text-lg mb-2"
        style={{ color: "var(--connect-text)" }}
      >
        {labels.connectModeErrorHeading}
      </h1>
      <p style={{ color: "var(--connect-text-muted)" }}>
        {labels.connectModeErrorDescription}
      </p>
      <PoweredByAirweave />
    </div>
  );
}

export function SuccessScreen({ session }: SuccessScreenProps) {
  const { labels } = useTheme();
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  if (session.mode === "connect") {
    return <ConnectModeError labels={labels} />;
  }

  if (isLoading) return <LoadingScreen />;

  if (error) {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center p-6 pb-12 text-center relative"
        style={{ backgroundColor: "var(--connect-bg)" }}
      >
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
        <h1
          className="font-medium text-lg mb-2"
          style={{ color: "var(--connect-text)" }}
        >
          {labels.loadErrorHeading}
        </h1>
        <p style={{ color: "var(--connect-text-muted)" }}>
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
        <PoweredByAirweave />
      </div>
    );
  }

  return (
    <div
      className="min-h-screen flex flex-col p-6 pb-12 relative"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      <h1
        className="font-medium text-lg mb-4"
        style={{ color: "var(--connect-text)" }}
      >
        {labels.sourcesHeading}
      </h1>

      {connections && connections.length > 0 ? (
        <div className="flex flex-col gap-3">
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
        <EmptyState labels={labels} />
      )}
      <PoweredByAirweave />
    </div>
  );
}
