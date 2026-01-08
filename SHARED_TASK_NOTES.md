# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Validation Integration in Source Connection Forms**
  - Updated `auth-fields-form.tsx` - uses `ValidatedInput` with `getAuthFieldValidation()`
  - Updated `direct-auth-fields.tsx` - credential fields now use validation
  - Updated `config-fields.tsx` - config fields now use validation
  - Updated `source-config-view.tsx` - connection name uses `sourceConnectionNameValidation`
  - Updated `oauth-settings.tsx` - client ID/secret use `clientIdValidation`/`clientSecretValidation`
  - Build verified passing

## Next Suggested Tasks (in priority order)

1. **QueryTool Enhancement - Phase 5 (MEDIUM)**
   - Port full QueryTool component
   - Port LiveApiDoc component
   - Add usage limit checking
   - Add API key validation

2. **SemanticMcp Page - Phase 6 (MEDIUM)**
   - Create `/semantic-mcp` route
   - Implement MCP authentication flow

3. **Billing Management Page (MEDIUM)**
   - Create `/$orgSlug/settings/billing` for managing subscriptions

4. **Polish Phase 7 (LOW)**
   - Port TagInput component
   - Port CollapsibleCard component
   - Enhance CodeBlock component

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
- Old QueryTool: `frontend/src/components/query/QueryTool.tsx`
