import { useCallback } from "react";
import type { FieldValidation } from "@/lib/validation/types";

/**
 * Hook to use validation with TanStack Form
 *
 * Returns a validator function compatible with TanStack Form's validators prop.
 *
 * @example
 * ```tsx
 * import { useFormValidator } from "@/hooks/use-form-validator";
 * import { collectionNameValidation } from "@/lib/validation";
 *
 * const validator = useFormValidator(collectionNameValidation);
 *
 * <form.Field
 *   name="name"
 *   validators={{ onChange: validator }}
 * >
 *   {(field) => <Input ... />}
 * </form.Field>
 * ```
 */
export function useFormValidator<T>(
  validation: FieldValidation<T>,
  context?: unknown
): (opts: { value: T }) => string | undefined {
  return useCallback(
    ({ value }: { value: T }) => {
      const result = validation.validate(value, context);
      if (!result.isValid) {
        return result.hint || result.warning || "Invalid value";
      }
      return undefined;
    },
    [validation, context]
  );
}
