import { useQuery } from "@tanstack/react-query";

import { fetchSourceConnections } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";

/**
 * Fetches source connections for a specific collection.
 * Uses React Query for caching - results are cached per collection for 30 seconds.
 */
export function useCollectionSourceConnections(collectionReadableId: string) {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const orgId = organization?.id ?? "";

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.sourceConnections.list(orgId, collectionReadableId),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSourceConnections(token, orgId, collectionReadableId);
    },
    enabled: !!orgId && !!collectionReadableId,
    staleTime: 30_000,
  });

  return {
    connections: data ?? [],
    isLoading,
  };
}

