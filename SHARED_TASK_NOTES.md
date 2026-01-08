# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Phase 6: SemanticMcp Page - COMPLETE**
  - Created `/semantic-mcp` route at `frontend-v2/src/routes/semantic-mcp.tsx`
  - Implemented source connection grid with SmallSourceButton component
  - Added authentication dialog for both OAuth and direct (API key/credentials) auth flows
  - Integrated real-time sync status display for connected sources
  - Added Search component integration for querying synced data
  - Session storage used for persisting state across OAuth redirects
  - Theme toggle (light/dark/system) in header
  - Build verified passing

## Next Suggested Tasks (in priority order)

1. **Billing Management Page (MEDIUM)**
   - Create `/$orgSlug/settings/billing` for managing subscriptions
   - Should allow users to upgrade/downgrade plans
   - Connect to Stripe portal

2. **Polish Phase 7 (LOW)**
   - Port TagInput component
   - Port CollapsibleCard component
   - Enhance CodeBlock component

## Blocked Tasks

- **Edit Member Roles** - Requires backend `PATCH /organizations/{id}/members/{memberId}` endpoint

## Key Files Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Validation system: `frontend-v2/src/lib/validation/`
- ValidatedInput: `frontend-v2/src/components/validated-input.tsx`
- API Integration Modal: `frontend-v2/src/features/search/components/api-integration-modal.tsx`
- SemanticMcp Page: `frontend-v2/src/routes/semantic-mcp.tsx`

## How to Use the Validation System

```typescript
// Option 1: ValidatedInput with built-in validation display
import { ValidatedInput } from "@/components/validated-input";
import { collectionNameValidation } from "@/lib/validation";

function MyForm() {
  const [name, setName] = useState("");

  return (
    <ValidatedInput
      value={name}
      onChange={setName}
      validation={collectionNameValidation}
      placeholder="Enter collection name"
    />
  );
}

// Option 2: With TanStack Form using createFormValidator
import { createFormValidator, collectionNameValidation } from "@/lib/validation";
import { ValidatedInput } from "@/components/validated-input";

function MyTanStackForm() {
  return (
    <form.Field
      name="name"
      validators={{ onChange: createFormValidator(collectionNameValidation) }}
    >
      {(field) => (
        <ValidatedInput
          value={field.state.value}
          onChange={field.handleChange}
          onBlur={field.handleBlur}
          validation={collectionNameValidation}
        />
      )}
    </form.Field>
  );
}
```
