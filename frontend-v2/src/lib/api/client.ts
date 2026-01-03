/**
 * Base API client configuration and utilities
 */

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "https://api.airweave.ai";

/**
 * Common request headers for authenticated API calls
 * @param token - Auth0 access token
 * @param organizationId - Optional organization ID to scope the request
 */
export function getAuthHeaders(
  token: string,
  organizationId?: string
): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(organizationId && { "X-Organization-ID": organizationId }),
  };
}

/**
 * Parse error response and extract message
 */
export async function parseErrorResponse(
  response: Response,
  defaultMessage: string
): Promise<string> {
  try {
    const errorText = await response.text();
    const parsed = JSON.parse(errorText);
    return parsed.detail || parsed.message || defaultMessage;
  } catch {
    return defaultMessage;
  }
}
