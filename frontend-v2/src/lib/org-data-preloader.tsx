/**
 * Org-scoped data preloader
 *
 * Prefetches commonly needed org-scoped data in the background once
 * the organization context is available. This ensures instant loading
 * when users navigate to API Keys, Auth Providers, etc.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import {
  fetchApiKeys,
  fetchAuthProviderConnections,
  fetchAuthProviders,
  type APIKey,
} from "./api";
import { useAuth0 } from "./auth-provider";
import { useOrg } from "./org-context";
import { queryKeys } from "./query-keys";

const API_KEYS_PAGE_SIZE = 20;

/**
 * Prefetches org-scoped data in the background.
 * Renders nothing - just triggers prefetch queries.
 */
export function OrgDataPreloader() {
  const { organization } = useOrg();
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const lastPrefetchedOrgId = useRef<string | null>(null);

  useEffect(() => {
    // Wait for organization to be available
    if (!organization?.id) return;

    const orgId = organization.id;

    // Skip if we already prefetched for this org
    if (lastPrefetchedOrgId.current === orgId) return;
    lastPrefetchedOrgId.current = orgId;

    // Prefetch org-scoped data in background
    const prefetchData = async () => {
      try {
        const token = await getAccessTokenSilently();

        // Prefetch API keys (infinite query)
        queryClient.prefetchInfiniteQuery({
          queryKey: queryKeys.apiKeys.list(orgId),
          queryFn: ({ pageParam = 0 }) =>
            fetchApiKeys(token, orgId, pageParam, API_KEYS_PAGE_SIZE),
          initialPageParam: 0,
          getNextPageParam: (lastPage: APIKey[], allPages: APIKey[][]) => {
            if (!lastPage || lastPage.length < API_KEYS_PAGE_SIZE)
              return undefined;
            return allPages.flat().length;
          },
          staleTime: 1000 * 60 * 5, // 5 minutes
        });

        // Prefetch auth providers
        queryClient.prefetchQuery({
          queryKey: queryKeys.authProviders.list(orgId),
          queryFn: () => fetchAuthProviders(token, orgId),
          staleTime: 1000 * 60 * 5, // 5 minutes
        });

        // Prefetch auth provider connections
        queryClient.prefetchQuery({
          queryKey: queryKeys.authProviders.connections(orgId),
          queryFn: () => fetchAuthProviderConnections(token, orgId),
          staleTime: 1000 * 60 * 5, // 5 minutes
        });
      } catch (error) {
        // Silently fail - prefetching is non-critical
        console.debug("Org data prefetch failed:", error);
      }
    };

    prefetchData();
  }, [organization?.id, getAccessTokenSilently, queryClient]);

  // Renders nothing - just prefetches data
  return null;
}
