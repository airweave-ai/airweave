# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done

- Created Members Settings page at `/$orgSlug/settings/members.tsx`
- Added navigation tabs to switch between General settings and Members pages
- Created Select UI component (`frontend-v2/src/components/ui/select.tsx`)
- Added member API functions: `fetchOrganizationMembers`, `fetchOrganizationInvitations`, `inviteOrganizationMemberWithResponse`, `removeOrganizationMember`, `cancelOrganizationInvitation`
- Added query keys for members and invitations

## Next Suggested Task

**Edit Member Roles** - MEDIUM PRIORITY

The members page currently allows viewing, inviting, and removing members, but doesn't support editing existing member roles. Consider adding:
1. Role dropdown/select for each member row
2. API function to update member role
3. Confirmation dialog for role changes

**Usage Dashboard** (`/$orgSlug/settings/usage.tsx`) - HIGH PRIORITY

This completes Phase 1 settings and provides usage tracking. Reference:
- Old component: `frontend/src/components/settings/UsageDashboard.tsx`
- Will need API functions for usage data

## Other Tasks (in order of priority)

1. S3ConfigModal and S3StatusCard components (MEDIUM - feature-flagged)
2. BillingGuard component + billing enforcement (HIGH)
3. Validation system - Phase 4:
   - Port `lib/validation/types.ts`
   - Port `lib/validation/rules.ts` (40+ rules)
   - Create ValidatedInput for TanStack Form
4. Real-time Sync - Phase 2:
   - Port `entityStateMediator.ts`
   - Port `syncStorageService.ts`

## Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Old usage dashboard: `frontend/src/components/settings/UsageDashboard.tsx`
- New members page: `frontend-v2/src/routes/$orgSlug/settings/members.tsx`
- New settings page: `frontend-v2/src/routes/$orgSlug/settings/index.tsx`
