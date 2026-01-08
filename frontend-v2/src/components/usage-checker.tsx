import { useEffect, useRef } from "react";

import { authConfig } from "@/config/auth";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { COMMON_ACTIONS, useUsageStore } from "@/stores/usage-store";

export function UsageChecker() {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const checkActions = useUsageStore((state) => state.checkActions);
  const clearCache = useUsageStore((state) => state.clearCache);
  const prevOrgId = useRef<string | null>(null);

  useEffect(() => {
    if (organization?.id && prevOrgId.current !== organization.id) {
      if (prevOrgId.current !== null) {
        clearCache();
      }
      prevOrgId.current = organization.id;
    }
  }, [organization?.id, clearCache]);

  useEffect(() => {
    if (!authConfig.authEnabled || !organization?.id) {
      return;
    }

    async function check() {
      try {
        const token = await getAccessTokenSilently();
        await checkActions(token, COMMON_ACTIONS);
      } catch {
        // Non-critical - store defaults to allowing actions
      }
    }

    check();
  }, [organization?.id, getAccessTokenSilently, checkActions]);

  return null;
}
