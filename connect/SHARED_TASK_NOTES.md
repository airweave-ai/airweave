# Shared Task Notes

## Current Status

Phase 1 (Backend) and Phase 2 (Frontend SSE Support) are complete.

## Available APIs

### Hook: `useSyncProgress`
Location: `connect/src/hooks/useSyncProgress.ts`

```tsx
const { subscribe, getProgress, subscriptions, cleanup } = useSyncProgress({
  onComplete: (connectionId, update) => {
    // Refetch connection list to update status
    queryClient.invalidateQueries(['connections']);
  },
  onError: (connectionId, error) => {
    console.error('SSE error:', error);
  }
});

// Subscribe to a connection's sync progress
await subscribe(connectionId);

// Get current progress
const progress = getProgress(connectionId);
```

### API Client Methods
- `apiClient.getConnectionJobs(connectionId)` - Get sync jobs for a connection
- `apiClient.subscribeToSyncProgress(connectionId, handlers)` - Subscribe to SSE

## Next Steps

1. Create `SyncProgressIndicator.tsx` component showing:
   - Progress bar (indeterminate)
   - Entity counts: inserted, updated, deleted, kept, skipped
   - Animated transitions for count updates

2. Update `ConnectionItem.tsx` to show inline progress when `status === "syncing"`

3. In `SuccessScreen.tsx`, auto-subscribe to SSE for syncing connections:
   ```tsx
   useEffect(() => {
     connections
       .filter(c => c.status === 'syncing')
       .forEach(c => subscribe(c.id));
   }, [connections]);
   ```

## Backend Endpoints

- `GET /connect/source-connections/{connection_id}/subscribe` - SSE stream
- `GET /connect/source-connections/{connection_id}/jobs` - List jobs

Both require session token auth.
