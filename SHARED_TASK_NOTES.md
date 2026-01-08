# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Admin Dashboard (Phase 3) - COMPLETE**
  - Created `/admin` route at `frontend-v2/src/routes/admin.tsx`
  - Created user API (`frontend-v2/src/lib/api/users.ts`) to fetch current user profile with `is_admin` check
  - Created admin API (`frontend-v2/src/lib/api/admin.ts`) with all admin endpoints
  - Features implemented:
    - Organization listing with metrics (users, connections, entities, queries)
    - Search and filtering (by name, membership status)
    - Sortable columns
    - Join any organization as owner/admin/member
    - Upgrade organizations to enterprise
    - Create new enterprise organizations
    - Feature flag management per organization
  - Superuser access control (redirects non-admins to home)

## Next Suggested Tasks (in priority order)

1. **Real-time Sync - Phase 2 (HIGH)**
   - Port `entityStateMediator.ts`
   - Port `syncStorageService.ts`
   - Create `entity-state-store` and `sync-state-store`
   - Add SSE sync progress subscription

2. **Validation System - Phase 4 (HIGH)**
   - Port `lib/validation/types.ts`
   - Port `lib/validation/rules.ts` (40+ rules)
   - Create ValidatedInput for TanStack Form

3. **QueryTool Enhancement - Phase 5 (MEDIUM)**
   - Port full QueryTool component
   - Port LiveApiDoc component

4. **SemanticMcp Page - Phase 6 (MEDIUM)**
   - Create `/semantic-mcp` route
   - Implement MCP authentication flow

## Blocked Tasks

- **Edit Member Roles** - Requires backend `PATCH /organizations/{id}/members/{memberId}` endpoint
- **Billing Management Page** - `/$orgSlug/settings/billing` for managing subscriptions

## Files Created This Iteration

- `frontend-v2/src/routes/admin.tsx` - Admin dashboard page
- `frontend-v2/src/lib/api/users.ts` - User API (fetchCurrentUser)
- `frontend-v2/src/lib/api/admin.ts` - Admin API functions
- Updated `frontend-v2/src/lib/api/index.ts` - Re-exports new APIs
- Updated `frontend-v2/src/lib/query-keys.ts` - Added user and admin query keys

## Key Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Old admin dashboard: `frontend/src/pages/AdminDashboard.tsx`
- Old real-time sync: `frontend/src/services/entityStateMediator.ts`
- Old validation rules: `frontend/src/lib/validation/rules.ts`
