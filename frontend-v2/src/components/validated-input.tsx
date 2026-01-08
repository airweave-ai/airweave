import { useState, useEffect, useRef } from "react";

import { Input } from "@/components/ui/input";
import type { FieldValidation, ValidationResult } from "@/lib/validation/types";
import { cn } from "@/lib/utils";

interface ValidatedInputProps extends Omit<
  React.ComponentProps<"input">,
  "onChange"
> {
  value: string;
  onChange: (value: string) => void;
  validation?: FieldValidation<string>;
  context?: unknown;
  showValidation?: boolean;
  forceValidate?: boolean;
}

/**
 * Input component with built-in validation support
 *
 * This component wraps the base Input component and adds validation
 * with debounced hints/warnings based on FieldValidation rules.
 *
 * @example
 * ```tsx
 * import { ValidatedInput } from "@/components/validated-input";
 * import { collectionNameValidation } from "@/lib/validation";
 *
 * function MyForm() {
 *   const [name, setName] = useState("");
 *
 *   return (
 *     <ValidatedInput
 *       value={name}
 *       onChange={setName}
 *       validation={collectionNameValidation}
 *       placeholder="Enter collection name"
 *     />
 *   );
 * }
 * ```
 *
 * @example
 * With TanStack Form:
 * ```tsx
 * <form.Field name="collectionName">
 *   {(field) => (
 *     <ValidatedInput
 *       value={field.state.value}
 *       onChange={field.handleChange}
 *       validation={collectionNameValidation}
 *       onBlur={field.handleBlur}
 *     />
 *   )}
 * </form.Field>
 * ```
 */
export function ValidatedInput({
  value,
  onChange,
  validation,
  context,
  showValidation = true,
  forceValidate = false,
  className,
  onBlur,
  ...props
}: ValidatedInputProps) {
  const [validationResult, setValidationResult] =
    useState<ValidationResult | null>(null);
  const [shouldShow, setShouldShow] = useState(false);
  const showTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!validation) return;

    // Clear any existing show timer when value changes
    if (showTimer.current) {
      clearTimeout(showTimer.current);
      showTimer.current = null;
      setShouldShow(false);
    }

    const result = validation.validate(value, context);
    setValidationResult(result);

    if (forceValidate) {
      setShouldShow(true);
    } else if (validation.showOn === "change" || !validation.showOn) {
      const timerId = setTimeout(() => {
        setShouldShow(true);
      }, validation.debounceMs || 500);
      showTimer.current = timerId;
    }

    const capturedShowTimer = showTimer.current;
    return () => {
      if (capturedShowTimer) {
        clearTimeout(capturedShowTimer);
      }
    };
  }, [value, context, validation, forceValidate]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    // Show validation on blur if we have a result
    if (
      validation &&
      validationResult &&
      (validation.showOn === "blur" ||
        validation.showOn === "change" ||
        !validation.showOn)
    ) {
      setShouldShow(true);
    }
    onBlur?.(e);
  };

  // Determine if input should show invalid state
  const isInvalid =
    shouldShow &&
    showValidation &&
    validationResult &&
    !validationResult.isValid;

  // Get the hint text to display
  const getHintText = () => {
    if (!shouldShow || !showValidation || !validationResult) return null;
    return validationResult.hint || validationResult.warning;
  };

  // Get hint text color
  const getHintColor = () => {
    if (!validationResult) return "";

    if (validationResult.severity === "warning") {
      return "text-amber-600 dark:text-amber-400";
    }

    return "text-muted-foreground";
  };

  const hintText = getHintText();

  return (
    <div className="w-full">
      <Input
        {...props}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        aria-invalid={isInvalid ? "true" : undefined}
        className={cn(
          isInvalid &&
            validationResult?.severity === "warning" &&
            "border-amber-400/50 focus-visible:border-amber-400 focus-visible:ring-amber-400/20",
          className
        )}
      />

      {/* Validation hint */}
      {hintText && (
        <p
          className={cn("mt-1.5 text-xs", getHintColor())}
          role="status"
          aria-live="polite"
        >
          {hintText}
        </p>
      )}
    </div>
  );
}
