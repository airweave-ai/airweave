# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- Implemented usage action checking infrastructure for billing enforcement:
  - Added `checkActions` and `checkSingleAction` API functions to `frontend-v2/src/lib/api/usage.ts`
  - Created `frontend-v2/src/stores/usage-store.ts` with caching (3s), request deduplication, and org-switch handling
  - Created `frontend-v2/src/components/usage-checker.tsx` that runs on org layout mount
  - Integrated `UsageChecker` into `$orgSlug/route.tsx`
- The store provides `useUsageChecks()` hook with convenience getters for common actions

## Next Suggested Task

**Integrate usage checks into UI components** - HIGH PRIORITY (continuation of billing enforcement)

The usage checking infrastructure is in place. Next step is to integrate it into key UI actions:

1. **Create Collection button** (sidebar) - disable when `sourceConnectionsAllowed` or `entitiesAllowed` is false
2. **Add Source button** (collection detail) - same checks
3. **Invite Members** (members settings) - disable when `teamMembersAllowed` is false
4. **Query execution** (query tool) - disable when `queriesAllowed` is false

Implementation approach:
```tsx
import { useUsageChecks } from "@/stores/usage-store";

const { sourceConnectionsAllowed, sourceConnectionsStatus } = useUsageChecks();

// Disable button and show tooltip when at limit
<Tooltip content={sourceConnectionsStatus?.details?.message}>
  <Button disabled={!sourceConnectionsAllowed}>Create Collection</Button>
</Tooltip>
```

**Edit Member Roles** - MEDIUM PRIORITY (blocked)

NOTE: Requires backend work. The `PATCH /organizations/{id}/members/{memberId}` endpoint doesn't exist yet.

## Other Tasks (in order of priority)

1. Admin Dashboard - Phase 3 (HIGH)
   - `/admin` route with superuser-only access
   - Port AdminDashboard component
2. Real-time Sync - Phase 2 (HIGH)
   - Port `entityStateMediator.ts`
   - Port `syncStorageService.ts`
3. Validation system - Phase 4 (HIGH)
   - Port `lib/validation/types.ts`
   - Port `lib/validation/rules.ts` (40+ rules)
   - Create ValidatedInput for TanStack Form

## Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Usage store: `frontend-v2/src/stores/usage-store.ts`
- Usage checker: `frontend-v2/src/components/usage-checker.tsx`
- Old billing enforcement: `frontend/src/components/DashboardLayout.tsx` (lines 256-307)
- Old MembersSettings: `frontend/src/components/settings/MembersSettings.tsx` (lines 58-60, 99-106)
