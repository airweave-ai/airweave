import { env } from '@/shared/config/env';

// Auth0 React keeps token access behind React context/hooks, but our router
// guards and generated API client also need auth access outside React.
// This bridge stores only the current auth accessors/state in memory so
// non-React code can ask for a token without trying to use hooks.
// Auth0 have explicitly discouraged exposing a global token getter from the
// React SDK, so we should not expect an official fix here:
// https://gist.github.com/adamjmcgrath/0ed6a04047aad16506ca24d85f1b2a5c

export interface AuthBridgeSnapshot {
  getAccessToken: () => Promise<string | null>;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const defaultAuthBridgeSnapshot: AuthBridgeSnapshot = {
  getAccessToken: () => Promise.resolve(null),
  isAuthenticated: !env.VITE_ENABLE_AUTH,
  isLoading: false,
};

let authBridgeSnapshot = defaultAuthBridgeSnapshot;

export function getAuthBridgeSnapshot() {
  return authBridgeSnapshot;
}

export function setAuthBridgeSnapshot(nextSnapshot: AuthBridgeSnapshot) {
  authBridgeSnapshot = nextSnapshot;
}

export function resetAuthBridgeSnapshot() {
  authBridgeSnapshot = defaultAuthBridgeSnapshot;
}
