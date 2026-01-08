# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done

- Created Organization Settings page at `/$orgSlug/settings/index.tsx`
- Implemented organization name/description editing
- Added primary organization toggle
- Added organization deletion with confirmation dialog
- Added Settings to navigation sidebar
- Created `Switch` and `Textarea` UI components
- Added `updateOrganization`, `deleteOrganization`, `setPrimaryOrganization` API functions

## Next Suggested Task

**Members Settings page** (`/$orgSlug/settings/members.tsx`) - HIGH PRIORITY

This is part of Phase 1 and provides full team management. Break down into:

1. Create `/$orgSlug/settings/members.tsx` route file
2. Fetch and display members list
3. Add invite member dialog (email + role selection)
4. Implement remove member functionality
5. View and cancel pending invitations

Reference: `frontend/src/components/settings/MembersSettings.tsx` for existing logic.

## Other Tasks (in order of priority)

1. Members Settings (`/$orgSlug/settings/members.tsx`) - Full CRUD (HIGH)
2. S3ConfigModal and S3StatusCard components (MEDIUM - feature-flagged)
3. Usage Dashboard (`/$orgSlug/settings/usage.tsx`) (HIGH)
4. BillingGuard component + billing enforcement (HIGH)
5. Validation system - Phase 4:
   - Port `lib/validation/types.ts`
   - Port `lib/validation/rules.ts` (40+ rules)
   - Create ValidatedInput for TanStack Form

## Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Old members settings: `frontend/src/components/settings/MembersSettings.tsx`
- New settings page: `frontend-v2/src/routes/$orgSlug/settings/index.tsx`
