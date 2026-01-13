import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import type { ConfigField } from "../../lib/types";
import { FieldWrapper } from "./FieldWrapper";
import { inputBaseStyles } from "./styles";

interface StringFieldProps {
  field: ConfigField;
  value: string;
  onChange: (value: string) => void;
  error?: string;
}

export function StringField({ field, value, onChange, error }: StringFieldProps) {
  const [showSecret, setShowSecret] = useState(false);
  const isSecret = field.is_secret === true;
  const inputType = isSecret && !showSecret ? "password" : "text";
  const inputId = `input-${field.name}`;
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
          aria-invalid={!!error}
          aria-describedby={error ? errorId : undefined}
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
