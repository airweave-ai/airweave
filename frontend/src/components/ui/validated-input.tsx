import React, { useState, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import type { FieldValidation, ValidationResult } from '@/lib/validation/types';

interface ValidatedInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  value: string;
  onChange: (value: string) => void;
  validation?: FieldValidation<string>;
  context?: any;
  showValidation?: boolean;
  forceValidate?: boolean;
}

export const ValidatedInput: React.FC<ValidatedInputProps> = ({
  value,
  onChange,
  validation,
  context,
  showValidation = true,
  forceValidate = false,
  className,
  onBlur,
  ...props
}) => {
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [shouldShow, setShouldShow] = useState(false);
  const debounceTimer = useRef<NodeJS.Timeout>();
  const showTimer = useRef<NodeJS.Timeout>();

  // Run validation
  useEffect(() => {
    if (!validation) return;

    // Clear any existing show timer when value changes
    if (showTimer.current) {
      clearTimeout(showTimer.current);
      setShouldShow(false);
    }

    const runValidation = () => {
      const result = validation.validate(value, context);
      setValidationResult(result);

      // Set timer to show validation after debounce
      if (validation.showOn === 'change' || !validation.showOn) {
        showTimer.current = setTimeout(() => {
          setShouldShow(true);
        }, validation.debounceMs || 500);
      }
    };

    // Clear previous validation timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Run validation immediately to get result, but don't show yet
    const result = validation.validate(value, context);
    setValidationResult(result);

    // If force validate, show immediately
    if (forceValidate) {
      setShouldShow(true);
    }

    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
      if (showTimer.current) {
        clearTimeout(showTimer.current);
      }
    };
  }, [value, context, validation, forceValidate]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    // Show validation on blur if we have a result
    if (validation && validationResult && (validation.showOn === 'blur' || validation.showOn === 'change' || !validation.showOn)) {
      setShouldShow(true);
    }
    onBlur?.(e);
  };

  const handleFocus = () => {
    // Don't hide on focus - keep showing if already visible
  };

  // Determine input border color based on validation state
  const getBorderClass = () => {
    if (!shouldShow || !showValidation || !validationResult) {
      return '';
    }

    if (validationResult.severity === 'warning') {
      return 'border-amber-400/30 focus:border-amber-400/50';
    }

    if (!validationResult.isValid) {
      return 'border-amber-400/20 focus:border-amber-400/40';
    }

    return '';
  };

  // Get the hint text to display
  const getHintText = () => {
    if (!shouldShow || !showValidation || !validationResult) return null;
    return validationResult.hint || validationResult.warning;
  };

  // Get hint text color
  const getHintColor = () => {
    if (!validationResult) return '';

    if (validationResult.severity === 'warning') {
      return 'text-amber-600 dark:text-amber-400';
    }

    return 'text-gray-500 dark:text-gray-400';
  };

  const hintText = getHintText();

  return (
    <div className="w-full">
      <input
        {...props}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        onFocus={handleFocus}
        className={cn(
          'w-full px-4 py-2 rounded-lg text-sm',
          'border transition-colors duration-150',
          'focus:outline-none',
          getBorderClass(),
          className
        )}
      />

      {/* Validation hint - no animations */}
      {hintText && (
        <div
          className={cn(
            'text-xs mt-1.5',
            getHintColor()
          )}
          role="status"
          aria-live="polite"
        >
          {hintText}
        </div>
      )}
    </div>
  );
};
