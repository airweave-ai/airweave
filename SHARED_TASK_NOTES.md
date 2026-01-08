# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done

- Added PostHog integration to frontend-v2
- Created `frontend-v2/src/lib/posthog-provider.tsx`
- Wrapped app with `<PostHogProvider>` in `__root.tsx`
- Phase 6 is now complete (utilities + PostHog)

## Next Suggested Task

**Start Organization Settings page** (`/$orgSlug/settings`) - HIGH PRIORITY

This is in the Phase 1 checklist and blocks user workflows. Break down into:

1. Create `/$orgSlug/settings/index.tsx` route file
2. Add basic page structure with tabs for sub-sections
3. Implement organization name/description editing
4. Add organization deletion with confirmation dialog

Reference: `frontend/src/pages/OrganizationSettingsUnified.tsx` for existing logic.

## Other Tasks (in order of priority)

1. Organization Settings page (HIGH PRIORITY - Phase 1)
2. Members Settings (`/$orgSlug/settings/members.tsx`) - Full CRUD
3. Usage Dashboard (`/$orgSlug/settings/usage.tsx`)
4. Validation system - Phase 4:
   - Port `lib/validation/types.ts`
   - Port `lib/validation/rules.ts` (40+ rules)
   - Create ValidatedInput for TanStack Form

## Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Old org settings: `frontend/src/pages/OrganizationSettingsUnified.tsx`
- Route structure example: `frontend-v2/src/routes/$orgSlug/collections/index.tsx`
