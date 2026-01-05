/**
 * DirectAuthFields - Form fields for API key/credential authentication
 */

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useIsDark } from "@/hooks/use-is-dark";
import { cn } from "@/lib/utils";

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
  const isDark = useIsDark();

  return (
    <div className="space-y-4">
      <Label
        className={cn(
          "text-xs tracking-wider uppercase",
          isDark ? "text-gray-400" : "text-gray-500"
        )}
      >
        Credentials
      </Label>
      {fields.map((field) => (
        <div key={field.name} className="space-y-1.5">
          <Label className="text-sm font-medium">
            {field.display_name || field.name}
            {field.required && <span className="ml-1 text-red-500">*</span>}
          </Label>
          {field.description && (
            <p
              className={cn(
                "text-xs",
                isDark ? "text-gray-500" : "text-gray-400"
              )}
            >
              {field.description}
            </p>
          )}
          <Input
            type={isSensitiveField(field.name) ? "password" : "text"}
            value={values[field.name] || ""}
            onChange={(e) => onChange(field.name, e.target.value)}
            className={cn(
              isDark
                ? "border-gray-700 bg-gray-800 placeholder:text-gray-500"
                : "border-gray-200 bg-white placeholder:text-gray-400"
            )}
          />
        </div>
      ))}
    </div>
  );
}
