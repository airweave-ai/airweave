/**
 * Prefetches org-scoped data in the background once the organization
 * context is available, ensuring instant loading when users navigate
 * to API Keys, Auth Providers, etc.
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

export function OrgDataPreloader() {
  const { organization } = useOrg();
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const lastPrefetchedOrgId = useRef<string | null>(null);

  useEffect(() => {
    if (!organization?.id) return;

    const orgId = organization.id;

    if (lastPrefetchedOrgId.current === orgId) return;
    lastPrefetchedOrgId.current = orgId;

    const prefetchData = async () => {
      try {
        const token = await getAccessTokenSilently();

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
          staleTime: 1000 * 60 * 5,
        });

        queryClient.prefetchQuery({
          queryKey: queryKeys.authProviders.list(orgId),
          queryFn: () => fetchAuthProviders(token, orgId),
          staleTime: 1000 * 60 * 5,
        });

        queryClient.prefetchQuery({
          queryKey: queryKeys.authProviders.connections(orgId),
          queryFn: () => fetchAuthProviderConnections(token, orgId),
          staleTime: 1000 * 60 * 5,
        });
      } catch (error) {
        console.debug("Org data prefetch failed:", error);
      }
    };

    prefetchData();
  }, [organization?.id, getAccessTokenSilently, queryClient]);

  return null;
}
