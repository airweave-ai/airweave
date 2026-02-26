import {
  fetchEventSource,
  type EventSourceMessage,
} from "@microsoft/fetch-event-source";
import { env } from "./env";
import type {
  ConnectSessionContext,
  Source,
  SourceConnectionCreateRequest,
  SourceConnectionCreateResponse,
  SourceConnectionJob,
  SourceConnectionListItem,
  SourceDetails,
  SyncProgressUpdate,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

class ConnectApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor() {
    this.baseUrl = env.API_URL;
  }

  setToken(token: string) {
    this.token = token;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(this.token && { Authorization: `Bearer ${this.token}` }),
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || "Request failed");
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  async validateSession(sessionId: string): Promise<ConnectSessionContext> {
    return this.fetch<ConnectSessionContext>(`/connect/sessions/${sessionId}`);
  }

  async getSourceConnections(): Promise<SourceConnectionListItem[]> {
    return this.fetch<SourceConnectionListItem[]>(
      "/connect/source-connections",
    );
  }

  async deleteSourceConnection(connectionId: string): Promise<void> {
    await this.fetch<void>(`/connect/source-connections/${connectionId}`, {
      method: "DELETE",
    });
  }

  async getSources(): Promise<Source[]> {
    return this.fetch<Source[]>("/connect/sources");
  }

  async getSourceDetails(shortName: string): Promise<SourceDetails> {
    return this.fetch<SourceDetails>(`/connect/sources/${shortName}`);
  }

  async createSourceConnection(
    payload: SourceConnectionCreateRequest,
  ): Promise<SourceConnectionCreateResponse> {
    return this.fetch<SourceConnectionCreateResponse>(
      "/connect/source-connections",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  async getSourceConnection(
    connectionId: string,
  ): Promise<SourceConnectionCreateResponse> {
    return this.fetch<SourceConnectionCreateResponse>(
      `/connect/source-connections/${connectionId}`,
    );
  }

  async getConnectionJobs(
    connectionId: string,
  ): Promise<SourceConnectionJob[]> {
    return this.fetch<SourceConnectionJob[]>(
      `/connect/source-connections/${connectionId}/jobs`,
    );
  }

  subscribeToSyncProgress(
    connectionId: string,
    handlers: {
      onProgress: (update: SyncProgressUpdate) => void;
      onComplete: (update: SyncProgressUpdate) => void;
      onError: (error: Error) => void;
      onConnected?: (jobId: string) => void;
      onReconnecting?: (attempt: number) => void;
    },
  ): () => void {
    const controller = new AbortController();
    const url = `${this.baseUrl}/connect/source-connections/${connectionId}/subscribe`;

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s (max 5 retries)
    const maxRetries = 5;
    let retryCount = 0;
    let isComplete = false;

    const getRetryDelay = (attempt: number): number => {
      return Math.min(1000 * Math.pow(2, attempt), 16000);
    };

    void fetchEventSource(url, {
      signal: controller.signal,
      headers: {
        ...(this.token && { Authorization: `Bearer ${this.token}` }),
      },
      onopen: async (response) => {
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(
            `SSE connection failed with status ${response.status}: ${errorText}`,
          );
        }
        retryCount = 0;
      },
      onmessage: (event: EventSourceMessage) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === "connected") {
            handlers.onConnected?.(data.job_id);
            return;
          }

          if (data.type === "heartbeat") {
            return;
          }

          if (data.type === "error") {
            handlers.onError(new Error(data.message));
            return;
          }

          const update: SyncProgressUpdate = {
            entities_inserted: data.inserted ?? 0,
            entities_updated: data.updated ?? 0,
            entities_deleted: data.deleted ?? 0,
            entities_kept: data.kept ?? 0,
            entities_skipped: data.skipped ?? 0,
            entities_encountered: data.entities_encountered ?? {},
            is_complete: data.is_complete,
            is_failed: data.is_failed,
            error: data.error,
          };

          if (data.is_complete || data.is_failed) {
            isComplete = true;
            handlers.onComplete(update);
          } else {
            handlers.onProgress(update);
          }
        } catch (error) {
          console.error("Error parsing SSE message:", error);
        }
      },
      onerror: (error) => {
        // Don't retry if sync is complete or was aborted by user
        if (isComplete || controller.signal.aborted) {
          throw error;
        }

        // Don't retry on 4xx errors (client errors) - these won't resolve with retry
        if (
          error instanceof Response &&
          error.status >= 400 &&
          error.status < 500
        ) {
          handlers.onError(new Error(`SSE connection failed: ${error.status}`));
          throw error;
        }

        retryCount++;

        if (retryCount > maxRetries) {
          handlers.onError(
            error instanceof Error
              ? error
              : new Error("SSE connection error after max retries"),
          );
          throw error;
        }

        handlers.onReconnecting?.(retryCount);

        // Return the delay for fetch-event-source to wait before retrying
        // By not throwing, we allow the library to retry
        return getRetryDelay(retryCount - 1);
      },
    });

    return () => {
      controller.abort();
    };
  }
}

export const apiClient = new ConnectApiClient();
