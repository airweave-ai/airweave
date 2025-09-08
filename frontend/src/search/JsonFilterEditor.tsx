import React, { useState, useEffect, useRef, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { AlertCircle, CheckCircle2, Copy, Check } from 'lucide-react';
import { apiClient } from '@/lib/api';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

interface JsonFilterEditorProps {
    value: string;
    onChange: (value: string, isValid: boolean) => void;
    placeholder?: string;
    height?: string;
    className?: string;
}

export const JsonFilterEditor: React.FC<JsonFilterEditorProps> = ({
    value,
    onChange,
    placeholder,
    height = "200px",
    className
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';

    // Example filter for users to start with
    const exampleFilter = `{
  "must": [
    {
      "key": "source_name",
      "match": {
        "value": "slack"
      }
    }
  ]
}`;

    // Initialize with example if no value provided
    const [localValue, setLocalValue] = useState(value || exampleFilter);
    const [validationError, setValidationError] = useState<string | null>(null);
    const [isValidating, setIsValidating] = useState(false);
    const [ajv, setAjv] = useState<any>(null);
    const [filterSchema, setFilterSchema] = useState<any>(null);
    const [copied, setCopied] = useState(false);
    const validationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const copyTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Initialize with example on first render if needed
    useEffect(() => {
        if (!value && localValue === exampleFilter) {
            // Initial state with example - trigger onChange
            onChange(exampleFilter, true);
        }
    }, []); // Only run once on mount

    // Initialize AJV and fetch schema
    useEffect(() => {
        const initializeValidation = async () => {
            try {
                // Initialize AJV directly (no dynamic import)
                const ajvInstance = new Ajv({
                    allErrors: true,
                    verbose: true,
                    strict: false,  // Be less strict about additional properties
                    validateSchema: false  // Don't validate the schema itself
                });
                // Add support for date/datetime formats
                addFormats(ajvInstance);
                setAjv(ajvInstance);

                // Fetch the filter schema from backend
                try {
                    const response = await apiClient.get('/collections/internal/filter-schema');
                    if (response.ok) {
                        const schema = await response.json();

                        // Verify the schema looks reasonable
                        if (schema && typeof schema === 'object') {
                            setFilterSchema(schema);
                        } else {
                            console.error('Invalid schema format:', schema);
                        }
                    } else {
                        const errorText = await response.text();
                        console.error('Failed to fetch filter schema:', response.status, errorText);
                    }
                } catch (fetchError) {
                    console.error('Error fetching schema:', fetchError);
                }
            } catch (error) {
                console.error('Failed to initialize filter validation:', error);
            }
        };

        initializeValidation();

        return () => {
            if (validationTimeoutRef.current) {
                clearTimeout(validationTimeoutRef.current);
            }
            if (copyTimeoutRef.current) {
                clearTimeout(copyTimeoutRef.current);
            }
        };
    }, []);

    // Helper function to clean up AJV error messages
    const cleanupErrorMessage = (errors: any[] | null | undefined): string => {
        if (!errors || errors.length === 0) return 'Invalid filter format';

        // Collect unique, meaningful errors
        const errorMessages = new Set<string>();

        for (const error of errors) {
            // Skip generic anyOf errors - they're usually followed by more specific ones
            if (error.keyword === 'anyOf') continue;

            const path = error.instancePath || '';

            // Create a more readable message based on error type
            if (error.keyword === 'required' && error.params?.missingProperty) {
                errorMessages.add(`Missing required field: "${error.params.missingProperty}"${path ? ` at ${path}` : ''}`);
            } else if (error.keyword === 'additionalProperties' && error.params?.additionalProperty) {
                errorMessages.add(`Unknown field: "${error.params.additionalProperty}"${path ? ` at ${path}` : ''}`);
            } else if (error.keyword === 'type') {
                errorMessages.add(`${path || 'Value'} must be ${error.params?.type}`);
            } else if (error.keyword === 'enum') {
                errorMessages.add(`${path || 'Value'} must be one of: ${error.params?.allowedValues?.join(', ')}`);
            } else if (error.message && !error.message.includes('must match')) {
                // Use the error message but clean it up
                errorMessages.add(`${path ? path + ': ' : ''}${error.message}`);
            }
        }

        // If we have specific errors, use them; otherwise try to be helpful
        const messages = Array.from(errorMessages);
        if (messages.length === 0) {
            // Look for common patterns in the original errors
            const hasMatchError = errors.some(e => e.instancePath?.includes('/match'));
            if (hasMatchError) {
                return 'Invalid match condition. Use either "value", "text", "any", or "except"';
            }
            return 'Invalid filter format';
        }

        // Return up to 2 error messages for clarity
        return messages.slice(0, 2).join('. ');
    };

    // Validate the JSON filter
    const validateFilter = useCallback((filterValue: string) => {
        if (!filterValue.trim()) {
            return { isValid: true, error: null }; // Empty is valid (no filter)
        }

        // First check if it's valid JSON
        let parsed;
        try {
            parsed = JSON.parse(filterValue);
        } catch (e) {
            console.error('JSON parse failed:', e);
            return { isValid: false, error: 'Invalid JSON syntax' };
        }

        // If we don't have AJV or schema yet, only check JSON syntax
        if (!ajv || !filterSchema) {
            return { isValid: true, error: null };
        }

        try {
            // Try to compile the schema - this might fail if schema is invalid
            let validate;
            try {
                validate = ajv.compile(filterSchema);
            } catch (compileError) {
                console.error('Failed to compile schema:', compileError);
                // If we can't compile the schema, just check JSON syntax
                return { isValid: true, error: null };
            }

            const isValid = validate(parsed);

            if (!isValid && validate.errors) {
                // Use the cleanup function for better error messages
                const cleanError = cleanupErrorMessage(validate.errors);
                return { isValid: false, error: cleanError };
            }

            return { isValid: true, error: null };
        } catch (e) {
            console.error('Validation error:', e);
            // If validation fails catastrophically, just accept it
            return { isValid: true, error: null };
        }
    }, [ajv, filterSchema]);

    // Validate current value when AJV/schema becomes available or value changes from outside
    useEffect(() => {
        if (localValue && ajv && filterSchema) {
            // Validate existing value when dependencies are ready
            const validation = validateFilter(localValue);
            setValidationError(validation.error);
        }
    }, [ajv, filterSchema, validateFilter, localValue]);

    // Handle input changes with debounced validation
    const handleChange = useCallback((newValue: string) => {
        setLocalValue(newValue);

        // If empty, immediately mark as valid
        if (!newValue.trim()) {
            setValidationError(null);
            setIsValidating(false);
            onChange('', true);
            return;
        }

        setIsValidating(true);

        // Clear previous timeout
        if (validationTimeoutRef.current) {
            clearTimeout(validationTimeoutRef.current);
        }

        // Debounce validation
        validationTimeoutRef.current = setTimeout(() => {
            const validation = validateFilter(newValue);
            setValidationError(validation.error);
            setIsValidating(false);

            // Always propagate the value, along with its validity status
            onChange(newValue, validation.isValid);
        }, 500);
    }, [validateFilter, onChange]);

    const handleCopy = useCallback(() => {
        const textToCopy = localValue.trim();
        if (textToCopy) {
            navigator.clipboard.writeText(textToCopy);
            setCopied(true);

            if (copyTimeoutRef.current) {
                clearTimeout(copyTimeoutRef.current);
            }
            copyTimeoutRef.current = setTimeout(() => {
                setCopied(false);
            }, 2000);
        }
    }, [localValue]);

    return (
        <div className={cn("space-y-2", className)}>
            <div className="relative">
                <textarea
                    value={localValue}
                    onChange={(e) => handleChange(e.target.value)}
                    className={cn(
                        "w-full font-mono text-xs p-3 pr-20 rounded-md border resize-none",
                        "transition-colors",
                        isDark
                            ? "bg-gray-900 text-gray-100 border-gray-700 placeholder:text-gray-600"
                            : "bg-white text-gray-900 border-gray-300 placeholder:text-gray-400",
                        validationError
                            ? "border-red-500 focus:border-red-500"
                            : "focus:border-blue-500",
                        "focus:outline-none focus:ring-1",
                        validationError
                            ? "focus:ring-red-500"
                            : "focus:ring-blue-500"
                    )}
                    style={{ height }}
                    spellCheck={false}
                />

                {/* Validation and copy indicators */}
                <div className="absolute top-2 right-2 flex items-center gap-2">
                    {/* Copy button */}
                    <button
                        type="button"
                        onClick={handleCopy}
                        className={cn(
                            "p-1 rounded transition-colors",
                            isDark
                                ? "hover:bg-gray-700 text-gray-400 hover:text-gray-200"
                                : "hover:bg-gray-100 text-gray-600 hover:text-gray-900"
                        )}
                        title="Copy filter"
                    >
                        {copied ? (
                            <Check className="h-3.5 w-3.5 text-green-500" />
                        ) : (
                            <Copy className="h-3.5 w-3.5" />
                        )}
                    </button>

                    {/* Validation indicator */}
                    {isValidating ? (
                        <div className="text-gray-400 text-xs">Validating...</div>
                    ) : validationError ? (
                        <AlertCircle className="h-4 w-4 text-red-500" />
                    ) : localValue.trim() ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                    ) : null}
                </div>
            </div>

            {/* Error message */}
            {validationError && (
                <div className="text-xs text-red-500 flex items-start gap-1">
                    <AlertCircle className="h-3 w-3 mt-0.5 flex-shrink-0" />
                    <span>{validationError}</span>
                </div>
            )}
        </div>
    );
};
