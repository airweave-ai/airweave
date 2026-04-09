import { create } from 'zustand';
import { apiClient } from '@/lib/api';

export interface APIKey {
  id: string;
  organization_id: string;
  created_at: string;
  modified_at: string;
  last_used_date: string | null;
  last_used_ip: string | null;
  expiration_date: string;
  status: "active" | "expired" | "revoked";
  revoked_at: string | null;
  key_prefix: string | null;
  description: string | null;
  created_by_email: string | null;
  modified_by_email: string | null;
  decrypted_key: string | null;
}

export interface APIKeyUsageLogEntry {
  id: string;
  api_key_id: string | null;
  organization_id: string;
  timestamp: string;
  ip_address: string;
  endpoint: string;
  user_agent: string | null;
}

export interface APIKeyUsageStats {
  api_key_id: string;
  total_requests: number;
  first_used: string | null;
  last_used: string | null;
  unique_ips: number;
  unique_endpoints: number;
}

interface CreateAPIKeyRequest {
  expiration_days?: number;
  description?: string;
}

interface APIKeysState {
  // State
  apiKeys: APIKey[];
  isLoading: boolean;
  error: string | null;
  usageStats: Record<string, APIKeyUsageStats>;
  usageLogs: Record<string, APIKeyUsageLogEntry[]>;
  usageLogsHasMore: Record<string, boolean>;

  // Actions
  setAPIKeys: (keys: APIKey[]) => void;
  addAPIKey: (key: APIKey) => void;
  removeAPIKey: (keyId: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // API actions
  fetchAPIKeys: (forceRefresh?: boolean) => Promise<APIKey[]>;
  createAPIKey: (expirationDays?: number, description?: string) => Promise<APIKey>;
  rotateAPIKey: (keyId: string) => Promise<APIKey>;
  deleteAPIKey: (keyId: string) => Promise<void>;
  fetchUsageStats: (keyId: string) => Promise<APIKeyUsageStats>;
  fetchUsageLogs: (keyId: string, skip?: number, limit?: number) => Promise<APIKeyUsageLogEntry[]>;

  // Utility actions
  clearAPIKeys: () => void;
}

export const useAPIKeysStore = create<APIKeysState>((set, get) => ({
  // Initial state
  apiKeys: [],
  isLoading: false,
  error: null,
  usageStats: {},
  usageLogs: {},
  usageLogsHasMore: {},

  // Basic setters
  setAPIKeys: (apiKeys) => set({ apiKeys }),

  addAPIKey: (key) => set((state) => ({
    apiKeys: [key, ...state.apiKeys]
  })),

  removeAPIKey: (keyId) => set((state) => ({
    apiKeys: state.apiKeys.filter(key => key.id !== keyId)
  })),

  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),

  // API actions
  fetchAPIKeys: async (forceRefresh = false) => {
    const { apiKeys, isLoading } = get();

    if (apiKeys.length > 0 && !forceRefresh) {
      return apiKeys;
    }

    if (isLoading && !forceRefresh) {
      return apiKeys;
    }

    set({ isLoading: true, error: null });

    try {
      const response = await apiClient.get('/api-keys');

      if (!response.ok) {
        throw new Error(`Failed to fetch API keys: ${response.status}`);
      }

      const data = await response.json();
      const keys = Array.isArray(data) ? data : [];

      set({ apiKeys: keys, isLoading: false });
      return keys;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch API keys';
      set({ error: errorMessage, isLoading: false });
      return get().apiKeys;
    }
  },

  createAPIKey: async (expirationDays?: number, description?: string) => {
    set({ error: null });

    try {
      const body: CreateAPIKeyRequest = {};
      if (expirationDays) body.expiration_days = expirationDays;
      if (description) body.description = description;
      const response = await apiClient.post('/api-keys', body);

      if (!response.ok) {
        throw new Error(`Failed to create API key: ${response.status}`);
      }

      const newKey = await response.json();

      set((state) => ({
        apiKeys: [newKey, ...state.apiKeys],
      }));

      return newKey;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create API key';
      set({ error: errorMessage });
      throw new Error(errorMessage);
    }
  },

  rotateAPIKey: async (keyId: string) => {
    set({ error: null });

    try {
      const response = await apiClient.post(`/api-keys/${keyId}/rotate`, {});

      if (!response.ok) {
        throw new Error(`Failed to rotate API key: ${response.status}`);
      }

      const newKey = await response.json();

      // Refresh the full list to reflect revoked status on old key
      await get().fetchAPIKeys(true);

      return newKey;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to rotate API key';
      set({ error: errorMessage });
      throw new Error(errorMessage);
    }
  },

  deleteAPIKey: async (keyId: string) => {
    set({ error: null });

    try {
      const response = await apiClient.delete('/api-keys', { id: keyId });

      if (!response.ok) {
        throw new Error(`Failed to delete API key: ${response.status}`);
      }

      set((state) => ({
        apiKeys: state.apiKeys.filter(key => key.id !== keyId),
      }));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete API key';
      set({ error: errorMessage });
      throw new Error(errorMessage);
    }
  },

  fetchUsageStats: async (keyId: string) => {
    try {
      const response = await apiClient.get(`/api-keys/${keyId}/usage/stats`);

      if (!response.ok) {
        throw new Error(`Failed to fetch usage stats: ${response.status}`);
      }

      const stats: APIKeyUsageStats = await response.json();
      set((state) => ({
        usageStats: { ...state.usageStats, [keyId]: stats }
      }));
      return stats;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch usage stats';
      throw new Error(errorMessage);
    }
  },

  fetchUsageLogs: async (keyId: string, skip = 0, limit = 20) => {
    try {
      const response = await apiClient.get(
        `/api-keys/${keyId}/usage?skip=${skip}&limit=${limit}`
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch usage logs: ${response.status}`);
      }

      const entries: APIKeyUsageLogEntry[] = await response.json();
      set((state) => ({
        usageLogs: {
          ...state.usageLogs,
          [keyId]: skip === 0 ? entries : [...(state.usageLogs[keyId] || []), ...entries],
        },
        usageLogsHasMore: {
          ...state.usageLogsHasMore,
          [keyId]: entries.length === limit,
        },
      }));
      return entries;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch usage logs';
      throw new Error(errorMessage);
    }
  },

  clearAPIKeys: () => {
    set({
      apiKeys: [],
      isLoading: false,
      error: null,
      usageStats: {},
      usageLogs: {},
      usageLogsHasMore: {},
    });
  }
}));
