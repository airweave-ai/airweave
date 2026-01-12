// Session mode enum matching backend ConnectSessionMode
export type ConnectSessionMode = "all" | "connect" | "manage" | "reauth";

// Theme types for customization
export type ThemeMode = "dark" | "light" | "system";

export interface ThemeColors {
  background?: string;
  surface?: string;
  text?: string;
  textMuted?: string;
  primary?: string;
  primaryHover?: string;
  secondary?: string;
  secondaryHover?: string;
  border?: string;
  success?: string;
  error?: string;
}

export interface ConnectLabels {
  // Main headings
  sourcesHeading?: string;

  // Connection status labels
  statusActive?: string;
  statusSyncing?: string;
  statusPendingAuth?: string;
  statusError?: string;
  statusInactive?: string;

  // Connection item
  entitiesCount?: string; // Use {count} placeholder, e.g. "{count} entities"

  // Menu actions
  menuReconnect?: string;
  menuDelete?: string;

  // Empty state
  emptyStateHeading?: string;
  emptyStateDescription?: string;

  // Connect mode error
  connectModeErrorHeading?: string;
  connectModeErrorDescription?: string;

  // Load error
  loadErrorHeading?: string;

  // Error screen titles
  errorInvalidTokenTitle?: string;
  errorExpiredTokenTitle?: string;
  errorNetworkTitle?: string;
  errorSessionMismatchTitle?: string;
  errorDefaultTitle?: string;

  // Error screen descriptions
  errorInvalidTokenDescription?: string;
  errorExpiredTokenDescription?: string;
  errorNetworkDescription?: string;
  errorSessionMismatchDescription?: string;

  // Buttons
  buttonRetry?: string;
  buttonClose?: string;

  // Footer
  poweredBy?: string;
}

export interface ConnectTheme {
  mode: ThemeMode;
  colors?: {
    dark?: ThemeColors;
    light?: ThemeColors;
  };
  labels?: ConnectLabels;
}

// Session context returned by API (matches backend ConnectSessionContext)
export interface ConnectSessionContext {
  session_id: string;
  organization_id: string;
  collection_id: string;
  allowed_integrations: string[] | null;
  mode: ConnectSessionMode;
  end_user_id: string | null;
  expires_at: string;
}

// Session error types
export type SessionErrorCode =
  | "invalid_token"
  | "expired_token"
  | "network_error"
  | "session_mismatch";

export interface SessionError {
  code: SessionErrorCode;
  message: string;
}

// Session status for state machine
export type SessionStatus =
  | { status: "idle" }
  | { status: "waiting_for_token" }
  | { status: "validating" }
  | { status: "valid"; session: ConnectSessionContext }
  | { status: "error"; error: SessionError };

// postMessage types - messages sent from child (Connect iframe) to parent
export type ChildToParentMessage =
  | { type: "CONNECT_READY" }
  | { type: "REQUEST_TOKEN"; requestId: string }
  | { type: "STATUS_CHANGE"; status: SessionStatus }
  | { type: "CONNECTION_CREATED"; connectionId: string }
  | { type: "CLOSE"; reason: "success" | "cancel" | "error" };

// postMessage types - messages sent from parent to child
export type ParentToChildMessage =
  | {
      type: "TOKEN_RESPONSE";
      requestId: string;
      token: string;
      theme?: ConnectTheme;
    }
  | { type: "TOKEN_ERROR"; requestId: string; error: string }
  | { type: "SET_THEME"; theme: ConnectTheme };

// Source connection types
export type SourceConnectionStatus =
  | "active"
  | "inactive"
  | "pending_auth"
  | "syncing"
  | "error";

export type AuthenticationMethod =
  | "direct"
  | "oauth_browser"
  | "oauth_token"
  | "oauth_byoc"
  | "auth_provider";

export interface SourceConnectionListItem {
  id: string;
  name: string;
  short_name: string;
  readable_collection_id: string;
  created_at: string;
  modified_at: string;
  is_authenticated: boolean;
  entity_count: number;
  federated_search: boolean;
  auth_method: AuthenticationMethod;
  status: SourceConnectionStatus;
}
