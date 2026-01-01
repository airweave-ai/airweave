// Auth0 configuration
export const authConfig = {
  domain: "airweave.us.auth0.com",
  clientId: "jXyLRWR9lg0kZQvVjpJ2YmiSYn1UtUSw",
  audience: "https://app.airweave.ai/",
  redirectUri: typeof window !== "undefined" ? window.location.origin : "",
};
