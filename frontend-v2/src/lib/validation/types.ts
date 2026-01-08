/**
 * Core validation types for the Airweave validation system
 */

export type ValidationSeverity = "info" | "warning";

export interface ValidationResult {
  isValid: boolean;
  hint?: string; // Helpful guidance text
  warning?: string; // Soft warning (user can proceed)
  severity: ValidationSeverity;
}

export type ValidationTrigger = "blur" | "change" | "submit";

export interface FieldValidation<T = unknown> {
  field: string;
  validate: (value: T, context?: unknown) => ValidationResult;
  debounceMs?: number; // Delay before showing validation
  showOn?: ValidationTrigger;
}

export interface ValidationState {
  [field: string]: ValidationResult | null;
}

/**
 * Helper to create a TanStack Form validator from a FieldValidation
 * Returns the hint/warning message if invalid, undefined if valid
 */
export function createFormValidator<T>(
  validation: FieldValidation<T>,
  context?: unknown
): (opts: { value: T }) => string | undefined {
  return ({ value }) => {
    const result = validation.validate(value, context);
    if (!result.isValid) {
      return result.hint || result.warning || "Invalid value";
    }
    return undefined;
  };
}

/**
 * Helper to get validation result without converting to form validator format
 * Useful when you need access to both isValid and hint/warning separately
 */
export function getValidationResult<T>(
  validation: FieldValidation<T>,
  value: T,
  context?: unknown
): ValidationResult {
  return validation.validate(value, context);
}
