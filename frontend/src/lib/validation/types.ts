/**
 * Core validation types for the Airweave validation system
 */

export type ValidationSeverity = 'info' | 'warning';

export interface ValidationResult {
  isValid: boolean;
  hint?: string;           // Helpful guidance text
  warning?: string;        // Soft warning (user can proceed)
  severity: ValidationSeverity;
}

export type ValidationTrigger = 'blur' | 'change' | 'submit';

export interface FieldValidation<T = any> {
  field: string;
  validate: (value: T, context?: any) => ValidationResult;
  debounceMs?: number;     // Delay before showing validation
  showOn?: ValidationTrigger;
}

export interface ValidationState {
  [field: string]: ValidationResult | null;
}
