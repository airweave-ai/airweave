# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done

- Added `X-Airweave-Session-ID` header infrastructure to `frontend-v2/src/lib/api/client.ts`
- The header is conditionally included when PostHog session ID is available via `window.posthog`
- Currently returns `undefined` since PostHog isn't ported yet - will work automatically once PostHog provider is added

## Next Suggested Task

**Port `dateTime.ts` utility** (MIGRATION_SPEC section 9.2)

Small task:
1. Create `frontend-v2/src/lib/utils/dateTime.ts`
2. Copy contents from `frontend/src/utils/dateTime.ts`
3. Verify TypeScript compiles

## Other Quick Tasks (in order of simplicity)

1. Port `cronParser.ts` utility (check if exists in old frontend)
2. Port `error-utils.ts` utility
3. Add PostHog provider (larger task - requires `posthog-js` dependency)

## Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Route patterns: See existing routes in `frontend-v2/src/routes/`
