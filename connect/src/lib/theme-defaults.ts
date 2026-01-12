import type { ConnectLabels, ThemeColors } from "./types";

// Default theme colors
export const defaultDarkColors: Required<ThemeColors> = {
  background: "#0f172a",
  surface: "#1e293b",
  text: "#ffffff",
  textMuted: "#9ca3af",
  primary: "#06b6d4",
  primaryHover: "#0891b2",
  secondary: "#334155",
  secondaryHover: "#475569",
  border: "#334155",
  success: "#22c55e",
  error: "#ef4444",
};

export const defaultLightColors: Required<ThemeColors> = {
  background: "#ffffff",
  surface: "#f9fafb",
  text: "#111827",
  textMuted: "#6b7280",
  primary: "#0891b2",
  primaryHover: "#0e7490",
  secondary: "#e5e7eb",
  secondaryHover: "#d1d5db",
  border: "#e5e7eb",
  success: "#16a34a",
  error: "#dc2626",
};

// Default labels
export const defaultLabels: Required<ConnectLabels> = {
  // Main headings
  sourcesHeading: "Sources",

  // Connection status labels
  statusActive: "Active",
  statusSyncing: "Syncing",
  statusPendingAuth: "Pending Auth",
  statusError: "Error",
  statusInactive: "Inactive",

  // Connection item
  entitiesCount: "{count} entities",

  // Menu actions
  menuReconnect: "Reconnect",
  menuDelete: "Delete",

  // Empty state
  emptyStateHeading: "No sources connected yet",
  emptyStateDescription: "Connect a source to get started.",

  // Connect mode error
  connectModeErrorHeading: "Cannot View Connections",
  connectModeErrorDescription:
    "Viewing connections is not available in connect mode.",

  // Load error
  loadErrorHeading: "Failed to Load Connections",

  // Error screen titles
  errorInvalidTokenTitle: "Invalid Session",
  errorExpiredTokenTitle: "Session Expired",
  errorNetworkTitle: "Connection Error",
  errorSessionMismatchTitle: "Session Mismatch",
  errorDefaultTitle: "Error",

  // Error screen descriptions
  errorInvalidTokenDescription:
    "The session token is invalid. Please try again.",
  errorExpiredTokenDescription:
    "Your session has expired. Please refresh and try again.",
  errorNetworkDescription:
    "Unable to connect to the server. Please check your connection.",
  errorSessionMismatchDescription:
    "The session ID does not match. Please try again.",

  // Buttons
  buttonRetry: "Retry",
  buttonClose: "Close",
  buttonConnect: "Connect",
  buttonBack: "Back",

  // Sources list (available apps)
  sourcesListHeading: "Connect a Source",
  sourcesListLoading: "Loading sources...",
  sourcesListEmpty: "No sources available.",

  // Footer
  poweredBy: "Powered by",
};
