# Shared Task Notes - Real-Time Sync Status

## Current Status

The real-time sync status feature is **mostly complete**. Unit tests are now comprehensive:
- SSE subscription from frontend to backend
- Progress updates displayed in the UI
- Auto-subscription for syncing connections
- Full test coverage for both `useSyncProgress` hook and `SyncProgressIndicator` component

## Next Tasks to Pick Up

### 1. SSE Reconnection Logic (Priority: High)

Currently if SSE drops, there's no explicit reconnection. `fetch-event-source` doesn't auto-retry like native EventSource. Consider:
- Adding exponential backoff retry
- Showing "reconnecting..." state in UI

Location: `src/lib/api.ts` in `subscribeToSyncProgress()`

### 2. Failed Sync UI State (Priority: Medium)

When `is_failed: true` arrives, we update state but don't have distinct UI. Consider:
- Red progress bar or error icon
- Show error message from SSE payload

Location: `src/components/SyncProgressIndicator.tsx`

### 3. Integration Tests for SSE Flow (Priority: Low)

Would require mocking SSE at a higher level or using MSW (Mock Service Worker).

### 4. E2E Tests (Priority: Low)

Would require full backend running. Consider Playwright or Cypress.

## Test Setup

Tests run with: `npm run test`

Key files:
- `vitest.config.ts` - jsdom environment, globals enabled
- `vitest.setup.ts` - jest-dom matchers
- `src/hooks/useSyncProgress.test.ts` - 22 tests for the hook
- `src/components/SyncProgressIndicator.test.tsx` - 8 tests for the UI

## How to Test Manually

1. Start backend: `cd backend && ./scripts/dev.sh`
2. Start connect: `cd connect && npm run dev`
3. Open test harness: `http://localhost:5173/examples/`
4. Connect a source (e.g., Slack) and watch the sync progress
