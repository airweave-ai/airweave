import * as React from 'react';
import { Auth0Provider, useAuth0 } from '@auth0/auth0-react';
import { getAuthCallbackRedirectTarget } from './auth-redirects';
import type { AuthStoreSnapshot } from './auth-store';
import { resetAuthStoreSnapshot, setAuthStoreSnapshot } from './auth-store';
import type { AppState, User as AuthUser } from '@auth0/auth0-react';
import { env } from '@/shared/config/env';

export interface AuthLoginOptions {
  invitation?: string;
  organizationName?: string;
  organization?: string;
  returnTo?: string;
}

interface AuthStateSharedFields {
  error: Error | null;
  getAccessToken: () => Promise<string | null>;
  login: (options?: AuthLoginOptions) => Promise<void>;
  logout: () => void;
}

export type AuthLoadingState = AuthStateSharedFields & {
  isAuthenticated: false;
  isLoading: true;
  status: 'loading';
  user: null;
};

export type AuthUnauthenticatedState = AuthStateSharedFields & {
  isAuthenticated: false;
  isLoading: false;
  status: 'unauthenticated';
  user: null;
};

export type AuthAuthenticatedState = AuthStateSharedFields & {
  isAuthenticated: true;
  isLoading: false;
  status: 'authenticated';
  user: AuthUser;
};

export type AuthState =
  | AuthLoadingState
  | AuthUnauthenticatedState
  | AuthAuthenticatedState;
export type AuthResolvedState =
  | AuthUnauthenticatedState
  | AuthAuthenticatedState;

export type { AuthUser };

const AuthContext = React.createContext<AuthState | undefined>(undefined);

const authConfig = {
  authEnabled: env.VITE_ENABLE_AUTH,
  audience: env.VITE_AUTH0_AUDIENCE ?? '',
  clientId: env.VITE_AUTH0_CLIENT_ID ?? '',
  domain: env.VITE_AUTH0_DOMAIN ?? '',
};

const devUser = {
  name: 'Developer',
  email: 'dev@example.com',
  is_admin: env.VITE_DEV_IS_ADMIN ?? true,
};

const disabledAuthState: AuthState = {
  error: null,
  getAccessToken: () => Promise.resolve(null),
  isAuthenticated: true,
  isLoading: false,
  login: () => Promise.resolve(),
  logout: () => {},
  status: 'authenticated',
  user: devUser,
};

function createAuthState({
  error,
  getAccessToken,
  isAuthenticated,
  isLoading,
  login,
  logout,
  user,
}: {
  error: Error | null;
  getAccessToken: () => Promise<string | null>;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (options?: AuthLoginOptions) => Promise<void>;
  logout: () => void;
  user: AuthUser | undefined;
}): AuthState {
  const sharedFields: AuthStateSharedFields = {
    error,
    getAccessToken,
    login,
    logout,
  };

  if (isLoading) {
    return {
      ...sharedFields,
      isAuthenticated: false,
      isLoading: true,
      status: 'loading',
      user: null,
    };
  }

  if (!isAuthenticated) {
    return {
      ...sharedFields,
      isAuthenticated: false,
      isLoading: false,
      status: 'unauthenticated',
      user: null,
    };
  }

  if (!user) {
    return {
      ...sharedFields,
      isAuthenticated: false,
      isLoading: true,
      status: 'loading',
      user: null,
    };
  }

  return {
    ...sharedFields,
    isAuthenticated: true,
    isLoading: false,
    status: 'authenticated',
    user,
  };
}

function AuthSnapshotReadyBoundary({
  children,
  value,
}: React.PropsWithChildren<{ value: AuthState }>) {
  const snapshot = React.useMemo<AuthStoreSnapshot>(
    () => ({
      getAccessToken: value.getAccessToken,
      isAuthenticated: value.isAuthenticated,
      isLoading: value.isLoading,
    }),
    [value.getAccessToken, value.isAuthenticated, value.isLoading],
  );
  const [readySnapshot, setReadySnapshot] =
    React.useState<AuthStoreSnapshot | null>(null);

  React.useLayoutEffect(() => {
    setAuthStoreSnapshot(snapshot);
    setReadySnapshot(snapshot);
  }, [snapshot]);

  React.useEffect(() => {
    return () => {
      resetAuthStoreSnapshot();
    };
  }, []);

  if (readySnapshot !== snapshot) {
    return null;
  }

  return children;
}

function StaticAuthProvider({
  children,
  value,
}: React.PropsWithChildren<{ value: AuthState }>) {
  return (
    <AuthContext.Provider value={value}>
      <AuthSnapshotReadyBoundary value={value}>
        {children}
      </AuthSnapshotReadyBoundary>
    </AuthContext.Provider>
  );
}

function getCacheLocation(domain: string): 'memory' | 'localstorage' {
  return domain.endsWith('.auth0.com') ? 'localstorage' : 'memory';
}

function getReturnTo(returnTo?: string) {
  if (returnTo) {
    return returnTo;
  }

  return window.location.href;
}

function AuthStateProvider({ children }: React.PropsWithChildren) {
  const {
    error,
    getAccessTokenSilently,
    isAuthenticated,
    isLoading,
    loginWithRedirect,
    logout: auth0Logout,
    user,
  } = useAuth0();

  const getAccessToken = React.useCallback(async () => {
    if (!isAuthenticated) {
      return null;
    }

    try {
      return await getAccessTokenSilently();
    } catch {
      return null;
    }
  }, [getAccessTokenSilently, isAuthenticated]);

  const login = React.useCallback(
    async (options?: AuthLoginOptions) => {
      const returnTo = getReturnTo(options?.returnTo);

      await loginWithRedirect({
        appState: {
          organizationName: options?.organizationName,
          returnTo,
        },
        authorizationParams:
          options?.invitation && options.organization
            ? {
                invitation: options.invitation,
                organization: options.organization,
              }
            : undefined,
      });
    },
    [loginWithRedirect],
  );

  const logout = React.useCallback(() => {
    auth0Logout({
      logoutParams: {
        returnTo: window.location.origin,
      },
    });
  }, [auth0Logout]);

  const value = React.useMemo<AuthState>(
    () =>
      createAuthState({
        error: error ?? null,
        getAccessToken,
        isAuthenticated,
        isLoading,
        login,
        logout,
        user: user ?? undefined,
      }),
    [error, getAccessToken, isAuthenticated, isLoading, login, logout, user],
  );

  return (
    <AuthContext.Provider value={value}>
      <AuthSnapshotReadyBoundary value={value}>
        {children}
      </AuthSnapshotReadyBoundary>
    </AuthContext.Provider>
  );
}

type AuthProviderProps = React.PropsWithChildren<{
  callbackPath: string;
  defaultReturnTo: string;
  onRedirect: (returnTo: string) => void;
  organizationNameSearchParam: string;
  redirectSearchParam: string;
}>;

export function AuthProvider({
  callbackPath,
  children,
  defaultReturnTo,
  onRedirect,
  organizationNameSearchParam,
  redirectSearchParam,
}: AuthProviderProps) {
  if (!authConfig.authEnabled) {
    return (
      <StaticAuthProvider value={disabledAuthState}>
        {children}
      </StaticAuthProvider>
    );
  }

  const onRedirectCallback = (appState?: AppState) => {
    const organizationName =
      typeof appState?.organizationName === 'string'
        ? appState.organizationName
        : undefined;
    const returnTo =
      typeof appState?.returnTo === 'string'
        ? appState.returnTo
        : defaultReturnTo;

    onRedirect(
      getAuthCallbackRedirectTarget({
        callbackPath,
        searchParams: {
          [organizationNameSearchParam]: organizationName,
          [redirectSearchParam]: returnTo,
        },
      }),
    );
  };

  return (
    <Auth0Provider
      authorizationParams={{
        audience: authConfig.audience,
        redirect_uri: `${window.location.origin}${callbackPath}`,
        scope: 'openid profile email',
      }}
      cacheLocation={getCacheLocation(authConfig.domain)}
      clientId={authConfig.clientId}
      domain={authConfig.domain}
      onRedirectCallback={onRedirectCallback}
    >
      <AuthStateProvider>{children}</AuthStateProvider>
    </Auth0Provider>
  );
}

export function useAuth() {
  const context = React.useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }

  return context;
}
