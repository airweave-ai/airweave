import { apiClient } from '@/lib/api';
import { useEntityStateStore, SourceConnectionState, SyncProgressUpdate, SyncCompleteUpdate } from '@/stores/entityStateStore';
import { useSyncStateStore } from '@/stores/syncStateStore';

export class EntityStateMediator {
  private connectionId: string;
  private currentJobId?: string;
  private stateStore = useEntityStateStore.getState();
  private syncStore = useSyncStateStore.getState();
  private eventSource?: AbortController;

  constructor(connectionId: string) {
    this.connectionId = connectionId;
  }

  async initialize(): Promise<SourceConnectionState | undefined> {
    // RULE 1: Show local state instantly if available
    const localState = this.stateStore.getConnection(this.connectionId);

    // RULE 2: ALWAYS fetch DB state in parallel (non-blocking)
    const dbFetchPromise = this.fetchDatabaseState()
      .then(dbState => {
        if (dbState) {
          // Update local store with DB truth
          this.stateStore.setSourceConnection(dbState);

          // RULE 3: If sync is active (pending/in_progress), subscribe to stream
          if (dbState.last_sync_job?.status === 'in_progress' || dbState.last_sync_job?.status === 'pending') {
            const jobId = dbState.last_sync_job.id;
            if (jobId) {
              this.subscribeToUpdates(jobId);
            }
          }
        }
        return dbState;
      })
      .catch(error => {
        console.error('Failed to fetch database state:', error);
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

  private async fetchCompleteSyncJobData(jobId: string): Promise<void> {
    try {
      // Get the source connection ID from the current connection
      const currentConnection = this.stateStore.getConnection(this.connectionId);
      if (!currentConnection) {
        return;
      }

      // Fetch the complete sync job data from the API
      const response = await apiClient.get(`/source-connections/${this.connectionId}/jobs/${jobId}`);
      if (response.ok) {
        const jobData = await response.json();

        // Update the connection with the complete job data
        const updatedConnection = {
          ...currentConnection,
          last_sync_job: {
            ...currentConnection.last_sync_job,
            ...jobData,
            id: jobData.id,
            status: jobData.status,
            started_at: jobData.started_at,
            completed_at: jobData.completed_at,
            entities_inserted: jobData.entities_inserted || 0,
            entities_updated: jobData.entities_updated || 0,
            entities_deleted: jobData.entities_deleted || 0,
            duration_seconds: jobData.duration_seconds,
            error: jobData.error
          },
          lastUpdated: new Date()
        };

        this.stateStore.setSourceConnection(updatedConnection);
      }
    } catch (error) {
      console.error('[EntityStateMediator] Error fetching complete sync job data:', error);
    }
  }

  private async fetchDatabaseState(): Promise<SourceConnectionState | undefined> {
    try {
      // Fetch source connection details with entity_states included
      const connectionResponse = await apiClient.get(
        `/source-connections/${this.connectionId}`
      );

      if (!connectionResponse.ok) {
        console.error('Failed to fetch source connection:', connectionResponse.status);
        return undefined;
      }

      const connection = await connectionResponse.json();

      // Convert backend response to our store format
      const state: SourceConnectionState = {
        id: connection.id,
        name: connection.name,
        short_name: connection.short_name,
        collection: connection.readable_collection_id,  // Changed from connection.collection
        status: connection.status || 'active',
        is_authenticated: connection.auth?.authenticated ?? true,  // Changed from connection.is_authenticated
        last_sync_job: connection.sync?.last_job || connection.last_sync_job,  // Try new structure first
        schedule: connection.schedule,
        entity_states: connection.entities ?  // Convert entities object to entity_states array
          Object.entries(connection.entities.by_type || {}).map(([type, stats]: [string, any]) => ({
            entity_type: type,
            total_count: stats.count,
            last_updated_at: stats.last_updated,
            sync_status: stats.sync_status
          })) : [],
        lastUpdated: new Date()
      };

      return state;
    } catch (error) {
      console.error('Error fetching database state:', error);
      return undefined;
    }
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
      (update: SyncProgressUpdate) => {
        // Progress updates are handled by the store
        // The store will update the connection state
      }
    );
  }

  async subscribeToJobUpdates(jobId: string): Promise<void> {
    // Public method called when a new sync is triggered
    // Immediately update state to show sync is starting
    const currentState = this.stateStore.getConnection(this.connectionId);

    if (currentState) {
      // Update the existing state to show sync is starting
      const updatedState: SourceConnectionState = {
        ...currentState,
        status: 'in_progress',
        last_sync_job: {
          id: jobId,
          status: 'pending',
          entities_inserted: 0,
          entities_updated: 0,
          entities_deleted: 0,
          entities_failed: 0
        },
        lastUpdated: new Date()
      };

      this.stateStore.setSourceConnection(updatedState);
    }

    // Subscribe to stream updates
    await this.subscribeToUpdates(jobId);
  }

  private async subscribeToEntityState(
    jobId: string,
    sourceConnectionId: string,
    onUpdate: (update: SyncProgressUpdate) => void
  ): Promise<void> {
    // Use apiClient.sse so headers/baseURL/token-refresh are consistent
    const controller = new AbortController();
    this.eventSource = controller;

    try {
      await apiClient.sse(
        `/sync/job/${jobId}/subscribe-state`,
        {
          onMessage: (msg: MessageEvent) => {
            const data = JSON.parse((msg as any).data);

            if (data.type === 'entity_state') {
              // Handle entity state updates from backend
              // The backend sends entity_counts as a map of entity_type -> count

              // Update the store's entity_states array
              const currentConnection = this.stateStore.getConnection(this.connectionId);
              if (currentConnection) {
                // Convert entity_counts map to entity_states array format
                const entityStates = Object.entries(data.entity_counts || {}).map(([entityType, count]) => ({
                  entity_type: entityType + 'Entity',  // Add Entity suffix back for consistency
                  total_count: count as number,
                  last_updated_at: data.timestamp || new Date().toISOString(),
                  sync_status: 'syncing' as const
                }));

                // Update the connection with new entity states
                const updatedConnection = {
                  ...currentConnection,
                  entity_states: entityStates,
                  last_sync_job: {
                    ...currentConnection.last_sync_job,
                    status: 'in_progress' as const
                  },
                  lastUpdated: new Date()
                };

                this.stateStore.setSourceConnection(updatedConnection);
              }
            } else if (data.type === 'sync_progress') {
              // Handle regular sync progress updates if any
              const progressUpdate: SyncProgressUpdate = data as SyncProgressUpdate;
              this.stateStore.updateFromProgress(progressUpdate);
            } else if (data.type === 'sync_complete') {
              // Update the store with final entity states
              const currentConnection = this.stateStore.getConnection(this.connectionId);
              if (currentConnection) {
                // Convert final_counts to entity_states array
                const finalEntityStates = Object.entries(data.final_counts || {}).map(([entityType, count]) => ({
                  entity_type: entityType + 'Entity',  // Add Entity suffix back
                  total_count: count as number,
                  last_updated_at: data.timestamp || new Date().toISOString(),
                  sync_status: 'synced' as const
                }));

                // Update connection with final state
                const updatedConnection = {
                  ...currentConnection,
                  entity_states: finalEntityStates,
                  status: data.is_failed ? 'failing' : 'active' as any,
                  last_sync_job: {
                    ...currentConnection.last_sync_job,
                    status: data.final_status || (data.is_failed ? 'failed' : 'completed'),
                    completed_at: data.timestamp || new Date().toISOString(),
                    error: data.error
                  },
                  lastUpdated: new Date()
                };

                this.stateStore.setSourceConnection(updatedConnection);
              }

              // Close the SSE connection
              controller.abort();
              this.eventSource = undefined;

              // Fetch complete sync job data from API to get detailed statistics
              this.fetchCompleteSyncJobData(data.job_id).catch(error => {
                console.error('[EntityStateMediator] Error fetching complete sync job data:', error);
              });

              // Fetch DB state after a short delay to ensure it's updated
              setTimeout(() => {
                this.fetchDatabaseState().then(dbState => {
                  if (dbState) {
                    // Just update with the new state from backend
                    this.stateStore.setSourceConnection(dbState);
                  }
                }).catch(error => {
                  // Silent fail - we already have the stream data
                });
              }, 1000);
            }
          },
          onError: (err) => {
            // Don't retry on error here - let it fail gracefully
          }
        },
        { signal: controller.signal }
      );
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
