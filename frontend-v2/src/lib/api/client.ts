/**
 * Base API client configuration and utilities
 */

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "https://api.airweave.ai";

/**
 * Get PostHog session ID safely
 * Returns undefined if PostHog is not initialized or available
 *
 * Note: PostHog integration is pending. Once posthog-provider is ported,
 * this function will return the actual session ID for analytics correlation.
 */
function getPostHogSessionId(): string | undefined {
  try {
    // Check if PostHog is available on window (set by posthog-provider)
    const posthog = (window as { posthog?: { get_session_id?: () => string } })
      .posthog;
    if (posthog && typeof posthog.get_session_id === "function") {
      return posthog.get_session_id();
    }
  } catch {
    // Silently ignore - PostHog may not be initialized yet
  }
  return undefined;
}

/**
 * Common request headers for authenticated API calls
 * @param token - Auth0 access token
 * @param organizationId - Optional organization ID to scope the request
 */
export function getAuthHeaders(
  token: string,
  organizationId?: string
): HeadersInit {
  const sessionId = getPostHogSessionId();

  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(organizationId && { "X-Organization-ID": organizationId }),
    ...(sessionId && { "X-Airweave-Session-ID": sessionId }),
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
