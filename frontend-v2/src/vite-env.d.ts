/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Access token for local development (bypasses Auth0 login) */
  readonly VITE_ACCESS_TOKEN?: string;
  /** Set to 'false' to disable Auth0 authentication */
  readonly VITE_ENABLE_AUTH?: string;
  /** API base URL */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
