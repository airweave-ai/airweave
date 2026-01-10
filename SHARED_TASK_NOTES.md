# Shared Task Notes

Context for the next iteration.

## Project Status: COMPLETE

The frontend migration from `frontend` to `frontend-v2` is **complete**.

### Verification (2026-01-08)
- Build: Passes (4.13s, no errors)
- Lint: Passes (0 warnings)
- Tests: All 25 pass

### What's Done
- All Phase 1-7 migration tasks complete
- All routes ported
- All features implemented
- All UI components ported (including ValidatedInput, TagInput, CollapsibleCard, CodeBlock)
- PostHog integration complete
- Real-time sync infrastructure complete
- Billing enforcement complete
- S3 configuration complete (feature-flagged)

### Remaining (Blocked)
The only incomplete item requires backend work:
- **Edit Member Roles**: Needs `PATCH /organizations/{id}/members/{memberId}` API endpoint
  - Backend CRUD function `update_member_role` exists in `crud_organization.py`
  - No API route exposes this function yet
  - Frontend UI placeholder exists in members settings page

## Key Files Reference

### Migration Spec
- `MIGRATION_SPEC.md` - Full migration specification with checklist

### Frontend-v2 Structure
- Routes: `frontend-v2/src/routes/`
- Components: `frontend-v2/src/components/`
- Features: `frontend-v2/src/features/`
- API: `frontend-v2/src/lib/api/`
- Validation: `frontend-v2/src/lib/validation/`

## Next Steps

If backend support for member role editing is added:
1. Create API function in `frontend-v2/src/lib/api/organizations.ts`:
   ```typescript
   export async function updateMemberRole(
     token: string,
     organizationId: string,
     memberId: string,
     role: 'admin' | 'member'
   ): Promise<void>
   ```
2. Add mutation in `frontend-v2/src/routes/$orgSlug/settings/members.tsx`
3. Add edit button/dropdown to member row UI

Otherwise, the frontend migration project is complete.
