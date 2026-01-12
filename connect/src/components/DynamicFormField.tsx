import { useState } from "react";
import type { ConfigField } from "../lib/types";

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
  const labelId = `field-${field.name}`;
  const errorId = `error-${field.name}`;

  return (
    <div className="mb-4">
      <label
        id={labelId}
        htmlFor={`input-${field.name}`}
        className="block text-sm font-medium mb-1"
        style={{ color: "var(--connect-text)" }}
      >
        {field.title}
        {field.required && (
          <span style={{ color: "var(--connect-error)" }} className="ml-1">
            *
          </span>
        )}
      </label>
      {field.description && (
        <p
          className="text-xs mt-1 mb-2"
          style={{ color: "var(--connect-text-muted)" }}
        >
          {field.description}
        </p>
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
  const labelId = `field-${field.name}`;
  const errorId = `error-${field.name}`;

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
          aria-labelledby={labelId}
          aria-describedby={error ? errorId : undefined}
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
              <EyeOffIcon className="w-4 h-4" />
            ) : (
              <EyeIcon className="w-4 h-4" />
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
  const labelId = `field-${field.name}`;
  const errorId = `error-${field.name}`;

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
        aria-labelledby={labelId}
        aria-describedby={error ? errorId : undefined}
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
  const isChecked = value ?? false;
  const labelId = `field-${field.name}`;
  const errorId = `error-${field.name}`;

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <label
            id={labelId}
            className="block text-sm font-medium mb-1"
            style={{ color: "var(--connect-text)" }}
          >
            {field.title}
            {field.required && (
              <span style={{ color: "var(--connect-error)" }} className="ml-1">
                *
              </span>
            )}
          </label>
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
  const labelId = `field-${field.name}`;
  const errorId = `error-${field.name}`;

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
              <XIcon className="w-3 h-3" />
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
          aria-labelledby={labelId}
          aria-describedby={error ? errorId : undefined}
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
          <p
            className="text-xs"
            style={{ color: "var(--connect-text-muted)" }}
          >
            Unsupported field type: {field.type}
          </p>
        </FieldWrapper>
      );
  }
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
      />
    </svg>
  );
}

function EyeOffIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
      />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  );
}
