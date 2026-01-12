import { env } from "./env";
import type { ConnectSessionContext, SourceConnectionListItem } from "./types";

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

    return response.json();
  }

  async validateSession(sessionId: string): Promise<ConnectSessionContext> {
    return this.fetch<ConnectSessionContext>(`/connect/sessions/${sessionId}`);
  }

  async getSourceConnections(): Promise<SourceConnectionListItem[]> {
    return this.fetch<SourceConnectionListItem[]>("/connect/source-connections");
  }
}

export const apiClient = new ConnectApiClient();
