import { create } from "zustand";

import {
  checkActions as checkActionsApi,
  type ActionCheckResponse,
} from "@/lib/api/usage";

export const COMMON_ACTIONS = {
  source_connections: 1,
  entities: 1,
  queries: 1,
  team_members: 1,
} as const;

interface UsageState {
  actionChecks: Record<string, ActionCheckResponse>;
  isLoading: boolean;
  error: string | null;
  lastFetchedAt: number | null;
  cacheDuration: number;
  inflightRequest: Promise<Record<string, ActionCheckResponse>> | null;

  checkActions: (
    token: string,
    actions: Record<string, number>
  ) => Promise<Record<string, ActionCheckResponse>>;
  isActionAllowed: (action: string) => boolean;
  getActionStatus: (action: string) => ActionCheckResponse | undefined;
  clearCache: () => void;
  setCacheDuration: (duration: number) => void;
  shouldRefetch: () => boolean;
}

export const useUsageStore = create<UsageState>((set, get) => ({
  actionChecks: {},
  isLoading: false,
  error: null,
  lastFetchedAt: null,
  cacheDuration: 3000,
  inflightRequest: null,

  checkActions: async (token, actions) => {
    const state = get();

    if (!state.shouldRefetch() && Object.keys(state.actionChecks).length > 0) {
      return state.actionChecks;
    }

    if (state.inflightRequest) {
      return state.inflightRequest;
    }

    set({ isLoading: true, error: null });

    const request = (async () => {
      try {
        const response = await checkActionsApi(token, actions);
        set({
          actionChecks: response.results,
          lastFetchedAt: Date.now(),
          isLoading: false,
          inflightRequest: null,
        });
        return response.results;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to check usage";
        set({
          error: message,
          isLoading: false,
          inflightRequest: null,
        });
        return {};
      }
    })();

    set({ inflightRequest: request });
    return request;
  },

  isActionAllowed: (action) => {
    const check = get().actionChecks[action];
    return check ? check.allowed : true;
  },

  getActionStatus: (action) => {
    return get().actionChecks[action];
  },

  clearCache: () => {
    set({
      actionChecks: {},
      lastFetchedAt: null,
      error: null,
    });
  },

  setCacheDuration: (duration) => {
    set({ cacheDuration: duration });
  },

  shouldRefetch: () => {
    const { lastFetchedAt, cacheDuration } = get();
    if (!lastFetchedAt) return true;
    return Date.now() - lastFetchedAt > cacheDuration;
  },
}));

export function useUsageChecks() {
  const actionChecks = useUsageStore((state) => state.actionChecks);
  const isLoading = useUsageStore((state) => state.isLoading);
  const error = useUsageStore((state) => state.error);
  const isActionAllowed = useUsageStore((state) => state.isActionAllowed);
  const getActionStatus = useUsageStore((state) => state.getActionStatus);

  return {
    actionChecks,
    isLoading,
    error,
    isActionAllowed,
    getActionStatus,
    sourceConnectionsAllowed: isActionAllowed("source_connections"),
    entitiesAllowed: isActionAllowed("entities"),
    queriesAllowed: isActionAllowed("queries"),
    teamMembersAllowed: isActionAllowed("team_members"),
    sourceConnectionsStatus: getActionStatus("source_connections"),
    entitiesStatus: getActionStatus("entities"),
    queriesStatus: getActionStatus("queries"),
    teamMembersStatus: getActionStatus("team_members"),
  };
}
