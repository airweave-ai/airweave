/**
 * Entity State Mediator
 *
 * Coordinates real-time sync state between:
 * - Local UI state (entityStateStore)
 * - SSE subscriptions (syncStateStore)
 * - Backend API (source-connections)
 *
 * Usage:
 *   const mediator = new EntityStateMediator(connectionId);
 *   const state = await mediator.initialize(token, orgId);
 *   // Later, when sync starts:
 *   await mediator.subscribeToJobUpdates(jobId, token, orgId);
 *   // On cleanup:
 *   await mediator.cleanup();
 */

import { API_BASE_URL, getAuthHeaders } from "@/lib/api/client";
import {
  useEntityStateStore,
  type SourceConnectionState,
  type SyncProgressMessage,
  type SyncJobStatus,
} from "@/stores/entity-state-store";
import { useSyncStateStore } from "@/stores/sync-state-store";

export class EntityStateMediator {
  private connectionId: string;
  private currentJobId?: string;
  private stateStore = useEntityStateStore.getState();
  private syncStore = useSyncStateStore.getState();

  constructor(connectionId: string) {
    this.connectionId = connectionId;
  }

  /**
   * Initialize the mediator - fetches latest state and subscribes if needed.
   * Returns local state immediately if available, fetches DB state in background.
   */
  async initialize(
    token: string,
    organizationId: string
  ): Promise<SourceConnectionState | undefined> {
    // RULE 1: Show local state instantly if available
    const localState = this.stateStore.getConnection(this.connectionId);

    // RULE 2: ALWAYS fetch DB state in parallel (non-blocking)
    const dbFetchPromise = this.fetchDatabaseState(token, organizationId)
      .then((dbState) => {
        if (dbState) {
          // Update local store with DB truth
          this.stateStore.setSourceConnection(dbState);

          // RULE 3: If sync is active (pending/in_progress), subscribe to stream
          if (
            dbState.last_sync_job?.status === "in_progress" ||
            dbState.last_sync_job?.status === "pending"
          ) {
            const jobId = dbState.last_sync_job.id;
            if (jobId) {
              this.subscribeToUpdates(jobId, token, organizationId);
            }
          }
        }
        return dbState;
      })
      .catch((error) => {
        console.error("Failed to fetch database state:", error);
        return localState; // Fallback to local if DB fails
      });

    // If we have local state, return it immediately
    if (localState) {
      // DB fetch happens in background (fire and forget)
      void dbFetchPromise;
      return localState;
    }

    // No local state - must wait for DB
    return await dbFetchPromise;
  }

  /**
   * Fetch the current state from the database
   */
  private async fetchDatabaseState(
    token: string,
    organizationId: string
  ): Promise<SourceConnectionState | undefined> {
    try {
      const response = await fetch(
        `${API_BASE_URL}/source-connections/${this.connectionId}`,
        {
          headers: getAuthHeaders(token, organizationId),
        }
      );

      if (!response.ok) {
        console.error("Failed to fetch source connection:", response.status);
        return undefined;
      }

      const connection = await response.json();

      // Convert backend response to our store format
      const state: SourceConnectionState = {
        id: connection.id,
        name: connection.name,
        short_name: connection.short_name,
        collection: connection.readable_collection_id,
        status: connection.status || "active",
        is_authenticated: connection.auth?.authenticated ?? true,
        last_sync_job: connection.sync?.last_job || connection.last_sync_job,
        schedule: connection.schedule,
        entity_states: connection.entities
          ? Object.entries(
              (connection.entities.by_type as Record<
                string,
                { count: number; last_updated?: string; sync_status?: string }
              >) || {}
            ).map(([type, stats]) => ({
              entity_type: type,
              total_count: stats.count,
              last_updated_at: stats.last_updated,
              sync_status: (stats.sync_status || "synced") as
                | "pending"
                | "syncing"
                | "synced"
                | "failed",
            }))
          : [],
        lastUpdated: new Date(),
      };

      return state;
    } catch (error) {
      console.error("Error fetching database state:", error);
      return undefined;
    }
  }

  /**
   * Internal method to subscribe to sync updates
   */
  private async subscribeToUpdates(
    jobId: string,
    token: string,
    organizationId: string
  ): Promise<void> {
    // Prevent duplicate subscriptions
    if (
      this.currentJobId === jobId &&
      this.syncStore.hasActiveSubscription(this.connectionId)
    ) {
      return;
    }

    // Clean up any existing subscription
    if (this.syncStore.hasActiveSubscription(this.connectionId)) {
      this.syncStore.unsubscribe(this.connectionId);
    }

    this.currentJobId = jobId;

    // Subscribe to the stream for real-time updates via entity state endpoint
    await this.subscribeToEntityState(jobId, token, organizationId);
  }

  /**
   * Public method called when a new sync is triggered
   */
  async subscribeToJobUpdates(
    jobId: string,
    token: string,
    organizationId: string
  ): Promise<void> {
    // Immediately update state to show sync is starting
    const currentState = this.stateStore.getConnection(this.connectionId);

    if (currentState) {
      // Update the existing state to show sync is starting
      const updatedState: SourceConnectionState = {
        ...currentState,
        status: "in_progress",
        last_sync_job: {
          id: jobId,
          status: "pending",
          entities_inserted: 0,
          entities_updated: 0,
          entities_deleted: 0,
          entities_failed: 0,
        },
        lastUpdated: new Date(),
      };

      this.stateStore.setSourceConnection(updatedState);
    }

    // Subscribe to stream updates
    await this.subscribeToUpdates(jobId, token, organizationId);
  }

  /**
   * Subscribe to entity state updates via SSE
   */
  private async subscribeToEntityState(
    jobId: string,
    token: string,
    organizationId: string
  ): Promise<void> {
    const controller = new AbortController();

    try {
      const response = await fetch(
        `${API_BASE_URL}/sync/job/${jobId}/subscribe-state`,
        {
          headers: getAuthHeaders(token, organizationId),
          signal: controller.signal,
        }
      );

      if (!response.ok || !response.body) {
        console.error(
          "Failed to connect to entity state SSE:",
          response.status
        );
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";

        for (const frame of frames) {
          const dataLines = frame
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.slice(5).trim());

          if (dataLines.length === 0) continue;

          const payloadStr = dataLines.join("\n");
          let data: Record<string, unknown>;
          try {
            data = JSON.parse(payloadStr);
          } catch {
            continue;
          }

          if (data.type === "entity_state") {
            console.debug("[EntityStateMediator] Entity state update:", data);

            const currentConnection = this.stateStore.getConnection(
              this.connectionId
            );
            if (currentConnection) {
              // Convert entity_counts map to entity_states array format
              const entityCounts = (data.entity_counts || {}) as Record<
                string,
                number
              >;
              const entityStates = Object.entries(entityCounts).map(
                ([entityType, count]) => ({
                  entity_type: entityType + "Entity",
                  total_count: count,
                  last_updated_at:
                    (data.timestamp as string) || new Date().toISOString(),
                  sync_status: "syncing" as const,
                })
              );

              // Update the connection with new entity states
              const updatedConnection: SourceConnectionState = {
                ...currentConnection,
                entity_states: entityStates,
                last_sync_job: {
                  ...currentConnection.last_sync_job,
                  id: jobId,
                  status: "in_progress",
                  entities_inserted:
                    currentConnection.last_sync_job?.entities_inserted ?? 0,
                  entities_updated:
                    currentConnection.last_sync_job?.entities_updated ?? 0,
                  entities_deleted:
                    currentConnection.last_sync_job?.entities_deleted ?? 0,
                  entities_failed:
                    currentConnection.last_sync_job?.entities_failed ?? 0,
                },
                lastUpdated: new Date(),
              };

              this.stateStore.setSourceConnection(updatedConnection);
            }
          } else if (data.type === "sync_progress") {
            // Handle regular sync progress updates
            const progressUpdate: SyncProgressMessage =
              data as unknown as SyncProgressMessage;
            this.stateStore.updateFromProgress(progressUpdate);
          } else if (data.type === "sync_complete") {
            console.debug("[EntityStateMediator] Sync complete:", data);

            const currentConnection = this.stateStore.getConnection(
              this.connectionId
            );
            if (currentConnection) {
              // Convert final_counts to entity_states array
              const finalCounts = (data.final_counts || {}) as Record<
                string,
                number
              >;
              const finalEntityStates = Object.entries(finalCounts).map(
                ([entityType, count]) => ({
                  entity_type: entityType + "Entity",
                  total_count: count,
                  last_updated_at:
                    (data.timestamp as string) || new Date().toISOString(),
                  sync_status: "synced" as const,
                })
              );

              // Update connection with final state
              const finalStatus = ((data.final_status as string) ||
                (data.is_failed ? "failed" : "completed")) as SyncJobStatus;
              const updatedConnection: SourceConnectionState = {
                ...currentConnection,
                entity_states: finalEntityStates,
                status: data.is_failed ? "failing" : "active",
                last_sync_job: {
                  id: jobId,
                  status: finalStatus,
                  completed_at:
                    (data.timestamp as string) || new Date().toISOString(),
                  error: data.error as string | undefined,
                  entities_inserted:
                    currentConnection.last_sync_job?.entities_inserted ?? 0,
                  entities_updated:
                    currentConnection.last_sync_job?.entities_updated ?? 0,
                  entities_deleted:
                    currentConnection.last_sync_job?.entities_deleted ?? 0,
                  entities_failed:
                    currentConnection.last_sync_job?.entities_failed ?? 0,
                },
                lastUpdated: new Date(),
              };

              this.stateStore.setSourceConnection(updatedConnection);
            }

            // Close the SSE connection
            controller.abort();

            // Fetch DB state after a short delay to ensure it's updated
            setTimeout(() => {
              this.fetchDatabaseState(token, organizationId)
                .then((dbState) => {
                  if (dbState) {
                    this.stateStore.setSourceConnection(dbState);
                  }
                })
                .catch(() => {
                  // Silent fail - we already have the stream data
                });
            }, 1000);
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        console.error("[EntityStateMediator] SSE error:", error);
      }
    }
  }

  /**
   * Clean up all subscriptions and resources
   */
  async cleanup(): Promise<void> {
    if (this.syncStore.hasActiveSubscription(this.connectionId)) {
      this.syncStore.unsubscribe(this.connectionId);
    }
    this.currentJobId = undefined;
  }
}

/**
 * Hook for using the mediator in React components.
 * Creates a mediator instance for a source connection and handles cleanup.
 */
export function useEntityStateMediator(connectionId: string) {
  return new EntityStateMediator(connectionId);
}
