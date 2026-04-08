import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "@/App";
import "@/index.css";
import { ThemeProvider } from "@/lib/theme-provider";
import { Auth0ProviderWithNavigation } from "@/lib/auth0-provider";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { setTokenProvider } from "@/lib/api";
import { PostHogProvider } from "@/lib/posthog-provider";

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      refetchOnWindowFocus: false,
    },
  },
});

// Component to initialize the API with auth
function ApiAuthConnector({ children }: { children: React.ReactNode }) {
  const auth = useAuth();

  useEffect(() => {
    setTokenProvider({
      getToken: async () => await auth.getToken(),
      clearToken: () => auth.clearToken(),
      isReady: () => auth.isReady()
    });
  }, [auth]);

  return <>{children}</>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
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
    </QueryClientProvider>
  </React.StrictMode>
);
