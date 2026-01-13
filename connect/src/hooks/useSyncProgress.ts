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
  cleanup: () => void;
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

    try {
      const jobs = await apiClient.getConnectionJobs(connectionId);
      if (jobs.length === 0) {
        console.warn(`No sync jobs found for connection ${connectionId}`);
        return;
      }

      const activeJob = jobs.find(
        (j) => j.status === "in_progress" || j.status === "pending",
      );

      if (!activeJob) {
        return;
      }

      const initialSubscription: SyncSubscription = {
        connectionId,
        jobId: activeJob.id,
        controller: new AbortController(),
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
          setSubscriptions((prev) => {
            const sub = prev.get(connectionId);
            if (sub && sub.jobId !== jobId) {
              const next = new Map(prev);
              next.set(connectionId, { ...sub, jobId });
              return next;
            }
            return prev;
          });
        },
        onProgress: (update) => {
          setSubscriptions((prev) => {
            const sub = prev.get(connectionId);
            if (!sub) return prev;

            const next = new Map(prev);
            next.set(connectionId, {
              ...sub,
              lastUpdate: update,
              lastMessageTime: Date.now(),
            });
            return next;
          });
        },
        onComplete: (update) => {
          setSubscriptions((prev) => {
            const sub = prev.get(connectionId);
            if (!sub) return prev;

            const next = new Map(prev);
            next.set(connectionId, {
              ...sub,
              lastUpdate: update,
              lastMessageTime: Date.now(),
              status: update.is_failed ? "failed" : "completed",
            });
            return next;
          });

          onCompleteRef.current?.(connectionId, update);

          setTimeout(() => {
            unsubscribeFnsRef.current.get(connectionId)?.();
            unsubscribeFnsRef.current.delete(connectionId);
            setSubscriptions((prev) => {
              const next = new Map(prev);
              next.delete(connectionId);
              return next;
            });
          }, 2000);
        },
        onError: (error) => {
          console.error(`SSE error for ${connectionId}:`, error);
          onErrorRef.current?.(connectionId, error);

          unsubscribeFnsRef.current.get(connectionId)?.();
          unsubscribeFnsRef.current.delete(connectionId);
          setSubscriptions((prev) => {
            const next = new Map(prev);
            next.delete(connectionId);
            return next;
          });
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
    const unsubscribeFn = unsubscribeFnsRef.current.get(connectionId);
    if (unsubscribeFn) {
      unsubscribeFn();
      unsubscribeFnsRef.current.delete(connectionId);
    }

    setSubscriptions((prev) => {
      if (!prev.has(connectionId)) return prev;
      const next = new Map(prev);
      next.delete(connectionId);
      return next;
    });
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
    cleanup,
  };
}
