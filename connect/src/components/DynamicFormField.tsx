import { Eye, EyeOff, X } from "lucide-react";
import { marked } from "marked";
import { useState } from "react";
import { useTheme } from "../lib/theme";
import type { ConfigField } from "../lib/types";

// Safe URL protocols for links in field descriptions
const SAFE_PROTOCOLS = ["http:", "https:", "mailto:"];

/**
 * Validates that a URL uses a safe protocol to prevent XSS attacks.
 * Returns true if the URL is safe, false otherwise.
 */
function isSafeUrl(href: string): boolean {
  try {
    const url = new URL(href, window.location.origin);
    return SAFE_PROTOCOLS.includes(url.protocol);
  } catch {
    // Invalid URL
    return false;
  }
}

// Configure marked to render links with underline and open in new tab
// with XSS protection by validating URL protocols
const renderer = new marked.Renderer();
renderer.link = ({ href, text }) => {
  // Validate URL protocol to prevent XSS (e.g., javascript: URLs)
  if (!isSafeUrl(href)) {
    // Return plain text for unsafe protocols
    return text;
  }
  return `<a href="${href}" target="_blank" rel="noopener noreferrer" style="text-decoration: underline; font-weight: 500;">${text}</a>`;
};
marked.use({ renderer });

interface DynamicFormFieldProps {
  field: ConfigField;
  value: unknown;
  onChange: (value: unknown) => void;
  error?: string;
}

interface FieldWrapperProps {
  field: ConfigField;
  error?: string;
  children: React.ReactNode;
}

const inputBaseStyles = (error?: string) => ({
  backgroundColor: "var(--connect-surface)",
  color: "var(--connect-text)",
  borderColor: error ? "var(--connect-error)" : "var(--connect-border)",
});

function FieldWrapper({ field, error, children }: FieldWrapperProps) {
  const { labels } = useTheme();
  const labelId = `field-${field.name}`;
  const errorId = `error-${field.name}`;

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between gap-2 mb-1">
        <label
          id={labelId}
          htmlFor={`input-${field.name}`}
          className="text-sm font-medium truncate grow"
          style={{ color: "var(--connect-text)" }}
        >
          {field.title}
        </label>
        {!field.required && (
          <span
            className="text-xs shrink-0"
            style={{ color: "var(--connect-text-muted)" }}
          >
            {labels.fieldOptional}
          </span>
        )}
      </div>
      {field.description && (
        <p
          className="text-xs mt-1 mb-2"
          style={{ color: "var(--connect-text-muted)" }}
          dangerouslySetInnerHTML={{
            __html: marked.parseInline(field.description) as string,
          }}
        />
      )}
      {children}
      {error && (
        <p
          id={errorId}
          className="text-xs mt-1"
          style={{ color: "var(--connect-error)" }}
        >
          {error}
        </p>
      )}
    </div>
  );
}

interface StringFieldProps {
  field: ConfigField;
  value: string;
  onChange: (value: string) => void;
  error?: string;
}

function StringField({ field, value, onChange, error }: StringFieldProps) {
  const [showSecret, setShowSecret] = useState(false);
  const isSecret = field.is_secret === true;
  const inputType = isSecret && !showSecret ? "password" : "text";
  const inputId = `input-${field.name}`;

  return (
    <FieldWrapper field={field} error={error}>
      <div className="relative">
        <input
          id={inputId}
          type={inputType}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-2 text-sm rounded-md border outline-none transition-colors"
          style={inputBaseStyles(error)}
          aria-invalid={!!error}
        />
        {isSecret && (
          <button
            type="button"
            onClick={() => setShowSecret(!showSecret)}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-xs rounded"
            style={{ color: "var(--connect-text-muted)" }}
            aria-label={showSecret ? "Hide value" : "Show value"}
          >
            {showSecret ? (
              <EyeOff className="w-4 h-4" />
            ) : (
              <Eye className="w-4 h-4" />
            )}
          </button>
        )}
      </div>
    </FieldWrapper>
  );
}

interface NumberFieldProps {
  field: ConfigField;
  value: number | undefined;
  onChange: (value: number | undefined) => void;
  error?: string;
}

function NumberField({ field, value, onChange, error }: NumberFieldProps) {
  const inputId = `input-${field.name}`;

  return (
    <FieldWrapper field={field} error={error}>
      <input
        id={inputId}
        type="number"
        value={value ?? ""}
        onChange={(e) => {
          const num =
            e.target.value === "" ? undefined : Number(e.target.value);
          onChange(num);
        }}
        className="w-full px-3 py-2 text-sm rounded-md border outline-none transition-colors"
        style={inputBaseStyles(error)}
        aria-invalid={!!error}
      />
    </FieldWrapper>
  );
}

interface BooleanFieldProps {
  field: ConfigField;
  value: boolean;
  onChange: (value: boolean) => void;
  error?: string;
}

function BooleanField({ field, value, onChange, error }: BooleanFieldProps) {
  const { labels } = useTheme();
  const isChecked = value ?? false;
  const labelId = `field-${field.name}`;

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <label
              id={labelId}
              className="text-sm font-medium truncate grow"
              style={{ color: "var(--connect-text)" }}
            >
              {field.title}
            </label>
            {!field.required && (
              <span
                className="text-xs shrink-0"
                style={{ color: "var(--connect-text-muted)" }}
              >
                {labels.fieldOptional}
              </span>
            )}
          </div>
          {field.description && (
            <p
              className="text-xs mt-1 mb-2"
              style={{ color: "var(--connect-text-muted)" }}
            >
              {field.description}
            </p>
          )}
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={isChecked}
          aria-labelledby={labelId}
          onClick={() => onChange(!isChecked)}
          className="relative w-10 h-6 rounded-full transition-colors flex-shrink-0 ml-3"
          style={{
            backgroundColor: isChecked
              ? "var(--connect-primary)"
              : "var(--connect-border)",
          }}
        >
          <span
            className="absolute top-1 w-4 h-4 rounded-full bg-white transition-transform"
            style={{
              left: isChecked ? "calc(100% - 1.25rem)" : "0.25rem",
            }}
          />
        </button>
      </div>
      {error && (
        <p className="text-xs mt-1" style={{ color: "var(--connect-error)" }}>
          {error}
        </p>
      )}
    </div>
  );
}

interface ArrayFieldProps {
  field: ConfigField;
  value: string[];
  onChange: (value: string[]) => void;
  error?: string;
}

function ArrayField({ field, value, onChange, error }: ArrayFieldProps) {
  const [inputValue, setInputValue] = useState("");
  const arrayValue = value ?? [];
  const inputId = `input-${field.name}`;

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !arrayValue.includes(trimmed)) {
      onChange([...arrayValue, trimmed]);
    }
    setInputValue("");
  };

  const removeTag = (index: number) => {
    const newArray = [...arrayValue];
    newArray.splice(index, 1);
    onChange(newArray);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(inputValue);
    } else if (
      e.key === "Backspace" &&
      inputValue === "" &&
      arrayValue.length > 0
    ) {
      removeTag(arrayValue.length - 1);
    }
  };

  return (
    <FieldWrapper field={field} error={error}>
      <div
        className="flex flex-wrap gap-1 p-2 rounded-md border min-h-[42px]"
        style={inputBaseStyles(error)}
      >
        {arrayValue.map((tag, index) => (
          <span
            key={index}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded"
            style={{
              backgroundColor: "var(--connect-primary)",
              color: "white",
            }}
          >
            {tag}
            <button
              type="button"
              onClick={() => removeTag(index)}
              className="hover:opacity-80"
              aria-label={`Remove ${tag}`}
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
        <input
          id={inputId}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => inputValue && addTag(inputValue)}
          placeholder={arrayValue.length === 0 ? "Type and press Enter" : ""}
          className="flex-1 min-w-[100px] text-sm bg-transparent border-none outline-none"
          style={{ color: "var(--connect-text)" }}
        />
      </div>
    </FieldWrapper>
  );
}

export function DynamicFormField({
  field,
  value,
  onChange,
  error,
}: DynamicFormFieldProps) {
  switch (field.type) {
    case "string":
      return (
        <StringField
          field={field}
          value={value as string}
          onChange={onChange}
          error={error}
        />
      );
    case "number":
      return (
        <NumberField
          field={field}
          value={value as number | undefined}
          onChange={onChange}
          error={error}
        />
      );
    case "boolean":
      return (
        <BooleanField
          field={field}
          value={value as boolean}
          onChange={onChange}
          error={error}
        />
      );
    case "array":
      return (
        <ArrayField
          field={field}
          value={value as string[]}
          onChange={onChange}
          error={error}
        />
      );
    default:
      return (
        <FieldWrapper field={field} error={error}>
          <p className="text-xs" style={{ color: "var(--connect-text-muted)" }}>
            Unsupported field type: {field.type}
          </p>
        </FieldWrapper>
      );
  }
}
