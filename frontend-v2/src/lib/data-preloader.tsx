import { useIsRestoring, useQueryClient } from "@tanstack/react-query";
import { ReactNode, useEffect, useRef, useState } from "react";

import {
  fetchApiKeys,
  fetchAuthProviderConnections,
  fetchAuthProviders,
  type APIKey,
} from "./api";
import { useAuth0 } from "./auth-provider";

const API_KEYS_PAGE_SIZE = 20;

interface DataPreloaderProps {
  children: ReactNode;
}

// Minimum time before showing loading indicator (prevents flash for fast loads)
const LOADING_DELAY_MS = 50;

// Maximum time to wait for preloading before giving up and rendering anyway
const LOADING_TIMEOUT_MS = 10_000;

/**
 * Preloads commonly needed data after authentication.
 * Waits for IndexedDB cache restoration, then:
 * - If data is cached: renders immediately (instant load)
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

  // Check if cache is being restored from IndexedDB
  const isRestoring = useIsRestoring();

  // Check if we have cached data (only valid after restoration completes)
  const hasApiKeysCache =
    !isRestoring &&
    queryClient.getQueryData(["api-keys", "list"]) !== undefined;
  const hasAuthProvidersCache =
    !isRestoring && queryClient.getQueryData(["auth-providers"]) !== undefined;
  const hasAuthProviderConnectionsCache =
    !isRestoring &&
    queryClient.getQueryData(["auth-provider-connections"]) !== undefined;

  // Delay showing the loading indicator to prevent flash
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

  // Timeout: give up after 10 seconds and render children anyway
  useEffect(() => {
    if (!isRestoring && !isFetching) return;

    const timeout = setTimeout(() => {
      console.debug("Data preloading timed out after 10s, rendering anyway");
      setTimedOut(true);
    }, LOADING_TIMEOUT_MS);

    return () => clearTimeout(timeout);
  }, [isRestoring, isFetching]);

  useEffect(() => {
    // Wait for cache restoration to complete
    if (isRestoring) return;

    // Only prefetch once
    if (hasStartedPreloading.current) return;
    hasStartedPreloading.current = true;

    // If we already have all caches, just do a background refresh (non-blocking)
    const hasAllCaches =
      hasApiKeysCache &&
      hasAuthProvidersCache &&
      hasAuthProviderConnectionsCache;
    if (hasAllCaches) {
      getAccessTokenSilently().then((token) => {
        queryClient.prefetchInfiniteQuery({
          queryKey: ["api-keys", "list"],
          queryFn: ({ pageParam = 0 }) =>
            fetchApiKeys(token, pageParam, API_KEYS_PAGE_SIZE),
          initialPageParam: 0,
          getNextPageParam: (lastPage: APIKey[], allPages: APIKey[][]) => {
            if (!lastPage || lastPage.length < API_KEYS_PAGE_SIZE)
              return undefined;
            return allPages.flat().length;
          },
          staleTime: 1000 * 60 * 5,
        });
        queryClient.prefetchQuery({
          queryKey: ["auth-providers"],
          queryFn: () => fetchAuthProviders(token),
          staleTime: 1000 * 60 * 5,
        });
        queryClient.prefetchQuery({
          queryKey: ["auth-provider-connections"],
          queryFn: () => fetchAuthProviderConnections(token),
          staleTime: 1000 * 60 * 5,
        });
      });
      return;
    }

    // No cache - fetch data
    setIsFetching(true);
    const prefetchData = async () => {
      try {
        const token = await getAccessTokenSilently();

        await Promise.all([
          queryClient.prefetchInfiniteQuery({
            queryKey: ["api-keys", "list"],
            queryFn: ({ pageParam = 0 }) =>
              fetchApiKeys(token, pageParam, API_KEYS_PAGE_SIZE),
            initialPageParam: 0,
            getNextPageParam: (lastPage: APIKey[], allPages: APIKey[][]) => {
              if (!lastPage || lastPage.length < API_KEYS_PAGE_SIZE)
                return undefined;
              return allPages.flat().length;
            },
            staleTime: 1000 * 60 * 5,
          }),
          queryClient.prefetchQuery({
            queryKey: ["auth-providers"],
            queryFn: () => fetchAuthProviders(token),
            staleTime: 1000 * 60 * 5,
          }),
          queryClient.prefetchQuery({
            queryKey: ["auth-provider-connections"],
            queryFn: () => fetchAuthProviderConnections(token),
            staleTime: 1000 * 60 * 5,
          }),
        ]);
      } catch (error) {
        console.debug("Data preloading failed:", error);
      } finally {
        setIsFetching(false);
      }
    };

    prefetchData();
  }, [
    queryClient,
    getAccessTokenSilently,
    isRestoring,
    hasApiKeysCache,
    hasAuthProvidersCache,
    hasAuthProviderConnectionsCache,
  ]);

  // Show loading only after delay (prevents flash for fast loads)
  if (showLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Still loading but under threshold - render nothing to prevent flash
  if (isLoading) {
    return null;
  }

  return <>{children}</>;
}
