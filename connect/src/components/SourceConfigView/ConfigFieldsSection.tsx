import type { ConfigField, ConnectLabels } from "../../lib/types";
import { DynamicFormField } from "../DynamicFormField";

interface ConfigFieldsSectionProps {
  fields: ConfigField[];
  configValues: Record<string, unknown>;
  errors: Record<string, string>;
  onFieldChange: (fieldName: string, value: unknown) => void;
  labels: Required<ConnectLabels>;
}

export function ConfigFieldsSection({
  fields,
  configValues,
  errors,
  onFieldChange,
  labels,
}: ConfigFieldsSectionProps) {
  return (
    <div className="mb-4">
      <h2
        className="text-sm font-bold opacity-70 mb-3"
        style={{ color: "var(--connect-text)" }}
      >
        {labels.configureConfigSection}
      </h2>
      {fields.map((field: ConfigField) => (
        <DynamicFormField
          key={field.name}
          field={field}
          value={configValues[field.name]}
          onChange={(value) => onFieldChange(field.name, value)}
          error={errors[`config_${field.name}`]}
        />
      ))}
    </div>
  );
}
