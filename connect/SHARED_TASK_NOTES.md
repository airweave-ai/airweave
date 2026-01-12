# Shared Task Notes

## Current Status
Phase 4 (Polish) in progress. BYOC fields implementation complete. Build passes (`npm run build`).

## What Was Done
Added BYOC (Bring Your Own Credentials) support to `SourceConfigView.tsx`:
- New `byocValues` state for `client_id` and `client_secret`
- BYOC form fields shown when `sourceDetails.requires_byoc` is true and OAuth method is selected
- Validation: requires both fields before OAuth flow starts
- BYOC credentials included in OAuth payload via spread: `{ redirect_uri, client_id, client_secret }`
- Error display for missing BYOC fields
- Help text explaining why credentials are needed

## Next Tasks (from SPEC.md Phase 4)
Remaining unchecked items:
1. **Handle popup blockers** - Show manual link option when popup is blocked (currently just shows error message)
2. **Add labels to theme** - Add customizable labels to `ConnectLabels` interface for new UI text
3. **Add unit tests, linting, formatting, e2e tests** - Testing infrastructure

Also unchecked from Phase 2:
- Test direct auth flow end-to-end (manual testing required)

## Implementation Notes

### BYOC Flow
When `sourceDetails.requires_byoc === true`:
1. UI shows Client ID and Client Secret fields before OAuth button
2. Both fields are required (validation happens on button click)
3. Credentials are sent in the `authentication` payload along with `redirect_uri`

### Popup Blocked Enhancement
Current: Shows error "Popup was blocked. Please allow popups..."
Suggested enhancement: Add a manual link option showing the `auth_url` so user can open it themselves.
