import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../lib/api";
import type { SyncProgressUpdate, SyncSubscription } from "../lib/types";

interface UseSyncProgressOptions {
  onComplete?: (connectionId: string, update: SyncProgressUpdate) => void;
  onError?: (connectionId: string, error: Error) => void;
}

interface UseSyncProgressReturn {
  subscriptions: Map<string, SyncSubscription>;
  subscribe: (connectionId: string) => Promise<void>;
  unsubscribe: (connectionId: string) => void;
  getProgress: (connectionId: string) => SyncProgressUpdate | null;
  hasActiveSubscription: (connectionId: string) => boolean;
  isReconnecting: (connectionId: string) => boolean;
  cleanup: () => void;
}

function removeSubscription(
  connectionId: string,
  unsubscribeFnsRef: React.MutableRefObject<Map<string, () => void>>,
  setSubscriptions: React.Dispatch<
    React.SetStateAction<Map<string, SyncSubscription>>
  >,
) {
  unsubscribeFnsRef.current.get(connectionId)?.();
  unsubscribeFnsRef.current.delete(connectionId);
  setSubscriptions((prev) => {
    if (!prev.has(connectionId)) return prev;
    const next = new Map(prev);
    next.delete(connectionId);
    return next;
  });
}

function updateSubscription(
  connectionId: string,
  updater: (sub: SyncSubscription) => Partial<SyncSubscription>,
  setSubscriptions: React.Dispatch<
    React.SetStateAction<Map<string, SyncSubscription>>
  >,
) {
  setSubscriptions((prev) => {
    const sub = prev.get(connectionId);
    if (!sub) return prev;
    const next = new Map(prev);
    next.set(connectionId, { ...sub, ...updater(sub) });
    return next;
  });
}

export function useSyncProgress(
  options?: UseSyncProgressOptions,
): UseSyncProgressReturn {
  const [subscriptions, setSubscriptions] = useState<
    Map<string, SyncSubscription>
  >(new Map());

  const onCompleteRef = useRef(options?.onComplete);
  const onErrorRef = useRef(options?.onError);
  const unsubscribeFnsRef = useRef<Map<string, () => void>>(new Map());

  useEffect(() => {
    onCompleteRef.current = options?.onComplete;
    onErrorRef.current = options?.onError;
  });

  useEffect(() => {
    const fns = unsubscribeFnsRef.current;
    return () => {
      fns.forEach((unsubscribe) => unsubscribe());
      fns.clear();
    };
  }, []);

  const subscribe = useCallback(async (connectionId: string) => {
    if (unsubscribeFnsRef.current.has(connectionId)) {
      return;
    }

    // Jobs may not exist immediately after connection creation due to async processing
    const maxRetries = 3;
    const retryDelays = [500, 1000, 2000];

    const findActiveJob = async (
      attempt: number,
    ): Promise<
      Awaited<ReturnType<typeof apiClient.getConnectionJobs>>[number] | null
    > => {
      const jobs = await apiClient.getConnectionJobs(connectionId);

      if (jobs.length === 0) {
        if (attempt < maxRetries) {
          await new Promise((resolve) =>
            setTimeout(resolve, retryDelays[attempt]),
          );
          return findActiveJob(attempt + 1);
        }
        console.warn(
          `No sync jobs found for connection ${connectionId} after ${maxRetries} retries`,
        );
        return null;
      }

      const activeJob = jobs.find(
        (j) => j.status === "running" || j.status === "pending",
      );

      if (!activeJob && attempt < maxRetries) {
        await new Promise((resolve) =>
          setTimeout(resolve, retryDelays[attempt]),
        );
        return findActiveJob(attempt + 1);
      }

      return activeJob ?? null;
    };

    try {
      const activeJob = await findActiveJob(0);

      if (!activeJob) {
        return;
      }

      const initialSubscription: SyncSubscription = {
        connectionId,
        jobId: activeJob.id,
        lastUpdate: {
          entities_inserted: activeJob.entities_inserted ?? 0,
          entities_updated: activeJob.entities_updated ?? 0,
          entities_deleted: activeJob.entities_deleted ?? 0,
          entities_kept: activeJob.entities_kept ?? 0,
          entities_skipped: activeJob.entities_skipped ?? 0,
          entities_encountered: activeJob.entities_encountered ?? {},
        },
        lastMessageTime: Date.now(),
        status: "active",
      };

      setSubscriptions((prev) => {
        const next = new Map(prev);
        next.set(connectionId, initialSubscription);
        return next;
      });

      const unsubscribe = apiClient.subscribeToSyncProgress(connectionId, {
        onConnected: (jobId) => {
          // Reset to active status on successful connection (clears reconnecting state)
          updateSubscription(
            connectionId,
            () => ({
              jobId,
              status: "active",
              reconnectAttempt: undefined,
            }),
            setSubscriptions,
          );
        },
        onReconnecting: (attempt) => {
          updateSubscription(
            connectionId,
            () => ({
              status: "reconnecting",
              reconnectAttempt: attempt,
            }),
            setSubscriptions,
          );
        },
        onProgress: (update) => {
          updateSubscription(
            connectionId,
            () => ({
              lastUpdate: update,
              lastMessageTime: Date.now(),
            }),
            setSubscriptions,
          );
        },
        onComplete: (update) => {
          updateSubscription(
            connectionId,
            () => ({
              lastUpdate: update,
              lastMessageTime: Date.now(),
              status: update.is_failed ? "failed" : "completed",
            }),
            setSubscriptions,
          );

          onCompleteRef.current?.(connectionId, update);

          setTimeout(() => {
            removeSubscription(
              connectionId,
              unsubscribeFnsRef,
              setSubscriptions,
            );
          }, 2000);
        },
        onError: (error) => {
          console.error(`SSE error for ${connectionId}:`, error);
          onErrorRef.current?.(connectionId, error);
          removeSubscription(connectionId, unsubscribeFnsRef, setSubscriptions);
        },
      });

      unsubscribeFnsRef.current.set(connectionId, unsubscribe);
    } catch (error) {
      console.error(`Failed to subscribe to ${connectionId}:`, error);
      onErrorRef.current?.(
        connectionId,
        error instanceof Error ? error : new Error("Failed to subscribe"),
      );
    }
  }, []);

  const unsubscribe = useCallback((connectionId: string) => {
    removeSubscription(connectionId, unsubscribeFnsRef, setSubscriptions);
  }, []);

  const getProgress = useCallback(
    (connectionId: string): SyncProgressUpdate | null => {
      return subscriptions.get(connectionId)?.lastUpdate ?? null;
    },
    [subscriptions],
  );

  const hasActiveSubscription = useCallback(
    (connectionId: string): boolean => {
      const sub = subscriptions.get(connectionId);
      return sub?.status === "active";
    },
    [subscriptions],
  );

  const isReconnecting = useCallback(
    (connectionId: string): boolean => {
      const sub = subscriptions.get(connectionId);
      return sub?.status === "reconnecting";
    },
    [subscriptions],
  );

  const cleanup = useCallback(() => {
    unsubscribeFnsRef.current.forEach((unsubscribe) => unsubscribe());
    unsubscribeFnsRef.current.clear();
    setSubscriptions(new Map());
  }, []);

  return {
    subscriptions,
    subscribe,
    unsubscribe,
    getProgress,
    hasActiveSubscription,
    isReconnecting,
    cleanup,
  };
}
