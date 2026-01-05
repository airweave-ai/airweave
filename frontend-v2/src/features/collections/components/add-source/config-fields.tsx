/**
 * ConfigFields - Additional configuration form fields for source connections
 */

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
      <Label className="text-xs tracking-wider text-gray-500 uppercase dark:text-gray-400">
        Additional Configuration
        {!hasRequiredFields && " (optional)"}
      </Label>
      {fields.map((field) => (
        <div key={field.name} className="space-y-1.5">
          <Label className="text-sm font-medium">
            {field.display_name || field.name}
            {field.required && <span className="ml-1 text-red-500">*</span>}
          </Label>
          {field.description && (
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {field.description}
            </p>
          )}
          <Input
            value={
              Array.isArray(values[field.name])
                ? (values[field.name] as string[]).join(", ")
                : (values[field.name] as string) || ""
            }
            onChange={(e) => onChange(field.name, e.target.value)}
            className="border-gray-200 bg-white placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500"
          />
        </div>
      ))}
    </div>
  );
}
