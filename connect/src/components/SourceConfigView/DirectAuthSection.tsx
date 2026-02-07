import type { ConfigField, ConnectLabels } from "../../lib/types";
import { DynamicFormField } from "../DynamicFormField";

interface DirectAuthSectionProps {
  fields: ConfigField[];
  authValues: Record<string, unknown>;
  errors: Record<string, string>;
  onFieldChange: (fieldName: string, value: unknown) => void;
  labels: Required<ConnectLabels>;
}

export function DirectAuthSection({
  fields,
  authValues,
  errors,
  onFieldChange,
  labels,
}: DirectAuthSectionProps) {
  return (
    <div className="mb-4">
      <h2
        className="text-sm font-bold opacity-70 mb-3"
        style={{ color: "var(--connect-text)" }}
      >
        {labels.configureAuthSection}
      </h2>
      {fields.map((field: ConfigField) => (
        <DynamicFormField
          key={field.name}
          field={field}
          value={authValues[field.name]}
          onChange={(value) => onFieldChange(field.name, value)}
          error={errors[field.name]}
        />
      ))}
    </div>
  );
}
