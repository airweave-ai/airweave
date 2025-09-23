import { useEffect } from 'react';
import { useUsageStore } from '@/lib/stores/usage';
import { useOrganizationStore } from '@/lib/stores/organizations';

/**
 * Component that checks usage limits at the app level.
 * This should be mounted once at the root of the app to avoid duplicate checks.
 */
export const UsageChecker = () => {
  const checkActions = useUsageStore(state => state.checkActions);
  const currentOrganization = useOrganizationStore(state => state.currentOrganization);

  useEffect(() => {
    // Check usage when organization changes or on mount
    if (currentOrganization) {
      console.log('[UsageChecker] Checking usage for organization:', currentOrganization.id);
      checkActions({
        source_connections: 1,
        entities: 1,
        queries: 1,
        team_members: 1
      });
    }
  }, [currentOrganization?.id]); // Only re-check when organization changes

  // This component doesn't render anything
  return null;
};
