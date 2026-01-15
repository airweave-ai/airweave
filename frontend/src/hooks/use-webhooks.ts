/**
 * TanStack Query hooks for webhook subscriptions and event messages
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

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
 * Message type based on Svix MessageOut (includes payload)
 */
export interface Message {
  id: string;
  eventType: string;
  payload: Record<string, unknown>;
  timestamp: string;
  channels?: string[];
}

/**
 * Subscription with message attempts response type
 */
export interface SubscriptionWithAttempts {
  endpoint: Subscription;
  message_attempts: MessageAttempt[];
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
}

/**
 * Subscription secret response type
 */
export interface SubscriptionSecret {
  key: string;
}

// Query keys
export const webhookKeys = {
  all: ["webhooks"] as const,
  subscriptions: () => [...webhookKeys.all, "subscriptions"] as const,
  subscription: (id: string) => [...webhookKeys.subscriptions(), id] as const,
  subscriptionSecret: (id: string) => [...webhookKeys.subscription(id), "secret"] as const,
  messages: () => [...webhookKeys.all, "messages"] as const,
  message: (id: string) => [...webhookKeys.messages(), id] as const,
  messageAttempts: (id: string) => [...webhookKeys.message(id), "attempts"] as const,
};

/**
 * Fetch all webhook subscriptions
 */
async function fetchSubscriptions(): Promise<Subscription[]> {
  const response = await apiClient.get("/events/subscriptions");
  if (!response.ok) {
    throw new Error(`Failed to fetch subscriptions: ${response.status}`);
  }
  return response.json();
}

/**
 * Fetch a single subscription with its delivery attempts
 */
async function fetchSubscription(id: string): Promise<SubscriptionWithAttempts> {
  const response = await apiClient.get(`/events/subscriptions/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch subscription: ${response.status}`);
  }
  return response.json();
}

/**
 * Fetch subscription secret
 */
async function fetchSubscriptionSecret(id: string): Promise<SubscriptionSecret> {
  const response = await apiClient.get(`/events/subscriptions/${id}/secret`);
  if (!response.ok) {
    throw new Error(`Failed to fetch subscription secret: ${response.status}`);
  }
  return response.json();
}

/**
 * Fetch a specific message by ID (includes payload)
 */
async function fetchMessage(id: string): Promise<Message> {
  const response = await apiClient.get(`/events/messages/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch message: ${response.status}`);
  }
  return response.json();
}

/**
 * Fetch all messages (events)
 */
async function fetchMessages(): Promise<Message[]> {
  const response = await apiClient.get("/events/messages");
  if (!response.ok) {
    throw new Error(`Failed to fetch messages: ${response.status}`);
  }
  return response.json();
}

/**
 * Fetch delivery attempts for a specific message
 */
async function fetchMessageAttempts(messageId: string): Promise<MessageAttempt[]> {
  const response = await apiClient.get(`/events/messages/${messageId}/attempts`);
  if (!response.ok) {
    throw new Error(`Failed to fetch message attempts: ${response.status}`);
  }
  return response.json();
}

/**
 * Create a new subscription
 */
async function createSubscription(data: CreateSubscriptionRequest): Promise<Subscription> {
  const response = await apiClient.post("/events/subscriptions", data);
  if (!response.ok) {
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
  const response = await apiClient.patch(`/events/subscriptions/${id}`, data);
  if (!response.ok) {
    throw new Error(`Failed to update subscription: ${response.status}`);
  }
  return response.json();
}

/**
 * Delete a subscription
 */
async function deleteSubscription(id: string): Promise<void> {
  const response = await apiClient.delete(`/events/subscriptions/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to delete subscription: ${response.status}`);
  }
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
 * Hook to fetch a single subscription with delivery attempts
 */
export function useSubscription(id: string | null) {
  return useQuery({
    queryKey: webhookKeys.subscription(id ?? ""),
    queryFn: () => fetchSubscription(id!),
    enabled: !!id,
  });
}

/**
 * Hook to fetch subscription secret (on-demand, not cached long)
 */
export function useSubscriptionSecret(id: string | null, enabled = false) {
  return useQuery({
    queryKey: webhookKeys.subscriptionSecret(id ?? ""),
    queryFn: () => fetchSubscriptionSecret(id!),
    enabled: enabled && !!id,
    staleTime: 0, // Always refetch when requested
  });
}

/**
 * Hook to fetch a specific message (includes payload)
 */
export function useMessage(id: string | null) {
  return useQuery({
    queryKey: webhookKeys.message(id ?? ""),
    queryFn: () => fetchMessage(id!),
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
 * Hook to fetch delivery attempts for a specific message
 */
export function useMessageAttempts(messageId: string | null) {
  return useQuery({
    queryKey: webhookKeys.messageAttempts(messageId ?? ""),
    queryFn: () => fetchMessageAttempts(messageId!),
    enabled: !!messageId,
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
      queryClient.invalidateQueries({ queryKey: webhookKeys.subscription(id) });
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
