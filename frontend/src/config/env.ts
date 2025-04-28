interface Env {
  VITE_API_URL: string;
  VITE_ACCESS_TOKEN?: string;
  VITE_LOCAL_DEVELOPMENT: boolean;
  VITE_ENABLE_AUTH?: string;
}

// Define the window.ENV type
declare global {
  interface Window {
    ENV?: {
      API_URL: string;
      LOCAL_DEVELOPMENT?: boolean;
      ENABLE_AUTH?: string;
    };
  }
}

export const env: Env = {
  // Use runtime config if available, otherwise fall back to Vite env vars
  VITE_API_URL: window.ENV?.API_URL || import.meta.env.VITE_API_URL || 'http://localhost:8001',
  VITE_ACCESS_TOKEN: import.meta.env.VITE_ACCESS_TOKEN || '',
  VITE_LOCAL_DEVELOPMENT: window.ENV?.LOCAL_DEVELOPMENT ||
    import.meta.env.VITE_LOCAL_DEVELOPMENT === 'true' ||
    (import.meta.env.MODE === 'development'),
  VITE_ENABLE_AUTH: window.ENV?.ENABLE_AUTH || import.meta.env.VITE_ENABLE_AUTH || 'true',
};
