/**
 * Webhooks store for managing webhook subscriptions and messages
 */

import { create } from 'zustand';
import { apiClient } from '../api';

/**
 * Webhook message type (snake_case to match API response)
 */
export interface WebhookMessage {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  timestamp: string;
  channels?: string[];
  delivery_attempts?: MessageAttempt[] | null;
}

/**
 * Subscription type (snake_case to match API response)
 */
export interface Subscription {
  id: string;
  url: string;
  filter_types?: string[] | null;
  created_at: string;
  updated_at: string;
  description?: string;
  disabled?: boolean;
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

interface WebhooksState {
  subscriptions: Subscription[];
  messages: WebhookMessage[];
  isLoadingSubscriptions: boolean;
  isLoadingMessages: boolean;
  error: string | null;

  // Actions
  fetchSubscriptions: () => Promise<void>;
  fetchMessages: (eventTypes?: string[]) => Promise<void>;
  fetchSubscription: (subscriptionId: string, includeSecret?: boolean) => Promise<Subscription>;
  createSubscription: (request: CreateSubscriptionRequest) => Promise<Subscription>;
  updateSubscription: (subscriptionId: string, request: UpdateSubscriptionRequest) => Promise<Subscription>;
  deleteSubscription: (subscriptionId: string) => Promise<void>;
  deleteSubscriptions: (subscriptionIds: string[]) => Promise<void>;
  clearWebhooks: () => void;
}

export const useWebhooksStore = create<WebhooksState>((set, get) => ({
  subscriptions: [],
  messages: [],
  isLoadingSubscriptions: false,
  isLoadingMessages: false,
  error: null,

  fetchSubscriptions: async () => {
    set({ isLoadingSubscriptions: true, error: null });
    try {
      const response = await apiClient.get('/webhooks/subscriptions');
      if (!response.ok) {
        throw new Error(`Failed to fetch subscriptions: ${response.status}`);
      }
      const subscriptions = await response.json();
      set({ subscriptions, isLoadingSubscriptions: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch subscriptions',
        isLoadingSubscriptions: false
      });
    }
  },

  fetchMessages: async (eventTypes?: string[]) => {
    set({ isLoadingMessages: true, error: null });
    try {
      let endpoint = '/webhooks/messages';
      if (eventTypes && eventTypes.length > 0) {
        const params = new URLSearchParams();
        eventTypes.forEach((type) => params.append('event_types', type));
        endpoint += `?${params.toString()}`;
      }
      const response = await apiClient.get(endpoint);
      if (!response.ok) {
        throw new Error(`Failed to fetch messages: ${response.status}`);
      }
      const messages = await response.json();
      set({ messages, isLoadingMessages: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch messages',
        isLoadingMessages: false
      });
    }
  },

  fetchSubscription: async (subscriptionId: string, includeSecret = false) => {
    const params = new URLSearchParams();
    if (includeSecret) {
      params.set("include_secret", "true");
    }
    const url = params.toString()
      ? `/webhooks/subscriptions/${subscriptionId}?${params}`
      : `/webhooks/subscriptions/${subscriptionId}`;
    const response = await apiClient.get(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch subscription: ${response.status}`);
    }
    return response.json();
  },

  createSubscription: async (request: CreateSubscriptionRequest) => {
    const response = await apiClient.post('/webhooks/subscriptions', request);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const detail = body?.detail || `HTTP ${response.status}`;
      throw new Error(detail);
    }
    const subscription = await response.json();
    // Refresh subscriptions list
    get().fetchSubscriptions();
    return subscription;
  },

  updateSubscription: async (subscriptionId: string, request: UpdateSubscriptionRequest) => {
    const response = await apiClient.patch(`/webhooks/subscriptions/${subscriptionId}`, request);
    if (!response.ok) {
      throw new Error(`Failed to update subscription: ${response.status}`);
    }
    const subscription = await response.json();
    // Refresh subscriptions list
    get().fetchSubscriptions();
    return subscription;
  },

  deleteSubscription: async (subscriptionId: string) => {
    const response = await apiClient.delete(`/webhooks/subscriptions/${subscriptionId}`);
    if (!response.ok) {
      throw new Error(`Failed to delete subscription: ${response.status}`);
    }
    // Refresh subscriptions list
    get().fetchSubscriptions();
  },

  deleteSubscriptions: async (subscriptionIds: string[]) => {
    // Delete all subscriptions in parallel
    const results = await Promise.allSettled(
      subscriptionIds.map(id =>
        apiClient.delete(`/webhooks/subscriptions/${id}`)
      )
    );

    // Check if any failed
    const failed = results.filter(r => r.status === 'rejected');
    if (failed.length > 0) {
      console.error(`Failed to delete ${failed.length} subscription(s)`);
    }

    // Refresh subscriptions list
    get().fetchSubscriptions();
  },

  clearWebhooks: () => {
    set({ subscriptions: [], messages: [], error: null });
  },
}));
