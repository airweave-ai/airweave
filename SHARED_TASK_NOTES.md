# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- Integrated usage checks into key UI components for billing enforcement:
  - **Sidebar Create Collection button** (`frontend-v2/src/components/app-sidebar.tsx`) - disabled when `sourceConnectionsAllowed` or `entitiesAllowed` is false, with tooltip showing limit message
  - **Add Source button** (`frontend-v2/src/features/collections/components/source-connections-list.tsx`) - both the empty state and list views are disabled when `sourceConnectionsAllowed` is false
  - **Invite Members button** (`frontend-v2/src/routes/$orgSlug/settings/members.tsx`) - disabled when `teamMembersAllowed` is false
  - **Search box** (`frontend-v2/src/features/search/components/search-box.tsx`) - refactored to use centralized `useUsageChecks()` hook instead of local API calls, reducing redundant requests

## Next Suggested Task

**Mark Phase 1 "Implement strict blocking throughout app" as complete** in MIGRATION_SPEC.md

The billing enforcement UI integration is now complete. All key actions are gated by usage checks:
- Creating collections
- Adding source connections
- Inviting team members
- Running queries

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
