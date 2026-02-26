import type { SourceConnectionStatus } from "./connection";
import type { AuthenticationMethod } from "./source";

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
  readable_collection_id: string;
  name?: string;
  redirect_url?: string;
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
