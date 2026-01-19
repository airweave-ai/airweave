/**
 * Entity state store for source connection schema.
 * Manages real-time sync state for source connections with nested LastSyncJob objects.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

/** Match backend SyncJobStatus enum */
export type SyncJobStatus =
  | "created"
  | "pending"
  | "in_progress"
  | "cancelling"
  | "completed"
  | "failed"
  | "cancelled";

/** Match backend nested objects */
export interface LastSyncJob {
  id: string;
  status: SyncJobStatus;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;

  // Entity metrics
  entities_inserted: number;
  entities_updated: number;
  entities_deleted: number;
  entities_failed: number;

  // Error information
  error?: string;
  error_details?: Record<string, unknown>;
}

export interface Schedule {
  cron_expression?: string;
  next_run_at?: string;
  is_continuous: boolean;
  cursor_field?: string;
  cursor_value?: unknown;
}

export interface EntityState {
  entity_type: string;
  total_count: number;
  last_updated_at?: string;
  sync_status: "pending" | "syncing" | "synced" | "failed";
  error?: string;
}

/** Source connection with nested data */
export interface SourceConnectionState {
  id: string;
  name: string;
  short_name: string;
  collection: string;
  status: "active" | "in_progress" | "failing" | "not_yet_authorized";
  is_authenticated: boolean;

  // Nested objects (from API with depth > 0)
  last_sync_job?: LastSyncJob;
  schedule?: Schedule;
  entity_states?: EntityState[];

  // UI state
  lastUpdated: Date;
}

/** Real-time update message from SSE */
export interface SyncProgressMessage {
  type: "sync_progress";
  source_connection_id: string;
  job_id: string;
  entities_inserted: number;
  entities_updated: number;
  entities_deleted: number;
  entities_failed: number;
  timestamp: string;
}

export interface SyncCompleteUpdate {
  type: "sync_complete";
  source_connection_id: string;
  job_id: string;
  status: SyncJobStatus;
  duration_seconds: number;
  final_counts: {
    entities_inserted: number;
    entities_updated: number;
    entities_deleted: number;
    entities_failed: number;
  };
  error?: string;
  timestamp: string;
}

interface EntityStateStore {
  // State
  sourceConnections: Map<string, SourceConnectionState>;
  activeJobs: Set<string>; // Track active job IDs

  // Actions
  setSourceConnection: (connection: SourceConnectionState) => void;
  updateFromProgress: (update: SyncProgressMessage) => void;
  updateFromComplete: (update: SyncCompleteUpdate) => void;
  clearConnection: (connectionId: string) => void;
  clearAll: () => void;

  // Getters
  getConnection: (connectionId: string) => SourceConnectionState | undefined;
  getLastSyncJob: (connectionId: string) => LastSyncJob | undefined;
  isJobActive: (jobId: string) => boolean;
  getActiveJobsCount: () => number;
}

export const useEntityStateStore = create<EntityStateStore>()(
  persist(
    (set, get) => ({
      sourceConnections: new Map<string, SourceConnectionState>(),
      activeJobs: new Set<string>(),

      setSourceConnection: (connection) => {
        set((state) => {
          const connections = new Map(state.sourceConnections);
          connections.set(connection.id, {
            ...connection,
            lastUpdated: new Date(),
          });

          // Track active job if present
          const activeJobs = new Set(state.activeJobs);
          if (connection.last_sync_job?.status === "in_progress") {
            activeJobs.add(connection.last_sync_job.id);
          }

          return { sourceConnections: connections, activeJobs };
        });
      },

      updateFromProgress: (update) => {
        set((state) => {
          const connections = new Map(state.sourceConnections);
          const existing = connections.get(update.source_connection_id);

          if (!existing) {
            // Create minimal state if doesn't exist
            connections.set(update.source_connection_id, {
              id: update.source_connection_id,
              name: "Unknown",
              short_name: "unknown",
              collection: "",
              status: "in_progress",
              is_authenticated: true,
              last_sync_job: {
                id: update.job_id,
                status: "in_progress",
                entities_inserted: update.entities_inserted,
                entities_updated: update.entities_updated,
                entities_deleted: update.entities_deleted,
                entities_failed: update.entities_failed,
              },
              lastUpdated: new Date(),
            });
          } else {
            // Update existing connection
            connections.set(update.source_connection_id, {
              ...existing,
              status: "in_progress",
              last_sync_job: {
                ...existing.last_sync_job,
                id: update.job_id,
                status: "in_progress",
                entities_inserted: update.entities_inserted,
                entities_updated: update.entities_updated,
                entities_deleted: update.entities_deleted,
                entities_failed: update.entities_failed,
              },
              lastUpdated: new Date(),
            });
          }

          // Track as active job
          const activeJobs = new Set(state.activeJobs);
          activeJobs.add(update.job_id);

          return { sourceConnections: connections, activeJobs };
        });
      },

      updateFromComplete: (update) => {
        set((state) => {
          const connections = new Map(state.sourceConnections);
          const existing = connections.get(update.source_connection_id);

          if (existing) {
            // Determine connection status based on job status
            let connectionStatus: SourceConnectionState["status"] = "active";
            if (update.status === "failed") {
              connectionStatus = "failing";
            }

            connections.set(update.source_connection_id, {
              ...existing,
              status: connectionStatus,
              last_sync_job: {
                id: update.job_id,
                status: update.status,
                duration_seconds: update.duration_seconds,
                entities_inserted: update.final_counts.entities_inserted,
                entities_updated: update.final_counts.entities_updated,
                entities_deleted: update.final_counts.entities_deleted,
                entities_failed: update.final_counts.entities_failed,
                error: update.error,
                completed_at: update.timestamp,
              },
              lastUpdated: new Date(),
            });
          }

          // Remove from active jobs
          const activeJobs = new Set(state.activeJobs);
          activeJobs.delete(update.job_id);

          return { sourceConnections: connections, activeJobs };
        });
      },

      clearConnection: (connectionId) => {
        set((state) => {
          const connections = new Map(state.sourceConnections);
          const connection = connections.get(connectionId);

          // Remove associated active job if exists
          const activeJobs = new Set(state.activeJobs);
          if (connection?.last_sync_job?.id) {
            activeJobs.delete(connection.last_sync_job.id);
          }

          connections.delete(connectionId);
          return { sourceConnections: connections, activeJobs };
        });
      },

      clearAll: () => {
        set({
          sourceConnections: new Map<string, SourceConnectionState>(),
          activeJobs: new Set<string>(),
        });
      },

      getConnection: (connectionId) => {
        return get().sourceConnections.get(connectionId);
      },

      getLastSyncJob: (connectionId) => {
        return get().sourceConnections.get(connectionId)?.last_sync_job;
      },

      isJobActive: (jobId) => {
        return get().activeJobs.has(jobId);
      },

      getActiveJobsCount: () => {
        return get().activeJobs.size;
      },
    }),
    {
      name: "entity-state",
      // Custom storage to handle Map serialization
      storage: {
        getItem: (name) => {
          const str = localStorage.getItem(name);
          if (!str) return null;

          const { state } = JSON.parse(str);
          return {
            state: {
              ...state,
              sourceConnections: new Map(state.sourceConnections || []),
              activeJobs: new Set(state.activeJobs || []),
            },
          };
        },
        setItem: (name, value) => {
          const { state } = value as {
            state: {
              sourceConnections: Map<string, SourceConnectionState>;
              activeJobs: Set<string>;
            };
          };
          localStorage.setItem(
            name,
            JSON.stringify({
              state: {
                ...state,
                sourceConnections: Array.from(
                  state.sourceConnections.entries()
                ),
                activeJobs: Array.from(state.activeJobs),
              },
            })
          );
        },
        removeItem: (name) => localStorage.removeItem(name),
      },
    }
  )
);

/** Hook for easy access to entity state */
export function useEntityState(connectionId: string) {
  const connection = useEntityStateStore((state) =>
    state.sourceConnections.get(connectionId)
  );
  const activeJobs = useEntityStateStore((state) => state.activeJobs);

  const lastSyncJob = connection?.last_sync_job;
  const isActive = lastSyncJob ? activeJobs.has(lastSyncJob.id) : false;

  return {
    connection,
    lastSyncJob,
    isActive,
    entityStates: connection?.entity_states,
  };
}
