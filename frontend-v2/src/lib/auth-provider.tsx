import {
  Auth0Provider,
  useAuth0 as useAuth0Hook,
  User,
} from "@auth0/auth0-react";
import { createContext, ReactNode, useContext, useMemo } from "react";
import { authConfig, devUser, getRedirectUrl } from "../config/auth";
import { DataPreloader } from "./data-preloader";

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Custom auth context that unifies dev mode and Auth0 authentication.
 */
interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | undefined;
  logout: (options?: { logoutParams?: { returnTo?: string } }) => void;
  loginWithRedirect: () => void;
  getAccessTokenSilently: () => Promise<string>;
}

const AuthContext = createContext<AuthContextType | null>(null);

/**
 * Hook that provides unified authentication regardless of mode.
 */
export function useAuth0(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth0 must be used within an AuthProvider");
  }
  return context;
}

/**
 * Internal component that bridges Auth0 context to our unified context.
 */
function Auth0Bridge({ children }: { children: ReactNode }) {
  const auth0 = useAuth0Hook();
  return <AuthContext.Provider value={auth0}>{children}</AuthContext.Provider>;
}

/**
 * Auth0 provider wrapper that configures authentication for the app.
 * When VITE_ACCESS_TOKEN is set, skips Auth0 and uses dev mode.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const devAuthValue = useMemo<AuthContextType>(
    () => ({
      isAuthenticated: true,
      isLoading: false,
      user: devUser as User,
      logout: () => {},
      loginWithRedirect: () => {},
      getAccessTokenSilently: async () => authConfig.accessToken,
    }),
    []
  );

  if (typeof window === "undefined") {
    return <>{children}</>;
  }

  if (!authConfig.authEnabled) {
    return (
      <AuthContext.Provider value={devAuthValue}>
        {children}
      </AuthContext.Provider>
    );
  }

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
      <Auth0Bridge>{children}</Auth0Bridge>
    </Auth0Provider>
  );
}

/**
 * Auth guard component that redirects to login if not authenticated.
 * In dev mode with access token, always renders children without redirect.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();

  if (!authConfig.authEnabled) {
    return <DataPreloader>{children}</DataPreloader>;
  }

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

  return <DataPreloader>{children}</DataPreloader>;
}

export { getRedirectUrl };
