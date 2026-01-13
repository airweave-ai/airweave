# Shared Task Notes - Real-Time Sync Status

## Current Status

The real-time sync status feature is **mostly complete**. All unit tests pass (37 tests).

## What Was Just Done

Added SSE reconnection logic with exponential backoff:
- `api.ts`: `subscribeToSyncProgress()` now retries on connection errors (max 5 attempts, 1s/2s/4s/8s/16s delays)
- Won't retry on 4xx client errors or after sync completes
- Calls `onReconnecting(attempt)` callback to notify UI of retry attempts
- `useSyncProgress` hook: Added `isReconnecting()` method and tracks `reconnectAttempt` in subscription state
- `SyncProgressIndicator`: Shows "Reconnecting..." with pulsing WifiOff icon when reconnecting
- Added 7 new tests covering reconnection states

## Next Tasks to Pick Up

### 1. Integration Tests for SSE Flow (Priority: Low)

Would require mocking SSE at a higher level or using MSW (Mock Service Worker).

### 2. E2E Tests (Priority: Low)

Would require full backend running. Consider Playwright or Cypress.

## Test Setup

Tests run with: `npm run test`

Key files:
- `vitest.config.ts` - jsdom environment, globals enabled
- `vitest.setup.ts` - jest-dom matchers
- `src/hooks/useSyncProgress.test.ts` - 26 tests for the hook
- `src/components/SyncProgressIndicator.test.tsx` - 11 tests for the UI

## How to Test Manually

1. Start backend: `cd backend && ./scripts/dev.sh`
2. Start connect: `cd connect && npm run dev`
3. Open test harness: `http://localhost:5173/examples/`
4. Connect a source (e.g., Slack) and watch the sync progress
5. To test reconnection: Kill/restart the backend during a sync
