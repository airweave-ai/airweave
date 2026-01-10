import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

export interface UsageData {
  entities: number;
  queries: number;
  source_connections: number;
  max_entities: number | null;
  max_queries: number | null;
  max_source_connections: number | null;
  team_members: number;
  max_team_members: number | null;
}

export interface ActionCheckResponse {
  allowed: boolean;
  action: string;
  reason?: "payment_required" | "usage_limit_exceeded" | null;
  details?: {
    message: string;
    current_usage?: number;
    limit?: number;
    payment_status?: string;
    upgrade_url?: string;
  } | null;
}

export interface CheckActionsResponse {
  results: Record<string, ActionCheckResponse>;
}

export type UsageAction =
  | "source_connections"
  | "entities"
  | "queries"
  | "team_members";

export async function checkActions(
  token: string,
  actions: Record<string, number>
): Promise<CheckActionsResponse> {
  const response = await fetch(`${API_BASE_URL}/usage/check-actions`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({ actions }),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to check usage actions"
    );
    throw new Error(message);
  }

  return response.json();
}

export async function checkSingleAction(
  token: string,
  action: string,
  quantity: number = 1
): Promise<ActionCheckResponse> {
  const response = await checkActions(token, { [action]: quantity });
  return (
    response.results[action] ?? {
      allowed: true,
      action,
    }
  );
}

export interface CurrentPeriod {
  period_id: string;
  period_start: string;
  period_end: string;
  status: string;
  plan: string;
  usage: UsageData;
  days_remaining?: number | null;
  is_current: boolean;
}

export interface UsageDashboardData {
  current_period: CurrentPeriod;
}

export async function fetchUsageDashboard(
  token: string
): Promise<UsageDashboardData> {
  const response = await fetch(`${API_BASE_URL}/usage/dashboard`, {
    method: "GET",
    headers: getAuthHeaders(token),
  });

  if (!response.ok) {
    const message = await parseErrorResponse(
      response,
      "Failed to fetch usage data"
    );
    throw new Error(message);
  }

  return response.json();
}
