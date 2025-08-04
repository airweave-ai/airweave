import { useState, useCallback } from "react";
import { toast } from "sonner";
import {
  SyncService,
  SyncScheduleConfig,
  ScheduleResponse,
} from "@/services/syncService";
import { buildCronExpression } from "@/components/sync/SyncSchedule";

interface UseSyncScheduleProps {
  syncId: string;
}

interface UseSyncScheduleReturn {
  // State
  isLoading: boolean;
  currentSchedule: ScheduleResponse | null;
  error: string | null;

  // Actions
  createSchedule: (config: SyncScheduleConfig) => Promise<void>;
  updateSchedule: (config: SyncScheduleConfig) => Promise<void>;
  pauseSchedule: () => Promise<void>;
  resumeSchedule: () => Promise<void>;
  deleteSchedule: () => Promise<void>;
  loadSchedule: () => Promise<void>;

  // Utilities
  clearError: () => void;
}

export function useSyncSchedule({
  syncId,
}: UseSyncScheduleProps): UseSyncScheduleReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [currentSchedule, setCurrentSchedule] =
    useState<ScheduleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const loadSchedule = useCallback(async () => {
    if (!syncId) return;

    setIsLoading(true);
    setError(null);

    try {
      const schedule = await SyncService.getMinuteLevelScheduleInfo(syncId);
      setCurrentSchedule(schedule);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to load schedule";
      setError(errorMessage);
      console.error("Error loading schedule:", err);
    } finally {
      setIsLoading(false);
    }
  }, [syncId]);

  const createSchedule = useCallback(
    async (config: SyncScheduleConfig) => {
      if (!syncId) {
        setError("No sync ID provided");
        return;
      }

      if (config.type !== "incremental") {
        setError(
          "Only incremental schedules are supported for minute-level scheduling"
        );
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const cronExpression = buildCronExpression(config);
        if (!cronExpression) {
          throw new Error("Invalid schedule configuration");
        }

        const schedule = await SyncService.createMinuteLevelSchedule(
          syncId,
          cronExpression
        );
        setCurrentSchedule(schedule);

        toast.success("Incremental sync schedule created successfully", {
          description: `Sync will run every ${
            config.frequency === "minute" ? "minute" : config.frequency
          }`,
        });
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to create schedule";
        setError(errorMessage);
        toast.error("Failed to create schedule", {
          description: errorMessage,
        });
        console.error("Error creating schedule:", err);
      } finally {
        setIsLoading(false);
      }
    },
    [syncId]
  );

  const updateSchedule = useCallback(
    async (config: SyncScheduleConfig) => {
      if (!syncId) {
        setError("No sync ID provided");
        return;
      }

      if (config.type !== "incremental") {
        setError(
          "Only incremental schedules are supported for minute-level scheduling"
        );
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const cronExpression = buildCronExpression(config);
        if (!cronExpression) {
          throw new Error("Invalid schedule configuration");
        }

        const schedule = await SyncService.updateMinuteLevelSchedule(
          syncId,
          cronExpression
        );
        setCurrentSchedule(schedule);

        toast.success("Incremental sync schedule updated successfully", {
          description: `Sync will now run every ${
            config.frequency === "minute" ? "minute" : config.frequency
          }`,
        });
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to update schedule";
        setError(errorMessage);
        toast.error("Failed to update schedule", {
          description: errorMessage,
        });
        console.error("Error updating schedule:", err);
      } finally {
        setIsLoading(false);
      }
    },
    [syncId]
  );

  const pauseSchedule = useCallback(async () => {
    if (!syncId) {
      setError("No sync ID provided");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const schedule = await SyncService.pauseMinuteLevelSchedule(syncId);
      setCurrentSchedule(schedule);

      toast.success("Incremental sync schedule paused", {
        description: "The sync will no longer run automatically",
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to pause schedule";
      setError(errorMessage);
      toast.error("Failed to pause schedule", {
        description: errorMessage,
      });
      console.error("Error pausing schedule:", err);
    } finally {
      setIsLoading(false);
    }
  }, [syncId]);

  const resumeSchedule = useCallback(async () => {
    if (!syncId) {
      setError("No sync ID provided");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const schedule = await SyncService.resumeMinuteLevelSchedule(syncId);
      setCurrentSchedule(schedule);

      toast.success("Incremental sync schedule resumed", {
        description: "The sync will now run automatically again",
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to resume schedule";
      setError(errorMessage);
      toast.error("Failed to resume schedule", {
        description: errorMessage,
      });
      console.error("Error resuming schedule:", err);
    } finally {
      setIsLoading(false);
    }
  }, [syncId]);

  const deleteSchedule = useCallback(async () => {
    if (!syncId) {
      setError("No sync ID provided");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await SyncService.deleteMinuteLevelSchedule(syncId);
      setCurrentSchedule(null);

      toast.success("Incremental sync schedule deleted", {
        description: "The sync will no longer run automatically",
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to delete schedule";
      setError(errorMessage);
      toast.error("Failed to delete schedule", {
        description: errorMessage,
      });
      console.error("Error deleting schedule:", err);
    } finally {
      setIsLoading(false);
    }
  }, [syncId]);

  return {
    // State
    isLoading,
    currentSchedule,
    error,

    // Actions
    createSchedule,
    updateSchedule,
    pauseSchedule,
    resumeSchedule,
    deleteSchedule,
    loadSchedule,

    // Utilities
    clearError,
  };
}
