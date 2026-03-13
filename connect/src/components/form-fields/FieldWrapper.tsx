import { useTheme } from "../../lib/theme";
import type { ConfigField } from "../../lib/types";
import { parseInlineMarkdown } from "./markdown";

interface FieldWrapperProps {
  field: ConfigField;
  error?: string;
  children: React.ReactNode;
}

export function FieldWrapper({ field, error, children }: FieldWrapperProps) {
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
            __html: parseInlineMarkdown(field.description),
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
