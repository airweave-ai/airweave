import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "@/App";
import "@/index.css";
import { ThemeProvider } from "@/lib/theme-provider";
import { Auth0ProviderWithNavigation } from "@/lib/auth0-provider";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { setTokenProvider } from "@/lib/api";
import { PostHogProvider } from "posthog-js/react";
import { env } from "@/config/env";

// Component to initialize the API with auth
function ApiAuthConnector({ children }: { children: React.ReactNode }) {
  const auth = useAuth();

  useEffect(() => {
    console.log("Setting up token provider with auth context");

    // Set the token provider to use auth context
    setTokenProvider({
      getToken: async () => await auth.getToken(),
      clearToken: () => {
        // Use auth context's clearToken
        auth.clearToken();
        console.log("Token cleared via auth context");
      },
      isReady: () => auth.isReady()
    });

    // Log the auth state for debugging
    console.log("Auth state:", {
      isLoading: auth.isLoading,
      isAuthenticated: auth.isAuthenticated,
      tokenInitialized: auth.tokenInitialized
    });
  }, [auth]);

  return <>{children}</>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="dark" storageKey="airweave-ui-theme">
      <BrowserRouter>
        <Auth0ProviderWithNavigation>
          <AuthProvider>
            <PostHogProvider
              apiKey={env.VITE_POSTHOG_KEY || ''}
              options={{
                api_host: env.VITE_POSTHOG_HOST || '',
                loaded: (posthog) => {
                  // Disable capturing in development or if analytics disabled
                  if (
                    env.VITE_ENABLE_ANALYTICS !== 'true' || 
                    (env.VITE_LOCAL_DEVELOPMENT && 
                     window.location.host.includes('localhost'))
                  ) {
                    posthog.opt_out_capturing();
                  }
                }
              }}
            >
              <ApiAuthConnector>
                <App />
              </ApiAuthConnector>
            </PostHogProvider>
          </AuthProvider>
        </Auth0ProviderWithNavigation>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
);
