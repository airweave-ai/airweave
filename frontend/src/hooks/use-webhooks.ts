/**
 * TanStack Query hooks for webhook subscriptions and event messages
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

/**
 * Subscription type (snake_case to match API response)
 */
export type HealthStatus = "healthy" | "degraded" | "failing" | "unknown";

export interface Subscription {
  id: string;
  url: string;
  filter_types?: string[] | null;
  created_at: string;
  updated_at: string;
  description?: string;
  disabled?: boolean;
  health_status?: HealthStatus;
}

/**
 * Detail type returned by GET /subscriptions/{id} — includes delivery attempts and secret
 */
export interface SubscriptionDetail extends Subscription {
  delivery_attempts?: MessageAttempt[] | null;
  secret?: string | null;
}

/**
 * Message attempt type (snake_case to match API response)
 */
export interface MessageAttempt {
  id: string;
  message_id: string;
  endpoint_id: string;
  response: string | null;
  response_status_code: number;
  timestamp: string;
  status: string;
}

/**
 * Message type (snake_case to match API response)
 */
export interface Message {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  timestamp: string;
  channels?: string[];
  delivery_attempts?: MessageAttempt[] | null;
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
 * Update subscription request type
 */
export interface UpdateSubscriptionRequest {
  url?: string;
  event_types?: string[];
  disabled?: boolean;
}

/**
 * Recover messages request type
 */
export interface RecoverMessagesRequest {
  since: string;
  until?: string;
}

/**
 * Recover messages response type
 */
export interface RecoverOut {
  id: string;
  status: string;
  task: string;
}

// Query keys
export const webhookKeys = {
  all: ["webhooks"] as const,
  subscriptions: () => [...webhookKeys.all, "subscriptions"] as const,
  subscription: (id: string, includeSecret?: boolean) =>
    [...webhookKeys.subscriptions(), id, { includeSecret }] as const,
  messages: () => [...webhookKeys.all, "messages"] as const,
  message: (id: string, includeAttempts?: boolean) =>
    [...webhookKeys.messages(), id, { includeAttempts }] as const,
};

/**
 * Fetch all webhook subscriptions
 */
async function fetchSubscriptions(): Promise<Subscription[]> {
  const response = await apiClient.get("/webhooks/subscriptions");
  if (!response.ok) {
    throw new Error(`Failed to fetch subscriptions: ${response.status}`);
  }
  return response.json();
}

/**
 * Fetch a single subscription with its delivery attempts
 * @param id - Subscription ID
 * @param includeSecret - Whether to include the signing secret
 */
async function fetchSubscription(
  id: string,
  includeSecret = false
): Promise<SubscriptionDetail> {
  const params = new URLSearchParams();
  if (includeSecret) {
    params.set("include_secret", "true");
  }
  const url = params.toString()
    ? `/webhooks/subscriptions/${id}?${params}`
    : `/webhooks/subscriptions/${id}`;
  const response = await apiClient.get(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch subscription: ${response.status}`);
  }
  return response.json();
}

/**
 * Fetch a specific message by ID (includes payload)
 * @param id - Message ID
 * @param includeAttempts - Whether to include delivery attempts
 */
async function fetchMessage(id: string, includeAttempts = false): Promise<Message> {
  const params = new URLSearchParams();
  if (includeAttempts) {
    params.set("include_attempts", "true");
  }
  const url = params.toString()
    ? `/webhooks/messages/${id}?${params}`
    : `/webhooks/messages/${id}`;
  const response = await apiClient.get(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch message: ${response.status}`);
  }
  return response.json();
}

/**
 * Fetch all messages (events)
 */
async function fetchMessages(): Promise<Message[]> {
  const response = await apiClient.get("/webhooks/messages");
  if (!response.ok) {
    throw new Error(`Failed to fetch messages: ${response.status}`);
  }
  return response.json();
}

/**
 * Create a new subscription
 */
async function createSubscription(data: CreateSubscriptionRequest): Promise<Subscription> {
  const response = await apiClient.post("/webhooks/subscriptions", data);
  if (!response.ok) {
    // Extract error detail from the response body (e.g. endpoint verification failures)
    try {
      const body = await response.json();
      if (body?.detail) {
        throw new Error(body.detail);
      }
    } catch (e) {
      if (e instanceof Error && !e.message.startsWith("Failed to create")) {
        throw e;
      }
    }
    throw new Error(`Failed to create subscription: ${response.status}`);
  }
  return response.json();
}

/**
 * Update an existing subscription
 */
async function updateSubscription(
  id: string,
  data: UpdateSubscriptionRequest
): Promise<Subscription> {
  const response = await apiClient.patch(`/webhooks/subscriptions/${id}`, data);
  if (!response.ok) {
    throw new Error(`Failed to update subscription: ${response.status}`);
  }
  return response.json();
}

/**
 * Delete a subscription
 */
async function deleteSubscription(id: string): Promise<void> {
  const response = await apiClient.delete(`/webhooks/subscriptions/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to delete subscription: ${response.status}`);
  }
}

/**
 * Recover failed messages for a subscription
 */
async function recoverFailedMessages(
  id: string,
  data: RecoverMessagesRequest
): Promise<RecoverOut> {
  const response = await apiClient.post(`/webhooks/subscriptions/${id}/recover`, data);
  if (!response.ok) {
    throw new Error(`Failed to recover messages: ${response.status}`);
  }
  return response.json();
}


// ============ HOOKS ============

/**
 * Hook to fetch all subscriptions
 */
export function useSubscriptions() {
  return useQuery({
    queryKey: webhookKeys.subscriptions(),
    queryFn: fetchSubscriptions,
  });
}

/**
 * Hook to fetch a single subscription detail (delivery attempts + optional secret)
 * @param id - Subscription ID
 * @param includeSecret - Whether to include the signing secret
 */
export function useSubscription(id: string | null, includeSecret = false) {
  return useQuery<SubscriptionDetail>({
    queryKey: webhookKeys.subscription(id ?? "", includeSecret),
    queryFn: () => fetchSubscription(id!, includeSecret),
    enabled: !!id,
    // Don't cache when secret is included (sensitive data)
    staleTime: includeSecret ? 0 : undefined,
  });
}

/**
 * Hook to fetch a specific message (includes payload)
 * @param id - Message ID
 * @param includeAttempts - Whether to include delivery attempts
 */
export function useMessage(id: string | null, includeAttempts = false) {
  return useQuery({
    queryKey: webhookKeys.message(id ?? "", includeAttempts),
    queryFn: () => fetchMessage(id!, includeAttempts),
    enabled: !!id,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes since payloads don't change
  });
}

/**
 * Hook to fetch all messages (events)
 */
export function useMessages() {
  return useQuery({
    queryKey: webhookKeys.messages(),
    queryFn: fetchMessages,
  });
}

/**
 * Hook to create a subscription
 */
export function useCreateSubscription() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: webhookKeys.subscriptions() });
    },
  });
}

/**
 * Hook to update a subscription
 */
export function useUpdateSubscription() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateSubscriptionRequest }) =>
      updateSubscription(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: webhookKeys.subscriptions() });
      // Invalidate all subscription queries for this ID (with any includeSecret value)
      queryClient.invalidateQueries({ queryKey: [...webhookKeys.subscriptions(), id] });
    },
  });
}

/**
 * Hook to delete a subscription
 */
export function useDeleteSubscription() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: webhookKeys.subscriptions() });
    },
  });
}

/**
 * Hook to delete multiple subscriptions
 */
export function useDeleteSubscriptions() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (ids: string[]) => {
      await Promise.allSettled(ids.map((id) => deleteSubscription(id)));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: webhookKeys.subscriptions() });
    },
  });
}

/**
 * Hook to recover failed messages for a subscription
 */
export function useRecoverFailedMessages() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RecoverMessagesRequest }) =>
      recoverFailedMessages(id, data),
    onSuccess: (_, { id }) => {
      // Invalidate all subscription queries for this ID
      queryClient.invalidateQueries({ queryKey: [...webhookKeys.subscriptions(), id] });
    },
  });
}

/**
 * Hook to enable a disabled endpoint with optional message recovery
 */
export function useEnableEndpoint() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, recoverSince }: { id: string; recoverSince?: string }) =>
      updateSubscription(id, {
        disabled: false,
        ...(recoverSince ? { recover_since: recoverSince } : {}),
      }),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: webhookKeys.subscriptions() });
      // Invalidate all subscription queries for this ID
      queryClient.invalidateQueries({ queryKey: [...webhookKeys.subscriptions(), id] });
    },
  });
}

/**
 * Hook to disable an endpoint
 */
export function useDisableEndpoint() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => updateSubscription(id, { disabled: true }),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: webhookKeys.subscriptions() });
      // Invalidate all subscription queries for this ID
      queryClient.invalidateQueries({ queryKey: [...webhookKeys.subscriptions(), id] });
    },
  });
}
