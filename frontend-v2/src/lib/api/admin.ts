/**
 * Admin API client - superuser-only endpoints
 */

import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

export interface AvailableFeatureFlag {
  name: string;
  value: string;
}

export interface OrganizationMetrics {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  modified_at: string;
  auth0_org_id?: string;
  billing_plan?: string;
  billing_status?: string;
  stripe_customer_id?: string;
  trial_ends_at?: string;
  user_count: number;
  source_connection_count: number;
  entity_count: number;
  query_count: number;
  last_active_at?: string;
  is_member: boolean;
  member_role?: string;
  enabled_features?: string[];
}

export interface AdminOrganizationsParams {
  limit?: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  search?: string;
}

/**
 * Fetch all organizations with metrics (admin only)
 */
export async function fetchAdminOrganizations(
  token: string,
  params: AdminOrganizationsParams = {}
): Promise<OrganizationMetrics[]> {
  const searchParams = new URLSearchParams();

  if (params.limit) searchParams.set("limit", params.limit.toString());
  if (params.sort_by) searchParams.set("sort_by", params.sort_by);
  if (params.sort_order) searchParams.set("sort_order", params.sort_order);
  if (params.search) searchParams.set("search", params.search);

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/admin/organizations${queryString ? `?${queryString}` : ""}`;

  const response = await fetch(url, {
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
 * Fetch available feature flags (admin only)
 */
export async function fetchAvailableFeatureFlags(
  token: string
): Promise<AvailableFeatureFlag[]> {
  const response = await fetch(`${API_BASE_URL}/admin/feature-flags`, {
    method: "GET",
    headers: getAuthHeaders(token),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch feature flags"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Add current user to an organization (admin only)
 */
export async function adminJoinOrganization(
  token: string,
  organizationId: string,
  role: "owner" | "admin" | "member"
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/admin/organizations/${organizationId}/add-self?role=${role}`,
    {
      method: "POST",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to join organization"
    );
    throw new Error(message);
  }
}

/**
 * Upgrade organization to enterprise (admin only)
 */
export async function adminUpgradeToEnterprise(
  token: string,
  organizationId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/admin/organizations/${organizationId}/upgrade-to-enterprise`,
    {
      method: "POST",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to upgrade organization"
    );
    throw new Error(message);
  }
}

export interface CreateEnterpriseOrgRequest {
  name: string;
  description?: string;
  owner_email: string;
}

/**
 * Create a new enterprise organization (admin only)
 */
export async function adminCreateEnterpriseOrg(
  token: string,
  data: CreateEnterpriseOrgRequest
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/admin/organizations/create-enterprise`,
    {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create organization"
    );
    throw new Error(message);
  }
}

/**
 * Enable a feature flag for an organization (admin only)
 */
export async function adminEnableFeatureFlag(
  token: string,
  organizationId: string,
  flag: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/admin/organizations/${organizationId}/feature-flags/${flag}/enable`,
    {
      method: "POST",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to enable feature flag"
    );
    throw new Error(message);
  }
}

/**
 * Disable a feature flag for an organization (admin only)
 */
export async function adminDisableFeatureFlag(
  token: string,
  organizationId: string,
  flag: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/admin/organizations/${organizationId}/feature-flags/${flag}/disable`,
    {
      method: "POST",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to disable feature flag"
    );
    throw new Error(message);
  }
}
