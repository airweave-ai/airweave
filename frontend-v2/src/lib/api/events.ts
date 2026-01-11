/**
 * Events API operations
 */

import { API_BASE_URL, getAuthHeaders } from "./client";

/**
 * Event message type based on Svix MessageOut
 */
export interface EventMessage {
  id: string;
  eventType: string;
  payload: Record<string, unknown>;
  timestamp: string;
  channels?: string[];
}

/**
 * Subscription type based on Svix EndpointOut
 */
export interface Subscription {
  id: string;
  url: string;
  channels?: string[];
  createdAt: string;
  updatedAt: string;
  description?: string;
  disabled?: boolean;
}

/**
 * Message attempt type based on Svix MessageAttemptOut
 */
export interface MessageAttempt {
  id: string;
  url: string;
  msgId: string;
  endpointId: string;
  response: string;
  responseStatusCode: number;
  timestamp: string;
  status: number;
  triggerType: number;
}

/**
 * Subscription with message attempts response type
 */
export interface SubscriptionWithAttempts {
  endpoint: Subscription;
  message_attempts: MessageAttempt[];
}

/**
 * Fetch event messages for the current organization
 */
export async function fetchEventMessages(
  token: string,
  orgId: string,
  eventTypes?: string[]
): Promise<EventMessage[]> {
  let url = `${API_BASE_URL}/events/messages`;
  if (eventTypes && eventTypes.length > 0) {
    const params = new URLSearchParams();
    eventTypes.forEach((type) => params.append("event_types", type));
    url += `?${params.toString()}`;
  }

  const response = await fetch(url, {
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch event messages: ${response.status}`);
  }

  return response.json();
}

/**
 * Fetch subscriptions for the current organization
 */
export async function fetchSubscriptions(
  token: string,
  orgId: string
): Promise<Subscription[]> {
  const response = await fetch(`${API_BASE_URL}/events/subscriptions`, {
    headers: getAuthHeaders(token, orgId),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch subscriptions: ${response.status}`);
  }

  return response.json();
}

/**
 * Fetch a single subscription by ID with its message attempts
 */
export async function fetchSubscription(
  token: string,
  orgId: string,
  subscriptionId: string
): Promise<SubscriptionWithAttempts> {
  const response = await fetch(
    `${API_BASE_URL}/events/subscriptions/${subscriptionId}`,
    {
      headers: getAuthHeaders(token, orgId),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch subscription: ${response.status}`);
  }

  return response.json();
}

/**
 * Create subscription request type
 */
export interface CreateSubscriptionRequest {
  url: string;
  event_types: string[];
  secret?: string;
}

/**
 * Create a new subscription
 */
export async function createSubscription(
  token: string,
  orgId: string,
  request: CreateSubscriptionRequest
): Promise<Subscription> {
  const response = await fetch(`${API_BASE_URL}/events/subscriptions`, {
    method: "POST",
    headers: getAuthHeaders(token, orgId),
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to create subscription: ${response.status}`);
  }

  return response.json();
}

/**
 * Update subscription request type
 */
export interface UpdateSubscriptionRequest {
  url?: string;
  event_types?: string[];
}

/**
 * Update an existing subscription
 */
export async function updateSubscription(
  token: string,
  orgId: string,
  subscriptionId: string,
  request: UpdateSubscriptionRequest
): Promise<Subscription> {
  const response = await fetch(
    `${API_BASE_URL}/events/subscriptions/${subscriptionId}`,
    {
      method: "PATCH",
      headers: getAuthHeaders(token, orgId),
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to update subscription: ${response.status}`);
  }

  return response.json();
}

/**
 * Delete a subscription
 */
export async function deleteSubscription(
  token: string,
  orgId: string,
  subscriptionId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/events/subscriptions/${subscriptionId}`,
    {
      method: "DELETE",
      headers: getAuthHeaders(token, orgId),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to delete subscription: ${response.status}`);
  }
}

/**
 * Subscription secret response type
 */
export interface SubscriptionSecret {
  key: string;
}

/**
 * Fetch a subscription's signing secret
 */
export async function fetchSubscriptionSecret(
  token: string,
  orgId: string,
  subscriptionId: string
): Promise<SubscriptionSecret> {
  const response = await fetch(
    `${API_BASE_URL}/events/subscriptions/${subscriptionId}/secret`,
    {
      headers: getAuthHeaders(token, orgId),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch subscription secret: ${response.status}`);
  }

  return response.json();
}
