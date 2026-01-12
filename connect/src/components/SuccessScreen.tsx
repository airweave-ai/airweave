import { LoadingScreen } from "@/components/LoadingScreen";
import { PoweredByAirweave } from "@/components/PoweredByAirweave";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Link2 } from "lucide-react";
import { useState } from "react";
import { apiClient } from "../lib/api";
import { getAppIconUrl } from "../lib/icons";
import { useTheme } from "../lib/theme";
import type {
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

function getStatusLabel(status: SourceConnectionStatus): string {
  switch (status) {
    case "active":
      return "Active";
    case "syncing":
      return "Syncing";
    case "pending_auth":
      return "Pending Auth";
    case "error":
      return "Error";
    case "inactive":
      return "Inactive";
    default:
      return status;
  }
}

function ConnectionItem({
  connection,
}: {
  connection: SourceConnectionListItem;
}) {
  const { resolvedMode } = useTheme();
  const [imgError, setImgError] = useState(false);
  const statusColor = getStatusColor(connection.status);

  return (
    <div
      className="flex items-center justify-between p-4 rounded-lg"
      style={{
        backgroundColor: "var(--connect-surface)",
        border: "1px solid var(--connect-border)",
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
            {connection.entity_count} entities
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
          {getStatusLabel(connection.status)}
        </span>
      </div>
    </div>
  );
}

function EmptyState() {
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
        No apps connected yet
      </p>
      <p className="text-sm" style={{ color: "var(--connect-text-muted)" }}>
        Connect an app to get started.
      </p>
    </div>
  );
}

function ConnectModeError() {
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
        Cannot View Connections
      </h1>
      <p style={{ color: "var(--connect-text-muted)" }}>
        Viewing connections is not available in connect mode.
      </p>
      <PoweredByAirweave />
    </div>
  );
}

export function SuccessScreen({ session }: SuccessScreenProps) {
  const {
    data: connections,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["source-connections"],
    queryFn: () => apiClient.getSourceConnections(),
    enabled: session.mode !== "connect",
  });

  if (session.mode === "connect") {
    return <ConnectModeError />;
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
          Failed to Load Connections
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
        Connected Apps
      </h1>

      {connections && connections.length > 0 ? (
        <div className="flex flex-col gap-3">
          {connections.map((connection) => (
            <ConnectionItem key={connection.id} connection={connection} />
          ))}
        </div>
      ) : (
        <EmptyState />
      )}
      <PoweredByAirweave />
    </div>
  );
}
