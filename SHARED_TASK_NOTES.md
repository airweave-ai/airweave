# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- Added S3 Event Streaming configuration (feature-flagged) to Organization Settings
- Created `frontend-v2/src/lib/api/s3.ts` with API functions
- Created `S3ConfigModal` component with test connection + save flow
- Created `S3StatusCard` component (only renders when `S3_DESTINATION` feature flag enabled)
- Created `Alert` UI component
- Added `s3.status` query key

## Next Suggested Task

**BillingGuard component** - HIGH PRIORITY

Blocks UI actions when subscription is inactive. This is needed for billing enforcement across the app.

Files to reference:
- Old frontend: Search for billing enforcement patterns
- Backend endpoint: `GET /usage/check-action?action={action}`

Implementation steps:
1. Create `checkUsageAction` API function in `frontend-v2/src/lib/api/usage.ts`
2. Create `BillingGuard` component that wraps children and shows upgrade prompt when action blocked
3. Integrate into key UI actions (create collection, add source, invite members, etc.)

**Edit Member Roles** - MEDIUM PRIORITY (blocked)

NOTE: This requires backend work first. The `PATCH /organizations/{id}/members/{memberId}` endpoint doesn't exist yet. Suggest deferring until backend adds the endpoint.

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
- New S3 components: `frontend-v2/src/components/s3-*.tsx`
- Organization settings: `frontend-v2/src/routes/$orgSlug/settings/index.tsx`
