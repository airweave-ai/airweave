import * as React from 'react';
import { Auth0Provider, useAuth0 } from '@auth0/auth0-react';
import { resetAuthBridgeSnapshot, setAuthBridgeSnapshot } from './auth-bridge';
import type { AppState, User } from '@auth0/auth0-react';
import { env } from '@/shared/config/env';

export interface AuthState {
  error: Error | null;
  getAccessToken: () => Promise<string | null>;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (returnTo?: string) => Promise<void>;
  logout: () => void;
  user: User | null;
}

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
  user: devUser,
};

function AuthBridgeSync({ value }: { value: AuthState }) {
  React.useEffect(() => {
    setAuthBridgeSnapshot({
      getAccessToken: value.getAccessToken,
      isAuthenticated: value.isAuthenticated,
      isLoading: value.isLoading,
    });

    return () => {
      resetAuthBridgeSnapshot();
    };
  }, [value.getAccessToken, value.isAuthenticated, value.isLoading]);

  return null;
}

function StaticAuthProvider({
  children,
  value,
}: React.PropsWithChildren<{ value: AuthState }>) {
  return (
    <AuthContext.Provider value={value}>
      <AuthBridgeSync value={value} />
      {children}
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
    async (returnTo?: string) => {
      await loginWithRedirect({
        appState: {
          returnTo: getReturnTo(returnTo),
        },
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
    () => ({
      error: error ?? null,
      getAccessToken,
      isAuthenticated,
      isLoading,
      login,
      logout,
      user: user ?? null,
    }),
    [error, getAccessToken, isAuthenticated, isLoading, login, logout, user],
  );

  return (
    <AuthContext.Provider value={value}>
      <AuthBridgeSync value={value} />
      {children}
    </AuthContext.Provider>
  );
}

type AuthProviderProps = React.PropsWithChildren<{
  callbackPath: string;
  defaultReturnTo: string;
  onRedirect: (returnTo: string) => void;
}>;

export function AuthProvider({
  callbackPath,
  children,
  defaultReturnTo,
  onRedirect,
}: AuthProviderProps) {
  if (!authConfig.authEnabled) {
    return (
      <StaticAuthProvider value={disabledAuthState}>
        {children}
      </StaticAuthProvider>
    );
  }

  const onRedirectCallback = (appState?: AppState) => {
    const returnTo =
      typeof appState?.returnTo === 'string' ? appState.returnTo : defaultReturnTo;

    onRedirect(returnTo);
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
      useRefreshTokens
      useRefreshTokensFallback
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
