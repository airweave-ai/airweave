interface Env {
  VITE_API_URL: string;
  VITE_ACCESS_TOKEN?: string;
  VITE_LOCAL_DEVELOPMENT: boolean;
  VITE_ENABLE_AUTH?: string;
  VITE_POSTHOG_KEY?: string;
  VITE_POSTHOG_HOST?: string;
  VITE_ENABLE_ANALYTICS?: string;
}

// Using the Window interface declaration from vite-env.d.ts
// No need to redeclare it here since it's already in vite-env.d.ts

export const env: Env = {
  // Use runtime config if available, otherwise fall back to Vite env vars
  VITE_API_URL: window.ENV?.API_URL || import.meta.env.VITE_API_URL || 'http://localhost:8001',
  VITE_ACCESS_TOKEN: import.meta.env.VITE_ACCESS_TOKEN || '',
  VITE_LOCAL_DEVELOPMENT: window.ENV?.LOCAL_DEVELOPMENT ||
    import.meta.env.VITE_LOCAL_DEVELOPMENT === 'true' ||
    (import.meta.env.MODE === 'development'),
  VITE_ENABLE_AUTH: window.ENV?.AUTH_ENABLED !== undefined 
    ? window.ENV.AUTH_ENABLED.toString() 
    : import.meta.env.VITE_ENABLE_AUTH || 'true',
  
  // PostHog variables
  VITE_POSTHOG_KEY: import.meta.env.VITE_POSTHOG_KEY || '',
  VITE_POSTHOG_HOST: import.meta.env.VITE_POSTHOG_HOST || '',
  VITE_ENABLE_ANALYTICS: import.meta.env.VITE_ENABLE_ANALYTICS || 'true',
};
