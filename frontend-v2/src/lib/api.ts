/**
 * API client for Airweave backend
 */

const API_BASE_URL = "https://api.airweave.ai";

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
 * Fetch all API keys for the current organization
 */
export async function fetchApiKeys(token: string): Promise<APIKey[]> {
  const response = await fetch(`${API_BASE_URL}/api-keys`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

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
  keyId: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api-keys?id=${keyId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
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
  expirationDays?: number,
): Promise<APIKey> {
  const response = await fetch(`${API_BASE_URL}/api-keys`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(
      expirationDays ? { expiration_days: expirationDays } : {},
    ),
  });

  if (!response.ok) {
    throw new Error(`Failed to create API key: ${response.status}`);
  }

  return response.json();
}
