/**
 * DirectAuthFields - Form fields for API key/credential authentication
 */

import { ValidatedInput } from "@/components/validated-input";
import { Label } from "@/components/ui/label";
import { getAuthFieldValidation } from "@/lib/validation";

interface AuthField {
  name: string;
  display_name?: string;
  description?: string;
  required: boolean;
}

interface DirectAuthFieldsProps {
  fields: AuthField[];
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
}

function isSensitiveField(name: string): boolean {
  return ["password", "token", "secret", "key"].some((s) =>
    name.toLowerCase().includes(s)
  );
}

export function DirectAuthFields({
  fields,
  values,
  onChange,
}: DirectAuthFieldsProps) {
  return (
    <div className="space-y-4">
      <Label className="text-muted-foreground text-xs tracking-wider uppercase">
        Credentials
      </Label>
      {fields.map((field) => {
        const validation = getAuthFieldValidation(field.name);
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
              type={isSensitiveField(field.name) ? "password" : "text"}
              value={values[field.name] || ""}
              onChange={(value) => onChange(field.name, value)}
              validation={validation ?? undefined}
            />
          </div>
        );
      })}
    </div>
  );
}
