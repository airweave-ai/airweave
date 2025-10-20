import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "@/App";
import "@/index.css";
import { ThemeProvider } from "@/lib/theme-provider";
import { Auth0ProviderWithNavigation } from "@/lib/auth0-provider";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { setTokenProvider } from "@/lib/api";
import { PostHogProvider } from "@/lib/posthog-provider";

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
    <PostHogProvider>
      <ThemeProvider defaultTheme="dark" storageKey="airweave-ui-theme">
        <BrowserRouter>
          <Auth0ProviderWithNavigation>
            <AuthProvider>
              <ApiAuthConnector>
                <App />
              </ApiAuthConnector>
            </AuthProvider>
          </Auth0ProviderWithNavigation>
        </BrowserRouter>
      </ThemeProvider>
    </PostHogProvider>
  </React.StrictMode>
);
