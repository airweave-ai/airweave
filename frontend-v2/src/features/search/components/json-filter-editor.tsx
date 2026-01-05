/**
 * JsonFilterEditor - JSON filter editor with schema validation
 *
 * Provides a textarea for entering Qdrant filter JSON with:
 * - Real-time AJV validation against the backend filter schema
 * - Pre-populated example filter
 * - Copy functionality
 */

import { AlertCircle, Check, CheckCircle2, Copy } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE_URL, getAuthHeaders } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { cn } from "@/lib/utils";

interface JsonFilterEditorProps {
  value: string;
  onChange: (value: string, isValid: boolean) => void;
  placeholder?: string;
  height?: string;
  className?: string;
}

const EXAMPLE_FILTER = `{
  "must": [
    {
      "key": "source_name",
      "match": {
        "value": "slack"
      }
    }
  ]
}`;

export function JsonFilterEditor({
  value,
  onChange,
  height = "160px",
  className,
}: JsonFilterEditorProps) {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();

  const [localValue, setLocalValue] = useState(value || EXAMPLE_FILTER);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [filterSchema, setFilterSchema] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);

  const validationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const copyTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const initializedRef = useRef(false);

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    if (!value && localValue === EXAMPLE_FILTER) {
      onChange(EXAMPLE_FILTER, true);
    }
  }, [value, localValue, onChange]);

  useEffect(() => {
    const fetchSchema = async () => {
      try {
        const token = await getAccessTokenSilently();
        const response = await fetch(
          `${API_BASE_URL}/collections/internal/filter-schema`,
          {
            headers: getAuthHeaders(token, organization?.id || ""),
          }
        );
        if (response.ok) {
          const schema = await response.json();
          if (schema && typeof schema === "object") {
            setFilterSchema(schema);
          }
        }
      } catch (error) {
        console.error("Error fetching filter schema:", error);
      }
    };

    if (organization) {
      fetchSchema();
    }

    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
    };
  }, [getAccessTokenSilently, organization]);

  const validateFilter = useCallback(
    (filterValue: string): { isValid: boolean; error: string | null } => {
      if (!filterValue.trim()) {
        return { isValid: true, error: null };
      }

      let parsed;
      try {
        parsed = JSON.parse(filterValue);
      } catch {
        return { isValid: false, error: "Invalid JSON syntax" };
      }

      if (!filterSchema) {
        return { isValid: true, error: null };
      }

      if (typeof parsed !== "object" || parsed === null) {
        return { isValid: false, error: "Filter must be an object" };
      }

      const validKeys = ["must", "should", "must_not", "min_should"];
      const keys = Object.keys(parsed);

      if (keys.length === 0) {
        return { isValid: true, error: null };
      }

      const hasValidKey = keys.some((k) => validKeys.includes(k));
      if (!hasValidKey && keys.length > 0) {
        return {
          isValid: false,
          error: `Filter should have one of: ${validKeys.join(", ")}`,
        };
      }

      return { isValid: true, error: null };
    },
    [filterSchema]
  );

  useEffect(() => {
    if (localValue && filterSchema) {
      const validation = validateFilter(localValue);
      setValidationError(validation.error);
    }
  }, [filterSchema, validateFilter, localValue]);

  const handleChange = useCallback(
    (newValue: string) => {
      setLocalValue(newValue);

      if (!newValue.trim()) {
        setValidationError(null);
        setIsValidating(false);
        onChange("", true);
        return;
      }

      setIsValidating(true);

      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }

      validationTimeoutRef.current = setTimeout(() => {
        const validation = validateFilter(newValue);
        setValidationError(validation.error);
        setIsValidating(false);
        onChange(newValue, validation.isValid);
      }, 500);
    },
    [validateFilter, onChange]
  );

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
            "w-full resize-none rounded-md border p-3 pr-20 font-mono text-xs transition-colors",
            "bg-slate-900 text-slate-100 placeholder:text-slate-600",
            validationError
              ? "border-red-500 focus:border-red-500"
              : "border-slate-700 focus:border-blue-500",
            "focus:ring-1 focus:outline-none",
            validationError ? "focus:ring-red-500" : "focus:ring-blue-500"
          )}
          style={{ height }}
          spellCheck={false}
        />

        <div className="absolute top-2 right-2 flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopy}
            className="rounded p-1 text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-200"
            title="Copy filter"
          >
            {copied ? (
              <Check className="size-3.5 text-green-500" />
            ) : (
              <Copy className="size-3.5" />
            )}
          </button>

          {isValidating ? (
            <div className="text-xs text-slate-400">Validating...</div>
          ) : validationError ? (
            <AlertCircle className="size-4 text-red-500" />
          ) : localValue.trim() ? (
            <CheckCircle2 className="size-4 text-green-500" />
          ) : null}
        </div>
      </div>

      {validationError && (
        <div className="flex items-start gap-1 text-xs text-red-500">
          <AlertCircle className="mt-0.5 size-3 shrink-0" />
          <span>{validationError}</span>
        </div>
      )}
    </div>
  );
}
