# Shared Task Notes

## Current Status
Phase 3 (OAuth Flow) implementation is complete. Build passes (`npm run build`).

Files created:
- `src/lib/oauth.ts` - Popup window utilities (`openOAuthPopup`, `listenForOAuthComplete`, `isPopupOpen`)
- `src/routes/oauth-callback.tsx` - OAuth callback route that receives result and posts to opener

`SourceConfigView.tsx` updated with:
- OAuth state management (status: idle/creating/waiting/error)
- `handleOAuthConnect` - Creates connection, opens popup with auth_url
- `handleOAuthResult` - Receives postMessage, handles success/error
- Popup close detection (polls to detect if user closes popup)
- "Connect with {source}" button replaces placeholder
- Waiting state UI with spinner

## Next Tasks

### Phase 4 - Polish
After testing, remaining items from SPEC.md:
- Add BYOC fields for `requires_byoc` sources
- Handle popup blockers (show manual link option)
- Add labels to theme for new UI text

Note: Form validation and loading/error states are already implemented in current code.

## Implementation Details

### OAuth Flow Sequence
1. User clicks "Connect with {source}" button
2. `handleOAuthConnect`:
   - Sets status to "creating"
   - POSTs to `/connect/source-connections` with `redirect_uri`
   - Backend returns `{ auth: { auth_url } }`
   - Opens popup with `auth_url`
   - Sets status to "waiting"
3. User authorizes in popup
4. OAuth provider redirects to backend callback
5. Backend redirects popup to `/oauth-callback?status=success&source_connection_id=xxx`
6. `oauth-callback.tsx` posts `{ type: "OAUTH_COMPLETE", ... }` to opener
7. `handleOAuthResult` receives message, closes popup, calls `onSuccess`

### Popup Blocked Handling
Current implementation shows error: "Popup was blocked. Please allow popups..."
Future: Could add manual link option.
