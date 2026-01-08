# Shared Task Notes

Context for the next iteration of frontend migration work.

## What Was Done (Latest)

- **Phase 5: QueryTool Enhancement - COMPLETE**
  - Enhanced `ApiIntegrationModal` with view mode selector (REST API vs MCP Server)
  - Added MCP client-specific tabs: Claude, Cursor, Windsurf, Server/Other
  - Each MCP client shows appropriate config file path in footer
  - Added Claude, Cursor, Windsurf, and improved MCP icons
  - Build verified passing
  - Note: frontend-v2 Search component is more advanced than old QueryTool (streaming, toggles, usage limits)

## Next Suggested Tasks (in priority order)

1. **SemanticMcp Page - Phase 6 (MEDIUM)**
   - Create `/semantic-mcp` route
   - Implement MCP authentication flow
   - Reference: `frontend/src/pages/SemanticMcp.tsx`

2. **Billing Management Page (MEDIUM)**
   - Create `/$orgSlug/settings/billing` for managing subscriptions

3. **Polish Phase 7 (LOW)**
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
- Old SemanticMcp: `frontend/src/pages/SemanticMcp.tsx`

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
