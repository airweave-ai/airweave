/**
 * Service for managing sync progress state in session storage.
 * Provides persistence across page reloads for active sync operations.
 */

import type { SyncProgressUpdate } from "@/stores/sync-state-store";

/** Persisted sync state structure */
export interface PersistedSyncState {
  [sourceConnectionId: string]: {
    jobId: string;
    lastUpdate: SyncProgressUpdate;
    timestamp: number;
    status: "active" | "completed" | "failed";
  };
}

class SyncStorageService {
  private readonly STORAGE_KEY = "sync_progress_state";
  private readonly MAX_AGE_MS = 60 * 60 * 1000; // 1 hour

  /**
   * Save progress for a source connection
   */
  saveProgress(
    sourceConnectionId: string,
    jobId: string,
    progress: SyncProgressUpdate
  ): void {
    try {
      const currentState = this.getStoredState();

      currentState[sourceConnectionId] = {
        jobId,
        lastUpdate: progress,
        timestamp: Date.now(),
        status: progress.is_complete
          ? "completed"
          : progress.is_failed
            ? "failed"
            : "active",
      };

      sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(currentState));
    } catch (error) {
      console.error("Error saving sync progress to storage:", error);
    }
  }

  /**
   * Get all stored sync state
   */
  getStoredState(): PersistedSyncState {
    try {
      const stored = sessionStorage.getItem(this.STORAGE_KEY);
      if (!stored) {
        return {};
      }

      const state: PersistedSyncState = JSON.parse(stored);

      // Clean up old entries
      const now = Date.now();
      const cleaned: PersistedSyncState = {};

      Object.entries(state).forEach(([sourceConnectionId, data]) => {
        // Keep if less than 1 hour old
        if (now - data.timestamp < this.MAX_AGE_MS) {
          cleaned[sourceConnectionId] = data;
        }
      });

      // Save cleaned state if anything was removed
      if (Object.keys(cleaned).length !== Object.keys(state).length) {
        sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(cleaned));
      }

      return cleaned;
    } catch (error) {
      console.error("Error reading sync progress from storage:", error);
      return {};
    }
  }

  /**
   * Get stored state for a specific source connection
   */
  getProgressForSource(
    sourceConnectionId: string
  ): PersistedSyncState[string] | null {
    const state = this.getStoredState();
    return state[sourceConnectionId] || null;
  }

  /**
   * Remove progress for a source connection
   */
  removeProgress(sourceConnectionId: string): void {
    try {
      const currentState = this.getStoredState();
      delete currentState[sourceConnectionId];
      sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(currentState));
    } catch (error) {
      console.error("Error removing sync progress from storage:", error);
    }
  }

  /**
   * Clear all stored sync progress
   */
  clearAll(): void {
    try {
      sessionStorage.removeItem(this.STORAGE_KEY);
    } catch (error) {
      console.error("Error clearing sync progress storage:", error);
    }
  }

  /**
   * Check if we have active sync data for a source
   */
  hasActiveSync(sourceConnectionId: string): boolean {
    const data = this.getProgressForSource(sourceConnectionId);
    return data?.status === "active" || false;
  }
}

// Export singleton instance
export const syncStorageService = new SyncStorageService();
