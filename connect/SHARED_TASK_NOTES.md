# Shared Task Notes

## Current Status
Phase 1 (Types & API) is complete. Phase 2 (Direct Auth Flow) is next.

## Next Task
Start Phase 2 by creating `DynamicFormField.tsx` - a component that renders form fields based on `ConfigField` definitions.

### DynamicFormField Implementation Notes
- Location: `src/components/DynamicFormField.tsx`
- Uses the `ConfigField` type from `types.ts`
- Field type mapping:
  - `string` + `is_secret=true` → Password input with show/hide toggle
  - `string` + `is_secret=false` → Text input
  - `number` → Number input
  - `boolean` → Toggle switch
  - `array` → Tag input (comma-separated or similar)
- Props: `{ field: ConfigField; value: unknown; onChange: (value: unknown) => void; error?: string; }`
- Check existing components in `src/components/` for styling patterns (uses Tailwind & Base UI)

## Files Changed This Iteration
- `src/lib/types.ts` - Added all Phase 1 types
- `src/lib/api.ts` - Added `getSourceDetails()` and `createSourceConnection()` methods
- `SPEC.md` - Marked Phase 1 checklist items complete
