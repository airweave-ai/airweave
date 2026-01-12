# Shared Task Notes

## Current Status
Phase 4 (Polish) in progress. Build passes (`npm run build`).

## What Was Done This Iteration
Implemented popup blocker handling with manual link option in `SourceConfigView.tsx`:
- Added `popup_blocked` state to `oauthStatus`
- Added `blockedAuthUrl` state to store the auth URL when popup is blocked
- When popup is blocked, shows a warning UI with:
  - "Try again" button that attempts to open the popup again
  - "Open link manually" link that opens in a new tab
- Modified the OAuth message listener to also listen in `popup_blocked` state (so manual link clicks work)
- Uses `--connect-warning` CSS variable with fallback `#f59e0b` for the warning UI

## Next Tasks (from SPEC.md Phase 4)
Remaining unchecked items:
1. **Add labels to theme** - Add customizable labels to `ConnectLabels` interface for new UI text (see SPEC.md "Labels to Add" section)
2. **Add unit tests, linting, formatting, e2e tests** - Testing infrastructure

Also unchecked from Phase 2:
- Test direct auth flow end-to-end (manual testing required)

## Implementation Notes

### Popup Blocked Flow
When popup is blocked:
1. `oauthStatus` is set to `popup_blocked` and `blockedAuthUrl` stores the URL
2. UI shows warning box with two options
3. "Try again" calls `handleRetryPopup()` which tries `openOAuthPopup` again
4. "Open link manually" is a regular `<a>` tag with `target="_blank"` - clicking it switches to `waiting` state so the OAuth listener is active
5. OAuth message listener runs in both `waiting` and `popup_blocked` states to catch the callback

### Files Modified
- `connect/src/components/SourceConfigView.tsx` - popup blocker handling
