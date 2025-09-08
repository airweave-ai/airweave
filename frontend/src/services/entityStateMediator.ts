// services/entityStateMediator.ts
import { apiClient } from '@/lib/api';
import { useEntityStateStore, EntityState, EntityStateUpdate, SyncCompleteMessage, SyncStatus } from '@/stores/entityStateStore';
import { useSyncStateStore } from '@/stores/syncStateStore';

export class EntityStateMediator {
  private connectionId: string;
  private syncId?: string;
  private currentJobId?: string;
  private stateStore = useEntityStateStore.getState();
  private syncStore = useSyncStateStore.getState();
  private eventSource?: AbortController;

  constructor(connectionId: string) {
    this.connectionId = connectionId;
  }

  async initialize(): Promise<EntityState> {
    // RULE 1: Show local state instantly if available
    const localState = this.stateStore.getEntityState(this.connectionId);

    // Use local state if available

    // RULE 2: ALWAYS fetch DB state in parallel (non-blocking)
    const dbFetchPromise = this.fetchDatabaseState()
      .then(dbState => {
        // Update local store with DB truth
        this.stateStore.setEntityState(this.connectionId, dbState);

        // RULE 3: If sync is active (pending/in_progress), subscribe to stream
        if ((dbState.syncStatus === 'in_progress' || dbState.syncStatus === 'pending') && dbState.currentJobId) {
          this.subscribeToUpdates(dbState.currentJobId);
        }

        return dbState;
      })
      .catch(error => {
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

  private async fetchDatabaseState(): Promise<EntityState> {
    // Fetch source connection details
    const connectionResponse = await apiClient.get(
      `/source-connections/${this.connectionId}`
    );
    const connection = await connectionResponse.json();

    this.syncId = connection.sync_id;

    // Fetch entity counts if sync exists
    let entityCounts: Record<string, number> = {};
    let syncStatus: SyncStatus = 'completed';  // Default to completed if no active sync
    let currentJobId: string | undefined;

    if (this.syncId) {
      // Fetch entity counts
      const countsResponse = await apiClient.get(
        `/entity-counts/syncs/${this.syncId}/counts`
      );

      if (countsResponse.ok) {
        const counts = await countsResponse.json();
        entityCounts = counts.reduce((acc: Record<string, number>, count: any) => {
          const name = count.entity_definition_name
            .replace('Entity', '')
            .trim();
          acc[name] = count.count;
          return acc;
        }, {});
      }
    }

    // Map backend status directly - no translation needed anymore

    // Map backend status directly - no translation needed anymore
    switch (connection.latest_sync_job_status) {
      case 'created':
      case 'pending':
        syncStatus = 'pending';
        currentJobId = connection.latest_sync_job_id;
        break;
      case 'in_progress':
        syncStatus = 'in_progress';
        currentJobId = connection.latest_sync_job_id;
        break;
      case 'failed':
        syncStatus = 'failed';
        break;
      case 'completed':
        syncStatus = 'completed';
        break;
      case 'cancelled':
        syncStatus = 'cancelled';
        break;
      default:
        // No sync job or unknown status - check if we have a job ID
        // This handles the case where a new sync was just started
        if (connection.latest_sync_job_id && !connection.latest_sync_job_status) {
          syncStatus = 'pending';
          currentJobId = connection.latest_sync_job_id;
        } else {
          syncStatus = 'completed';  // Default to completed if no active sync
        }
    }

    return {
      connectionId: this.connectionId,
      syncId: this.syncId,
      entityCounts,
      totalEntities: Object.values(entityCounts).reduce((a, b) => a + b, 0),
      syncStatus,
      currentJobId,
      lastUpdated: new Date(),
      error: connection.latest_sync_job_error
    };
  }

  private async subscribeToUpdates(jobId: string): Promise<void> {
    // Prevent duplicate subscriptions
    if (this.currentJobId === jobId && this.eventSource) {
      return;
    }

    // Clean up any existing subscription
    if (this.eventSource) {
      this.eventSource.abort();
    }

    this.currentJobId = jobId;

    // Subscribe to the stream for real-time updates
    await this.subscribeToEntityState(
      jobId,
      this.connectionId,
      (update: EntityStateUpdate) => {
        // Stream updates are authoritative during sync
        this.stateStore.updateFromStream(this.connectionId, update);
      }
    );
  }

  async subscribeToJobUpdates(jobId: string): Promise<void> {
    // Public method called when a new sync is triggered
    // Immediately update state to show sync is starting
    const currentState = this.stateStore.getEntityState(this.connectionId);

    // For a brand new source connection, we might not have a syncId yet
    // The syncId will be created by the backend when the sync starts
    const stateToSet: EntityState = {
      connectionId: this.connectionId,
      syncId: currentState?.syncId || this.syncId, // Use existing or current syncId
      entityCounts: currentState?.entityCounts || {},
      totalEntities: currentState?.totalEntities || 0,
      syncStatus: 'pending',
      currentJobId: jobId,
      lastUpdated: new Date()
    };

    this.stateStore.setEntityState(this.connectionId, stateToSet);

    // Subscribe to stream updates
    await this.subscribeToUpdates(jobId);
  }

  private async subscribeToEntityState(
    jobId: string,
    sourceConnectionId: string,
    onUpdate: (state: EntityStateUpdate) => void
  ): Promise<void> {
    // Use fetchEventSource from Microsoft's library which supports headers
    const { fetchEventSource } = await import('@microsoft/fetch-event-source');
    const controller = new AbortController();
    this.eventSource = controller;
    const sseUrl = `${import.meta.env.VITE_API_URL}/sync/job/${jobId}/subscribe-state`;

    try {
      await fetchEventSource(sseUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${await apiClient.getToken()}`,
        },
        signal: controller.signal,

        onmessage: (msg: any) => {
          const data = JSON.parse(msg.data);

          if (data.type === 'entity_state') {
            const update = data as EntityStateUpdate;

            // Always call onUpdate to update counts
            onUpdate(update);

            // Additionally, handle state transition from pending to running
            const currentState = this.stateStore.getEntityState(this.connectionId);
            if (currentState?.syncStatus === 'pending') {
              // The updateFromStream in the store will handle the transition
              // We just need to ensure the status changes
              this.stateStore.setEntityState(this.connectionId, {
                ...currentState,
                syncStatus: 'in_progress',
                lastUpdated: new Date()
              });
            }
          } else if (data.type === 'sync_complete') {
            const completeMsg = data as SyncCompleteMessage;

            console.log('[EntityStateMediator] Sync completion message received:', {
              is_failed: completeMsg.is_failed,
              final_status: completeMsg.final_status,
              error: completeMsg.error,
              final_counts: completeMsg.final_counts
            });

            // IMMEDIATELY update status to reflect completion
            const currentState = this.stateStore.getEntityState(this.connectionId);
            if (currentState) {
              // Use the final_status from backend (completed/failed)
              const finalStatus = completeMsg.final_status || (completeMsg.is_failed ? 'failed' : 'completed');
              const finalCounts = completeMsg.final_counts || currentState.entityCounts;
              const finalTotal = completeMsg.total_entities ?? currentState.totalEntities;
              const errorMessage = completeMsg.error || (completeMsg.is_failed ? 'Sync failed' : undefined);

              console.log('[EntityStateMediator] Updating state with:', {
                finalStatus,
                errorMessage,
                isSyncing: false
              });

              this.stateStore.setEntityState(this.connectionId, {
                ...currentState,
                entityCounts: finalCounts,
                totalEntities: finalTotal,
                syncStatus: finalStatus,
                currentJobId: undefined, // Clear job ID
                lastUpdated: new Date(),
                error: errorMessage
              });
            }

            // Close the SSE connection
            controller.abort();
            this.eventSource = undefined;

            // Fetch DB state after a short delay to ensure it's updated
            setTimeout(() => {
              this.fetchDatabaseState().then(dbState => {
                const current = this.stateStore.getEntityState(this.connectionId);
                if (current && dbState.totalEntities !== current.totalEntities) {
                  this.stateStore.setEntityState(this.connectionId, dbState);
                }
              }).catch(error => {
                // Silent fail - we already have the stream data
              });
            }, 1000);
          }
        },

        onerror: (err) => {
          // Don't retry on error - let it fail gracefully
          throw err;
        }
      });
    } catch (error) {
      // Silent fail - subscription errors are non-critical
    }
  }



  async cleanup(): Promise<void> {
    if (this.eventSource) {
      this.eventSource.abort();
      this.eventSource = undefined;
    }
    if (this.currentJobId) {
      this.syncStore.unsubscribe(this.connectionId);
    }
  }
}
