# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Billing Routes - COMPLETE**
  - Created `/billing/portal` route - simple redirect to Stripe Customer Portal
  - Created `/billing/setup` route - initial billing setup page for onboarding
    - Shows plan details (Pro/Team) with feature lists
    - Polls for subscription activation (Stripe webhook)
    - Past due status alert for failed payments
    - Redirects to success page when active
  - Added `queryKeys.billing.currentSubscription` for non-org-scoped billing queries
  - Build verified passing

## Next Suggested Tasks (in priority order)

1. **Polish Phase 7 (LOW)**
   - Port TagInput component (for tagging features)
   - Port CollapsibleCard component (collapsible sections)
   - Enhance CodeBlock component (better syntax highlighting)
   - Auth0 conflict error handling UI

2. **Edit Member Roles (BLOCKED)**
   - Requires backend `PATCH /organizations/{id}/members/{memberId}` endpoint
   - UI is prepared in members settings page, just needs backend API

## Key Files Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Billing API: `frontend-v2/src/lib/api/billing.ts`
- Billing Settings Page: `frontend-v2/src/routes/$orgSlug/settings/billing.tsx`
- Billing Setup Page: `frontend-v2/src/routes/billing/setup.tsx`
- Billing Portal Page: `frontend-v2/src/routes/billing/portal.tsx`
- Query Keys: `frontend-v2/src/lib/query-keys.ts`

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

Remaining:
- Phase 7 polish (TagInput, CollapsibleCard, CodeBlock enhancements)
- Edit member roles (blocked on backend API)
