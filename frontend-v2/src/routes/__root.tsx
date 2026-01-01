import { TanStackDevtools } from "@tanstack/react-devtools";
import { QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import {
  HeadContent,
  Outlet,
  Scripts,
  createRootRoute,
} from "@tanstack/react-router";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";

import { AppRightSidebar } from "../components/app-right-sidebar";
import { AppSidebar } from "../components/app-sidebar";
import { RightSidebarProvider } from "../components/ui/right-sidebar";
import { Toaster } from "../components/ui/sonner";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "../components/ui/sidebar";
import { useThemeEffect } from "../hooks/use-theme-effect";
import { AuthGuard, AuthProvider } from "../lib/auth-provider";
import { CACHE_MAX_AGE, createIDBPersister } from "../lib/query-persister";
import { useUISettingsHydrated } from "../stores/ui-settings";

import appCss from "../styles.css?url";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Keep unused query data in memory for 1 hour (matches IndexedDB persistence)
      gcTime: CACHE_MAX_AGE,
      // Consider data fresh for 5 minutes before refetching in background
      staleTime: 1000 * 60 * 5,
    },
  },
});

const persister = createIDBPersister();

export const Route = createRootRoute({
  head: () => ({
    meta: [
      {
        charSet: "utf-8",
      },
      {
        name: "viewport",
        content: "width=device-width, initial-scale=1",
      },
      {
        title: "Airweave",
      },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
    ],
  }),

  component: RootComponent,
  shellComponent: RootDocument,
});

function RootComponent() {
  const isHydrated = useUISettingsHydrated();

  // Apply theme based on user preference (system/light/dark)
  useThemeEffect();

  // Wait for UI settings to hydrate from localStorage to prevent flash of incorrect state
  if (!isHydrated) {
    return null;
  }

  return (
    <AuthGuard>
      <SidebarProvider>
        <RightSidebarProvider>
          <AppSidebar />
          <SidebarInset>
            <header className="flex h-14 shrink-0 items-center border-b px-4">
              <SidebarTrigger className="-ml-1" />
            </header>
            <div className="flex-1 overflow-auto pb-16 md:pb-0">
              <Outlet />
            </div>
          </SidebarInset>
          <AppRightSidebar />
        </RightSidebarProvider>
      </SidebarProvider>
      <Toaster />
    </AuthGuard>
  );
}

function RootDocument({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        <PersistQueryClientProvider
          client={queryClient}
          persistOptions={{
            persister,
            maxAge: CACHE_MAX_AGE,
          }}
        >
          <AuthProvider>{children}</AuthProvider>
        </PersistQueryClientProvider>
        <TanStackDevtools
          config={{
            position: "bottom-right",
          }}
          plugins={[
            {
              name: "Tanstack Router",
              render: <TanStackRouterDevtoolsPanel />,
            },
          ]}
        />
        <Scripts />
      </body>
    </html>
  );
}
