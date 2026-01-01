/**
 * Auth Provider operations
 */

import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

/**
 * Auth field definition for auth provider configuration
 */
export interface AuthField {
  name: string;
  title?: string;
  description?: string;
  type?: string;
  required?: boolean;
  secret?: boolean;
}

/**
 * Auth fields container
 */
export interface AuthFields {
  fields: AuthField[];
}

/**
 * Auth provider type matching the backend schema
 */
export interface AuthProvider {
  id: string;
  name: string;
  short_name: string;
  description?: string;
  auth_type: string;
  class_name: string;
  auth_config_class: string;
  config_class: string;
  organization_id?: string;
  created_at: string;
  modified_at: string;
  auth_fields?: AuthFields;
}

/**
 * Auth provider connection type matching the backend schema
 */
export interface AuthProviderConnection {
  id: string;
  name: string;
  readable_id: string;
  short_name: string;
  description?: string;
  created_by_email?: string;
  modified_by_email?: string;
  created_at: string;
  modified_at: string;
  masked_client_id?: string;
}

/**
 * Request body for creating an auth provider connection
 */
export interface CreateAuthProviderConnectionRequest {
  name: string;
  readable_id: string;
  short_name: string;
  auth_fields: Record<string, string>;
}

/**
 * Request body for updating an auth provider connection
 */
export interface UpdateAuthProviderConnectionRequest {
  name?: string;
  auth_fields?: Record<string, string>;
}

/**
 * Fetch all available auth providers
 */
export async function fetchAuthProviders(
  token: string
): Promise<AuthProvider[]> {
  const response = await fetch(`${API_BASE_URL}/auth-providers/list`, {
    headers: getAuthHeaders(token),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch auth providers: ${response.status}`);
  }

  return response.json();
}

/**
 * Fetch all auth provider connections for the current organization
 */
export async function fetchAuthProviderConnections(
  token: string
): Promise<AuthProviderConnection[]> {
  const response = await fetch(`${API_BASE_URL}/auth-providers/connections/`, {
    headers: getAuthHeaders(token),
  });

  if (!response.ok) {
    throw new Error(
      `Failed to fetch auth provider connections: ${response.status}`
    );
  }

  return response.json();
}

/**
 * Fetch auth provider details by short name
 */
export async function fetchAuthProviderDetail(
  token: string,
  shortName: string
): Promise<AuthProvider> {
  const response = await fetch(
    `${API_BASE_URL}/auth-providers/detail/${shortName}`,
    {
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch auth provider details: ${response.status}`
    );
  }

  return response.json();
}

/**
 * Fetch a specific auth provider connection by readable ID
 */
export async function fetchAuthProviderConnection(
  token: string,
  readableId: string
): Promise<AuthProviderConnection> {
  const response = await fetch(
    `${API_BASE_URL}/auth-providers/connections/${readableId}`,
    {
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch auth provider connection: ${response.status}`
    );
  }

  return response.json();
}

/**
 * Create a new auth provider connection
 */
export async function createAuthProviderConnection(
  token: string,
  data: CreateAuthProviderConnectionRequest
): Promise<AuthProviderConnection> {
  const response = await fetch(`${API_BASE_URL}/auth-providers/`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorMessage = await parseErrorResponse(
      response,
      `Failed to create auth provider connection: ${response.status}`
    );
    throw new Error(errorMessage);
  }

  return response.json();
}

/**
 * Update an existing auth provider connection
 */
export async function updateAuthProviderConnection(
  token: string,
  readableId: string,
  data: UpdateAuthProviderConnectionRequest
): Promise<AuthProviderConnection> {
  const response = await fetch(`${API_BASE_URL}/auth-providers/${readableId}`, {
    method: "PUT",
    headers: getAuthHeaders(token),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorMessage = await parseErrorResponse(
      response,
      `Failed to update auth provider connection: ${response.status}`
    );
    throw new Error(errorMessage);
  }

  return response.json();
}

/**
 * Delete an auth provider connection
 */
export async function deleteAuthProviderConnection(
  token: string,
  readableId: string
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth-providers/${readableId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(
      `Failed to delete auth provider connection: ${response.status}`
    );
  }
}
