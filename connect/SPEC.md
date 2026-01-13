# Real-Time Sync Status in Connect Modal

## Summary

Add real-time sync status updates to the connect modal using Server-Sent Events (SSE).

## Architecture

The connect widget uses session tokens (not API keys), so dedicated SSE endpoints were added to the `/connect/*` namespace:

- `GET /connect/source-connections/{connection_id}/subscribe` - SSE stream for sync progress
- `GET /connect/source-connections/{connection_id}/jobs` - List sync jobs for a connection

These endpoints use session token auth and reuse the existing Redis PubSub infrastructure.

## Implementation Status

### Completed (Phase 1 & 2)
- Backend SSE and jobs endpoints
- `useSyncProgress.ts` hook for managing SSE subscriptions
- Types for sync progress (`SyncProgressUpdate`, `SourceConnectionJob`, etc.)
- API client methods (`getConnectionJobs`, `subscribeToSyncProgress`)
- `@microsoft/fetch-event-source` dependency

### Remaining (Phase 3-5)
- [ ] Create `SyncProgressIndicator.tsx` component for inline progress display
- [ ] Update `ConnectionItem.tsx` to show progress during sync
- [ ] Auto-subscribe to SSE for syncing connections in `SuccessScreen.tsx`
- [ ] Handle sync completion and refresh connection list
- [ ] Show inline progress after folder selection starts sync

## UI Approach

Inline progress in `ConnectionItem` - compact progress bar and entity counts directly in each connection row. No full-screen overlay needed.

## Testing

1. Create a new connection with `sync_immediately` enabled
2. Verify real-time progress appears in the connection item
3. Verify entity counts update as entities are synced
4. Verify status changes from "syncing" to "active" on completion
