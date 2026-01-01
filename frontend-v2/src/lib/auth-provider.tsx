import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import { ReactNode } from "react";
import { authConfig } from "../config/auth";

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Auth0 provider wrapper that configures authentication for the app.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  // Don't render Auth0Provider on the server
  if (typeof window === "undefined") {
    return <>{children}</>;
  }

  return (
    <Auth0Provider
      domain={authConfig.domain}
      clientId={authConfig.clientId}
      authorizationParams={{
        redirect_uri: window.location.origin,
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
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();

  // Show loading state while Auth0 initializes
  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    loginWithRedirect();
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Redirecting to login...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

// Re-export useAuth0 for convenience
export { useAuth0 };

