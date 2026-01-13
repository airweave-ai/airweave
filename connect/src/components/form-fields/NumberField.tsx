import type { ConfigField } from "../../lib/types";
import { FieldWrapper } from "./FieldWrapper";
import { inputBaseStyles } from "./styles";

interface NumberFieldProps {
  field: ConfigField;
  value: number | undefined;
  onChange: (value: number | undefined) => void;
  error?: string;
}

export function NumberField({ field, value, onChange, error }: NumberFieldProps) {
  const inputId = `input-${field.name}`;
  const errorId = `error-${field.name}`;

  return (
    <FieldWrapper field={field} error={error}>
      <input
        id={inputId}
        type="number"
        value={value ?? ""}
        onChange={(e) => {
          const num = e.target.value === "" ? undefined : Number(e.target.value);
          onChange(num);
        }}
        className="w-full px-3 py-2 text-sm rounded-md border outline-none transition-colors"
        style={inputBaseStyles(error)}
        aria-invalid={!!error}
        aria-describedby={error ? errorId : undefined}
      />
    </FieldWrapper>
  );
}
