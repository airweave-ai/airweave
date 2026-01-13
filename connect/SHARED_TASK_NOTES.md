# Shared Task Notes

## Current Status

Phase 3 SSE wiring in SuccessScreen.tsx is complete. Syncing connections now auto-subscribe to real-time progress updates.

## What's Done

- `SuccessScreen.tsx` now uses `useSyncProgress` hook
- Auto-subscribes to SSE for connections with `status === "syncing"`
- Passes real-time progress to each `ConnectionItem` via `syncProgress` prop
- Connection list refreshes automatically when sync completes

## Next Task: Show inline progress after folder selection

The final remaining task is to show inline progress immediately after folder selection triggers a sync. Currently:
1. User completes folder selection
2. Sync starts (with `sync_immediately`)
3. User is redirected to connections list
4. Progress shows up once `connections` query returns with `status: "syncing"`

The gap: There's a brief moment after folder selection completes but before the connection appears with "syncing" status.

**Approach options:**
1. Subscribe to SSE immediately in `FolderSelectionView.onComplete` before navigating
2. Pass `recentConnectionId` to trigger immediate subscription in SuccessScreen
3. Accept the brief delay (simplest - progress appears within ~1s anyway)

## Files to Reference

- `connect/src/components/SuccessScreen.tsx:104-119` - SSE hook setup and auto-subscribe logic
- `connect/src/components/FolderSelectionView.tsx` - Where folder selection completes and sync starts
