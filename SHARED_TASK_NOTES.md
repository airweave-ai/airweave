# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Phase 7 Polish - TagInput & CollapsibleCard COMPLETE**
  - Ported `TagInput` component to `frontend-v2/src/components/ui/tag-input.tsx`
    - Add tags with Enter or comma, remove with X or Backspace
    - Optional `transformInput` prop (e.g., uppercase for Jira keys)
    - Duplicate prevention, accessible with aria-labels
  - Ported `CollapsibleCard` component to `frontend-v2/src/components/ui/collapsible-card.tsx`
    - Smooth height animations using ResizeObserver
    - Copy button option with copyTooltip
    - Controlled/uncontrolled modes, autoExpandOnSearch prop
    - Status ribbon support
  - Created base `Collapsible` primitives from @radix-ui/react-collapsible
  - Build verified passing

## Next Suggested Tasks (in priority order)

1. **Enhance CodeBlock component (LOW)**
   - Add better syntax highlighting (maybe Shiki or Prism)
   - Check old frontend CodeBlock for features to port

2. **Auth0 conflict error handling UI (LOW)**
   - Handle Auth0 account conflict errors gracefully in UI
   - Check old frontend for error handling patterns

3. **Port ValidatedInput component (LOW)**
   - Validation system is already ported (rules.ts, types.ts)
   - Create wrapper for TanStack Form integration

4. **Edit Member Roles (BLOCKED)**
   - Requires backend `PATCH /organizations/{id}/members/{memberId}` endpoint
   - UI is prepared in members settings page, just needs backend API

## Key Files Reference

- TagInput: `frontend-v2/src/components/ui/tag-input.tsx`
- CollapsibleCard: `frontend-v2/src/components/ui/collapsible-card.tsx`
- Collapsible primitives: `frontend-v2/src/components/ui/collapsible.tsx`
- Old CodeBlock: `frontend/src/components/ui/code-block.tsx`
- Validation rules: `frontend-v2/src/lib/validation/rules.ts`

## Migration Status Summary

All core routes and features are now complete:
- ✅ Collections CRUD + Search
- ✅ API Keys Management
- ✅ Auth Providers
- ✅ Onboarding
- ✅ Source Connections
- ✅ Organization Settings (with S3 config)
- ✅ Billing (settings, setup, portal, success, cancel)
- ✅ Admin Dashboard
- ✅ Real-time Sync (SSE)
- ✅ Usage Dashboard
- ✅ Members Settings (partial - role editing blocked on backend)
- ✅ Validation System
- ✅ QueryTool with MCP client tabs
- ✅ SemanticMcp Page
- ✅ PostHog Integration
- ✅ TagInput component
- ✅ CollapsibleCard component

Remaining Phase 7 polish:
- Enhance CodeBlock component
- Auth0 conflict error handling UI
- Port ValidatedInput component
- Edit member roles (blocked on backend API)
