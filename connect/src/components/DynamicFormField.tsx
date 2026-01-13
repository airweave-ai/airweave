import type { ConfigField } from "../lib/types";
import {
  ArrayField,
  BooleanField,
  NumberField,
  StringField,
} from "./form-fields";
import { FieldWrapper } from "./form-fields/FieldWrapper";

interface DynamicFormFieldProps {
  field: ConfigField;
  value: unknown;
  onChange: (value: unknown) => void;
  error?: string;
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
