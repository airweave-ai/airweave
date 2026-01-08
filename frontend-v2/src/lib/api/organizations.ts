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

/**
 * Create organization request payload
 */
export interface CreateOrganizationRequest {
  name: string;
  description?: string;
  org_metadata?: {
    onboarding?: {
      organizationSize?: string;
      userRole?: string;
      organizationType?: string;
      subscriptionPlan?: string;
      teamInvites?: Array<{ email: string; role: string }>;
      completedAt?: string;
    };
  };
}

/**
 * Create a new organization
 */
export async function createOrganization(
  token: string,
  data: CreateOrganizationRequest
): Promise<Organization> {
  const response = await fetch(`${API_BASE_URL}/organizations/`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create organization"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Billing checkout session request
 */
export interface CheckoutSessionRequest {
  plan: string;
  success_url: string;
  cancel_url: string;
}

/**
 * Billing checkout session response
 */
export interface CheckoutSessionResponse {
  checkout_url: string;
}

/**
 * Create a billing checkout session
 */
export async function createCheckoutSession(
  token: string,
  data: CheckoutSessionRequest,
  yearly: boolean = false
): Promise<CheckoutSessionResponse> {
  const endpoint = yearly
    ? `${API_BASE_URL}/billing/yearly/checkout-session`
    : `${API_BASE_URL}/billing/checkout-session`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to create checkout session"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Invite a member to an organization
 */
export async function inviteOrganizationMember(
  token: string,
  organizationId: string,
  email: string,
  role: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}/invite`,
    {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify({ email, role }),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to invite member"
    );
    throw new Error(message);
  }
}
