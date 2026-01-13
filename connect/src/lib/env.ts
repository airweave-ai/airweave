// Runtime config type
interface ConnectEnv {
  API_URL: string;
}

// Extend Window interface for runtime config
declare global {
  interface Window {
    __CONNECT_ENV__?: ConnectEnv;
  }
}

/**
 * Get environment configuration.
 * Priority:
 * 1. Runtime injection via window.__CONNECT_ENV__ (from docker-entrypoint.sh)
 * 2. Vite compile-time env vars (import.meta.env.VITE_*)
 * 3. Default values
 */
function getEnv(): ConnectEnv {
  // Browser: check window.__CONNECT_ENV__ first (runtime injection from Docker)
  if (typeof window !== "undefined" && window.__CONNECT_ENV__) {
    return window.__CONNECT_ENV__;
  }

  // Fallback to Vite env vars (compile-time) or defaults
  return {
    API_URL: import.meta.env.VITE_API_URL || "http://localhost:8001",
  };
}

export const env = getEnv();

// Re-export for backwards compatibility
export const VITE_API_URL = env.API_URL;
