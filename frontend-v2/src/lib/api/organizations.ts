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

/**
 * Update organization request payload
 */
export interface UpdateOrganizationRequest {
  name?: string;
  description?: string;
}

/**
 * Update an organization
 */
export async function updateOrganization(
  token: string,
  organizationId: string,
  data: UpdateOrganizationRequest
): Promise<Organization> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}`,
    {
      method: "PUT",
      headers: getAuthHeaders(token),
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to update organization"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Delete an organization
 */
export async function deleteOrganization(
  token: string,
  organizationId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}`,
    {
      method: "DELETE",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to delete organization"
    );
    throw new Error(message);
  }
}

/**
 * Set an organization as primary
 */
export async function setPrimaryOrganization(
  token: string,
  organizationId: string
): Promise<Organization> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}/set-primary`,
    {
      method: "POST",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to set primary organization"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Organization member interface
 */
export interface OrganizationMember {
  id: string;
  email: string;
  name: string;
  role: "owner" | "admin" | "member";
  status: "active" | "pending";
  is_primary?: boolean;
  auth0_id?: string;
}

/**
 * Pending invitation interface
 */
export interface PendingInvitation {
  id: string;
  email: string;
  role: "admin" | "member";
  invited_at: string;
  status: "pending" | "expired";
}

/**
 * Fetch organization members
 */
export async function fetchOrganizationMembers(
  token: string,
  organizationId: string
): Promise<OrganizationMember[]> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}/members`,
    {
      method: "GET",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch organization members"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Fetch pending invitations for an organization
 */
export async function fetchOrganizationInvitations(
  token: string,
  organizationId: string
): Promise<PendingInvitation[]> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}/invitations`,
    {
      method: "GET",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch invitations"
    );
    throw new Error(message);
  }

  return response.json();
}

/**
 * Invite response interface
 */
export interface InviteResponse {
  id: string;
  invited_at: string;
}

/**
 * Invite a member to an organization (enhanced version with return type)
 */
export async function inviteOrganizationMemberWithResponse(
  token: string,
  organizationId: string,
  email: string,
  role: string
): Promise<InviteResponse> {
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

  return response.json();
}

/**
 * Remove a member from an organization
 */
export async function removeOrganizationMember(
  token: string,
  organizationId: string,
  memberId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}/members/${memberId}`,
    {
      method: "DELETE",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to remove member"
    );
    throw new Error(message);
  }
}

/**
 * Cancel a pending invitation
 */
export async function cancelOrganizationInvitation(
  token: string,
  organizationId: string,
  invitationId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}/invitations/${invitationId}`,
    {
      method: "DELETE",
      headers: getAuthHeaders(token),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to cancel invitation"
    );
    throw new Error(message);
  }
}

/**
 * Update a member's role in an organization
 */
export async function updateMemberRole(
  token: string,
  organizationId: string,
  memberId: string,
  role: "admin" | "member"
): Promise<OrganizationMember> {
  const response = await fetch(
    `${API_BASE_URL}/organizations/${organizationId}/members/${memberId}`,
    {
      method: "PATCH",
      headers: getAuthHeaders(token),
      body: JSON.stringify({ role }),
    }
  );

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to update member role"
    );
    throw new Error(message);
  }

  return response.json();
}
