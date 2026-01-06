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

/** Default access token for local development */
const LOCAL_DEV_TOKEN =
  "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IlkzN3F5b1NieEIzbzhFdlQtZ2tjVSJ9.eyJodHRwczovL2FwcC5haXJ3ZWF2ZS5haS9lbWFpbCI6ImFuYW5kQGNob3dkaGFyeS5vcmciLCJpc3MiOiJodHRwczovL2FpcndlYXZlLnVzLmF1dGgwLmNvbS8iLCJzdWIiOiJnb29nbGUtb2F1dGgyfDExNTE3NDgwNDU1MDk5NTEzMDkyMCIsImF1ZCI6WyJodHRwczovL2FwcC5haXJ3ZWF2ZS5haS8iLCJodHRwczovL2FpcndlYXZlLnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE3Njc2NTYxNjMsImV4cCI6MTc2Nzc0MjU2Mywic2NvcGUiOiJvcGVuaWQgcHJvZmlsZSBlbWFpbCIsImF6cCI6ImpYeUxSV1I5bGcwa1pRdlZqcEoyWW1pU1luMVV0VVN3In0.ZQJh2LxFKftLLjFYFU_C1i6fObRnc-VVoQ7NgnVjlJ3raeAsLCcAoKD53EoylabonIADIogfjEqUPrZ-0tzT8xiUVw0bWNr9TJJp9KUOkqlXU_QVjsSZvBxf6JAMHEgjmShbAlD68OZApqTGPeRkNBK01NXCqxsANbrb_LPC5H91gNo5A1UmwLOmcQ-MqmCbrgPKLga1McW_B0GjFr8eegIf7Yo--PC28xxSFwbsjVpodDhyXPqU14qg2yHJ4Y7H-Xm5gUBsyb3IJofxIN03v4j9dOnAf45lzrHYyIo-j8ZmvLqlBkX2nasCEOBGgrF2LzrtHwj2lRLz0AXiKtBaLQ";

/**
 * Check if we're running on localhost.
 */
function isLocalhost(): boolean {
  if (typeof window === "undefined") return false;
  const origin = window.location.origin;
  return origin.includes("localhost") || origin.includes("127.0.0.1");
}

/**
 * Access token for local development.
 * Uses VITE_ACCESS_TOKEN if set, otherwise uses default local dev token on localhost.
 */
const accessToken =
  import.meta.env.VITE_ACCESS_TOKEN || (isLocalhost() ? LOCAL_DEV_TOKEN : "");

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
  /** Access token for local development (skips Auth0 login) */
  accessToken,
  /** Whether Auth0 authentication is enabled */
  authEnabled,
};

/** Fake user shown when using access token for local development */
export const devUser = {
  name: import.meta.env.VITE_DEV_USER_NAME || "Anand Chowdhary",
  email: import.meta.env.VITE_DEV_USER_EMAIL || "anand@chowdhary.org",
  picture: "",
};
