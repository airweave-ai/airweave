import type { ConnectLabels, ConnectOptions, ThemeColors } from "./types";

// Default theme colors
export const defaultDarkColors: Required<ThemeColors> = {
  background: "#0f172a",
  surface: "#1e293b",
  text: "#ffffff",
  textMuted: "#9ca3af",
  primary: "#06b6d4",
  primaryForeground: "#ffffff",
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
  primaryForeground: "#ffffff",
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
  emptyStateHeading: "Connect your apps",
  emptyStateDescription:
    "Add context from your apps to start working with your data.",

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

  // Source config view - connection name
  configureNameLabel: "Connection name",
  configureNameDescription: "Optional. Give this connection a memorable name.",
  configureNamePlaceholder: "My {source} connection",

  // Source config view - sections
  configureAuthSection: "Authentication",
  configureConfigSection: "Configuration",

  // Source config view - buttons and status
  buttonCreateConnection: "Create connection",
  buttonCreatingConnection: "Creating...",
  connectionFailed: "Failed to create connection",
  loadSourceDetailsFailed: "Failed to load source details",
  fieldRequired: "This field is required",
  fieldOptional: "Optional",

  // Auth method selector
  authMethodLabel: "Authentication method",
  authMethodDirect: "Enter credentials",
  authMethodDirectDescription: "Manually enter API key or token",
  authMethodOAuth: "Connect with {source}",
  authMethodOAuthDescription: "Authorize via browser login",

  // OAuth status UI
  oauthWaiting: "Waiting for authorization...",
  oauthWaitingDescription: "Complete the sign-in in the popup window",
  oauthPopupBlocked: "Popup was blocked",
  oauthPopupBlockedDescription:
    "Your browser blocked the authentication popup. You can try again or open the link manually.",
  buttonTryAgain: "Try again",
  buttonOpenLinkManually: "Open link manually",
  buttonConnectOAuth: "Connect with {source}",
  buttonConnecting: "Connecting...",

  // BYOC fields
  byocDescription:
    "This integration requires you to provide your own OAuth app credentials.",
  byocClientIdLabel: "Client ID",
  byocClientIdPlaceholder: "Your OAuth app client ID",
  byocClientSecretLabel: "Client Secret",
  byocClientSecretPlaceholder: "Your OAuth app client secret",

  // Empty state info
  welcomeInfoVerify:
    "Your credentials are encrypted and your data is securely stored.",
  welcomeInfoAccess:
    "You control which apps to connect and can disconnect anytime.",

  // Folder selection
  folderSelectionHeading: "Select folders to sync",
  folderSelectionStartSync: "Start sync",
  folderSelectionCount: "{count} folders",
};

// Default options
export const defaultOptions: Required<ConnectOptions> = {
  showConnectionName: false,
  enableFolderSelection: false,
  logoUrl: "",
};
