# Shared Task Notes

## Current Status

Phase 1-2 (Backend + Frontend SSE) complete. Phase 3 UI components partially done.

## What's Done

- `SyncProgressIndicator.tsx` - Shows indeterminate progress bar + entity counts (inserted/updated/deleted)
- `ConnectionItem.tsx` - Now accepts optional `syncProgress` prop to show inline progress

## Next Task: Wire up SSE in SuccessScreen.tsx

The UI components exist but aren't connected to live data yet. Next step:

```tsx
// In SuccessScreen.tsx
const { subscribe, getProgress } = useSyncProgress({
  onComplete: () => queryClient.invalidateQueries(['connections']),
});

// Auto-subscribe to syncing connections
useEffect(() => {
  connections
    .filter(c => c.status === 'syncing')
    .forEach(c => subscribe(c.id));
}, [connections]);

// Pass progress to each ConnectionItem
<ConnectionItem
  connection={conn}
  syncProgress={getProgress(conn.id)}
  ...
/>
```

## Files to Modify

- `connect/src/components/SuccessScreen.tsx` - Add useSyncProgress hook, pass progress to ConnectionItem

## Available APIs

- `useSyncProgress()` hook - manages SSE subscriptions, returns `subscribe`, `getProgress`, `cleanup`
- `SyncProgressIndicator` - takes `progress: SyncProgressUpdate` prop
- `ConnectionItem` - takes optional `syncProgress` prop
