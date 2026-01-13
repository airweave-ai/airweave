import type { AuthenticationMethod } from "./source";

// Source connection types
export type SourceConnectionStatus =
  | "active"
  | "inactive"
  | "pending_auth"
  | "syncing"
  | "error";

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
