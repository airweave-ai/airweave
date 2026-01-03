import {
  Auth0Provider,
  useAuth0 as useAuth0Hook,
  User,
} from "@auth0/auth0-react";
import { createContext, ReactNode, useContext } from "react";
import { authConfig, devUser, getRedirectUrl } from "../config/auth";
import { DataPreloader } from "./data-preloader";

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Custom auth context for dev mode (when using access token).
 */
interface DevAuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | undefined;
  logout: (options?: { logoutParams?: { returnTo?: string } }) => void;
  loginWithRedirect: () => void;
  getAccessTokenSilently: () => Promise<string>;
}

const DevAuthContext = createContext<DevAuthContextType | null>(null);

/**
 * Custom hook that works for both Auth0 and dev mode.
 * In dev mode (with access token), returns fake user data.
 * In Auth0 mode, delegates to the real useAuth0 hook.
 */
export function useAuth0() {
  const devContext = useContext(DevAuthContext);

  // If we're in dev mode, use the dev context
  if (devContext) {
    return devContext;
  }

  // Otherwise, use the real Auth0 hook
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useAuth0Hook();
}

/**
 * Auth0 provider wrapper that configures authentication for the app.
 * When VITE_ACCESS_TOKEN is set, skips Auth0 and uses dev mode.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  // Don't render Auth0Provider on the server
  if (typeof window === "undefined") {
    return <>{children}</>;
  }

  // Dev mode: Skip Auth0 when access token is provided
  if (!authConfig.authEnabled) {
    const devAuthValue: DevAuthContextType = {
      isAuthenticated: true,
      isLoading: false,
      user: devUser as User,
      logout: () => {
        // Dev mode - no-op
      },
      loginWithRedirect: () => {
        // Dev mode - no-op
      },
      getAccessTokenSilently: async () => {
        return authConfig.accessToken;
      },
    };

    return (
      <DevAuthContext.Provider value={devAuthValue}>
        {children}
      </DevAuthContext.Provider>
    );
  }

  // Production mode: Use Auth0
  return (
    <Auth0Provider
      domain={authConfig.domain}
      clientId={authConfig.clientId}
      authorizationParams={{
        redirect_uri: getRedirectUrl(),
        audience: authConfig.audience,
        scope: "openid profile email",
      }}
      cacheLocation="localstorage"
    >
      {children}
    </Auth0Provider>
  );
}

/**
 * Auth guard component that redirects to login if not authenticated.
 * In dev mode with access token, always renders children without redirect.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();

  // In dev mode, always render children (with preloading)
  if (!authConfig.authEnabled) {
    return <DataPreloader>{children}</DataPreloader>;
  }

  // Show loading state while Auth0 initializes
  if (isLoading) {
    return (
      <div className="bg-background flex h-screen w-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" />
          <p className="text-muted-foreground text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    loginWithRedirect();
    return (
      <div className="bg-background flex h-screen w-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" />
          <p className="text-muted-foreground text-sm">
            Redirecting to login...
          </p>
        </div>
      </div>
    );
  }

  // User is authenticated - preload data and render children
  return <DataPreloader>{children}</DataPreloader>;
}

// Re-export getRedirectUrl for convenience
export { getRedirectUrl };
