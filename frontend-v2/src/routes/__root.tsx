import { QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import {
  HeadContent,
  Outlet,
  Scripts,
  createRootRoute,
  useParams,
} from "@tanstack/react-router";

import { AppRightSidebar } from "../components/app-right-sidebar";
import { AppSidebar } from "../components/app-sidebar";
import { CommandMenu } from "../components/command-menu";
import {
  PageHeaderContent,
  PageHeaderProvider,
} from "../components/ui/page-header";
import { RightSidebarProvider } from "../components/ui/right-sidebar";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "../components/ui/sidebar";
import { Toaster } from "../components/ui/sonner";
import { useThemeEffect } from "../hooks/use-theme-effect";
import { AuthGuard, AuthProvider } from "../lib/auth-provider";
import { PostHogProvider } from "../lib/posthog-provider";
import { CACHE_MAX_AGE, createIDBPersister } from "../lib/query-persister";
import { useUISettingsHydrated } from "../stores/ui-settings";

import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import appCss from "../styles.css?url";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Matches IndexedDB persistence duration
      gcTime: CACHE_MAX_AGE,
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
        rel: "preconnect",
        href: "https://fonts.googleapis.com",
      },
      {
        rel: "preconnect",
        href: "https://fonts.gstatic.com",
        crossOrigin: "anonymous",
      },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Fira+Code:wght@300..700&display=swap",
      },
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
  const isMobile = useIsMobile();
  const params = useParams({ strict: false }) as { orgSlug?: string };
  const hasOrgContext = Boolean(params.orgSlug);

  useThemeEffect();

  // Prevents flash of incorrect state before localStorage hydration
  if (!isHydrated) {
    return null;
  }

  if (!hasOrgContext) {
    return (
      <AuthGuard>
        <Outlet />
        <Toaster />
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <CommandMenu />
      <PageHeaderProvider>
        <SidebarProvider>
          <RightSidebarProvider>
            <AppSidebar />
            <SidebarInset>
              <div
                className={cn(
                  "bg-sidebar h-full px-1",
                  isMobile ? "p-0" : "py-4"
                )}
              >
                <div
                  className={cn(
                    "bg-background border-border/50 flex h-full flex-col border shadow-sm",
                    isMobile ? "rounded-none" : "rounded-lg"
                  )}
                >
                  <header className="flex h-14 shrink-0 items-center border-b px-4">
                    <SidebarTrigger className="mr-1.5 -ml-1" />
                    <PageHeaderContent />
                  </header>
                  <div className="flex-1 overflow-auto pb-16 md:pb-0">
                    <Outlet />
                  </div>
                </div>
              </div>
            </SidebarInset>
            <AppRightSidebar />
          </RightSidebarProvider>
        </SidebarProvider>
      </PageHeaderProvider>
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
        <PostHogProvider>
          <PersistQueryClientProvider
            client={queryClient}
            persistOptions={{
              persister,
              maxAge: CACHE_MAX_AGE,
            }}
          >
            <AuthProvider>{children}</AuthProvider>
          </PersistQueryClientProvider>
        </PostHogProvider>
        <Scripts />
      </body>
    </html>
  );
}
