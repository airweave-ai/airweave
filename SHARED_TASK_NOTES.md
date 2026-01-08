# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done

- Ported `error-utils.ts` to `frontend-v2/src/lib/error-utils.ts`
- Adapted for TanStack Router (removed React Router dependency)
- Added helper functions: `hasStoredError()`, `createErrorFromResponse()`
- All Phase 6 utilities are now complete (dateTime, cronParser, syncStatus, error-utils)

## Next Suggested Task

**Add PostHog provider** (MIGRATION_SPEC section 6.1 and 9.3)

This is a straightforward task:
1. Add `posthog-js` dependency to package.json
2. Create PostHog provider component
3. Wrap app with provider in main.tsx or root layout
4. Implement `getPostHogSessionId()` helper for API client

Reference: `frontend/src/` for existing PostHog implementation patterns.

## Other Quick Tasks (in order of suggested priority)

1. Add PostHog provider (small, enables session tracking)
2. Start Organization Settings page (`/$orgSlug/settings`) - HIGH PRIORITY in spec
3. Port Phase 4 validation system - break down into:
   - Port `lib/validation/types.ts` first
   - Port `lib/validation/rules.ts` (40+ rules)
   - Create ValidatedInput component for TanStack Form

## Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Ported utilities: `frontend-v2/src/lib/error-utils.ts`, `dateTime.ts`, `cronParser.ts`
