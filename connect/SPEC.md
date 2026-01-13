# Connect Widget - Real-Time Sync Status Feature

## Overview

This document tracks the implementation of real-time sync status updates in the Connect widget. Users should see live progress as their data syncs after connecting a source.

## Architecture

```
┌─────────────────┐     SSE      ┌──────────────────┐
│  Connect Widget │ ◄──────────► │  Backend API     │
│  (React)        │              │  (FastAPI + SSE) │
└────────┬────────┘              └────────┬─────────┘
         │                                │
         │ useSyncProgress hook           │ Redis PubSub
         │                                │
         ▼                                ▼
┌─────────────────┐              ┌──────────────────┐
│ SyncProgress    │              │  Sync Worker     │
│ Indicator       │              │  (Temporal)      │
└─────────────────┘              └──────────────────┘
```

## Implementation Checklist

### Backend (Complete)

- [x] SSE endpoint: `GET /connect/source-connections/{id}/subscribe`
- [x] Redis PubSub channel subscription (`sync_job` channel)
- [x] Event types: `connected`, `heartbeat`, `progress`, `error`
- [x] Jobs endpoint: `GET /connect/source-connections/{id}/jobs`
- [x] Authorization via Connect session token

### Frontend - API Client (Complete)

- [x] `apiClient.subscribeToSyncProgress()` - SSE subscription method
- [x] `apiClient.getConnectionJobs()` - Get job list for connection
- [x] Event parsing: `connected`, `heartbeat`, `error`, progress updates
- [x] Proper cleanup with AbortController

### Frontend - React Hook (Complete)

- [x] `useSyncProgress` hook in `src/hooks/useSyncProgress.ts`
- [x] Map-based subscription tracking
- [x] Auto-subscribe to connections with `status: "syncing"`
- [x] Callbacks: `onComplete`, `onError`
- [x] Cleanup on unmount

### Frontend - UI Components (Complete)

- [x] `SyncProgressIndicator` component
- [x] Indeterminate progress bar animation
- [x] Entity counts display (inserted, updated, deleted)
- [x] Integration in `ConnectionItem` component

### Frontend - Integration (Complete)

- [x] `SuccessScreen` wires up `useSyncProgress`
- [x] Auto-subscribe for syncing connections
- [x] Immediate subscription for newly created connections
- [x] Invalidate queries on sync completion
- [x] Progress passed to `ConnectionItem` via `syncProgress` prop

### Testing

- [ ] Unit tests for `useSyncProgress` hook
- [x] Unit tests for `SyncProgressIndicator` component
- [ ] Integration tests for SSE subscription flow
- [ ] E2E test for complete sync progress flow

### Polish & Edge Cases

- [x] Handle SSE connection errors gracefully
- [x] Auto-cleanup subscriptions on component unmount
- [x] Delay removal of completed syncs (2 second buffer)
- [ ] Reconnection logic for dropped SSE connections
- [ ] Show error state when sync fails

## Key Files

| File | Purpose |
|------|---------|
| `src/hooks/useSyncProgress.ts` | React hook for SSE subscriptions |
| `src/lib/api.ts` | API client with `subscribeToSyncProgress` |
| `src/components/SyncProgressIndicator.tsx` | Progress UI component |
| `src/components/SyncProgressIndicator.test.tsx` | Tests for progress UI |
| `src/components/ConnectionItem.tsx` | Connection card with progress |
| `src/components/SuccessScreen.tsx` | Main view with SSE wiring |
| `src/lib/types.ts` | TypeScript types for sync progress |
| `src/styles.css` | Progress bar animation CSS |
| `vitest.config.ts` | Test configuration (jsdom env) |
| `vitest.setup.ts` | Test setup with jest-dom matchers |

## Types

```typescript
// Progress update from SSE
interface SyncProgressUpdate {
  entities_inserted: number;
  entities_updated: number;
  entities_deleted: number;
  entities_kept: number;
  entities_skipped: number;
  entities_encountered: Record<string, number>;
  is_complete?: boolean;
  is_failed?: boolean;
  error?: string;
}

// Subscription state
interface SyncSubscription {
  connectionId: string;
  jobId: string;
  lastUpdate: SyncProgressUpdate;
  lastMessageTime: number;
  status: "active" | "completed" | "failed";
}
```

## SSE Event Format

```json
// Connected event
{"type": "connected", "job_id": "uuid"}

// Heartbeat (every 30s)
{"type": "heartbeat"}

// Progress update
{
  "inserted": 42,
  "updated": 3,
  "deleted": 0,
  "kept": 100,
  "skipped": 2,
  "entities_encountered": {"Message": 45, "Channel": 2},
  "is_complete": false
}

// Completion
{
  "inserted": 150,
  "updated": 10,
  "deleted": 5,
  "kept": 200,
  "skipped": 0,
  "entities_encountered": {"Message": 165},
  "is_complete": true
}
```

## Decisions

1. **SSE over WebSocket**: Simpler, one-way communication is sufficient
2. **Per-connection subscriptions**: More granular control vs. single multiplexed connection
3. **Redis PubSub**: Backend already uses this for sync progress; natural fit
4. **Indeterminate progress bar**: Total entity count unknown upfront
5. **2-second delay before cleanup**: Allows users to see completion state briefly

## Known Limitations

1. No reconnection logic for dropped SSE connections (browser will auto-retry)
2. Session token expiry during long syncs could disconnect SSE
3. No progress percentage (would require knowing total entities upfront)
