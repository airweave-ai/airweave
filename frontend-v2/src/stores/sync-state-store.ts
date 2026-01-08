/**
 * Sync state store for managing real-time SSE subscriptions to sync jobs.
 * Provides persistence across page reloads and health checks for stale subscriptions.
 */

import { create } from "zustand";

import { API_BASE_URL, getAuthHeaders } from "@/lib/api/client";
import { syncStorageService } from "@/services/syncStorageService";

/** Types for sync progress updates */
export interface SyncProgressUpdate {
  entities_inserted: number;
  entities_updated: number;
  entities_deleted: number;
  entities_kept: number;
  entities_skipped: number;
  entities_encountered: Record<string, number>;
  is_complete?: boolean;
  is_failed?: boolean;
  error?: string;
  started_at?: string;
}

/** Individual subscription tracking */
export interface SyncSubscription {
  jobId: string;
  sourceConnectionId: string;
  controller: AbortController;
  lastUpdate: SyncProgressUpdate;
  lastMessageTime: number;
  status: "active" | "completed" | "failed";
}

/** Store interface */
interface SyncStateStore {
  // Map of sourceConnectionId -> SyncSubscription
  activeSubscriptions: Map<string, SyncSubscription>;

  // Subscribe to a sync job
  subscribe: (
    jobId: string,
    sourceConnectionId: string,
    token: string,
    organizationId: string
  ) => Promise<void>;

  // Unsubscribe from a sync job
  unsubscribe: (sourceConnectionId: string) => void;

  // Update progress for a source connection
  updateProgress: (
    sourceConnectionId: string,
    update: SyncProgressUpdate
  ) => void;

  // Get current progress for a source connection
  getProgressForSource: (
    sourceConnectionId: string
  ) => SyncProgressUpdate | null;

  // Check if a source has an active subscription
  hasActiveSubscription: (sourceConnectionId: string) => boolean;

  // Restore progress from storage (for page reloads)
  restoreProgressFromStorage: (
    sourceConnectionId: string,
    jobId: string
  ) => void;

  // Clean up all subscriptions
  cleanup: (clearStorage?: boolean) => void;

  // Health check management
  startHealthCheck: () => void;
  stopHealthCheck: () => void;
}

// Keep track of the health check interval ID outside the store
let healthCheckIntervalId: ReturnType<typeof setInterval> | null = null;

/** Parse SSE event data from stream chunk */
function parseSSEEvent(chunk: string): Record<string, unknown> | null {
  const dataLines = chunk
    .split("\n")
    .filter((l) => l.startsWith("data:"))
    .map((l) => l.slice(5).trim());

  if (dataLines.length === 0) return null;

  const payloadStr = dataLines.join("\n");
  try {
    return JSON.parse(payloadStr);
  } catch {
    return null;
  }
}

/** Create the store */
export const useSyncStateStore = create<SyncStateStore>((set, get) => ({
  activeSubscriptions: new Map(),

  subscribe: async (
    jobId: string,
    sourceConnectionId: string,
    token: string,
    organizationId: string
  ) => {
    const state = get();

    // Start health check if it's the first subscription
    if (state.activeSubscriptions.size === 0) {
      state.startHealthCheck();
    }

    // Don't create duplicate subscriptions
    if (state.activeSubscriptions.has(sourceConnectionId)) {
      console.debug(`Already subscribed to ${sourceConnectionId}`);
      return;
    }

    if (!token) {
      console.error(
        "Cannot subscribe to SSE: No authentication token available."
      );
      return;
    }

    if (!organizationId) {
      console.error(
        "Cannot subscribe to SSE: No active organization selected."
      );
      return;
    }

    const controller = new AbortController();

    // Check for existing progress data to preserve during subscription
    const existingSubscription =
      state.activeSubscriptions.get(sourceConnectionId);
    const storedData =
      syncStorageService.getProgressForSource(sourceConnectionId);

    // Determine what progress data to use (priority: existing > stored > default zeros)
    let lastUpdate: SyncProgressUpdate;
    if (existingSubscription && existingSubscription.jobId === jobId) {
      // Same job, preserve existing progress
      lastUpdate = existingSubscription.lastUpdate;
      console.debug(
        `Preserving existing progress for ${sourceConnectionId}:`,
        lastUpdate
      );
    } else if (
      storedData &&
      storedData.jobId === jobId &&
      storedData.status === "active"
    ) {
      // Different job or fresh subscription, but we have stored data for this job
      lastUpdate = storedData.lastUpdate;
      console.debug(
        `Using stored progress for ${sourceConnectionId}:`,
        lastUpdate
      );
    } else {
      // No existing data, start fresh
      lastUpdate = {
        entities_inserted: 0,
        entities_updated: 0,
        entities_deleted: 0,
        entities_kept: 0,
        entities_skipped: 0,
        entities_encountered: {},
      };
      console.debug(`Starting fresh progress for ${sourceConnectionId}`);
    }

    // Create and add the subscription to the store *before* connecting
    const subscription: SyncSubscription = {
      jobId,
      sourceConnectionId,
      controller,
      lastUpdate,
      lastMessageTime: Date.now(),
      status: "active",
    };

    const newSubscriptions = new Map(state.activeSubscriptions);
    newSubscriptions.set(sourceConnectionId, subscription);
    set({ activeSubscriptions: newSubscriptions });

    // Start the SSE connection
    const sseUrl = `${API_BASE_URL}/sync/job/${jobId}/subscribe`;

    console.debug(`Starting SSE subscription:`, {
      url: sseUrl,
      jobId,
      sourceConnectionId,
      hasToken: !!token,
      organizationId,
    });

    // Fire and forget - run in background
    void (async () => {
      try {
        const response = await fetch(sseUrl, {
          headers: getAuthHeaders(token, organizationId),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorText = await response.text().catch(() => "");
          console.error(`SSE connection failed:`, {
            status: response.status,
            statusText: response.statusText,
            errorText,
            url: sseUrl,
          });
          get().unsubscribe(sourceConnectionId);
          return;
        }

        if (!response.body) {
          console.error("SSE response has no body");
          get().unsubscribe(sourceConnectionId);
          return;
        }

        console.debug(`SSE connection opened for ${sourceConnectionId}`);

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
            const data = parseSSEEvent(frame);
            if (!data) continue;

            console.debug(`SSE message for ${sourceConnectionId}:`, data);

            // Skip non-progress messages
            if (data.type === "connected") {
              console.debug(`Connection established for ${sourceConnectionId}`);
              continue;
            }

            // Map the incoming data to our expected interface
            // Backend sends: {inserted, updated, deleted, kept, skipped}
            // We expect: {entities_inserted, entities_updated, etc.}
            const mappedData: SyncProgressUpdate = {
              entities_inserted: (data.inserted as number) ?? 0,
              entities_updated: (data.updated as number) ?? 0,
              entities_deleted: (data.deleted as number) ?? 0,
              entities_kept: (data.kept as number) ?? 0,
              entities_skipped: (data.skipped as number) ?? 0,
              entities_encountered:
                (data.entities_encountered as Record<string, number>) || {},
              is_complete: data.is_complete as boolean | undefined,
              is_failed: data.is_failed as boolean | undefined,
              error: data.error as string | undefined,
            };

            // Update progress with mapped data
            get().updateProgress(sourceConnectionId, mappedData);

            // Handle completion
            if (data.is_complete || data.is_failed) {
              console.debug(
                `Sync ${data.is_complete ? "completed" : "failed"} for ${sourceConnectionId}`
              );

              // Wait a bit for final DB write, then switch to completed status
              setTimeout(() => {
                const sub = get().activeSubscriptions.get(sourceConnectionId);
                if (sub) {
                  sub.status = data.is_complete ? "completed" : "failed";
                  set({
                    activeSubscriptions: new Map(get().activeSubscriptions),
                  });
                }

                // Unsubscribe after another delay
                setTimeout(() => {
                  get().unsubscribe(sourceConnectionId);
                }, 2000);
              }, 2000);
            }
          }
        }

        console.debug(`SSE connection closed for ${sourceConnectionId}`);
      } catch (error) {
        if ((error as Error).name === "AbortError") {
          console.debug(`SSE subscription aborted for ${sourceConnectionId}`);
        } else {
          console.error(`SSE error for ${sourceConnectionId}:`, error);
          get().unsubscribe(sourceConnectionId);
        }
      }
    })();
  },

  unsubscribe: (sourceConnectionId: string) => {
    const state = get();
    const subscription = state.activeSubscriptions.get(sourceConnectionId);

    if (!subscription) {
      return;
    }

    // Close the EventSource connection
    subscription.controller.abort();

    // Remove from active subscriptions
    const newSubscriptions = new Map(state.activeSubscriptions);
    newSubscriptions.delete(sourceConnectionId);
    set({ activeSubscriptions: newSubscriptions });

    // If it was the last subscription, stop the health check
    if (newSubscriptions.size === 0) {
      get().stopHealthCheck();
    }

    syncStorageService.removeProgress(sourceConnectionId);
    console.debug(`Unsubscribed from ${sourceConnectionId}`);
  },

  updateProgress: (sourceConnectionId: string, update: SyncProgressUpdate) => {
    const state = get();
    const subscription = state.activeSubscriptions.get(sourceConnectionId);

    if (!subscription) {
      console.warn(`No subscription found for ${sourceConnectionId}`);
      return;
    }

    console.debug("Updating progress for", sourceConnectionId, update);

    // Update the subscription
    subscription.lastUpdate = update;
    subscription.lastMessageTime = Date.now();

    // Update the map to trigger re-render
    const newSubscriptions = new Map(state.activeSubscriptions);
    newSubscriptions.set(sourceConnectionId, { ...subscription });
    set({ activeSubscriptions: newSubscriptions });

    syncStorageService.saveProgress(
      sourceConnectionId,
      subscription.jobId,
      update
    );
  },

  getProgressForSource: (sourceConnectionId: string) => {
    const subscription = get().activeSubscriptions.get(sourceConnectionId);
    return subscription?.lastUpdate || null;
  },

  hasActiveSubscription: (sourceConnectionId: string) => {
    const subscription = get().activeSubscriptions.get(sourceConnectionId);
    return subscription?.status === "active";
  },

  restoreProgressFromStorage: (sourceConnectionId: string, jobId: string) => {
    const storedData =
      syncStorageService.getProgressForSource(sourceConnectionId);

    if (
      storedData &&
      storedData.jobId === jobId &&
      storedData.status === "active"
    ) {
      console.debug(
        `Restoring progress for ${sourceConnectionId}:`,
        storedData
      );

      // Create a "restored" subscription with the saved progress
      const subscription: SyncSubscription = {
        jobId,
        sourceConnectionId,
        controller: new AbortController(), // Placeholder, will be replaced by subscribe
        lastUpdate: storedData.lastUpdate,
        lastMessageTime: storedData.timestamp,
        status: "active",
      };

      const newSubscriptions = new Map(get().activeSubscriptions);
      newSubscriptions.set(sourceConnectionId, subscription);
      set({ activeSubscriptions: newSubscriptions });
    }
  },

  cleanup: (clearStorage: boolean = false) => {
    const state = get();

    // Close all EventSource connections
    state.activeSubscriptions.forEach((subscription) => {
      subscription.controller.abort();
    });

    // Clear the map
    set({ activeSubscriptions: new Map() });
    get().stopHealthCheck(); // Stop health checks

    if (clearStorage) {
      syncStorageService.clearAll();
    }
  },

  startHealthCheck: () => {
    if (healthCheckIntervalId) {
      return;
    }
    healthCheckIntervalId = setInterval(
      () => {
        const store = useSyncStateStore.getState();
        const now = Date.now();
        const staleThreshold = 60 * 60 * 1000; // 1 hour

        store.activeSubscriptions.forEach(
          (subscription, sourceConnectionId) => {
            if (
              subscription.status === "active" &&
              now - subscription.lastMessageTime > staleThreshold
            ) {
              console.warn(
                `No messages for ${sourceConnectionId} in 1 hour, cleaning up`
              );
              store.unsubscribe(sourceConnectionId);
            }
          }
        );
      },
      5 * 60 * 1000
    ); // Check every 5 minutes
  },

  stopHealthCheck: () => {
    if (healthCheckIntervalId) {
      clearInterval(healthCheckIntervalId);
      healthCheckIntervalId = null;
    }
  },
}));

// Set up a listener to clean up when the user leaves the app
if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    useSyncStateStore.getState().cleanup();
  });
}

/** Hook for accessing sync progress for a specific source connection */
export function useSyncProgress(sourceConnectionId: string) {
  const subscription = useSyncStateStore((state) =>
    state.activeSubscriptions.get(sourceConnectionId)
  );

  return {
    progress: subscription?.lastUpdate || null,
    status: subscription?.status || null,
    isActive: subscription?.status === "active",
    jobId: subscription?.jobId || null,
  };
}
