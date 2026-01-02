/**
 * Organizations API client
 */

import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

export interface Organization {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  modified_at: string;
  role: "owner" | "admin" | "member";
  is_primary: boolean;
  auth0_org_id?: string;
  org_metadata?: Record<string, unknown>;
  enabled_features?: string[];
}

/**
 * Fetch all organizations for the current user
 */
export async function fetchOrganizations(
  token: string
): Promise<Organization[]> {
  const response = await fetch(`${API_BASE_URL}/organizations/`, {
    method: "GET",
    headers: getAuthHeaders(token),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch organizations"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Get a single organization by ID
 */
export async function fetchOrganization(
  token: string,
  organizationId: string
): Promise<Organization> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}`,
    {
      method: "GET",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch organization"
    );
    throw new Error(message);
  }

  return response.json();
}
