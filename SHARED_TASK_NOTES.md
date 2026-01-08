# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Validation Integration in Create Collection Dialog**
  - Updated `frontend-v2/src/features/collections/components/create-dialog.tsx`
  - Replaced inline validators with `createFormValidator(collectionNameValidation)`
  - Added `ValidatedInput` component for the name field with debounced validation hints
  - Build verified passing

## Next Suggested Tasks (in priority order)

1. **Continue Validation Integration (HIGH)**
   - Update auth provider forms to use validation rules
   - Update source connection forms to use `getAuthFieldValidation()`
   - Look for other forms that could benefit from validation

2. **QueryTool Enhancement - Phase 5 (MEDIUM)**
   - Port full QueryTool component
   - Port LiveApiDoc component

3. **SemanticMcp Page - Phase 6 (MEDIUM)**
   - Create `/semantic-mcp` route
   - Implement MCP authentication flow

4. **Billing Management Page (MEDIUM)**
   - Create `/$orgSlug/settings/billing` for managing subscriptions

## Blocked Tasks

- **Edit Member Roles** - Requires backend `PATCH /organizations/{id}/members/{memberId}` endpoint

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

// Option 3: Dynamic validation based on field type
import { getAuthFieldValidation } from "@/lib/validation";

// Returns appropriate validation for the field type
const validation = getAuthFieldValidation("api_key", "stripe"); // Returns stripeApiKeyValidation
const validation = getAuthFieldValidation("host"); // Returns databaseHostValidation
```

## Key Files to Reference

- Main migration spec: `MIGRATION_SPEC.md`
- Old frontend source: `frontend/src/`
- New frontend source: `frontend-v2/src/`
- Validation system: `frontend-v2/src/lib/validation/`
- ValidatedInput: `frontend-v2/src/components/validated-input.tsx`
- Create collection dialog (validation integrated): `frontend-v2/src/features/collections/components/create-dialog.tsx`
- Old QueryTool: `frontend/src/components/query/QueryTool.tsx`
