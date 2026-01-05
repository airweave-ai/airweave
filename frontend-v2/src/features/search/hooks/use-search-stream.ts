/**
 * useSearchStream - Handles streaming search requests with abort support
 */

import { useCallback, useRef } from "react";

import { API_BASE_URL, getAuthHeaders } from "@/lib/api";

import type { SearchEvent, SearchResponse } from "../types";

class HandledStreamError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "HandledStreamError";
  }
}

interface StreamSearchParams {
  collectionId: string;
  query: string;
  requestBody: Record<string, unknown>;
  token: string;
  orgId: string;
  onStreamEvent?: (event: SearchEvent) => void;
  onSuccess: (response: SearchResponse, responseTime: number) => void;
  onError: (error: Error, responseTime: number, isTransient: boolean) => void;
}

export function useSearchStream() {
  const abortRef = useRef<AbortController | null>(null);
  const searchSeqRef = useRef(0);

  const cancelSearch = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const executeSearch = useCallback(
    async ({
      collectionId,
      requestBody,
      token,
      orgId,
      onStreamEvent,
      onSuccess,
      onError,
    }: StreamSearchParams) => {
      cancelSearch();

      const mySeq = ++searchSeqRef.current;
      const abortController = new AbortController();
      abortRef.current = abortController;

      const startTime = performance.now();

      try {
        const response = await fetch(
          `${API_BASE_URL}/collections/${collectionId}/search/stream`,
          {
            method: "POST",
            headers: getAuthHeaders(token, orgId),
            body: JSON.stringify(requestBody),
            signal: abortController.signal,
          }
        );

        if (!response.ok || !response.body) {
          const errorText = await response.text().catch(() => "");
          throw new Error(
            errorText ||
              `Stream failed: ${response.status} ${response.statusText}`
          );
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        let latestResults: unknown[] = [];
        let latestCompletion: string | null = null;

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          if (searchSeqRef.current !== mySeq) break;

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
            let event: SearchEvent;
            try {
              event = JSON.parse(payloadStr);
            } catch {
              continue;
            }

            onStreamEvent?.(event);

            switch (event.type) {
              case "results":
                if (Array.isArray((event as { results?: unknown[] }).results)) {
                  latestResults = (event as { results: unknown[] }).results;
                }
                break;
              case "completion_done":
                if (typeof (event as { text?: string }).text === "string") {
                  latestCompletion = (event as { text: string }).text;
                }
                break;
              case "error": {
                const endTime = performance.now();
                const responseTime = Math.round(endTime - startTime);
                const errorEvent = event as {
                  message?: string;
                  transient?: boolean;
                };
                const errorMessage = errorEvent.message || "Streaming error";
                const isTransient = errorEvent.transient === true;

                onError(new Error(errorMessage), responseTime, isTransient);
                throw new HandledStreamError(errorMessage);
              }
              case "done": {
                const endTime = performance.now();
                const responseTime = Math.round(endTime - startTime);
                onSuccess(
                  {
                    completion: latestCompletion,
                    results: latestResults,
                    responseTime,
                  },
                  responseTime
                );
                break;
              }
            }
          }
        }
      } catch (error) {
        const err = error as Error;
        if (err.name === "AbortError") {
          // User cancelled - ignore
        } else if (err instanceof HandledStreamError) {
          // Already handled and sent to onError - don't overwrite with generic message
        } else {
          const endTime = performance.now();
          const responseTime = Math.round(endTime - startTime);
          onError(err, responseTime, true);
        }
      } finally {
        if (
          searchSeqRef.current === mySeq &&
          abortRef.current === abortController
        ) {
          abortRef.current = null;
        }
      }
    },
    [cancelSearch]
  );

  return {
    executeSearch,
    cancelSearch,
    isActive: () => abortRef.current !== null,
  };
}
