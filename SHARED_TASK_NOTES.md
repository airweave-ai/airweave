# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done

- Ported `syncStatus.ts` utility to `frontend-v2/src/lib/syncStatus.ts` (HIGH PRIORITY per MIGRATION_SPEC 9.2)
- Includes `SyncProgressUpdate` type (defined locally until sync-state-store is ported)
- Exports: `deriveSyncStatus`, `getSyncStatusColorClass`, `getSyncStatusDisplayText`

## Next Suggested Task

**Port `error-utils.ts` utility** (MIGRATION_SPEC section 9.2)

Location: `frontend/src/lib/error-utils.ts`

Notes:
- Needs adaptation for TanStack Router (currently uses React Router's `NavigateFunction`)
- Uses `protectedPaths` constant - check if this exists in frontend-v2 or needs porting
- Core functionality: store/retrieve/clear error details in localStorage, redirect with error

## Other Quick Tasks (in order of simplicity)

1. Add PostHog provider (requires `posthog-js` dependency)
2. Start on Organization Settings page (`/$orgSlug/settings`)
3. Port Phase 4 validation system (larger task - may want to break down)

## Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- New utilities: `frontend-v2/src/lib/syncStatus.ts`, `dateTime.ts`, `cronParser.ts`
