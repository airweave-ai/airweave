/**
 * AuthFieldsForm - Dynamic form fields for authentication credentials
 */

import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useIsDark } from "@/hooks/use-is-dark";

import { getAuthProviderIconUrl } from "../utils/helpers";

interface AuthField {
  name: string;
  title?: string;
  description?: string;
  required?: boolean;
  secret?: boolean;
}

interface AuthFieldsFormProps {
  providerShortName: string;
  fields: AuthField[];
  values: Record<string, string>;
  onChange: (fieldName: string, value: string) => void;
}

const PLATFORM_LINKS: Record<string, { url: string; label: string }> = {
  composio: {
    url: "https://platform.composio.dev/",
    label: "Get API Key from Composio",
  },
  pipedream: {
    url: "https://pipedream.com/settings/api",
    label: "Get Client ID & Secret from Pipedream",
  },
};

export function AuthFieldsForm({
  providerShortName,
  fields,
  values,
  onChange,
}: AuthFieldsFormProps) {
  const isDark = useIsDark();
  const platformLink = PLATFORM_LINKS[providerShortName];

  if (!fields || fields.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4 pt-2">
      <div className="flex items-center justify-between">
        <label className="text-muted-foreground text-xs font-medium tracking-wider uppercase">
          Authentication
        </label>

        {platformLink && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={() => window.open(platformLink.url, "_blank")}
          >
            <img
              src={getAuthProviderIconUrl(
                providerShortName,
                isDark ? "dark" : "light"
              )}
              alt={providerShortName}
              className="mr-1.5 h-3 w-3 object-contain"
            />
            {platformLink.label}
            <ExternalLink className="ml-1.5 h-3 w-3" />
          </Button>
        )}
      </div>

      {fields.map((field) => (
        <div key={field.name} className="space-y-2">
          <label className="text-sm font-medium">
            {field.title || field.name}
            {field.required && (
              <span className="text-destructive ml-1">*</span>
            )}
          </label>
          {field.description && (
            <p className="text-muted-foreground text-xs">{field.description}</p>
          )}
          <Input
            type={field.secret ? "password" : "text"}
            value={values[field.name] || ""}
            onChange={(e) => onChange(field.name, e.target.value)}
            placeholder={
              field.secret
                ? "••••••••"
                : `Enter ${field.title || field.name}`
            }
          />
        </div>
      ))}
    </div>
  );
}

