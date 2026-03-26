import { createStore } from 'zustand/vanilla';
import { env } from '@/shared/config/env';

// Bridge auth state from React into non-React code.
//
// We cannot call `useAuth()` from the generated API client auth callback or from
// route/bootstrap code that runs outside React render. This store holds a small,
// non-persistent snapshot of auth state so those places can safely read whether
// auth is ready and fetch the latest access token.
//
// `AuthSnapshotReadyBoundary` in `auth.tsx` keeps this snapshot in sync before
// the router subtree renders, which avoids loader/API races during initial app
// bootstrap. In auth-disabled local development we expose a resolved snapshot so
// API calls can proceed without waiting for Auth0.

export interface AuthStoreSnapshot {
  getAccessToken: () => Promise<string | null>;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const defaultAuthStoreSnapshot: AuthStoreSnapshot = {
  getAccessToken: () => Promise.resolve(null),
  isAuthenticated: !env.VITE_ENABLE_AUTH,
  isLoading: false,
};

interface AuthStoreState {
  snapshot: AuthStoreSnapshot;
  resetSnapshot: () => void;
  setSnapshot: (snapshot: AuthStoreSnapshot) => void;
}

export const authStore = createStore<AuthStoreState>()((set) => ({
  snapshot: defaultAuthStoreSnapshot,
  resetSnapshot: () => {
    set({ snapshot: defaultAuthStoreSnapshot });
  },
  setSnapshot: (snapshot) => {
    set({ snapshot });
  },
}));

export function getAuthStoreSnapshot() {
  return authStore.getState().snapshot;
}

export function setAuthStoreSnapshot(snapshot: AuthStoreSnapshot) {
  authStore.getState().setSnapshot(snapshot);
}

export function resetAuthStoreSnapshot() {
  authStore.getState().resetSnapshot();
}
