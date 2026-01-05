/**
 * Source Connection operations
 */

import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

/**
 * Authentication info for a source connection
 */
export interface AuthenticationInfo {
  method?: string;
  authenticated?: boolean;
  authenticated_at?: string;
  expires_at?: string;
  auth_url?: string;
  auth_url_expires?: string;
  provider_id?: string;
  provider_readable_id?: string;
  redirect_url?: string;
}

/**
 * Last sync job info
 */
export interface LastSyncJob {
  id?: string;
  status?: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  entities_inserted?: number;
  entities_updated?: number;
  entities_deleted?: number;
  entities_failed?: number;
  error?: string;
  error_details?: Record<string, unknown>;
}

/**
 * Schedule configuration
 */
export interface Schedule {
  cron?: string;
  next_run?: string;
  continuous?: boolean;
  cursor_field?: string;
  cursor_value?: unknown;
}

/**
 * Entity type statistics
 */
export interface EntityTypeStats {
  count: number;
  last_updated?: string;
  sync_status: string;
}

/**
 * Entity summary for a source connection
 */
export interface EntitySummary {
  total_entities: number;
  by_type: Record<string, EntityTypeStats>;
  last_updated?: string;
}

/**
 * Source Connection type matching the backend schema
 */
export interface SourceConnection {
  id: string;
  name: string;
  description?: string;
  short_name: string;
  readable_collection_id: string;
  status?: string;
  created_at: string;
  modified_at: string;
  auth?: AuthenticationInfo;
  config?: Record<string, unknown>;
  schedule?: Schedule;
  last_sync_job?: LastSyncJob;
  entities?: EntitySummary;
  federated_search?: boolean;
  sync_id?: string;
  organization_id?: string;
  connection_id?: string;
  created_by_email?: string;
  modified_by_email?: string;
}

/**
 * Sync job response
 */
export interface SyncJob {
  id: string;
  source_connection_id: string;
  status: string;
  started_at?: string;
  completed_at?: string;
}

/**
 * Request type for updating a source connection
 */
export interface UpdateSourceConnectionRequest {
  name?: string;
  description?: string;
  config?: Record<string, unknown>;
  schedule?: {
    cron?: string;
  };
}

/**
 * Authentication options for creating a source connection
 */
export interface CreateSourceConnectionAuth {
  /** For direct auth (API keys, passwords) */
  credentials?: Record<string, string>;
  /** OAuth redirect URI */
  redirect_uri?: string;
  /** Custom OAuth client ID (BYOC) */
  client_id?: string;
  /** Custom OAuth client secret (BYOC) */
  client_secret?: string;
  /** OAuth1 consumer key */
  consumer_key?: string;
  /** OAuth1 consumer secret */
  consumer_secret?: string;
  /** Auth provider readable ID for external provider auth */
  provider_readable_id?: string;
  /** Auth provider specific config */
  provider_config?: Record<string, string>;
}

/**
 * Request type for creating a source connection
 */
export interface CreateSourceConnectionRequest {
  name: string;
  description?: string;
  short_name: string;
  readable_collection_id: string;
  authentication?: CreateSourceConnectionAuth;
  config?: Record<string, unknown>;
  sync_immediately?: boolean;
  redirect_url?: string;
}

/**
 * Create a new source connection
 */
export async function createSourceConnection(
  token: string,
  orgId: string,
  data: CreateSourceConnectionRequest
): Promise<SourceConnection> {
  const response = await fetch(`${API_BASE_URL}/source-connections`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create source connection"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Fetch source connections for a collection
 */
export async function fetchSourceConnections(
  token: string,
  orgId: string,
  collectionId: string
): Promise<SourceConnection[]> {
  const response = await fetch(
    `${API_BASE_URL}/source-connections/?collection=${collectionId}`,
    {
      headers: getAuthHeaders(token, orgId),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch source connections"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Fetch a single source connection by ID with full details
 */
export async function fetchSourceConnection(
  token: string,
  orgId: string,
  id: string,
  regenerateAuthUrl = false
): Promise<SourceConnection> {
  const url = regenerateAuthUrl
    ? `${API_BASE_URL}/source-connections/${id}?regenerate_auth_url=true`
    : `${API_BASE_URL}/source-connections/${id}`;

  const response = await fetch(url, {
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch source connection"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Run a sync for a source connection
 */
export async function runSourceConnectionSync(
  token: string,
  orgId: string,
  id: string
): Promise<SyncJob> {
  const response = await fetch(`${API_BASE_URL}/source-connections/${id}/run`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(response, "Failed to start sync");
    throw new Error(message);
  }

  return response.json();
}

/**
 * Cancel a running sync job
 */
export async function cancelSourceConnectionSync(
  token: string,
  orgId: string,
  connectionId: string,
  jobId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/source-connections/${connectionId}/jobs/${jobId}/cancel`,
    {
      method: "POST",
      headers: getAuthHeaders(token, orgId),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to cancel sync job"
    );
    throw new Error(message);
  }
}

/**
 * Update a source connection
 */
export async function updateSourceConnection(
  token: string,
  orgId: string,
  id: string,
  data: UpdateSourceConnectionRequest
): Promise<SourceConnection> {
  const response = await fetch(`${API_BASE_URL}/source-connections/${id}`, {
    method: "PATCH",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to update source connection"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Delete a source connection
 */
export async function deleteSourceConnection(
  token: string,
  orgId: string,
  id: string
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/source-connections/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to delete source connection"
    );
    throw new Error(message);
  }
}

/**
 * Refresh all sources in a collection
 */
export async function refreshAllSourceConnections(
  token: string,
  orgId: string,
  collectionId: string
): Promise<SyncJob[]> {
  const response = await fetch(
    `${API_BASE_URL}/collections/${collectionId}/refresh_all`,
    {
      method: "POST",
      headers: getAuthHeaders(token, orgId),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to refresh sources"
    );
    throw new Error(message);
  }

  return response.json();
}
