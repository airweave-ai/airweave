# Shared Task Notes

## Current Status
Phase 2 (Direct Auth Flow) is nearly complete. All UI components for direct auth are implemented:
- `SourceConfigView.tsx` - Main config form for creating connections
- `DynamicFormField.tsx` - Renders form fields based on ConfigField type
- `AuthMethodSelector.tsx` - Radio group for auth method selection
- `lib/messaging.ts` - Utility for parent window communication

Build passes (`npm run build`).

## Next Task
**Test direct auth flow end-to-end**, then start Phase 3 (OAuth).

### Testing Direct Auth
1. Run `npm run dev` in `connect/` folder
2. Open `test-parent.html` in browser (or test via the main app)
3. Click: Sources list → Select a source with direct auth → Fill form → Create
4. Verify connection appears in connections list
5. Verify parent receives `CONNECTION_CREATED` message

### Phase 3 - OAuth Flow
After testing, implement OAuth flow:
1. Create `src/lib/oauth.ts` - popup window utilities (`openOAuthPopup`, `listenForOAuthComplete`)
2. Create `src/routes/oauth-callback.tsx` - handles OAuth redirect, posts message to opener
3. Update `SourceConfigView.tsx` to:
   - Show "Connect with {Source}" button when OAuth selected
   - Open popup on click
   - Listen for `OAUTH_COMPLETE` postMessage
   - Handle success/error

See SPEC.md "OAuth Flow Sequence" diagram for the full flow.

## Implementation Notes

### SourceConfigView
- Fetches source details via `getSourceDetails(shortName)`
- Direct auth works; OAuth shows placeholder (disabled submit)
- Uses `createSourceConnection()` to POST credentials
- Form validation checks required fields
- Notifies parent via `notifyConnectionCreated()` on success

### OAuth Placeholder in SourceConfigView
Lines ~280-288 show a placeholder. When implementing OAuth:
1. Replace placeholder with "Connect with {Source}" button
2. On click: call API to create pending connection, get auth_url
3. Open popup with auth_url
4. Listen for `OAUTH_COMPLETE` postMessage
5. On success, call `onSuccess(connectionId)`
