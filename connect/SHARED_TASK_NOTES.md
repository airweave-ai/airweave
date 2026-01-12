# Shared Task Notes

## Current Status
Phase 2 (Direct Auth Flow) is in progress. Both `DynamicFormField.tsx` and `AuthMethodSelector.tsx` are complete.

## Next Task
Create `SourceConfigView.tsx` - the main configuration view for creating a source connection.

### SourceConfigView Implementation Notes
- Location: `src/components/SourceConfigView.tsx`
- This is the largest component in Phase 2, so consider breaking it into steps:
  1. Basic structure with header, back button, and source info
  2. Connection name input field
  3. Auth method selector (using AuthMethodSelector component)
  4. Direct auth fields section (using DynamicFormField)
  5. Config fields section (using DynamicFormField)
  6. Submit button and form handling
  7. API integration with `createSourceConnection()`

### Props (from SPEC.md)
```typescript
interface SourceConfigViewProps {
  source: Source;
  session: ConnectSessionContext;
  onBack: () => void;
  onSuccess: (connectionId: string) => void;
}
```

### State to manage
```typescript
const [sourceDetails, setSourceDetails] = useState<SourceDetails | null>(null);
const [authMethod, setAuthMethod] = useState<"direct" | "oauth_browser">("direct");
const [connectionName, setConnectionName] = useState("");
const [authValues, setAuthValues] = useState<Record<string, unknown>>({});
const [configValues, setConfigValues] = useState<Record<string, unknown>>({});
const [errors, setErrors] = useState<Record<string, string>>({});
const [isSubmitting, setIsSubmitting] = useState(false);
```

### Key API methods to use
- `api.getSourceDetails(source.short_name)` - to fetch auth_fields and config_fields
- `api.createSourceConnection(payload)` - to create the connection

### After SourceConfigView
Next tasks will be modifying `SuccessScreen.tsx` to:
- Add `selectedSource` state
- Add `configure` view rendering
- Wire up `handleSelectSource` to navigate to configure view

## Reference Components
- `DynamicFormField.tsx` - for rendering form fields based on ConfigField definition
- `AuthMethodSelector.tsx` - for selecting between direct and OAuth auth methods
- `SourceItem.tsx` - for styling patterns (border, hover states)
- `Button.tsx` - for button styling
