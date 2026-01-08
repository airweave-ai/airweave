/**
 * Usage API client
 */

import { API_BASE_URL, getAuthHeaders, parseErrorResponse } from "./client";

/**
 * Usage data for a billing period
 */
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

/**
 * Current billing period information
 */
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

/**
 * Usage dashboard response
 */
export interface UsageDashboardData {
  current_period: CurrentPeriod;
}

/**
 * Fetch usage dashboard data
 */
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
