# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done

- Ported `dateTime.ts` utility to `frontend-v2/src/lib/dateTime.ts`
- Ported `cronParser.ts` utility to `frontend-v2/src/lib/cronParser.ts`
- Both utilities compile successfully with TypeScript

## Next Suggested Task

**Port `error-utils.ts` utility** (MIGRATION_SPEC section 9.2)

Check if it exists:
```
frontend/src/utils/error-utils.ts
```

If it doesn't exist, move to the next task.

## Other Quick Tasks (in order of simplicity)

1. Port `syncStatus.ts` utility (HIGH PRIORITY per MIGRATION_SPEC 9.2)
2. Add PostHog provider (requires `posthog-js` dependency)
3. Start on Organization Settings page (`/$orgSlug/settings`)

## Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- New utilities: `frontend-v2/src/lib/dateTime.ts`, `frontend-v2/src/lib/cronParser.ts`
