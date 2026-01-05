import { useIsRestoring, useQueryClient } from "@tanstack/react-query";
import { ReactNode, useEffect, useRef, useState } from "react";

import { fetchOrganizations } from "./api/organizations";
import { useAuth0 } from "./auth-provider";
import { queryKeys } from "./query-keys";

interface DataPreloaderProps {
  children: ReactNode;
}

const LOADING_DELAY_MS = 50;
const LOADING_TIMEOUT_MS = 10_000;

/**
 * Preloads user-level data (like organizations) after authentication.
 * Org-scoped data is handled by org-scoped routes with proper context.
 *
 * Waits for IndexedDB cache restoration, then:
 * - If data is cached: renders immediately
 * - If no cache: shows loading while fetching essential data
 * - Loading indicator is delayed to prevent flash for fast operations
 */
export function DataPreloader({ children }: DataPreloaderProps) {
  const queryClient = useQueryClient();
  const { getAccessTokenSilently } = useAuth0();
  const hasStartedPreloading = useRef(false);
  const [isFetching, setIsFetching] = useState(false);
  const [showLoading, setShowLoading] = useState(false);
  const [timedOut, setTimedOut] = useState(false);

  const isRestoring = useIsRestoring();

  const hasOrganizationsCache =
    !isRestoring &&
    queryClient.getQueryData(queryKeys.organizations.all) !== undefined;

  const isLoading = (isRestoring || isFetching) && !timedOut;
  useEffect(() => {
    if (!isLoading) {
      setShowLoading(false);
      return;
    }

    const timer = setTimeout(() => {
      setShowLoading(true);
    }, LOADING_DELAY_MS);

    return () => clearTimeout(timer);
  }, [isLoading]);

  useEffect(() => {
    if (!isRestoring && !isFetching) return;

    const timeout = setTimeout(() => {
      console.debug("Data preloading timed out after 10s, rendering anyway");
      setTimedOut(true);
    }, LOADING_TIMEOUT_MS);

    return () => clearTimeout(timeout);
  }, [isRestoring, isFetching]);

  useEffect(() => {
    if (isRestoring) return;

    if (hasStartedPreloading.current) return;
    hasStartedPreloading.current = true;

    if (hasOrganizationsCache) {
      return;
    }

    setIsFetching(true);
    const prefetchData = async () => {
      try {
        const token = await getAccessTokenSilently();

        await queryClient.prefetchQuery({
          queryKey: queryKeys.organizations.all,
          queryFn: () => fetchOrganizations(token),
          staleTime: 1000 * 60 * 5,
        });
      } catch (error) {
        console.debug("Data preloading failed:", error);
      } finally {
        setIsFetching(false);
      }
    };

    prefetchData();
  }, [queryClient, getAccessTokenSilently, isRestoring, hasOrganizationsCache]);

  if (showLoading) {
    return (
      <div className="bg-background flex h-screen w-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="border-primary h-8 w-8 animate-spin rounded-full border-4 border-t-transparent" />
          <p className="text-muted-foreground text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return null;
  }

  return <>{children}</>;
}
