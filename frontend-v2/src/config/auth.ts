// Auth0 configuration

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
  "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IlkzN3F5b1NieEIzbzhFdlQtZ2tjVSJ9.eyJodHRwczovL2FwcC5haXJ3ZWF2ZS5haS9lbWFpbCI6ImFuYW5kQGNob3dkaGFyeS5vcmciLCJpc3MiOiJodHRwczovL2FpcndlYXZlLnVzLmF1dGgwLmNvbS8iLCJzdWIiOiJnb29nbGUtb2F1dGgyfDExNTE3NDgwNDU1MDk5NTEzMDkyMCIsImF1ZCI6WyJodHRwczovL2FwcC5haXJ3ZWF2ZS5haS8iLCJodHRwczovL2FpcndlYXZlLnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE3NjcyMzI4NTgsImV4cCI6MTc2NzMxOTI1OCwic2NvcGUiOiJvcGVuaWQgcHJvZmlsZSBlbWFpbCIsImF6cCI6ImpYeUxSV1I5bGcwa1pRdlZqcEoyWW1pU1luMVV0VVN3In0.Qpf5O561jFp42CCE5zeJcbughRmVFxeqm-3jze43GtkxZtuFoF1RoD-rcA0yg0O_baB7r4ISIvg0geAwETf5v0SOmGoPa_3blVHWDGzd4vPWGEnxEORhZD30pf4DvwyMcYkVZeFoXHJCGdjxDAZjdO62NQNZqQEW0GwBLkLqSZaFZaGlUYXoaMXEFTh9NmFW5P0ysw0M38FoCUpkn2btWWBsFqpnqaLOWOwT6-FvBy3QPesCblo0qJ75gRfnjV04bM5D1VvdTuqNO9bneeHnbXPwQY7_v9AwT21MFtXwL7raEm0HMu-7WRAf0Vu_X_NYv60-5C3-o0Z9n2Z5UpCP8w";

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
  domain: "airweave.us.auth0.com",
  clientId: "jXyLRWR9lg0kZQvVjpJ2YmiSYn1UtUSw",
  audience: "https://app.airweave.ai/",
  redirectUri: getRedirectUrl(),
  /** Access token for local development (skips Auth0 login) */
  accessToken,
  /** Whether Auth0 authentication is enabled */
  authEnabled,
};

/** Fake user shown when using access token for local development */
export const devUser = {
  name: "Anand Chowdhary",
  email: "anand@chowdhary.org",
  picture: "",
};
