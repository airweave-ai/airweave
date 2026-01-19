/**
 * ConfigFields - Additional configuration form fields for source connections
 */

import { ValidatedInput } from "@/components/validated-input";
import { Label } from "@/components/ui/label";
import { getAuthFieldValidation } from "@/lib/validation";

interface ConfigField {
  name: string;
  display_name?: string;
  description?: string;
  required: boolean;
}

interface ConfigFieldsProps {
  fields: ConfigField[];
  values: Record<string, string | string[]>;
  onChange: (name: string, value: string | string[]) => void;
}

export function ConfigFields({ fields, values, onChange }: ConfigFieldsProps) {
  const hasRequiredFields = fields.some((f) => f.required);

  return (
    <div className="space-y-4">
      <Label className="text-muted-foreground text-xs tracking-wider uppercase">
        Additional Configuration
        {!hasRequiredFields && " (optional)"}
      </Label>
      {fields.map((field) => {
        const validation = getAuthFieldValidation(field.name);
        const currentValue = Array.isArray(values[field.name])
          ? (values[field.name] as string[]).join(", ")
          : (values[field.name] as string) || "";
        return (
          <div key={field.name} className="space-y-1.5">
            <Label className="text-sm font-medium">
              {field.display_name || field.name}
              {field.required && (
                <span className="text-destructive ml-1">*</span>
              )}
            </Label>
            {field.description && (
              <p className="text-muted-foreground text-xs">
                {field.description}
              </p>
            )}
            <ValidatedInput
              value={currentValue}
              onChange={(value) => onChange(field.name, value)}
              validation={validation ?? undefined}
            />
          </div>
        );
      })}
    </div>
  );
}
