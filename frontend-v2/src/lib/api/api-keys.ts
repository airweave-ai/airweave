/**
 * API Key operations
 */

import { API_BASE_URL, getAuthHeaders } from "./client";

/**
 * API Key type matching the backend schema
 */
export interface APIKey {
  id: string;
  organization_id: string;
  created_at: string;
  modified_at: string;
  last_used_date: string | null;
  expiration_date: string;
  created_by_email: string | null;
  modified_by_email: string | null;
  decrypted_key: string;
}

/**
 * Fetch API keys for the current organization with pagination
 */
export async function fetchApiKeys(
  token: string,
  orgId: string,
  skip = 0,
  limit = 20
): Promise<APIKey[]> {
  const response = await fetch(
    `${API_BASE_URL}/api-keys?skip=${skip}&limit=${limit}`,
    {
      headers: getAuthHeaders(token, orgId),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch API keys: ${response.status}`);
  }

  return response.json();
}

/**
 * Delete an API key by ID
 */
export async function deleteApiKey(
  token: string,
  orgId: string,
  keyId: string
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api-keys?id=${keyId}`, {
    method: "DELETE",
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    throw new Error(`Failed to delete API key: ${response.status}`);
  }
}

/**
 * Create a new API key
 */
export async function createApiKey(
  token: string,
  orgId: string,
  expirationDays?: number
): Promise<APIKey> {
  const response = await fetch(`${API_BASE_URL}/api-keys`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(
      expirationDays ? { expiration_days: expirationDays } : {}
    ),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    if (errorBody?.errors && Array.isArray(errorBody.errors)) {
      const messages = errorBody.errors
        .map((err: Record<string, string>) => Object.values(err).join(", "))
        .join("; ");
      throw new Error(messages);
    }
    throw new Error(`Failed to create API key: ${response.status}`);
  }

  return response.json();
}
