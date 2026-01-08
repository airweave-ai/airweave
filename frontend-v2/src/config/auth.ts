/**
 * Get the redirect URL for Auth0.
 * Uses https://app.airweave.ai for localhost, otherwise uses current origin.
 */
export function getRedirectUrl(): string {
  if (typeof window === "undefined") return "";

  const origin = window.location.origin;
  if (origin.includes("localhost") || origin.includes("127.0.0.1")) {
    return "https://app.airweave.ai/callback";
  }
  return origin;
}

/**
 * Access token for local development (set via VITE_ACCESS_TOKEN env var).
 */
const accessToken = import.meta.env.VITE_ACCESS_TOKEN || "";

/**
 * Auth is enabled unless:
 * 1. VITE_ACCESS_TOKEN is provided (local dev with token)
 * 2. VITE_ENABLE_AUTH is explicitly set to 'false'
 */
const authEnabled =
  !accessToken && import.meta.env.VITE_ENABLE_AUTH !== "false";

export const authConfig = {
  domain: import.meta.env.VITE_AUTH0_DOMAIN || "airweave.us.auth0.com",
  clientId:
    import.meta.env.VITE_AUTH0_CLIENT_ID || "jXyLRWR9lg0kZQvVjpJ2YmiSYn1UtUSw",
  audience: import.meta.env.VITE_AUTH0_AUDIENCE || "https://app.airweave.ai/",
  redirectUri: getRedirectUrl(),
  accessToken,
  authEnabled,
};

/** Dev user info shown when using access token for local development */
export const devUser = {
  name: import.meta.env.VITE_DEV_USER_NAME || "Dev User",
  email: import.meta.env.VITE_DEV_USER_EMAIL || "dev@localhost",
  picture: "",
};
