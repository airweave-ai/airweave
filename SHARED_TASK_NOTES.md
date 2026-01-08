# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Real-time Sync (Phase 2) - COMPLETE**
  - Created `frontend-v2/src/stores/entity-state-store.ts` - Zustand store with localStorage persistence for entity/sync state
  - Created `frontend-v2/src/stores/sync-state-store.ts` - SSE subscription management with health checks
  - Created `frontend-v2/src/services/syncStorageService.ts` - Session storage for sync progress recovery
  - Created `frontend-v2/src/services/entityStateMediator.ts` - Coordinates state between stores and API
  - Created `frontend-v2/src/services/index.ts` - Service exports
  - Features implemented:
    - SSE subscriptions to `/sync/job/{jobId}/subscribe` and `/sync/job/{jobId}/subscribe-state`
    - Automatic subscription cleanup on stale connections (1 hour timeout)
    - Session storage recovery for page reloads
    - Local state caching with localStorage persistence
    - Health check interval for detecting stale subscriptions

## Next Suggested Tasks (in priority order)

1. **Validation System - Phase 4 (HIGH)**
   - Port `lib/validation/types.ts`
   - Port `lib/validation/rules.ts` (40+ rules)
   - Create ValidatedInput for TanStack Form

2. **QueryTool Enhancement - Phase 5 (MEDIUM)**
   - Port full QueryTool component
   - Port LiveApiDoc component

3. **SemanticMcp Page - Phase 6 (MEDIUM)**
   - Create `/semantic-mcp` route
   - Implement MCP authentication flow

4. **Billing Management Page (MEDIUM)**
   - Create `/$orgSlug/settings/billing` for managing subscriptions

## Blocked Tasks

- **Edit Member Roles** - Requires backend `PATCH /organizations/{id}/members/{memberId}` endpoint

## How to Use Real-time Sync

The real-time sync system is now available. To use it in a component:

```typescript
import { EntityStateMediator } from "@/services/entityStateMediator";
import { useSyncProgress } from "@/stores/sync-state-store";
import { useEntityState } from "@/stores/entity-state-store";

// In a component that shows sync progress:
function SourceConnectionCard({ connectionId }: { connectionId: string }) {
  const { connection, lastSyncJob, isActive } = useEntityState(connectionId);
  const { progress, status } = useSyncProgress(connectionId);

  // Initialize mediator on mount
  useEffect(() => {
    const mediator = new EntityStateMediator(connectionId);
    const init = async () => {
      const token = await getAccessTokenSilently();
      const orgId = currentOrg.id;
      await mediator.initialize(token, orgId);
    };
    init();
    return () => { mediator.cleanup(); };
  }, [connectionId]);

  // When starting a sync:
  const handleSync = async () => {
    const job = await runSourceConnectionSync(token, orgId, connectionId);
    const mediator = new EntityStateMediator(connectionId);
    await mediator.subscribeToJobUpdates(job.id, token, orgId);
  };
}
```

## Key Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Old validation rules: `frontend/src/lib/validation/rules.ts`
- Old QueryTool: `frontend/src/components/query/QueryTool.tsx`
