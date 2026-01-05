/**
 * ConfigFields - Additional configuration form fields for source connections
 */

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useIsDark } from "@/hooks/use-is-dark";
import { cn } from "@/lib/utils";

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
  const isDark = useIsDark();
  const hasRequiredFields = fields.some((f) => f.required);

  return (
    <div className="space-y-4">
      <Label
        className={cn(
          "text-xs tracking-wider uppercase",
          isDark ? "text-gray-400" : "text-gray-500"
        )}
      >
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
            value={
              Array.isArray(values[field.name])
                ? (values[field.name] as string[]).join(", ")
                : (values[field.name] as string) || ""
            }
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
