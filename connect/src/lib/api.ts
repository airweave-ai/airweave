import { env } from "./env";
import type {
  ConnectSessionContext,
  Source,
  SourceConnectionCreateRequest,
  SourceConnectionCreateResponse,
  SourceConnectionListItem,
  SourceDetails,
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
    this.baseUrl = env.VITE_API_URL;
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

    // Handle 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  async validateSession(sessionId: string): Promise<ConnectSessionContext> {
    return this.fetch<ConnectSessionContext>(`/connect/sessions/${sessionId}`);
  }

  async getSourceConnections(): Promise<SourceConnectionListItem[]> {
    return this.fetch<SourceConnectionListItem[]>("/connect/source-connections");
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
}

export const apiClient = new ConnectApiClient();
