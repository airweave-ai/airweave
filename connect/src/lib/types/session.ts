// Session mode enum matching backend ConnectSessionMode
export type ConnectSessionMode = "all" | "connect" | "manage" | "reauth";

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
