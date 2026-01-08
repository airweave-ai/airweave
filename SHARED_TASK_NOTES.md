# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- Created Usage Dashboard page at `/$orgSlug/settings/usage.tsx`
- Added `fetchUsageDashboard` API function in `frontend-v2/src/lib/api/usage.ts`
- Added `usage.dashboard` query key
- Added Usage tab to SettingsLayout navigation

## Next Suggested Task

**Edit Member Roles** - MEDIUM PRIORITY

The members page allows viewing, inviting, and removing members, but doesn't support editing existing member roles. Consider adding:
1. Role dropdown/select for each member row
2. API function to update member role (`PATCH /organizations/{id}/members/{memberId}`)
3. Confirmation dialog for role changes

**S3ConfigModal + S3StatusCard** - MEDIUM PRIORITY (feature-flagged)

These components are needed to complete Organization Settings. Reference:
- Old component: `frontend/src/components/settings/S3ConfigModal.tsx`
- API endpoints: `GET /s3/status`, `POST /s3/configure`, `DELETE /s3/configure`

## Other Tasks (in order of priority)

1. BillingGuard component + billing enforcement (HIGH)
   - Blocks UI actions when subscription inactive
   - Needs usage check API (`GET /usage/check-action`)
2. Admin Dashboard - Phase 3 (HIGH)
   - `/admin` route with superuser-only access
3. Real-time Sync - Phase 2 (HIGH)
   - Port `entityStateMediator.ts`
   - Port `syncStorageService.ts`
4. Validation system - Phase 4 (HIGH)
   - Port `lib/validation/types.ts`
   - Port `lib/validation/rules.ts` (40+ rules)
   - Create ValidatedInput for TanStack Form

## Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- New usage page: `frontend-v2/src/routes/$orgSlug/settings/usage.tsx`
- New settings layout: `frontend-v2/src/components/settings-layout.tsx`
