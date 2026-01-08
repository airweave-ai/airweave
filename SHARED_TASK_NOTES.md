# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Validation System (Phase 4) - PARTIAL**
  - Created `frontend-v2/src/lib/validation/types.ts` - Core validation types
  - Created `frontend-v2/src/lib/validation/rules.ts` - All 25+ validation rules ported
  - Created `frontend-v2/src/lib/validation/index.ts` - Barrel export
  - Created `frontend-v2/src/components/validated-input.tsx` - ValidatedInput component + useFormValidator hook
  - Features:
    - Debounced validation hints with configurable timing
    - Support for 'change', 'blur', 'submit' triggers
    - Severity-based styling (info vs warning)
    - `useFormValidator` hook for TanStack Form integration
    - Compatible with TanStack Form's validators prop

## Next Suggested Tasks (in priority order)

1. **Integrate Validation in Forms (HIGH)**
   - Update `frontend-v2/src/features/collections/components/create-dialog.tsx` to use ValidatedInput
   - Update auth provider forms to use validation rules
   - Update source connection forms to use getAuthFieldValidation()

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

// Option 2: With TanStack Form using the hook
import { useFormValidator } from "@/components/validated-input";
import { collectionNameValidation } from "@/lib/validation";

function MyTanStackForm() {
  const nameValidator = useFormValidator(collectionNameValidation);

  return (
    <form.Field
      name="name"
      validators={{ onChange: nameValidator }}
    >
      {(field) => (
        <Input
          value={field.state.value}
          onChange={(e) => field.handleChange(e.target.value)}
          onBlur={field.handleBlur}
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
- Old QueryTool: `frontend/src/components/query/QueryTool.tsx`
