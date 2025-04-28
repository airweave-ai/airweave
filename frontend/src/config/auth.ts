// Authentication configuration

// First check runtime config (from window.ENV), then development env vars, then default values
const config = {
  // Whether authentication is enabled
  authEnabled: (window.ENV?.AUTH_ENABLED !== undefined)
    ? window.ENV.AUTH_ENABLED
    : (import.meta.env.VITE_ENABLE_AUTH === 'true') || false,

  // Auth0 configuration
  auth0: {
    domain: window.ENV?.AUTH0_DOMAIN ||
      import.meta.env.VITE_AUTH0_DOMAIN ||
      '',
    clientId: window.ENV?.AUTH0_CLIENT_ID ||
      import.meta.env.VITE_AUTH0_CLIENT_ID ||
      '',
    audience: window.ENV?.AUTH0_AUDIENCE ||
      import.meta.env.VITE_AUTH0_AUDIENCE ||
      ''
  },

  // Whether all auth configuration is valid
  isConfigValid: function() {
    if (!this.authEnabled) return true; // If auth is disabled, config is valid

    return Boolean(
      this.auth0.domain &&
      this.auth0.clientId &&
      this.auth0.audience
    );
  }
};

export default config;
