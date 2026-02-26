import { useTheme } from "../../lib/theme";
import type { ConfigField } from "../../lib/types";
import { parseInlineMarkdown } from "./markdown";

interface BooleanFieldProps {
  field: ConfigField;
  value: boolean;
  onChange: (value: boolean) => void;
  error?: string;
}

export function BooleanField({ field, value, onChange, error }: BooleanFieldProps) {
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
              dangerouslySetInnerHTML={{
                __html: parseInlineMarkdown(field.description),
              }}
            />
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
