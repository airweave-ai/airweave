import { create } from 'zustand';
import { apiClient } from '@/lib/api';

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

interface CreateAPIKeyRequest {
  expiration_days?: number; // Number of days until expiration (default: 90)
}

interface APIKeysState {
  // State
  apiKeys: APIKey[];
  isLoading: boolean;
  error: string | null;

  // Actions
  setAPIKeys: (keys: APIKey[]) => void;
  addAPIKey: (key: APIKey) => void;
  removeAPIKey: (keyId: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // API actions
  fetchAPIKeys: (forceRefresh?: boolean) => Promise<APIKey[]>;
  createAPIKey: (expirationDays?: number) => Promise<APIKey>;
  rotateAPIKey: (keyId: string) => Promise<APIKey>;
  deleteAPIKey: (keyId: string) => Promise<void>;

  // Utility actions
  clearAPIKeys: () => void;
}

export const useAPIKeysStore = create<APIKeysState>((set, get) => ({
  // Initial state
  apiKeys: [],
  isLoading: false,
  error: null,

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

    // If we already have data and no force refresh, return cached data
    if (apiKeys.length > 0 && !forceRefresh) {
      console.log("🔍 [APIKeysStore] Using cached API keys, skipping API call");
      return apiKeys;
    }

    // If already loading, don't start another request
    if (isLoading && !forceRefresh) {
      console.log("🔍 [APIKeysStore] API keys already loading, skipping duplicate request");
      return apiKeys;
    }

    console.log("🔍 [APIKeysStore] Fetching API keys from API");
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
      console.error("❌ [APIKeysStore]", errorMessage);
      return get().apiKeys;
    }
  },

  createAPIKey: async (expirationDays?: number) => {
    set({ isLoading: true, error: null });

    try {
      const body: CreateAPIKeyRequest = expirationDays ? { expiration_days: expirationDays } : {};
      const response = await apiClient.post('/api-keys', body);

      if (!response.ok) {
        throw new Error(`Failed to create API key: ${response.status}`);
      }

      const newKey = await response.json();

      // Add to the beginning of the array
      set((state) => ({
        apiKeys: [newKey, ...state.apiKeys],
        isLoading: false
      }));

      return newKey;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create API key';
      set({ error: errorMessage, isLoading: false });
      throw new Error(errorMessage);
    }
  },

  rotateAPIKey: async (keyId: string) => {
    set({ isLoading: true, error: null });

    try {
      const response = await apiClient.post(`/api-keys/${keyId}/rotate`, {});

      if (!response.ok) {
        throw new Error(`Failed to rotate API key: ${response.status}`);
      }

      const newKey = await response.json();

      // Add the new key to the beginning of the array
      set((state) => ({
        apiKeys: [newKey, ...state.apiKeys],
        isLoading: false
      }));

      return newKey;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to rotate API key';
      set({ error: errorMessage, isLoading: false });
      throw new Error(errorMessage);
    }
  },

  deleteAPIKey: async (keyId: string) => {
    set({ isLoading: true, error: null });

    try {
      const response = await apiClient.delete('/api-keys', { id: keyId });

      if (!response.ok) {
        throw new Error(`Failed to delete API key: ${response.status}`);
      }

      // Remove from state
      set((state) => ({
        apiKeys: state.apiKeys.filter(key => key.id !== keyId),
        isLoading: false
      }));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete API key';
      set({ error: errorMessage, isLoading: false });
      throw new Error(errorMessage);
    }
  },

  // Utility action for clearing state (useful when switching organizations)
  clearAPIKeys: () => {
    console.log("🧹 [APIKeysStore] Clearing API keys state");
    set({
      apiKeys: [],
      isLoading: false,
      error: null
    });
  }
}));
