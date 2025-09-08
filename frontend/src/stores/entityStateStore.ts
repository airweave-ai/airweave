// stores/entityStateStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Match backend SyncJobStatus enum values exactly
export type SyncStatus = 'created' | 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled';

export interface EntityState {
  connectionId: string;
  syncId?: string;
  entityCounts: Record<string, number>;  // name -> count
  totalEntities: number;
  syncStatus: SyncStatus;
  currentJobId?: string;
  lastUpdated: Date;
  error?: string;
}

export interface EntityStateUpdate {
  type: 'entity_state';
  job_id: string;
  sync_id: string;
  entity_counts: Record<string, number>;
  total_entities: number;
  timestamp: string;
  job_status: SyncStatus;  // Backend sends current status
}

export interface SyncCompleteMessage {
  type: 'sync_complete';
  job_id: string;
  sync_id: string;
  is_complete: boolean;
  is_failed: boolean;
  final_counts: Record<string, number>;
  total_entities: number;
  total_operations: number;
  timestamp: string;
  final_status: SyncStatus;  // Backend sends final status
  error?: string;
}

interface EntityStateStore {
  // State
  entityStates: Map<string, EntityState>;

  // Actions
  setEntityState: (connectionId: string, state: EntityState) => void;
  updateFromStream: (connectionId: string, update: EntityStateUpdate) => void;
  clearState: (connectionId: string) => void;

  // Getters
  getEntityState: (connectionId: string) => EntityState | null;
  getTotalCount: (connectionId: string) => number;
}

export const useEntityStateStore = create<EntityStateStore>()(
  persist(
    (set, get) => ({
      entityStates: new Map<string, EntityState>(),

      setEntityState: (connectionId, state) => {
        set((current) => {
          // Ensure entityStates is a Map with proper typing
          const currentStates = current.entityStates instanceof Map
            ? current.entityStates
            : new Map<string, EntityState>(Array.isArray(current.entityStates)
              ? current.entityStates as [string, EntityState][]
              : []);

          const newStates = new Map<string, EntityState>(currentStates);
          newStates.set(connectionId, {
            ...state,
            lastUpdated: state.lastUpdated instanceof Date ? state.lastUpdated : new Date()
          });
          return { entityStates: newStates };
        });
      },

      updateFromStream: (connectionId, update) => {
        set((current) => {
          // Ensure entityStates is a Map
          const currentStates = current.entityStates instanceof Map
            ? current.entityStates
            : new Map<string, EntityState>(Array.isArray(current.entityStates)
              ? current.entityStates as [string, EntityState][]
              : []);

          const existing = currentStates.get(connectionId);

          if (!existing) {
            // Create new state from stream
            const newState: EntityState = {
              connectionId: connectionId,
              syncId: update.sync_id,
              entityCounts: update.entity_counts || {},
              totalEntities: update.total_entities || 0,
              syncStatus: 'in_progress',  // Stream = active sync
              currentJobId: update.job_id,
              lastUpdated: new Date()
            };
            const newStates = new Map<string, EntityState>(currentStates);
            newStates.set(connectionId, newState);
            return { entityStates: newStates };
          }

          // Use the job_status from the update if provided, otherwise infer
          const newStatus = update.job_status || 'in_progress';

          // Always update with latest stream data
          const updated: EntityState = {
            ...existing,
            entityCounts: update.entity_counts || {},
            totalEntities: update.total_entities || 0,
            syncStatus: newStatus,
            currentJobId: update.job_id, // Keep job ID from stream
            syncId: update.sync_id || existing.syncId,
            lastUpdated: new Date()
          };

          const newStates = new Map<string, EntityState>(currentStates);
          newStates.set(connectionId, updated);
          return { entityStates: newStates };
        });
      },

      clearState: (connectionId) => {
        set((current) => {
          // Ensure entityStates is a Map
          const currentStates = current.entityStates instanceof Map
            ? current.entityStates
            : new Map<string, EntityState>(Array.isArray(current.entityStates)
              ? current.entityStates as [string, EntityState][]
              : []);

          const newStates = new Map<string, EntityState>(currentStates);
          newStates.delete(connectionId);
          return { entityStates: newStates };
        });
      },

      getEntityState: (connectionId) => {
        const state = get();
        // Ensure entityStates is a Map
        const entityStates = state.entityStates instanceof Map
          ? state.entityStates
          : new Map<string, EntityState>(Array.isArray(state.entityStates)
            ? state.entityStates as [string, EntityState][]
            : []);

        return entityStates.get(connectionId) || null;
      },

      getTotalCount: (connectionId) => {
        const state = get();
        // Ensure entityStates is a Map
        const entityStates = state.entityStates instanceof Map
          ? state.entityStates
          : new Map<string, EntityState>(Array.isArray(state.entityStates)
            ? state.entityStates as [string, EntityState][]
            : []);

        const entityState = entityStates.get(connectionId);
        if (!entityState) return 0;

        return Object.values(entityState.entityCounts)
          .reduce((sum, count) => sum + count, 0);
      }
    }),
    {
      name: 'entity-state-storage',
      // Persist entityStates as array entries with ISO dates to avoid Map/Date serialization issues
      partialize: (state: EntityStateStore) => {
        const entityStates = state.entityStates instanceof Map
          ? Array.from(state.entityStates.entries()).map(([key, entityState]) => [
            key,
            {
              ...entityState,
              lastUpdated: entityState.lastUpdated instanceof Date
                ? entityState.lastUpdated.toISOString()
                : (entityState.lastUpdated as any)
            }
          ])
          : (state.entityStates as any);
        return { entityStates } as unknown as EntityStateStore;
      }
    }
  )
);
