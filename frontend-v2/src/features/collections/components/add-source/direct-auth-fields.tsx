/**
 * DirectAuthFields - Form fields for API key/credential authentication
 */

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
      <Label className="text-xs tracking-wider text-gray-500 uppercase dark:text-gray-400">
        Credentials
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
            type={isSensitiveField(field.name) ? "password" : "text"}
            value={values[field.name] || ""}
            onChange={(e) => onChange(field.name, e.target.value)}
            className="border-gray-200 bg-white placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:placeholder:text-gray-500"
          />
        </div>
      ))}
    </div>
  );
}
