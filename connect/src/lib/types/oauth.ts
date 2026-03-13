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
