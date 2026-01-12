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
  buttonConnect?: string;
  buttonBack?: string;

  // Sources list (available apps)
  sourcesListHeading?: string;
  sourcesListLoading?: string;
  sourcesListEmpty?: string;

  // Footer
  poweredBy?: string;

  // Source config view - connection name
  configureNameLabel?: string;
  configureNameDescription?: string;
  configureNamePlaceholder?: string; // Use {source} placeholder

  // Source config view - sections
  configureAuthSection?: string;
  configureConfigSection?: string;

  // Source config view - buttons and status
  buttonCreateConnection?: string;
  buttonCreatingConnection?: string;
  connectionFailed?: string;
  loadSourceDetailsFailed?: string;
  fieldRequired?: string;

  // Auth method selector
  authMethodLabel?: string;
  authMethodDirect?: string;
  authMethodDirectDescription?: string;
  authMethodOAuth?: string; // Use {source} placeholder
  authMethodOAuthDescription?: string;

  // OAuth status UI
  oauthWaiting?: string;
  oauthWaitingDescription?: string;
  oauthPopupBlocked?: string;
  oauthPopupBlockedDescription?: string;
  buttonTryAgain?: string;
  buttonOpenLinkManually?: string;
  buttonConnectOAuth?: string; // Use {source} placeholder
  buttonConnecting?: string;

  // BYOC fields
  byocDescription?: string;
  byocClientIdLabel?: string;
  byocClientIdPlaceholder?: string;
  byocClientSecretLabel?: string;
  byocClientSecretPlaceholder?: string;
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

// Navigation views for NAVIGATE message
export type NavigateView = "connections" | "sources" | "configure";

// postMessage types - messages sent from parent to child
export type ParentToChildMessage =
  | {
      type: "TOKEN_RESPONSE";
      requestId: string;
      token: string;
      theme?: ConnectTheme;
    }
  | { type: "TOKEN_ERROR"; requestId: string; error: string }
  | { type: "SET_THEME"; theme: ConnectTheme }
  | { type: "NAVIGATE"; view: NavigateView };

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

// Available source/integration from /connect/sources
export interface Source {
  name: string;
  short_name: string;
  auth_method: AuthenticationMethod;
}

// Config field definition for dynamic forms
export interface ConfigField {
  name: string;
  title: string;
  description?: string;
  type: "string" | "number" | "boolean" | "array";
  required: boolean;
  items_type?: string;
  is_secret?: boolean;
}

// Fields wrapper (matches backend response structure)
export interface Fields {
  fields: ConfigField[];
}

// Source details from GET /connect/sources/{short_name}
export interface SourceDetails {
  name: string;
  short_name: string;
  description?: string;
  auth_methods: AuthenticationMethod[];
  oauth_type?: "oauth1" | "access_only" | "with_refresh" | "with_rotating_refresh";
  requires_byoc: boolean;
  auth_fields?: Fields;
  config_fields?: Fields;
}

// Authentication payloads for creating connections
export interface DirectAuthPayload {
  credentials: Record<string, unknown>;
}

export interface OAuthBrowserAuthPayload {
  redirect_uri: string;
  client_id?: string; // For BYOC
  client_secret?: string; // For BYOC
}

export type AuthenticationPayload = DirectAuthPayload | OAuthBrowserAuthPayload;

// Create connection request
export interface SourceConnectionCreateRequest {
  short_name: string;
  name?: string;
  authentication?: AuthenticationPayload;
  config?: Record<string, unknown>;
  sync_immediately?: boolean;
}

// Create connection response
export interface SourceConnectionCreateResponse {
  id: string;
  name: string;
  short_name: string;
  status: SourceConnectionStatus;
  auth: {
    method: AuthenticationMethod;
    authenticated: boolean;
    auth_url?: string;
  };
}

// OAuth callback result (from popup postMessage)
export interface OAuthCallbackResult {
  status: "success" | "error";
  source_connection_id?: string;
  error_type?: string;
  error_message?: string;
}

// OAuth flow status for UI state management
export type OAuthFlowStatus =
  | "idle"
  | "creating"
  | "waiting"
  | "popup_blocked"
  | "error";
