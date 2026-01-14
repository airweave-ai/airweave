import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSyncProgress } from "./useSyncProgress";
import { apiClient } from "../lib/api";
import type { SourceConnectionJob, SyncProgressUpdate } from "../lib/types";

vi.mock("../lib/api", () => ({
  apiClient: {
    getConnectionJobs: vi.fn(),
    subscribeToSyncProgress: vi.fn(),
  },
}));

const mockGetConnectionJobs = vi.mocked(apiClient.getConnectionJobs);
const mockSubscribeToSyncProgress = vi.mocked(
  apiClient.subscribeToSyncProgress,
);

describe("useSyncProgress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const createMockJob = (
    overrides: Partial<SourceConnectionJob> = {},
  ): SourceConnectionJob => ({
    id: "job-123",
    source_connection_id: "conn-123",
    organization_id: "org-123",
    status: "running",
    scheduled: false,
    entities_inserted: 0,
    entities_updated: 0,
    entities_deleted: 0,
    entities_kept: 0,
    entities_skipped: 0,
    entities_encountered: {},
    ...overrides,
  });

  describe("subscribe", () => {
    it("subscribes to a connection and sets initial state from job", async () => {
      const mockJob = createMockJob({
        entities_inserted: 10,
        entities_updated: 5,
      });
      mockGetConnectionJobs.mockResolvedValue([mockJob]);
      mockSubscribeToSyncProgress.mockReturnValue(() => {});

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(mockGetConnectionJobs).toHaveBeenCalledWith("conn-123");
      expect(mockSubscribeToSyncProgress).toHaveBeenCalledWith(
        "conn-123",
        expect.objectContaining({
          onProgress: expect.any(Function),
          onComplete: expect.any(Function),
          onError: expect.any(Function),
          onConnected: expect.any(Function),
        }),
      );

      const progress = result.current.getProgress("conn-123");
      expect(progress).toEqual({
        entities_inserted: 10,
        entities_updated: 5,
        entities_deleted: 0,
        entities_kept: 0,
        entities_skipped: 0,
        entities_encountered: {},
      });
    });

    it("does not subscribe if no jobs found", async () => {
      mockGetConnectionJobs.mockResolvedValue([]);

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        const subscribePromise = result.current.subscribe("conn-123");
        // Advance through all retry delays (500 + 1000 + 2000 = 3500ms)
        await vi.advanceTimersByTimeAsync(3500);
        await subscribePromise;
      });

      expect(mockSubscribeToSyncProgress).not.toHaveBeenCalled();
      expect(result.current.subscriptions.size).toBe(0);
    });

    it("does not subscribe if no active job found", async () => {
      const completedJob = createMockJob({ status: "completed" });
      mockGetConnectionJobs.mockResolvedValue([completedJob]);

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        const subscribePromise = result.current.subscribe("conn-123");
        // Advance through all retry delays (500 + 1000 + 2000 = 3500ms)
        await vi.advanceTimersByTimeAsync(3500);
        await subscribePromise;
      });

      expect(mockSubscribeToSyncProgress).not.toHaveBeenCalled();
      expect(result.current.subscriptions.size).toBe(0);
    });

    it("subscribes to pending jobs", async () => {
      const pendingJob = createMockJob({ status: "pending" });
      mockGetConnectionJobs.mockResolvedValue([pendingJob]);
      mockSubscribeToSyncProgress.mockReturnValue(() => {});

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(mockSubscribeToSyncProgress).toHaveBeenCalled();
    });

    it("does not duplicate subscription for same connection", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);
      mockSubscribeToSyncProgress.mockReturnValue(() => {});

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(mockSubscribeToSyncProgress).toHaveBeenCalledTimes(1);
    });
  });

  describe("progress updates", () => {
    it("updates subscription state on progress event", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      let capturedHandlers: {
        onProgress: (update: SyncProgressUpdate) => void;
        onComplete: (update: SyncProgressUpdate) => void;
        onError: (error: Error) => void;
        onConnected?: (jobId: string) => void;
      } | null = null;

      mockSubscribeToSyncProgress.mockImplementation((_, handlers) => {
        capturedHandlers = handlers;
        return () => {};
      });

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(capturedHandlers).not.toBeNull();

      const progressUpdate: SyncProgressUpdate = {
        entities_inserted: 50,
        entities_updated: 10,
        entities_deleted: 2,
        entities_kept: 100,
        entities_skipped: 5,
        entities_encountered: { Message: 62 },
      };

      act(() => {
        capturedHandlers!.onProgress(progressUpdate);
      });

      const progress = result.current.getProgress("conn-123");
      expect(progress).toEqual(progressUpdate);
      expect(result.current.hasActiveSubscription("conn-123")).toBe(true);
    });

    it("updates job ID on connected event", async () => {
      const mockJob = createMockJob({ id: "job-old" });
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      let capturedHandlers: {
        onConnected?: (jobId: string) => void;
      } | null = null;

      mockSubscribeToSyncProgress.mockImplementation((_, handlers) => {
        capturedHandlers = handlers;
        return () => {};
      });

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      act(() => {
        capturedHandlers!.onConnected?.("job-new");
      });

      const sub = result.current.subscriptions.get("conn-123");
      expect(sub?.jobId).toBe("job-new");
    });
  });

  describe("completion", () => {
    it("marks subscription as completed and triggers callback", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      let capturedHandlers: {
        onComplete: (update: SyncProgressUpdate) => void;
      } | null = null;

      mockSubscribeToSyncProgress.mockImplementation((_, handlers) => {
        capturedHandlers = handlers;
        return () => {};
      });

      const onComplete = vi.fn();
      const { result } = renderHook(() => useSyncProgress({ onComplete }));

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      const completeUpdate: SyncProgressUpdate = {
        entities_inserted: 100,
        entities_updated: 20,
        entities_deleted: 5,
        entities_kept: 200,
        entities_skipped: 0,
        entities_encountered: { Message: 125 },
        is_complete: true,
      };

      act(() => {
        capturedHandlers!.onComplete(completeUpdate);
      });

      expect(onComplete).toHaveBeenCalledWith("conn-123", completeUpdate);

      const sub = result.current.subscriptions.get("conn-123");
      expect(sub?.status).toBe("completed");
    });

    it("marks subscription as failed when is_failed is true", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      let capturedHandlers: {
        onComplete: (update: SyncProgressUpdate) => void;
      } | null = null;

      mockSubscribeToSyncProgress.mockImplementation((_, handlers) => {
        capturedHandlers = handlers;
        return () => {};
      });

      const onComplete = vi.fn();
      const { result } = renderHook(() => useSyncProgress({ onComplete }));

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      const failedUpdate: SyncProgressUpdate = {
        entities_inserted: 50,
        entities_updated: 0,
        entities_deleted: 0,
        entities_kept: 0,
        entities_skipped: 0,
        entities_encountered: {},
        is_complete: true,
        is_failed: true,
        error: "Connection timeout",
      };

      act(() => {
        capturedHandlers!.onComplete(failedUpdate);
      });

      const sub = result.current.subscriptions.get("conn-123");
      expect(sub?.status).toBe("failed");
    });

    it("removes subscription after 2 second delay on completion", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      const mockUnsubscribe = vi.fn();
      let capturedHandlers: {
        onComplete: (update: SyncProgressUpdate) => void;
      } | null = null;

      mockSubscribeToSyncProgress.mockImplementation((_, handlers) => {
        capturedHandlers = handlers;
        return mockUnsubscribe;
      });

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      const completeUpdate: SyncProgressUpdate = {
        entities_inserted: 100,
        entities_updated: 0,
        entities_deleted: 0,
        entities_kept: 0,
        entities_skipped: 0,
        entities_encountered: {},
        is_complete: true,
      };

      act(() => {
        capturedHandlers!.onComplete(completeUpdate);
      });

      // Subscription should still exist immediately after completion
      expect(result.current.subscriptions.has("conn-123")).toBe(true);

      // Fast-forward 2 seconds
      await act(async () => {
        vi.advanceTimersByTime(2000);
      });

      // Now subscription should be removed
      expect(result.current.subscriptions.has("conn-123")).toBe(false);
      expect(mockUnsubscribe).toHaveBeenCalled();
    });
  });

  describe("error handling", () => {
    it("triggers error callback on SSE error", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      let capturedHandlers: {
        onError: (error: Error) => void;
      } | null = null;

      mockSubscribeToSyncProgress.mockImplementation((_, handlers) => {
        capturedHandlers = handlers;
        return () => {};
      });

      const onError = vi.fn();
      const { result } = renderHook(() => useSyncProgress({ onError }));

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      const error = new Error("SSE connection failed");

      act(() => {
        capturedHandlers!.onError(error);
      });

      expect(onError).toHaveBeenCalledWith("conn-123", error);
      // Subscription should be removed on error
      expect(result.current.subscriptions.has("conn-123")).toBe(false);
    });

    it("triggers error callback when getConnectionJobs fails", async () => {
      mockGetConnectionJobs.mockRejectedValue(new Error("Network error"));

      const onError = vi.fn();
      const { result } = renderHook(() => useSyncProgress({ onError }));

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(onError).toHaveBeenCalledWith(
        "conn-123",
        expect.objectContaining({ message: "Network error" }),
      );
    });

    it("wraps non-Error exceptions in Error object", async () => {
      mockGetConnectionJobs.mockRejectedValue("string error");

      const onError = vi.fn();
      const { result } = renderHook(() => useSyncProgress({ onError }));

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(onError).toHaveBeenCalledWith(
        "conn-123",
        expect.objectContaining({ message: "Failed to subscribe" }),
      );
    });
  });

  describe("unsubscribe", () => {
    it("calls unsubscribe function and removes subscription", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      const mockUnsubscribeFn = vi.fn();
      mockSubscribeToSyncProgress.mockReturnValue(mockUnsubscribeFn);

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(result.current.subscriptions.has("conn-123")).toBe(true);

      act(() => {
        result.current.unsubscribe("conn-123");
      });

      expect(mockUnsubscribeFn).toHaveBeenCalled();
      expect(result.current.subscriptions.has("conn-123")).toBe(false);
    });

    it("handles unsubscribe for non-existent connection gracefully", () => {
      const { result } = renderHook(() => useSyncProgress());

      // Should not throw
      act(() => {
        result.current.unsubscribe("non-existent");
      });

      expect(result.current.subscriptions.size).toBe(0);
    });
  });

  describe("cleanup", () => {
    it("cleans up all subscriptions", async () => {
      const mockJob1 = createMockJob({ id: "job-1" });
      const mockJob2 = createMockJob({ id: "job-2" });

      mockGetConnectionJobs
        .mockResolvedValueOnce([mockJob1])
        .mockResolvedValueOnce([mockJob2]);

      const mockUnsubscribe1 = vi.fn();
      const mockUnsubscribe2 = vi.fn();

      mockSubscribeToSyncProgress
        .mockReturnValueOnce(mockUnsubscribe1)
        .mockReturnValueOnce(mockUnsubscribe2);

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-1");
        await result.current.subscribe("conn-2");
      });

      expect(result.current.subscriptions.size).toBe(2);

      act(() => {
        result.current.cleanup();
      });

      expect(mockUnsubscribe1).toHaveBeenCalled();
      expect(mockUnsubscribe2).toHaveBeenCalled();
      expect(result.current.subscriptions.size).toBe(0);
    });

    it("cleans up subscriptions on unmount", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      const mockUnsubscribeFn = vi.fn();
      mockSubscribeToSyncProgress.mockReturnValue(mockUnsubscribeFn);

      const { result, unmount } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      unmount();

      expect(mockUnsubscribeFn).toHaveBeenCalled();
    });
  });

  describe("hasActiveSubscription", () => {
    it("returns true for active subscriptions", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);
      mockSubscribeToSyncProgress.mockReturnValue(() => {});

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(result.current.hasActiveSubscription("conn-123")).toBe(true);
    });

    it("returns false for non-existent subscriptions", () => {
      const { result } = renderHook(() => useSyncProgress());

      expect(result.current.hasActiveSubscription("non-existent")).toBe(false);
    });

    it("returns false for completed subscriptions", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      let capturedHandlers: {
        onComplete: (update: SyncProgressUpdate) => void;
      } | null = null;

      mockSubscribeToSyncProgress.mockImplementation((_, handlers) => {
        capturedHandlers = handlers;
        return () => {};
      });

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      const completeUpdate: SyncProgressUpdate = {
        entities_inserted: 100,
        entities_updated: 0,
        entities_deleted: 0,
        entities_kept: 0,
        entities_skipped: 0,
        entities_encountered: {},
        is_complete: true,
      };

      act(() => {
        capturedHandlers!.onComplete(completeUpdate);
      });

      expect(result.current.hasActiveSubscription("conn-123")).toBe(false);
    });
  });

  describe("getProgress", () => {
    it("returns null for non-existent subscriptions", () => {
      const { result } = renderHook(() => useSyncProgress());

      expect(result.current.getProgress("non-existent")).toBeNull();
    });

    it("returns latest progress for existing subscriptions", async () => {
      const mockJob = createMockJob({
        entities_inserted: 25,
        entities_updated: 10,
      });
      mockGetConnectionJobs.mockResolvedValue([mockJob]);
      mockSubscribeToSyncProgress.mockReturnValue(() => {});

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      const progress = result.current.getProgress("conn-123");
      expect(progress).toEqual({
        entities_inserted: 25,
        entities_updated: 10,
        entities_deleted: 0,
        entities_kept: 0,
        entities_skipped: 0,
        entities_encountered: {},
      });
    });
  });

  describe("isReconnecting", () => {
    it("returns false for non-existent subscriptions", () => {
      const { result } = renderHook(() => useSyncProgress());

      expect(result.current.isReconnecting("non-existent")).toBe(false);
    });

    it("returns false for active subscriptions", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);
      mockSubscribeToSyncProgress.mockReturnValue(() => {});

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(result.current.isReconnecting("conn-123")).toBe(false);
    });

    it("returns true when onReconnecting is called", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      let capturedHandlers: {
        onReconnecting?: (attempt: number) => void;
      } | null = null;

      mockSubscribeToSyncProgress.mockImplementation((_, handlers) => {
        capturedHandlers = handlers;
        return () => {};
      });

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      expect(result.current.isReconnecting("conn-123")).toBe(false);

      act(() => {
        capturedHandlers?.onReconnecting?.(1);
      });

      expect(result.current.isReconnecting("conn-123")).toBe(true);
      expect(
        result.current.subscriptions.get("conn-123")?.reconnectAttempt,
      ).toBe(1);
    });

    it("clears reconnecting state when onConnected is called after reconnect", async () => {
      const mockJob = createMockJob();
      mockGetConnectionJobs.mockResolvedValue([mockJob]);

      let capturedHandlers: {
        onReconnecting?: (attempt: number) => void;
        onConnected?: (jobId: string) => void;
      } | null = null;

      mockSubscribeToSyncProgress.mockImplementation((_, handlers) => {
        capturedHandlers = handlers;
        return () => {};
      });

      const { result } = renderHook(() => useSyncProgress());

      await act(async () => {
        await result.current.subscribe("conn-123");
      });

      // Simulate reconnecting state
      act(() => {
        capturedHandlers?.onReconnecting?.(1);
      });

      expect(result.current.isReconnecting("conn-123")).toBe(true);

      // Simulate successful reconnection
      act(() => {
        capturedHandlers?.onConnected?.("job-123");
      });

      expect(result.current.isReconnecting("conn-123")).toBe(false);
      expect(result.current.hasActiveSubscription("conn-123")).toBe(true);
      expect(
        result.current.subscriptions.get("conn-123")?.reconnectAttempt,
      ).toBeUndefined();
    });
  });
});
