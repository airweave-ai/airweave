# Shared Task Notes - Real-Time Sync Status

## Current Status

The real-time sync status feature is **mostly complete**. The core implementation is working:
- SSE subscription from frontend to backend
- Progress updates displayed in the UI
- Auto-subscription for syncing connections
- Test infrastructure set up with Vitest + jsdom

## Next Tasks to Pick Up

### 1. Add Unit Tests for useSyncProgress Hook (Priority: High)

`SyncProgressIndicator` tests done. Still need tests for:

```bash
src/hooks/useSyncProgress.test.ts
```

Key scenarios:
- Hook subscribes to connection when called
- Hook cleans up subscriptions on unmount
- Completion callback triggered correctly
- Error callback triggered on SSE failure

### 2. SSE Reconnection Logic (Priority: Medium)

Currently if SSE drops, there's no explicit reconnection. `fetch-event-source` doesn't auto-retry like native EventSource. Consider:
- Adding exponential backoff retry
- Showing "reconnecting..." state in UI

Location: `src/lib/api.ts` in `subscribeToSyncProgress()`

### 3. Failed Sync UI State (Priority: Medium)

When `is_failed: true` arrives, we update state but don't have distinct UI. Consider:
- Red progress bar or error icon
- Show error message from SSE payload

Location: `src/components/SyncProgressIndicator.tsx`

## Test Setup

Tests run with: `npm run test`

Key files:
- `vitest.config.ts` - jsdom environment, globals enabled
- `vitest.setup.ts` - jest-dom matchers

## How to Test Manually

1. Start backend: `cd backend && ./scripts/dev.sh`
2. Start connect: `cd connect && npm run dev`
3. Open test harness: `http://localhost:5173/examples/` (note: port changed)
4. Connect a source (e.g., Slack) and watch the sync progress

## Relevant Commits

- `959e3287` - Improve SSE subscription timing
- `8d774a1a` - Wire up SSE sync progress in SuccessScreen
- `a53d84ef` - Add SyncProgressIndicator component
- `cf8b5e39` - Add SSE endpoints for real-time sync progress
