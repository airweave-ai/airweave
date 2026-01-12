// Session mode enum matching backend ConnectSessionMode
export type ConnectSessionMode = 'all' | 'connect' | 'manage' | 'reauth';

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
  | 'invalid_token'
  | 'expired_token'
  | 'network_error'
  | 'session_mismatch';

export interface SessionError {
  code: SessionErrorCode;
  message: string;
}

// Session status for state machine
export type SessionStatus =
  | { status: 'idle' }
  | { status: 'waiting_for_token' }
  | { status: 'validating' }
  | { status: 'valid'; session: ConnectSessionContext }
  | { status: 'error'; error: SessionError };

// postMessage types - messages sent from child (Connect iframe) to parent
export type ChildToParentMessage =
  | { type: 'CONNECT_READY' }
  | { type: 'REQUEST_TOKEN'; requestId: string }
  | { type: 'STATUS_CHANGE'; status: SessionStatus }
  | { type: 'CONNECTION_CREATED'; connectionId: string }
  | { type: 'CLOSE'; reason: 'success' | 'cancel' | 'error' };

// postMessage types - messages sent from parent to child
export type ParentToChildMessage =
  | { type: 'TOKEN_RESPONSE'; requestId: string; token: string }
  | { type: 'TOKEN_ERROR'; requestId: string; error: string };
