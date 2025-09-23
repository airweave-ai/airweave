import { create } from 'zustand';
import { apiClient } from '../api';
import type { SingleActionCheckResponse } from '@/types';

interface ActionCheckResponse {
  results: Record<string, SingleActionCheckResponse>;
}

interface UsageState {
  // Action check results cache
  actionChecks: Record<string, SingleActionCheckResponse>;

  // Loading state
  isLoading: boolean;

  // Error state
  error: string | null;

  // Last fetch timestamp
  lastFetchedAt: number | null;

  // Cache duration in milliseconds (default: 30 seconds)
  cacheDuration: number;

  // In-flight request promise for deduplication
  inflightRequest: Promise<Record<string, SingleActionCheckResponse>> | null;

  // Actions
  checkActions: (actions: Record<string, number>) => Promise<Record<string, SingleActionCheckResponse>>;
  clearCache: () => void;
  setCacheDuration: (duration: number) => void;

  // Helper methods
  isActionAllowed: (action: string) => boolean;
  getActionStatus: (action: string) => SingleActionCheckResponse | undefined;
  shouldRefetch: () => boolean;
}

export const useUsageStore = create<UsageState>((set, get) => ({
  actionChecks: {},
  isLoading: false,
  error: null,
  lastFetchedAt: null,
  cacheDuration: 3000, // 3 seconds default
  inflightRequest: null,

  checkActions: async (actions: Record<string, number>) => {
    const state = get();

    // Check if we should use cached data
    if (!state.shouldRefetch()) {
      // Check if all requested actions are already cached
      const allCached = Object.keys(actions).every(action => action in state.actionChecks);
      if (allCached) {
        return state.actionChecks;
      }
    }

    // If there's already an in-flight request, return it (deduplication)
    if (state.inflightRequest) {
      console.log('[UsageStore] Deduplicating request - returning existing promise');
      return state.inflightRequest;
    }

    // Create the request promise
    const requestPromise = (async () => {
      set({ isLoading: true, error: null });

      try {
        const response = await apiClient.post('/usage/check-actions', {
          actions
        });

        if (!response.ok) {
          throw new Error(`Failed to check actions: ${response.status}`);
        }

        const data: ActionCheckResponse = await response.json();

        set({
          actionChecks: data.results,
          lastFetchedAt: Date.now(),
          isLoading: false,
          error: null,
          inflightRequest: null // Clear the in-flight request
        });

        return data.results;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to check actions';
        set({
          isLoading: false,
          error: errorMessage,
          inflightRequest: null // Clear the in-flight request
        });
        throw error;
      }
    })();

    // Store the in-flight request
    set({ inflightRequest: requestPromise });

    return requestPromise;
  },

  clearCache: () => {
    set({
      actionChecks: {},
      lastFetchedAt: null,
      error: null,
      inflightRequest: null
    });
  },

  setCacheDuration: (duration: number) => {
    set({ cacheDuration: duration });
  },

  isActionAllowed: (action: string) => {
    const state = get();
    const check = state.actionChecks[action];
    return check ? check.allowed : true; // Default to true if not checked
  },

  getActionStatus: (action: string) => {
    const state = get();
    return state.actionChecks[action];
  },

  shouldRefetch: () => {
    const state = get();
    if (!state.lastFetchedAt) return true;

    const now = Date.now();
    const timeSinceLastFetch = now - state.lastFetchedAt;
    return timeSinceLastFetch > state.cacheDuration;
  }
}));

// Helper hook for checking all common actions at once
export const useCheckCommonActions = () => {
  const checkActions = useUsageStore(state => state.checkActions);
  const actionChecks = useUsageStore(state => state.actionChecks);
  const isLoading = useUsageStore(state => state.isLoading);
  const error = useUsageStore(state => state.error);

  const checkCommonActions = async () => {
    return checkActions({
      source_connections: 1,
      entities: 1,
      queries: 1,
      team_members: 1
    });
  };

  return {
    checkCommonActions,
    actionChecks,
    isLoading,
    error
  };
};

// Helper hook for organization-specific cache clearing
export const useUsageStoreWithOrgSwitch = () => {
  const clearCache = useUsageStore(state => state.clearCache);

  // This should be called when organization changes
  const handleOrganizationChange = () => {
    clearCache();
  };

  return { handleOrganizationChange };
};
