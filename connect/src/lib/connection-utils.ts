import type {
  ConnectLabels,
  ConnectSessionMode,
  SourceConnectionStatus,
} from "./types";

export function canConnect(mode: ConnectSessionMode): boolean {
  return mode === "all" || mode === "connect";
}

export function getStatusColor(status: SourceConnectionStatus): string {
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

export function getStatusLabel(
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
