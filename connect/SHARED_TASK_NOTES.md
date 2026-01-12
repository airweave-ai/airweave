# Shared Task Notes

## Current Status
Phase 2 (Direct Auth Flow) is in progress. `DynamicFormField.tsx` is complete.

## Next Task
Create `AuthMethodSelector.tsx` - a radio group component for selecting between auth methods (direct vs OAuth).

### AuthMethodSelector Implementation Notes
- Location: `src/components/AuthMethodSelector.tsx`
- Props: `{ methods: AuthenticationMethod[]; selected: "direct" | "oauth_browser"; onChange: (method) => void; sourceName: string }`
- Should render radio buttons/cards for each available auth method
- Filter out `auth_provider` for initial implementation (per SPEC.md design decision)
- Label options should show "Enter credentials" for direct and "Connect with OAuth" for oauth_browser
- Use existing styling patterns: CSS custom properties (`var(--connect-*)`) and Tailwind classes
- See `Button.tsx` and `SourceItem.tsx` for hover/styling patterns

### After AuthMethodSelector
The next component after that is `SourceConfigView.tsx` which uses both `DynamicFormField` and `AuthMethodSelector`.

## DynamicFormField Notes (for reference)
The completed component supports:
- `string` fields (text/password with show/hide toggle when `is_secret=true`)
- `number` fields
- `boolean` fields (toggle switch)
- `array` fields (tag input with Enter/comma to add, Backspace to remove)
- Error display and required field indicators
- Full accessibility (aria labels, roles)
